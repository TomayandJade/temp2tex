#!/usr/bin/env python3
"""Reconcile atomic mapping decisions after a Word ledger is regenerated.

Only final decisions whose evidence identity and candidate semantic roles remain
unchanged are carried forward. Changed or ambiguous evidence stays pending in a
fresh queue, so an earlier mapping cannot silently certify a new extraction.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_atomic_mapping import FINAL_STATUSES, format_binding_errors, load_json, starter


EDITABLE_FIELDS = {
    "status",
    "role",
    "latex_owner",
    "latex_file",
    "latex_token",
    "format_bindings",
    "object_format_bindings",
    "guidance_kind",
    "reason",
}


def identity(decision: dict[str, Any]) -> tuple[Any, ...]:
    """Return an extraction-stable identity that excludes the group hash."""
    roles = sorted(
        str(item.get("role") or "")
        for item in decision.get("role_candidates") or []
        if isinstance(item, dict) and item.get("role")
    )
    return (
        str(decision.get("source_scope") or ""),
        str(decision.get("container") or ""),
        str(decision.get("kind") or ""),
        tuple(sorted(str(item) for item in decision.get("evidence_ids") or [])),
        tuple(roles),
        json.dumps(decision.get("required_format_binding_values") or {}, ensure_ascii=False, sort_keys=True),
        json.dumps(decision.get("required_object_format_binding_values") or {}, ensure_ascii=False, sort_keys=True),
    )


def final(decision: dict[str, Any]) -> bool:
    return str(decision.get("status") or "pending").strip().lower() in FINAL_STATUSES


def needs_binding_migration(decision: dict[str, Any]) -> bool:
    """Return whether a prior mapped/default decision lacks current bindings."""
    if str(decision.get("status") or "").strip().lower() not in {"mapped", "default"}:
        return False
    direct_errors = format_binding_errors(
        decision.get("required_format_binding_values") if isinstance(decision.get("required_format_binding_values"), dict) else {},
        decision.get("format_bindings"),
        None,
    )
    object_errors = format_binding_errors(
        decision.get("required_object_format_binding_values") if isinstance(decision.get("required_object_format_binding_values"), dict) else {},
        decision.get("object_format_bindings"),
        None,
        "object_format_bindings",
        "observable Word object layout",
    )
    return bool(direct_errors or object_errors)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("format_ledger", help="Regenerated word_format_ledger.json")
    parser.add_argument("--decisions", required=True, help="Prior atomic_mapping_decisions.json")
    parser.add_argument("--output", required=True, help="Fresh reconciled atomic_mapping_decisions.json")
    parser.add_argument("--report", help="Optional reconciliation report JSON")
    args = parser.parse_args()

    ledger = load_json(Path(args.format_ledger))
    prior = load_json(Path(args.decisions))
    fresh = starter(ledger)
    prior_groups = [item for item in prior.get("decisions") or [] if isinstance(item, dict)]
    by_key = {str(item.get("group_key") or ""): item for item in prior_groups if item.get("group_key")}
    by_identity: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for item in prior_groups:
        by_identity.setdefault(identity(item), []).append(item)

    exact = 0
    structural = 0
    pending_changed: list[str] = []
    ambiguous: list[str] = []
    binding_migration_required: list[str] = []
    for current in fresh["decisions"]:
        old = by_key.get(str(current.get("group_key") or ""))
        mode = "exact"
        if old is None:
            matches = by_identity.get(identity(current), [])
            if len(matches) == 1:
                old = matches[0]
                mode = "structural"
            elif len(matches) > 1:
                ambiguous.append(str(current.get("group_key") or ""))
        if old is None:
            pending_changed.append(str(current.get("group_key") or ""))
            continue
        if final(old):
            for field in EDITABLE_FIELDS:
                if field in old:
                    current[field] = old[field]
            if needs_binding_migration(current):
                # The source identity is stable, but the old decision cannot
                # certify current direct/object format requirements. Keep its
                # immutable evidence and role candidates, reset only the final
                # disposition, and send this group back through the bounded
                # review queue instead of producing a wall of invalid audits.
                for field in EDITABLE_FIELDS:
                    current[field] = "" if field not in {"format_bindings", "object_format_bindings"} else []
                current["status"] = "pending"
                binding_migration_required.append(str(current.get("group_key") or ""))
                continue
            if mode == "exact":
                exact += 1
            else:
                structural += 1

    fresh["reconciled_from"] = str(Path(args.decisions).resolve())
    fresh["reconciliation_rule"] = (
        "Final dispositions are retained only for an exact group key or a unique match on source scope, container, "
        "kind, evidence IDs, candidate roles, and direct Word-format values. All other groups require fresh review."
    )
    write_json(Path(args.output), fresh)
    report = {
        "schema_version": "temp2tex.atomic-mapping-reconciliation-report.v1",
        "ledger_fingerprint": ledger.get("evidence_fingerprint"),
        "prior_decisions": str(Path(args.decisions).resolve()),
        "output_decisions": str(Path(args.output).resolve()),
        "carried_exact_final_count": exact,
        "carried_structural_final_count": structural,
        "fresh_review_group_count": len(pending_changed),
        "ambiguous_prior_match_count": len(ambiguous),
        "binding_migration_required_count": len(binding_migration_required),
        "fresh_review_group_keys": pending_changed,
        "ambiguous_prior_match_keys": ambiguous,
        "binding_migration_required_keys": binding_migration_required,
        "next_action": "Review every fresh, ambiguous, or binding-migration group before strict audit. For binding migration groups, preserve the source values prefilled by the fresh queue and complete format_bindings/object_format_bindings; do not restore an old final disposition solely because its wording looks similar.",
    }
    if args.report:
        write_json(Path(args.report), report)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
