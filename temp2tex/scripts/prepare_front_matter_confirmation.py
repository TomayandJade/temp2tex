#!/usr/bin/env python3
"""Create and validate a ledger-bound front-matter semantic confirmation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "temp2tex.front-matter-semantic-confirmation.v1"


def expected_entries(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every ordered front-matter role that a blocking review exposes."""
    review = ledger.get("front_matter_sequence_review")
    if not isinstance(review, dict) or not review.get("requires_semantic_confirmation"):
        return []
    expected: list[dict[str, Any]] = []
    for entry in review.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        evidence_id = str(entry.get("evidence_id") or "").strip()
        try:
            source_index = int(entry.get("index"))
        except (TypeError, ValueError):
            source_index = 0
        for role in entry.get("roles") or []:
            candidate_role = str(role or "").strip()
            if evidence_id and source_index > 0 and candidate_role.startswith("front_matter."):
                expected.append({
                    "evidence_id": evidence_id,
                    "source_index": source_index,
                    "candidate_role": candidate_role,
                })
    return expected


def starter(ledger: dict[str, Any]) -> dict[str, Any]:
    """Build a pending confirmation file without rewriting source evidence."""
    items = expected_entries(ledger)
    return {
        "schema_version": SCHEMA_VERSION,
        "ledger_fingerprint": str(ledger.get("evidence_fingerprint") or ""),
        "purpose": "Confirm ordered front-matter role candidates before class-interface mapping.",
        "confirmations": [
            {
                **item,
                "status": "pending",
                "confirmed_role": "",
                "reason": "Review visible Word sequence, style evidence, and nearby paragraph context before confirming this field.",
            }
            for item in items
        ],
    }


def validation_errors(ledger: dict[str, Any], confirmation: object) -> list[str]:
    """Validate that every blocking front-matter record was confirmed exactly once."""
    expected = expected_entries(ledger)
    if not expected:
        return []
    if not isinstance(confirmation, dict):
        return ["front_matter_semantic_confirmation.json is required for the blocking front-matter sequence review"]
    if confirmation.get("schema_version") != SCHEMA_VERSION:
        return ["front_matter_semantic_confirmation.json has an unsupported schema_version"]
    if confirmation.get("ledger_fingerprint") != ledger.get("evidence_fingerprint"):
        return ["front_matter_semantic_confirmation.json does not match word_format_ledger.json evidence fingerprint"]
    confirmations = confirmation.get("confirmations")
    if not isinstance(confirmations, list):
        return ["front_matter_semantic_confirmation.json must contain confirmations"]

    expected_by_key = {
        (item["evidence_id"], item["source_index"], item["candidate_role"]): item
        for item in expected
    }
    seen: set[tuple[str, int, str]] = set()
    errors: list[str] = []
    for item in confirmations:
        if not isinstance(item, dict):
            errors.append("front_matter_semantic_confirmation.json has a non-object confirmation")
            continue
        evidence_id = str(item.get("evidence_id") or "").strip()
        try:
            source_index = int(item.get("source_index"))
        except (TypeError, ValueError):
            source_index = 0
        candidate_role = str(item.get("candidate_role") or "").strip()
        key = (evidence_id, source_index, candidate_role)
        if key not in expected_by_key:
            errors.append("front_matter_semantic_confirmation.json contains an unknown confirmation record: " + ":".join((evidence_id, str(source_index), candidate_role)))
            continue
        if key in seen:
            errors.append("front_matter_semantic_confirmation.json duplicates a confirmation record: " + ":".join((evidence_id, str(source_index), candidate_role)))
            continue
        seen.add(key)
        if str(item.get("status") or "").strip() != "confirmed":
            errors.append("front_matter_semantic_confirmation.json leaves a confirmation pending: " + evidence_id)
        else:
            if str(item.get("confirmed_role") or "").strip() != candidate_role:
                errors.append("front_matter_semantic_confirmation.json must retain the confirmed candidate role for " + evidence_id)
            if not str(item.get("reason") or "").strip():
                errors.append("front_matter_semantic_confirmation.json needs a visible-context reason for " + evidence_id)
    for key in expected_by_key:
        if key not in seen:
            errors.append("front_matter_semantic_confirmation.json is missing confirmation for " + key[0] + ":" + key[2])
    return errors


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("format_ledger", help="word_format_ledger.json")
    parser.add_argument("--output", required=True, help="Output front_matter_semantic_confirmation.json")
    args = parser.parse_args()
    ledger = load_json(Path(args.format_ledger).expanduser().resolve())
    if not expected_entries(ledger):
        raise SystemExit("No blocking front-matter semantic confirmation is required for this ledger.")
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(starter(ledger), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
