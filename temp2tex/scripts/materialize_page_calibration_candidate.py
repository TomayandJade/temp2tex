#!/usr/bin/env python3
"""Create a regression-only calibrated spec from a pending page proposal.

This never modifies the source spec. The caller must compile and compare the
candidate before promoting any calibration into an ordinary template package.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", help="Original template_spec.json")
    parser.add_argument("proposal", help="Pending output from suggest_page_calibration.py")
    parser.add_argument("--output", required=True, help="New candidate spec path")
    args = parser.parse_args()

    spec_path = Path(args.spec).expanduser().resolve()
    proposal_path = Path(args.proposal).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    spec = read_json(spec_path)
    proposal = read_json(proposal_path)
    margins = proposal.get("margins_mm")
    if proposal.get("status") != "pending" or not isinstance(margins, dict):
        raise SystemExit("Proposal has no bounded margin candidate; do not materialize it.")
    numeric_margins = {}
    for side in ("top", "right", "bottom", "left"):
        value = margins.get(side)
        if not isinstance(value, (int, float)) or not 5 <= float(value) <= 80:
            raise SystemExit(f"Invalid candidate margin for {side}: {value!r}")
        numeric_margins[side] = round(float(value), 2)

    page = spec.setdefault("page", {})
    page["render_calibration"] = {
        "status": "render_probe",
        "margins_mm": numeric_margins,
        "source": "regression-only candidate materialized from pending PDF layout proposal",
        "proposal_path": str(proposal_path),
        "requires_comparison_acceptance": True,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
