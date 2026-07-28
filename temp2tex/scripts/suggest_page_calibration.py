#!/usr/bin/env python3
"""Propose, but never apply, a page-frame calibration from PDF layout diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PT_TO_MM = 25.4 / 72.0


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def bounded(value: float, lower: float = 5.0, upper: float = 80.0) -> float:
    return round(min(max(value, lower), upper), 2)


def rejected(diagnostics_path: Path, reason: str, **details: object) -> dict:
    """Return a diagnostic result that cannot be materialized as a probe."""
    return {
        "status": "not_eligible",
        "candidate_available": False,
        "source": str(diagnostics_path),
        "reason": reason,
        "requires_visual_review": True,
        **details,
    }


def propose(spec: dict, diagnostics: dict, diagnostics_path: Path) -> dict:
    summary = diagnostics.get("summary") if isinstance(diagnostics.get("summary"), dict) else {}
    raw_contract_scope = summary.get("contract_scope") or diagnostics.get("contract_scope")
    # Pre-v13 full-document profiler reports did not persist the default scope.
    # Their existing semantic-comparable/pass pair is equivalent to the current
    # explicit full_document declaration; never infer that equivalence for a
    # partial-zone-only report.
    contract_scope = str(
        raw_contract_scope
        or ("full_document" if summary.get("semantic_comparable") is True and summary.get("same_content_contract_status") == "passed" else "")
    ).lower()
    if (
        contract_scope != "full_document"
        or summary.get("semantic_comparable") is not True
        or summary.get("same_content_contract_status") != "passed"
    ):
        return rejected(
            diagnostics_path,
            "A page-frame probe requires a full-document same-content contract; partial-zone or incomplete anchor evidence may not calibrate global margins.",
            contract_scope=contract_scope or None,
            same_content_contract_status=summary.get("same_content_contract_status"),
        )
    reference_page_count = diagnostics.get("reference_page_count")
    generated_page_count = diagnostics.get("generated_page_count")
    if (
        not isinstance(reference_page_count, int)
        or not isinstance(generated_page_count, int)
        or reference_page_count != generated_page_count
    ):
        return rejected(
            diagnostics_path,
            "A page-frame probe requires matching reference and generated page counts; resolve content flow before adjusting margins.",
            reference_page_count=reference_page_count,
            generated_page_count=generated_page_count,
        )
    if summary.get("missing_or_asymmetric_anchors") or summary.get("anchor_page_shifts"):
        return rejected(
            diagnostics_path,
            "A page-frame probe requires complete anchors with no page shifts; repair the fixture or structural flow before adjusting margins.",
            missing_or_asymmetric_anchors=summary.get("missing_or_asymmetric_anchors") or [],
            anchor_page_shifts=summary.get("anchor_page_shifts") or {},
        )
    if summary.get("local_zone_gate_status") == "failed":
        return rejected(
            diagnostics_path,
            "A declared local-zone gate failed; repair its named source-backed element before proposing global page margins.",
            out_of_tolerance_anchors=summary.get("out_of_tolerance_anchors") or [],
            failed_image_zones=summary.get("failed_image_zones") or [],
            failed_flow_context_anchors=summary.get("failed_flow_context_anchors") or [],
        )
    source = spec.get("page", {}).get("margins_mm", {})
    margins = {
        side: number(source.get(side)) or 25.0
        for side in ("top", "right", "bottom", "left")
    }
    comparisons = diagnostics.get("comparisons", [])
    deltas = [
        item.get("text_bbox_delta", {})
        for item in comparisons
        if isinstance(item, dict) and isinstance(item.get("text_bbox_delta"), dict)
        and item["text_bbox_delta"].get("available")
    ]
    if not deltas:
        return rejected(diagnostics_path, "No usable PDF text-box deltas were available.")
    if len(deltas) < 2:
        return rejected(
            diagnostics_path,
            "A page-frame probe requires at least two same-content page text boxes; one page cannot distinguish frame geometry from local content flow.",
            usable_page_count=len(deltas),
        )

    def median(key: str) -> float:
        values = sorted(number(item.get(key)) for item in deltas if number(item.get(key)) is not None)
        if not values:
            return 0.0
        middle = len(values) // 2
        return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2

    pt_deltas = {side: median(side) for side in ("top", "right", "bottom", "left")}
    edge_spread_pt = {
        side: max(values) - min(values)
        for side in ("top", "right", "bottom", "left")
        if (values := [number(item.get(side)) for item in deltas if number(item.get(side)) is not None])
    }
    inconsistent_edges = {
        side: round(spread, 3)
        for side, spread in edge_spread_pt.items()
        if spread > 6.0
    }
    if inconsistent_edges:
        return rejected(
            diagnostics_path,
            "Text-box edge deltas vary across pages, indicating content flow or local-layout effects rather than a stable page frame.",
            bbox_deltas_pt={side: round(value, 3) for side, value in pt_deltas.items()},
            edge_spread_pt={side: round(value, 3) for side, value in edge_spread_pt.items()},
            inconsistent_edges=inconsistent_edges,
        )
    max_abs_pt = max(abs(value) for value in pt_deltas.values())
    if max_abs_pt > 36:
        return {
            "status": "not_eligible",
            "candidate_available": False,
            "bbox_deltas_pt": {side: round(value, 3) for side, value in pt_deltas.items()},
            "edge_spread_pt": {side: round(value, 3) for side, value in edge_spread_pt.items()},
            "source": str(diagnostics_path),
            "reason": (
                "Text-box displacement is too large for a safe margin proposal and likely includes content-flow, "
                "float, or front-matter effects. Fix structural flow before calibrating page geometry."
            ),
            "requires_visual_review": True,
            "large_adjustment_warning": True,
        }
    # A positive generated-minus-reference left/top delta is corrected by
    # reducing that margin. At right/bottom, increasing the margin moves the
    # generated text edge inward by the same amount.
    candidate = {
        "top": bounded(margins["top"] - pt_deltas["top"] * PT_TO_MM),
        "right": bounded(margins["right"] + pt_deltas["right"] * PT_TO_MM),
        "bottom": bounded(margins["bottom"] + pt_deltas["bottom"] * PT_TO_MM),
        "left": bounded(margins["left"] - pt_deltas["left"] * PT_TO_MM),
    }
    return {
        "status": "pending",
        "candidate_available": True,
        "margins_mm": candidate,
        "source_margins_mm": margins,
        "bbox_deltas_pt": {side: round(value, 3) for side, value in pt_deltas.items()},
        "edge_spread_pt": {side: round(value, 3) for side, value in edge_spread_pt.items()},
        "usable_page_count": len(deltas),
        "source": str(diagnostics_path),
        "reason": (
            "Candidate derived from median generated-minus-reference text-box edges. "
            "Compile and compare the candidate; set status to render_verified only if the layered gate improves."
        ),
        "requires_visual_review": True,
        "large_adjustment_warning": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", help="template_spec.json")
    parser.add_argument("layout_diagnostics", help="layout_diagnostics.json from profile_pdf_layout.py")
    parser.add_argument("--output", default="page_render_calibration_proposal.json")
    args = parser.parse_args()
    spec_path = Path(args.spec).expanduser().resolve()
    diagnostics_path = Path(args.layout_diagnostics).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    proposal = propose(read_json(spec_path), read_json(diagnostics_path), diagnostics_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
