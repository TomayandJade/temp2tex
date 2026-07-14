#!/usr/bin/env python3
"""Create a separate regression-only spec from a pending body proposal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", help="Original template_spec.json")
    parser.add_argument("proposal", help="Pending output from suggest_body_calibration.py")
    parser.add_argument("--output", required=True, help="New candidate spec path")
    args = parser.parse_args()
    proposal_path = Path(args.proposal).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    spec = read_json(Path(args.spec).expanduser().resolve())
    proposal = read_json(proposal_path)
    if proposal.get("status") != "pending" or proposal.get("candidate_available") is not True:
        raise SystemExit("Proposal has no safe body-density candidate; do not materialize it.")
    font_size = proposal.get("calibrated_font_size_pt")
    baseline = proposal.get("body_baseline_pt")
    if not isinstance(font_size, (int, float)) or not 7 <= float(font_size) <= 14:
        raise SystemExit(f"Invalid candidate font size: {font_size!r}")
    if not isinstance(baseline, (int, float)) or not float(font_size) <= float(baseline) <= 30:
        raise SystemExit(f"Invalid candidate baseline: {baseline!r}")
    spec.setdefault("document", {})["render_calibration"] = {
        "status": "render_probe",
        "calibrated_font_size_pt": round(float(font_size), 2),
        "body_baseline_pt": round(float(baseline), 2),
        "source_font_size_pt": proposal.get("source_font_size_pt"),
        "source_body_baseline_pt": proposal.get("source_body_baseline_pt"),
        "proposal_mode": proposal.get("proposal_mode", "stable_visual_calibration"),
        "before_metrics": proposal.get("metrics", {}),
        "source": "regression-only candidate materialized from pending PDF body-density proposal",
        "proposal_path": str(proposal_path),
        "requires_comparison_acceptance": True,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
