#!/usr/bin/env python3
"""Transfer reviewed ordinary Word-unit dispositions into linked system children.

This is deliberately narrow. It only copies a disposition when a system child
already names one exact paragraph/run evidence ID and that ordinary mapping has
a final disposition. Unlinked samples, named style scaffolds, and mixed-role
evidence remain pending for role-local review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FINAL_STATUSES = {"mapped", "default", "unresolved", "not_observable", "guidance"}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def decisions_by_evidence_id(decisions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for decision in decisions.get("decisions") or []:
        if not isinstance(decision, dict):
            continue
        raw_ids = decision.get("evidence_ids") if isinstance(decision.get("evidence_ids"), list) else [decision.get("evidence_id")]
        for raw_id in raw_ids:
            evidence_id = str(raw_id or "")
            if not evidence_id:
                continue
            if evidence_id in index:
                duplicates.add(evidence_id)
            else:
                index[evidence_id] = decision
    return {key: value for key, value in index.items() if key not in duplicates}


def reconcile(triage: dict[str, Any], decisions: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    if triage.get("schema_version") != "temp2tex.system-format-triage.v2":
        raise ValueError("Expected a temp2tex.system-format-triage.v2 file. Rebuild the queue before reconciliation.")
    index = decisions_by_evidence_id(decisions)
    copied = 0
    scaffold_closed = 0
    left_pending = 0
    already_final = 0
    for record in triage.get("records") or []:
        if not isinstance(record, dict):
            continue
        for child in record.get("children") or []:
            if not isinstance(child, dict):
                continue
            status = str(child.get("status") or "pending").strip().lower()
            if status in FINAL_STATUSES:
                already_final += 1
                continue
            link = str(child.get("source_unit_evidence_id") or "")
            decision = index.get(link)
            decision_status = str(decision.get("status") or "").strip().lower() if decision else ""
            if not link or decision_status not in FINAL_STATUSES:
                locator = child.get("source_locator") if isinstance(child.get("source_locator"), dict) else {}
                # A named style rule has no visible span of its own. Visible
                # uses were emitted as separate children and must link to their
                # ordinary run mapping. Closing this orphan as not-observable
                # prevents an unused Word scaffold from becoming a global TeX
                # default while preserving the source record for later review.
                if not link and not str(child.get("source_text") or "").strip() and locator.get("style_id"):
                    child["status"] = "not_observable"
                    child["reason"] = "Named Word style rule has no visible-run evidence in this ledger; visible uses are reviewed through their linked role-local children."
                    child["guidance_kind"] = ""
                    scaffold_closed += 1
                    continue
                left_pending += 1
                continue
            child["status"] = decision_status
            child["guidance_kind"] = str(decision.get("guidance_kind") or "") if decision_status == "guidance" else ""
            child["reason"] = (
                f"Inherited from the final ordinary mapping for {link}; review the linked role before changing this system child."
            )
            child["applied_from_atomic_evidence_id"] = link
            copied += 1
    triage["reconciliation"] = {
        "method": "linked_final_atomic_disposition_only",
        "copied": copied,
        "closed_named_style_scaffolds": scaffold_closed,
        "already_final": already_final,
        "left_pending": left_pending,
        "warning": "Inherited dispositions do not resolve unlinked samples or prove visual fidelity. Review them as role-local evidence before handoff.",
    }
    return triage, {"copied": copied, "closed_named_style_scaffolds": scaffold_closed, "already_final": already_final, "left_pending": left_pending}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("system_triage", help="system_format_triage.json produced by prepare_system_format_triage.py")
    parser.add_argument("--decisions", required=True, help="atomic_mapping_decisions.json with final ordinary-unit dispositions")
    parser.add_argument("--output", required=True, help="Output reconciled system_format_triage.json")
    args = parser.parse_args()

    triage = load_json(Path(args.system_triage))
    decisions = load_json(Path(args.decisions))
    reconciled, summary = reconcile(triage, decisions)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(reconciled, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
