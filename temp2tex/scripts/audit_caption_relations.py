#!/usr/bin/env python3
"""Audit Word table/figure caption relations across one template or a corpus."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inspect_sources import caption_relation_disposition, inspect_file


WORD_SUFFIXES = {".doc", ".docx", ".docm", ".dot", ".dotx", ".dotm", ".rtf"}
CONFIRMED = {"adjacent", "nearby"}


def evidence_disposition(relation: dict[str, Any]) -> dict[str, Any]:
    """State exactly which reconstruction decisions a relation may drive."""
    confidence = str(relation.get("confidence") or "not_detected")
    position = str(relation.get("position") or "unknown")
    if confidence in CONFIRMED and position in {"above", "below"}:
        return {
            "state": "confirmed_source_relation",
            "may_drive": [
                "caption_order_candidate",
                "object_caption_gap_candidate",
                "object_specific_pdf_anchor_candidate",
            ],
            "must_not_drive": [],
            "next_action": "Retain the source evidence ID and confirm the selected rule by rendering when a comparable PDF is available.",
        }
    if confidence == "distant":
        return {
            "state": "remote_caption_candidate",
            "may_drive": ["caption_typography_candidate_if_independently_selected"],
            "must_not_drive": [
                "caption_order",
                "object_caption_gap",
                "float_policy",
                "object_specific_pdf_anchor",
            ],
            "next_action": "Log a source gap. Inspect the local rendered Word page or use an independently confirmed caption exemplar; do not infer attachment from XML distance.",
        }
    if confidence == "label_mismatch":
        return {
            "state": "label_mismatch",
            "may_drive": [],
            "must_not_drive": [
                "caption_order",
                "caption_spacing",
                "float_policy",
                "object_specific_pdf_anchor",
            ],
            "next_action": "Treat nearby labels as diagnostic context only. Resolve from a rendered page or retain the documented table-above/figure-below default.",
        }
    if confidence == "ambiguous":
        return {
            "state": "ambiguous_source_relation",
            "may_drive": [],
            "must_not_drive": [
                "caption_order",
                "object_caption_gap",
                "float_policy",
                "object_specific_pdf_anchor",
            ],
            "next_action": "Keep every tied candidate in the evidence ledger and resolve only with stronger source or same-content render evidence.",
        }
    return {
        "state": "no_observed_caption_relation",
        "may_drive": ["local_object_geometry_candidate"],
        "must_not_drive": [
            "caption_order",
            "caption_spacing",
            "float_policy",
            "object_specific_pdf_anchor",
        ],
        "next_action": "Record an evidence gap. The object may be uncaptioned artwork, page furniture, or an incomplete template example.",
    }


def word_files(source: Path, inputs_only: bool) -> list[Path]:
    if source.is_file():
        return [source] if source.suffix.lower() in WORD_SUFFIXES else []
    files = [path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in WORD_SUFFIXES]
    if inputs_only:
        files = [path for path in files if path.parent.name.lower() == "word" and path.parent.parent.name.lower() == "inputs"]
    return sorted(files)


def relation_record(kind: str, ordinal: int, relation: object) -> dict[str, Any]:
    value = relation if isinstance(relation, dict) else {}
    record = {
        "kind": kind,
        "ordinal": ordinal,
        "position": str(value.get("position") or "unknown"),
        "confidence": str(value.get("confidence") or "not_detected"),
        "caption_paragraph_index": value.get("caption_paragraph_index"),
        "caption_label": value.get("caption_label"),
        "target_object_ordinal": value.get("target_object_ordinal"),
        "label_match": value.get("label_match"),
        "caption_text": str(value.get("caption_text") or "")[:180],
        "ambiguous_candidates": value.get("nearest_caption_candidates") if isinstance(value.get("nearest_caption_candidates"), list) else [],
        "remote_candidate": value.get("nearest_caption_candidate") if isinstance(value.get("nearest_caption_candidate"), dict) else None,
    }
    source_disposition = value.get("evidence_disposition") if isinstance(value.get("evidence_disposition"), dict) else None
    # Source extraction owns the eligibility state; the audit augments it with
    # its human-readable remediation instruction for Markdown reports.
    record["evidence_disposition"] = {
        **evidence_disposition(record),
        **(source_disposition or {}),
    }
    return record


def audit_file(path: Path) -> dict[str, Any]:
    inspected = inspect_file(path)
    details = inspected.get("inspection") if isinstance(inspected.get("inspection"), dict) else {}
    if inspected.get("inspection_error"):
        return {"path": str(path), "status": "inspection_error", "error": str(inspected.get("inspection_error")), "relations": []}
    if not details or not (
        isinstance(details.get("tables"), list)
        or isinstance(details.get("body_drawings"), list)
    ):
        return {
            "path": str(path),
            "status": "not_inspectable",
            "reason": str(details.get("error") or details.get("warning") or "No structured Word object evidence was available."),
            "relations": [],
        }
    relations = []
    for ordinal, table in enumerate(details.get("tables") or [], start=1):
        if isinstance(table, dict):
            relations.append(relation_record("table", int(table.get("index") or ordinal), table.get("caption_relation")))
    for ordinal, drawing in enumerate(details.get("body_drawings") or [], start=1):
        if isinstance(drawing, dict):
            relations.append(relation_record("figure", ordinal, drawing.get("caption_relation")))
    duplicate_assignments: list[dict[str, Any]] = []
    owners: dict[tuple[str, int], list[int]] = defaultdict(list)
    for relation in relations:
        index = relation.get("caption_paragraph_index")
        if (
            relation["confidence"] in CONFIRMED
            and relation["position"] in {"above", "below"}
            and isinstance(index, int)
        ):
            owners[(relation["kind"], index)].append(int(relation["ordinal"]))
    for (kind, index), ordinals in sorted(owners.items()):
        if len(ordinals) > 1:
            duplicate_assignments.append({"kind": kind, "caption_paragraph_index": index, "object_ordinals": ordinals})
    return {
        "path": str(path),
        "status": "ok",
        "language_hint": details.get("language_hint"),
        "relations": relations,
        "duplicate_confirmed_assignments": duplicate_assignments,
    }


def summarize(cases: list[dict[str, Any]]) -> dict[str, Any]:
    relation_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    label_match_counts: Counter[str] = Counter()
    disposition_counts: Counter[str] = Counter()
    duplicate_count = 0
    object_count = 0
    for case in cases:
        for relation in case.get("relations") or []:
            object_count += 1
            relation_counts[str(relation.get("kind") or "unknown")] += 1
            confidence_counts[str(relation.get("confidence") or "not_detected")] += 1
            label_match_counts[str(relation.get("label_match") or "not_available")] += 1
            disposition = relation.get("evidence_disposition")
            if isinstance(disposition, dict):
                disposition_counts[str(disposition.get("state") or "unknown")] += 1
        duplicate_count += len(case.get("duplicate_confirmed_assignments") or [])
    status_counts = Counter(str(case.get("status") or "unknown") for case in cases)
    return {
        "templates": len(cases),
        "template_statuses": dict(sorted(status_counts.items())),
        "objects": object_count,
        "objects_by_kind": dict(sorted(relation_counts.items())),
        "relations_by_confidence": dict(sorted(confidence_counts.items())),
        "label_match_statuses": dict(sorted(label_match_counts.items())),
        "evidence_dispositions": dict(sorted(disposition_counts.items())),
        "duplicate_confirmed_assignments": duplicate_count,
        "rule": "A duplicate confirmed assignment is a source-extraction defect until a source-specific exception is documented; do not use it to set caption order, spacing, float placement, or a PDF object anchor.",
    }


def markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Caption Relation Audit",
        "",
        f"- Templates: `{summary['templates']}`",
        f"- Observable tables/figures: `{summary['objects']}`",
        f"- Duplicate confirmed assignments: `{summary['duplicate_confirmed_assignments']}`",
        f"- Confidence: `{json.dumps(summary['relations_by_confidence'], ensure_ascii=False, sort_keys=True)}`",
        f"- Label matching: `{json.dumps(summary['label_match_statuses'], ensure_ascii=False, sort_keys=True)}`",
        f"- Evidence dispositions: `{json.dumps(summary['evidence_dispositions'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Problems",
        "",
    ]
    problems = [case for case in report["cases"] if case.get("status") != "ok" or case.get("duplicate_confirmed_assignments")]
    if not problems:
        lines.append("- No duplicate confirmed caption assignments were detected.")
    unresolved = [
        relation
        for case in report["cases"]
        for relation in (case.get("relations") or [])
        if isinstance(relation.get("evidence_disposition"), dict)
        and relation["evidence_disposition"].get("state") != "confirmed_source_relation"
    ]
    if unresolved:
        lines.extend(["", "## Unresolved relation handling", ""])
        for state, count in sorted(Counter(
            str(relation["evidence_disposition"].get("state")) for relation in unresolved
        ).items()):
            example = next(
                relation for relation in unresolved
                if relation["evidence_disposition"].get("state") == state
            )
            lines.append(f"- `{state}`: `{count}` object(s). {example['evidence_disposition']['next_action']}")
    for case in problems:
        lines.append(f"- `{case['path']}`: `{case.get('status')}`")
        for duplicate in case.get("duplicate_confirmed_assignments") or []:
            lines.append(
                f"  - Duplicate `{duplicate['kind']}` caption paragraph `{duplicate['caption_paragraph_index']}` for objects "
                + ", ".join(str(value) for value in duplicate["object_ordinals"])
            )
        if case.get("reason"):
            lines.append(f"  - {case['reason']}")
        if case.get("error"):
            lines.append(f"  - {case['error']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Official Word file or a corpus directory")
    parser.add_argument("--inputs-only", action="store_true", help="For a corpus, inspect only files under case/inputs/word")
    parser.add_argument("--output", required=True, help="JSON report path")
    parser.add_argument("--markdown-output", help="Optional Markdown report path")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        raise SystemExit("source not found")
    files = word_files(source, args.inputs_only)
    if not files:
        raise SystemExit("No Word files matched the requested source scope")
    cases = [audit_file(path) for path in files]
    report = {
        "schema_version": "temp2tex.caption-relation-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "inputs_only": args.inputs_only,
        "summary": summarize(cases),
        "cases": cases,
    }
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        markdown_output = Path(args.markdown_output).expanduser().resolve()
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(markdown(report), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
