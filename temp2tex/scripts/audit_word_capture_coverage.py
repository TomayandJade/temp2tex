#!/usr/bin/env python3
"""Audit fine-grained Word evidence capture for one template or a corpus."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audit_atomic_mapping import layout_only_run_kind
from build_word_format_ledger import build_ledger_from_word_source


WORD_SUFFIXES = {".doc", ".docx", ".docm", ".dot", ".dotx", ".dotm", ".rtf"}


def word_files(source: Path, inputs_only: bool) -> list[Path]:
    if source.is_file():
        return [source] if source.suffix.lower() in WORD_SUFFIXES else []
    files = [path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in WORD_SUFFIXES]
    if inputs_only:
        files = [path for path in files if path.parent.name.lower() == "word" and path.parent.parent.name.lower() == "inputs"]
    return sorted(files)


def units(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        unit
        for collection in ("paragraphs", "ancillary_units")
        for unit in (ledger.get(collection) or [])
        if isinstance(unit, dict)
    ]


def audit_file(path: Path) -> dict[str, Any]:
    ledger = build_ledger_from_word_source(path)
    coverage = ledger.get("coverage") if isinstance(ledger.get("coverage"), dict) else {}
    captured_units = units(ledger)
    limitations = coverage.get("capture_limitations") if isinstance(coverage.get("capture_limitations"), list) else [
        {"area": "ledger_scope", "reason": "No v3 capture coverage record was available."}
    ]
    complete = (
        ledger.get("schema_version") == "temp2tex.word-format-ledger.v3"
        and coverage.get("all_visible_text_units_captured") is True
        and coverage.get("all_observable_object_units_captured") is True
        and not limitations
    )
    body = [unit for unit in (ledger.get("paragraphs") or []) if isinstance(unit, dict)]
    ancillary = [unit for unit in (ledger.get("ancillary_units") or []) if isinstance(unit, dict)]
    spans = [span for unit in captured_units for span in (unit.get("format_spans") or []) if isinstance(span, dict)]
    visible_spans = [span for span in spans if str(span.get("text") or span.get("format_span_text") or "").strip()]
    layout_spans = [span for span in spans if not str(span.get("text") or span.get("format_span_text") or "").strip() and layout_only_run_kind(span)]
    ancillary_by_container = Counter(str(unit.get("container") or "unknown") for unit in ancillary)
    object_kinds = Counter(
        str(unit.get("kind") or "unknown")
        for unit in (ledger.get("object_evidence") or [])
        if isinstance(unit, dict)
    )
    body_count = len(body)
    layout_only_body = sum(bool(unit.get("layout_only")) for unit in body)
    layout_only_ancillary = sum(bool(unit.get("layout_only")) for unit in ancillary)
    visible_body_count = body_count - layout_only_body
    if complete and visible_body_count == 0:
        status = "captured_sparse_or_empty"
        next_action = "Use official guides, styles, or sample PDFs for role evidence; do not invent a body exemplar."
    elif complete:
        status = "capture_complete"
        next_action = "Proceed to atomic map-or-gap decisions; every captured paragraph and contiguous run still needs a disposition."
    else:
        status = "capture_incomplete"
        next_action = "Resolve the stated capture limitation before strict mapping audit or visual calibration."
    return {
        "path": str(path),
        "status": status,
        "next_action": next_action,
        "schema_version": ledger.get("schema_version"),
        "source_conversion": ledger.get("source_conversion"),
        "capture_limitations": limitations,
        "units": {
            "body_and_table_cell_paragraphs": body_count,
            "visible_body_and_table_cell_paragraphs": visible_body_count,
            "layout_only_body_and_table_cell_paragraphs": layout_only_body,
            "table_cell_paragraphs": sum(bool(unit.get("in_table_cell")) for unit in body),
            "ancillary_paragraphs": len(ancillary),
            "layout_only_ancillary_paragraphs": layout_only_ancillary,
            "ancillary_by_container": dict(sorted(ancillary_by_container.items())),
            "contiguous_run_spans": len(spans),
            "visible_glyph_run_spans": len(visible_spans),
            "layout_only_run_spans": len(layout_spans),
            "inherited_whitespace_run_spans": len(spans) - len(visible_spans) - len(layout_spans),
            "multi_run_units": sum(len(unit.get("format_spans") or []) > 1 for unit in captured_units),
            "object_evidence": len(ledger.get("object_evidence") or []),
            "objects_by_kind": dict(sorted(object_kinds.items())),
        },
        "observable_systems": {
            key: value
            for key, value in coverage.items()
            if key.startswith("observable_") and isinstance(value, int)
        },
    }


def summarize(cases: list[dict[str, Any]]) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    system_totals: Counter[str] = Counter()
    for case in cases:
        for key, value in (case.get("units") or {}).items():
            if isinstance(value, int):
                totals[key] += value
        for key, value in (case.get("observable_systems") or {}).items():
            if isinstance(value, int):
                system_totals[key] += value
    statuses = Counter(str(case.get("status") or "unknown") for case in cases)
    incomplete = [case["path"] for case in cases if case.get("status") == "capture_incomplete"]
    return {
        "templates": len(cases),
        "statuses": dict(sorted(statuses.items())),
        "unit_totals": dict(sorted(totals.items())),
        "observable_system_totals": dict(sorted(system_totals.items())),
        "incomplete_paths": incomplete,
        "rule": "A complete capture audit proves source-unit availability, not that every unit has been mapped. Sparse templates require a documented default or external official evidence, never fabricated body formatting.",
    }


def markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Word Capture Coverage Audit",
        "",
        f"- Templates: `{summary['templates']}`",
        f"- Statuses: `{json.dumps(summary['statuses'], ensure_ascii=False, sort_keys=True)}`",
        f"- Unit totals: `{json.dumps(summary['unit_totals'], ensure_ascii=False, sort_keys=True)}`",
        f"- Observable systems: `{json.dumps(summary['observable_system_totals'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Incomplete Capture",
        "",
    ]
    incomplete = summary.get("incomplete_paths") or []
    if incomplete:
        lines.extend(f"- `{path}`" for path in incomplete)
    else:
        lines.append("- No capture-incomplete Word sources.")
    lines.extend([
        "",
        "## Gate",
        "",
        "- `capture_complete` permits atomic mapping review, not a fidelity claim.",
        "- `captured_sparse_or_empty` requires an explicit source gap or external official evidence.",
        "- `capture_incomplete` blocks strict mapping completion and visual calibration.",
    ])
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
        "schema_version": "temp2tex.word-capture-coverage-audit.v1",
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
