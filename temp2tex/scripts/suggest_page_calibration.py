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


def propose(spec: dict, diagnostics: dict, diagnostics_path: Path) -> dict:
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
        return {
            "status": "pending",
            "reason": "No usable PDF text-box deltas were available.",
            "source": str(diagnostics_path),
        }

    def median(key: str) -> float:
        values = sorted(number(item.get(key)) for item in deltas if number(item.get(key)) is not None)
        if not values:
            return 0.0
        middle = len(values) // 2
        return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2

    pt_deltas = {side: median(side) for side in ("top", "right", "bottom", "left")}
    max_abs_pt = max(abs(value) for value in pt_deltas.values())
    if max_abs_pt > 36:
        return {
            "status": "pending",
            "bbox_deltas_pt": {side: round(value, 3) for side, value in pt_deltas.items()},
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
        "margins_mm": candidate,
        "source_margins_mm": margins,
        "bbox_deltas_pt": {side: round(value, 3) for side, value in pt_deltas.items()},
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
