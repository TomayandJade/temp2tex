#!/usr/bin/env python3
"""Propose, but never apply, a bounded body-density render calibration."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def values(comparisons: list[dict], key: str) -> list[float]:
    return [float(item[key]) for item in comparisons if number(item.get(key)) is not None]


def baseline_values(comparisons: list[dict]) -> list[float]:
    return [
        float(item["median_baseline_step_delta_pt"])
        for item in comparisons
        if number(item.get("median_baseline_step_delta_pt")) is not None
        and int(item.get("reference_baseline_step_sample_count", 0)) >= 5
        and int(item.get("generated_baseline_step_sample_count", 0)) >= 5
    ]


def median_and_mad(items: list[float]) -> tuple[float | None, float | None]:
    if not items:
        return None, None
    center = statistics.median(items)
    return center, statistics.median(abs(item - center) for item in items)


def effective_source_font_size(spec: dict) -> float:
    role = spec.get("page", {}).get("source_body_style", {})
    if isinstance(role, dict) and str(role.get("render_mode", "")).lower() == "visible_flow_exemplar":
        candidate = role.get("visible_flow_override_candidate", {})
        try:
            half_points = candidate.get("effective_format", {}).get("font", {}).get("size_half_points")
            if half_points is not None:
                return float(half_points) / 2.0
        except (TypeError, ValueError, AttributeError):
            pass
    try:
        return float(spec.get("document", {}).get("font_size_pt", 10))
    except (TypeError, ValueError):
        return 10.0


def source_baseline(spec: dict, font_size: float) -> float:
    role = spec.get("page", {}).get("source_body_style", {})
    paragraph = role.get("direct_format", {}).get("paragraph", {}) if isinstance(role, dict) else {}
    if isinstance(role, dict) and str(role.get("render_mode", "")).lower() == "visible_flow_exemplar":
        candidate = role.get("visible_flow_override_candidate", {})
        if isinstance(candidate, dict):
            paragraph = candidate.get("direct_format", {}).get("paragraph", paragraph)
    try:
        if str(paragraph.get("line_spacing_rule", "")).lower() == "exact":
            exact = float(paragraph.get("line_spacing")) / 20.0
            if font_size <= exact <= 30:
                return exact
    except (TypeError, ValueError):
        pass
    try:
        spread = float(spec.get("page", {}).get("line_spacing", 1.15))
    except (TypeError, ValueError):
        spread = 1.15
    return max(font_size * 1.2, font_size + 1.5) * spread


def rejected(reason: str, diagnostics_path: Path, metrics: dict | None = None) -> dict:
    result = {
        "status": "pending",
        "candidate_available": False,
        "reason": reason,
        "source": str(diagnostics_path),
        "requires_comparison_acceptance": True,
    }
    if metrics:
        result["metrics"] = metrics
    return result


def propose(spec: dict, diagnostics: dict, diagnostics_path: Path, allow_page_count_repair: bool = False) -> dict:
    comparisons = [item for item in diagnostics.get("comparisons", []) if isinstance(item, dict)]
    summary = diagnostics.get("summary", {})
    ref_pages = diagnostics.get("reference_page_count")
    gen_pages = diagnostics.get("generated_page_count")
    if not isinstance(ref_pages, int) or not isinstance(gen_pages, int):
        ref_pages = gen_pages = len(comparisons)
    if not comparisons:
        return rejected("No comparable PDF pages were available.", diagnostics_path)
    shifts = summary.get("anchor_page_shifts", {})
    width_delta = number((summary.get("median_body_box_delta_pt") or {}).get("width"))
    font_delta, font_mad = median_and_mad(values(comparisons, "median_font_size_delta_pt"))
    measured_baseline_values = baseline_values(comparisons)
    baseline_delta, baseline_mad = median_and_mad(measured_baseline_values)
    if len(measured_baseline_values) < 2:
        baseline_delta = baseline_mad = None

    if ref_pages != gen_pages:
        metrics = {
            "reference_page_count": ref_pages,
            "generated_page_count": gen_pages,
            "comparable_page_count": len(comparisons),
            "median_body_box_width_delta_pt": width_delta,
            "median_font_size_delta_pt": font_delta,
            "font_size_delta_mad_pt": font_mad,
            "median_baseline_step_delta_pt": baseline_delta,
            "baseline_step_delta_mad_pt": baseline_mad,
            "baseline_comparable_page_count": len(measured_baseline_values),
        }
        if not allow_page_count_repair:
            return rejected(
                "Reference and generated page counts differ; use --allow-page-count-repair only for an isolated same-content density probe.",
                diagnostics_path,
                metrics,
            )
        if gen_pages <= ref_pages:
            return rejected("Body-density page repair only tightens an output that has more pages than the reference.", diagnostics_path, metrics)
        if len(comparisons) < 2:
            return rejected("Fewer than two comparable pages make a pagination density probe unsafe.", diagnostics_path, metrics)
        if not isinstance(shifts, dict) or not shifts:
            return rejected("Pagination differs without later positive anchor shifts; body density is not isolated as the cause.", diagnostics_path, metrics)
        shift_values = [number(value) for value in shifts.values()]
        if any(value is None or value <= 0 for value in shift_values):
            return rejected("Anchor shifts are not consistently later in the generated PDF.", diagnostics_path, metrics)
        if width_delta is not None and abs(width_delta) > 30:
            return rejected("Body text-box width differs by more than 30pt; repair geometry before a density page probe.", diagnostics_path, metrics)
        if font_delta is None or font_delta < 1.0:
            return rejected("Generated body font is not at least 1pt larger than the reference; density tightening lacks a measured cause.", diagnostics_path, metrics)
        if font_mad is not None and font_mad > 0.5:
            return rejected("Body font-size deltas vary too much across pages for a pagination density probe.", diagnostics_path, metrics)
        source_font = effective_source_font_size(spec)
        source_line = source_baseline(spec, source_font)
        font_adjustment = max(-2.5, min(-1.0, -font_delta))
        candidate_font = round(max(7.0, min(14.0, source_font + font_adjustment)), 2)
        candidate_baseline = round(min(source_line, max(candidate_font * 1.2, candidate_font + 1.5)), 2)
        return {
            "status": "pending",
            "candidate_available": True,
            "proposal_mode": "body_density_page_count_repair",
            "calibrated_font_size_pt": candidate_font,
            "body_baseline_pt": candidate_baseline,
            "source_font_size_pt": round(source_font, 2),
            "source_body_baseline_pt": round(source_line, 2),
            "metrics": metrics,
            "bounded_adjustments_pt": {
                "font_size": round(candidate_font - source_font, 2),
                "baseline": round(candidate_baseline - source_line, 2),
            },
            "source": str(diagnostics_path),
            "reason": "Isolated same-content page-count repair candidate: generated pages are longer, anchors shift later, and a stable body-font excess supplies the measured density cause.",
            "requires_comparison_acceptance": True,
        }

    if isinstance(shifts, dict) and any(number(value) not in {None, 0.0} for value in shifts.values()):
        return rejected("Document anchors move across pages; repair structural flow before body calibration.", diagnostics_path)
    if width_delta is not None and abs(width_delta) > 12:
        return rejected("Body text-box width differs by more than 12pt; repair page or paragraph geometry first.", diagnostics_path)
    causes = set(summary.get("top_causes") or [])
    if "pagination_or_structural_flow" in causes or "page_frame_or_body_box" in causes:
        return rejected("Layout diagnostics still identify page-frame or structural-flow instability.", diagnostics_path)

    metrics = {
        "page_count": ref_pages,
        "comparable_page_count": len(comparisons),
        "median_body_box_width_delta_pt": width_delta,
        "median_font_size_delta_pt": font_delta,
        "font_size_delta_mad_pt": font_mad,
        "median_baseline_step_delta_pt": baseline_delta,
        "baseline_step_delta_mad_pt": baseline_mad,
        "baseline_comparable_page_count": len(measured_baseline_values),
    }
    if font_delta is None and baseline_delta is None:
        return rejected("No usable font-size or same-lane baseline-step measurements were available.", diagnostics_path, metrics)
    if len(comparisons) < 2:
        return rejected("Fewer than two comparable pages make a global body calibration unsafe.", diagnostics_path, metrics)
    if font_mad is not None and font_mad > 0.75:
        return rejected("Body font-size deltas vary too much across pages for a global calibration.", diagnostics_path, metrics)
    if baseline_mad is not None and baseline_mad > 1.25:
        return rejected("Baseline-step deltas vary too much across pages for a global calibration.", diagnostics_path, metrics)

    source_font = effective_source_font_size(spec)
    source_line = source_baseline(spec, source_font)
    font_adjustment = max(-1.5, min(1.5, -(font_delta or 0.0)))
    baseline_adjustment = max(-2.5, min(2.5, -(baseline_delta or 0.0)))
    candidate_font = round(max(7.0, min(14.0, source_font + font_adjustment)), 2)
    candidate_baseline = round(max(candidate_font, min(30.0, source_line + baseline_adjustment)), 2)
    if abs(candidate_font - source_font) < 0.05 and abs(candidate_baseline - source_line) < 0.10:
        return rejected("Measured body-density difference is too small to justify a render probe.", diagnostics_path, metrics)
    return {
        "status": "pending",
        "candidate_available": True,
        "calibrated_font_size_pt": candidate_font,
        "body_baseline_pt": candidate_baseline,
        "source_font_size_pt": round(source_font, 2),
        "source_body_baseline_pt": round(source_line, 2),
        "metrics": metrics,
        "bounded_adjustments_pt": {
            "font_size": round(candidate_font - source_font, 2),
            "baseline": round(candidate_baseline - source_line, 2),
        },
        "source": str(diagnostics_path),
        "reason": "Bounded candidate from stable same-content PDF body metrics. Compile and compare it; promote only when every structural gate remains satisfied and visual metrics improve.",
        "requires_comparison_acceptance": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", help="template_spec.json")
    parser.add_argument("layout_diagnostics", help="layout_diagnostics.json from profile_pdf_layout.py")
    parser.add_argument("--output", default="body_render_calibration_proposal.json")
    parser.add_argument(
        "--allow-page-count-repair",
        action="store_true",
        help="Allow one isolated tightening probe when generated pages and all measured anchors run later than the reference.",
    )
    args = parser.parse_args()
    spec_path = Path(args.spec).expanduser().resolve()
    diagnostics_path = Path(args.layout_diagnostics).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    proposal = propose(
        read_json(spec_path),
        read_json(diagnostics_path),
        diagnostics_path,
        allow_page_count_repair=args.allow_page_count_repair,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
