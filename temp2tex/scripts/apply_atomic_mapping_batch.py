#!/usr/bin/env python3
"""Merge one model-reviewed atomic mapping batch without changing source evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_atomic_mapping import GUIDANCE_KINDS, FINAL_STATUSES, bare_macro_usage_errors, format_binding_errors, load_json, package_file_text


SCHEMA_VERSION = "temp2tex.atomic-mapping-batch.v1"
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


def require_final_fields(decision: dict[str, Any], candidate_roles: set[str], package: Path) -> None:
    """Reject a final batch disposition that strict audit would immediately fail."""
    status = str(decision.get("status") or "").strip().lower()
    role = str(decision.get("role") or "")
    if status in {"mapped", "default"}:
        if role not in candidate_roles:
            raise SystemExit("Mapped/default update has a role not supported by this group's Word evidence")
        if not str(decision.get("latex_owner") or "").strip():
            raise SystemExit("Mapped/default update requires latex_owner")
        latex_file = str(decision.get("latex_file") or "").strip()
        latex_token = str(decision.get("latex_token") or "")
        if not latex_file or not latex_token:
            raise SystemExit("Mapped/default update requires latex_file and latex_token")
        file_text, file_error = package_file_text(package, latex_file)
        if file_error:
            raise SystemExit(file_error)
        if latex_token not in str(file_text):
            raise SystemExit("latex_token was not found outside comments in latex_file")
        usage_errors = bare_macro_usage_errors(package, latex_file, latex_token)
        if usage_errors:
            raise SystemExit("; ".join(usage_errors))
        binding_errors = format_binding_errors(
            decision.get("required_format_binding_values") if isinstance(decision.get("required_format_binding_values"), dict) else {},
            decision.get("format_bindings"),
            package,
        )
        if binding_errors:
            raise SystemExit("; ".join(binding_errors))
        object_binding_errors = format_binding_errors(
            decision.get("required_object_format_binding_values") if isinstance(decision.get("required_object_format_binding_values"), dict) else {},
            decision.get("object_format_bindings"),
            package,
            "object_format_bindings",
            "observable Word object layout",
        )
        if object_binding_errors:
            raise SystemExit("; ".join(object_binding_errors))
    elif status == "guidance":
        if str(decision.get("guidance_kind") or "").strip().lower() not in GUIDANCE_KINDS:
            raise SystemExit("Guidance update requires a recognized guidance_kind")
        if not str(decision.get("reason") or "").strip():
            raise SystemExit("Guidance update requires a concise reason")
    elif status in {"unresolved", "not_observable"} and not str(decision.get("reason") or "").strip():
        raise SystemExit(f"{status} update requires a concise reason")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decisions", help="Current atomic_mapping_decisions.json")
    parser.add_argument("batch", help="Reviewed batch JSON with schema temp2tex.atomic-mapping-batch.v1")
    parser.add_argument("--ledger", required=True, help="word_format_ledger.json used to bind the batch to source evidence")
    parser.add_argument("--package", required=True, help="Generated package used to verify mapped/default owner files and tokens")
    parser.add_argument("--output", required=True, help="Merged atomic_mapping_decisions.json")
    parser.add_argument("--report", help="Optional apply report JSON")
    parser.add_argument("--allow-revise", action="store_true", help="Allow an explicit correction to a group that already has a final disposition")
    args = parser.parse_args()

    decisions = load_json(Path(args.decisions))
    ledger = load_json(Path(args.ledger))
    batch = load_json(Path(args.batch))
    if decisions.get("schema_version") != "temp2tex.atomic-mapping-decisions.v1":
        raise SystemExit("Decision file has an unsupported schema_version")
    if batch.get("schema_version") != SCHEMA_VERSION:
        raise SystemExit("Batch file has an unsupported schema_version")
    if batch.get("ledger_fingerprint") != ledger.get("evidence_fingerprint"):
        raise SystemExit("Batch ledger_fingerprint does not match the supplied Word ledger")
    package = Path(args.package).resolve()
    if not package.is_dir():
        raise SystemExit("--package must name the generated LaTeX package directory")
    updates = batch.get("updates")
    if not isinstance(updates, list) or not updates:
        raise SystemExit("Batch must contain a non-empty updates list")
    original = decisions.get("decisions")
    if not isinstance(original, list):
        raise SystemExit("Decision file must contain a decisions list")
    by_key = {str(item.get("group_key") or ""): item for item in original if isinstance(item, dict) and item.get("group_key")}
    seen: set[str] = set()
    applied: list[str] = []
    revised: list[str] = []
    for update in updates:
        if not isinstance(update, dict):
            raise SystemExit("Every batch update must be a JSON object")
        group_key = str(update.get("group_key") or "")
        if not group_key or group_key not in by_key:
            raise SystemExit(f"Batch references an unknown group_key: {group_key or '<empty>'}")
        if group_key in seen:
            raise SystemExit(f"Batch updates group_key more than once: {group_key}")
        seen.add(group_key)
        extra = set(update) - (EDITABLE_FIELDS | {"group_key"})
        if extra:
            raise SystemExit(f"Batch update {group_key} contains immutable or unknown fields: {', '.join(sorted(extra))}")
        status = str(update.get("status") or "").strip().lower()
        if status not in FINAL_STATUSES:
            raise SystemExit(f"Batch update {group_key} must use a final disposition, not {status or 'an empty status'}")
        existing = by_key[group_key]
        existing_status = str(existing.get("status") or "pending").strip().lower()
        if existing_status in FINAL_STATUSES and not args.allow_revise:
            raise SystemExit(f"Batch update {group_key} would overwrite an existing final disposition; use --allow-revise for an explicit correction")
        candidate_roles = {
            str(candidate.get("role") or "")
            for candidate in existing.get("role_candidates") or []
            if isinstance(candidate, dict)
        }
        role = str(update.get("role") or "")
        if status in {"mapped", "default"} and role not in candidate_roles:
            raise SystemExit(f"Batch update {group_key} maps/defaults a role not supported by this group's Word evidence")
        effective = dict(existing)
        for field in EDITABLE_FIELDS:
            if field in update:
                effective[field] = update[field]
        require_final_fields(effective, candidate_roles, package)
        existing.update(effective)
        applied.append(group_key)
        if existing_status in FINAL_STATUSES:
            revised.append(group_key)

    write_json(Path(args.output), decisions)
    report = {
        "schema_version": "temp2tex.atomic-mapping-batch-apply-report.v1",
        "ledger_fingerprint": ledger.get("evidence_fingerprint"),
        "source_decisions": str(Path(args.decisions).resolve()),
        "output_decisions": str(Path(args.output).resolve()),
        "applied_group_count": len(applied),
        "applied_group_keys": applied,
        "revised_group_count": len(revised),
        "revised_group_keys": revised,
        "package_checked": str(package),
        "next_action": "Run audit_atomic_mapping.py --strict with the merged decisions and generated package; batch merging verifies basic local fields but never approves a mapping by itself.",
    }
    if args.report:
        write_json(Path(args.report), report)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
