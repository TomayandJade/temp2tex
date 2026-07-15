#!/usr/bin/env python3
"""Audit whether visible Word template evidence has an editable LaTeX owner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


# The format ledger records the Word-side role proposal. These checks make the
# conversion audit prove that each proposal has both a spec decision and a
# concrete editable package interface, without treating a generic class macro
# as proof that the source-specific formatting has already been verified.
LEDGER_ROLE_AUDIT = {
    "front_matter.title": {"spec": "front_matter.title_style", "tokens": ("\\title{", "\\maketitle")},
    "front_matter.author": {"spec": "front_matter.author_style", "tokens": ("\\author{",)},
    "front_matter.affiliation": {"spec": "front_matter.affiliation_style", "tokens": ("\\affiliation{",)},
    "front_matter.abstract": {"spec": "abstracts.style", "tokens": ("\\begin{abstract}",)},
    "front_matter.keywords": {"spec": "abstracts.keyword_style", "tokens": ("\\tempTwoTexKeywords",)},
    "front_matter.metadata": {"spec": "front_matter.metadata_style", "tokens": ("\\maketitle",)},
    "front_matter.english_title": {"spec": "front_matter.english_title_style", "tokens": ("\\englishtitle{",)},
    "front_matter.english_author": {"spec": "front_matter.english_author_style", "tokens": ("\\englishauthor{",)},
    "front_matter.english_affiliation": {"spec": "front_matter.english_affiliation_style", "tokens": ("\\englishaffiliation{",)},
    "front_matter.english_abstract": {"spec": "front_matter.english_abstract_style", "tokens": ("\\englishabstract{",)},
    "front_matter.english_keywords": {"spec": "front_matter.english_keywords_style", "tokens": ("\\englishkeywords{",)},
    "heading.level0": {"spec": "body.heading_styles.level0", "tokens": ("\\section{",)},
    "heading.level1": {"spec": "body.heading_styles.level1", "tokens": ("\\subsection{",)},
    "heading.level2": {"spec": "body.heading_styles.level2", "tokens": ("\\subsubsection{",)},
    "body.paragraph": {"spec": "page.source_body_style", "tokens": ("\\setlength{\\parindent}", "\\linespread{")},
    "table.caption": {"spec": "tables.caption_style", "tokens": ("\\begin{journaltable}", "\\caption{")},
    "figure.caption": {"spec": "figures.caption_style", "tokens": ("\\begin{journalfigure}", "\\caption{")},
    "references.heading": {"spec": "references.style_evidence", "tokens": ("\\begin{thebibliography}",)},
    "references.entry": {"spec": "references.entry_style", "tokens": ("\\bibitem",)},
    "appendix.heading": {"spec": "appendices", "tokens": ("\\journalappendix",)},
}


def nested(value: Any, path: str, default: Any = None) -> Any:
    for key in path.split("."):
        if not isinstance(value, dict):
            return default
        value = value.get(key)
    return default if value is None else value


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def document_from(inventory: dict[str, Any]) -> dict[str, Any]:
    for item in inventory.get("files", []):
        if isinstance(item, dict) and isinstance(item.get("inspection"), dict):
            return item["inspection"]
    return inventory


def role_has_visible_spans(spec: dict[str, Any], path: str) -> bool:
    role = nested(spec, path, {})
    if not isinstance(role, dict):
        return False
    status = str(role.get("evidence_status") or "").lower()
    return status in {"source", "visible_role_exemplar", "direct_paragraph", "direct_run"} or bool(role.get("format_spans") or role.get("format_span_text"))


def package_contains(text: str, *tokens: str) -> bool:
    return all(token in text for token in tokens)


def record(name: str, observed: bool, mapped: bool, source: str, owner: str, reason: str, priority: str = "high") -> dict[str, Any]:
    status = "not_observable" if not observed else ("mapped" if mapped else "needs_mapping")
    return {"feature": name, "status": status, "priority": priority if status == "needs_mapping" else None, "source": source, "latex_owner": owner, "reason": reason}


def role_decision_state(value: Any) -> str:
    """Classify a selected spec value without promoting weak evidence."""
    if not isinstance(value, dict) or not value:
        return "missing"
    comment = value.get("comment_format_evidence")
    if isinstance(comment, dict) and comment.get("status") == "accepted":
        return "source"
    status = str(value.get("evidence_status") or "").lower()
    if status in {"source", "visible_role_exemplar", "direct_paragraph", "direct_run"}:
        return "source"
    if value.get("source") and status not in {"default", "template_style_candidate"}:
        return "candidate"
    if status in {"default", "template_style_candidate"}:
        return "candidate"
    return "candidate"


def audit_format_ledger(ledger: dict[str, Any] | None, spec: dict[str, Any], package_text: str) -> dict[str, Any] | None:
    """Reconcile every ledger role with the selected spec and editable package.

    `mapped_pending_visual_confirmation` is deliberate: an agent has provided
    a traceable owner for a candidate-style Word role, but the source has not
    established enough visible formatting evidence to call it matched.
    """
    if not isinstance(ledger, dict):
        return None
    paragraph_roles: dict[str, list[dict[str, Any]]] = {}
    for paragraph in ledger.get("paragraphs", []):
        if not isinstance(paragraph, dict):
            continue
        evidence_id = str(paragraph.get("evidence_id") or "")
        for candidate in paragraph.get("role_candidates", []):
            if not isinstance(candidate, dict) or not candidate.get("role"):
                continue
            paragraph_roles.setdefault(str(candidate["role"]), []).append({
                "evidence_id": evidence_id,
                "confidence": str(candidate.get("confidence") or "candidate"),
                "reason": str(candidate.get("reason") or ""),
            })
    queue_by_role = {
        str(item.get("role")): item
        for item in ledger.get("mapping_queue", [])
        if isinstance(item, dict) and item.get("role")
    }
    audits = []
    for role, config in LEDGER_ROLE_AUDIT.items():
        queue = queue_by_role.get(role, {})
        evidence = paragraph_roles.get(role, [])
        evidence_ids = list(queue.get("evidence_ids") or [item["evidence_id"] for item in evidence])
        if not evidence_ids:
            audits.append({
                "role": role,
                "status": "not_observable",
                "evidence_ids": [],
                "spec_path": config["spec"],
                "latex_owner": queue.get("owner"),
                "reason": "No role-matched visible Word paragraph was found in the format ledger.",
            })
            continue
        source_evidence = any(item["confidence"] == "source" for item in evidence)
        package_ready = package_contains(package_text, *config["tokens"])
        decision = role_decision_state(nested(spec, config["spec"], {}))
        if not package_ready or decision == "missing":
            missing = "editable package interface" if not package_ready else "role-specific template_spec decision"
            audits.append({
                "role": role,
                "status": "needs_mapping",
                "priority": "critical" if source_evidence else "high",
                "evidence_ids": evidence_ids,
                "spec_path": config["spec"],
                "latex_owner": queue.get("owner"),
                "reason": f"Visible Word evidence exists but the {missing} is absent.",
            })
            continue
        if source_evidence and decision == "source":
            status = "mapped"
            reason = "Role has source-backed Word evidence, a selected spec decision, and an editable package interface."
        else:
            status = "mapped_pending_visual_confirmation"
            reason = "Role has an editable package interface, but its selected evidence remains a candidate/default-level decision and needs visible-source or same-content confirmation."
        audits.append({
            "role": role,
            "status": status,
            "evidence_ids": evidence_ids,
            "spec_path": config["spec"],
            "latex_owner": queue.get("owner"),
            "reason": reason,
        })
    gaps = [item for item in audits if item["status"] == "needs_mapping"]
    pending = [item for item in audits if item["status"] == "mapped_pending_visual_confirmation"]
    return {
        "source": ledger.get("source"),
        "schema_version": ledger.get("schema_version"),
        "roles": audits,
        "summary": {
            "mapped": sum(item["status"] == "mapped" for item in audits),
            "needs_mapping": len(gaps),
            "pending_visual_confirmation": len(pending),
            "not_observable": sum(item["status"] == "not_observable" for item in audits),
        },
        "priority_gaps": gaps,
        "pending_confirmation": pending,
    }


def build_coverage(
    inventory: dict[str, Any],
    spec: dict[str, Any],
    package_dir: Path | None = None,
    format_ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = document_from(inventory)
    package_text = ""
    if package_dir:
        for filename in ("journal-template.cls", "main.tex", "textboxes.tex", "textboxes-active.tex", "equations.tex"):
            path = package_dir / filename
            if path.is_file():
                package_text += "\n" + path.read_text(encoding="utf-8", errors="replace")
    paragraphs = [item for item in document.get("paragraph_samples", []) if isinstance(item, dict)]
    front = [item for item in document.get("front_matter_candidates", []) if isinstance(item, dict)]
    headings = document.get("heading_candidates", []) or []
    headers = [item for item in document.get("header_footer_parts", []) if isinstance(item, dict)]
    tables = document.get("tables", []) or []
    text_boxes = document.get("text_boxes", []) or []
    drawings = document.get("body_drawings", []) or []
    captions = document.get("caption_candidates", []) or []
    equations = document.get("equations", []) or []
    spans = sum(len(item.get("format_spans") or []) for item in paragraphs)
    text_box_spans = sum(
        len(paragraph.get("format_spans") or [])
        for box in text_boxes if isinstance(box, dict)
        for paragraph in (box.get("paragraphs") or []) if isinstance(paragraph, dict)
    )
    selected_table_cells = nested(spec, "tables.layout_evidence.cell_format_samples", [])
    selected_table_cells = selected_table_cells if isinstance(selected_table_cells, list) else []
    selected_table_truncated = bool(nested(spec, "tables.layout_evidence.cell_format_samples_truncated", False))
    table_cell_spans = sum(
        len(paragraph.get("format_spans") or [])
        for cell in selected_table_cells if isinstance(cell, dict)
        for paragraph in (cell.get("paragraphs") or []) if isinstance(paragraph, dict)
    )
    table_cell_complexity = sorted({
        reason
        for cell in selected_table_cells if isinstance(cell, dict)
        for reason in (
            "unsupported vertical merge value" if cell.get("vertical_merge") not in {None, "restart", "continue"} else None,
            "more than four cell paragraphs" if str(cell.get("paragraph_count") or "0").isdigit() and int(cell.get("paragraph_count") or 0) > 4 else None,
            "truncated cell evidence" if cell.get("paragraphs_truncated") else None,
            "truncated table evidence" if selected_table_truncated else None,
        ) if reason
    })
    table_cell_replayed = package_contains(package_text, "temp2tex-source-table-spans")
    table_cell_reason = (
        "Selected table-cell evidence was replayed into the representative fixture."
        if table_cell_replayed else
        "Selected table-cell evidence could not be replayed. "
        + ("Observed unsupported structure: " + ", ".join(table_cell_complexity) + ". " if table_cell_complexity else "Inspect the selected cell sequence, spans, and text evidence. ")
        + "Retain the source ledger and map the unresolved structure before visual calibration."
    )
    # A template-style candidate is useful for generation but is not a
    # visible-source feature. Coverage must not manufacture a title obligation
    # from arbitrary first-page instructions or a blank placeholder.
    title_seen = role_has_visible_spans(spec, "front_matter.title_style")
    abstract_seen = any("abstract" in str(item.get("text") or "").lower() for item in front)
    keyword_seen = any(any(token in str(item.get("text") or "").lower() for token in ("keyword", "index term")) for item in front)
    line_numbers = bool(nested(document, "line_numbering.enabled", False)) or any("line number" in str(item.get("text") or "").lower() for item in paragraphs)
    furniture_seen = any(bool(item.get("text_samples") or item.get("rules") or item.get("drawings")) for item in headers)
    appendix_seen = any("appendix" in str(item.get("text") or "").lower() for item in paragraphs)
    reference_seen = any("reference" in str(item.get("text") or "").lower() for item in paragraphs)
    equation_candidates = nested(spec, "equations.latex_candidates", [])
    equation_candidates = equation_candidates if isinstance(equation_candidates, list) else []
    equation_statuses = [
        str(item.get("translation_status") or "not_convertible")
        for item in equation_candidates if isinstance(item, dict)
    ]
    equation_mapped = (
        bool(equations)
        and bool(equation_statuses)
        and all(status == "converted" for status in equation_statuses)
        and package_contains(package_text, "temp2tex-source-equation-candidates")
    )
    equation_reason = (
        "Every observed OMML sample has a conservative LaTeX candidate in equations.tex."
        if equation_mapped else
        "At least one observed OMML sample needs manual translation or the equations.tex candidate was not generated."
    )
    features = [
        record("run_level_format_spans", spans > 0, spans > 0 and any(role_has_visible_spans(spec, path) for path in ("front_matter.title_style", "abstracts.label_style", "abstracts.style", "body.style")), f"{spans} contiguous visible Word run-format span(s)", "template_spec.json role evidence", "Visible spans must be retained before choosing class-level typography.", "critical"),
        record("page_frame", bool(document.get("sections")), package_contains(package_text, "\\geometry{") or bool(nested(spec, "page.margins_mm", {})), "Word section page size, margins, and columns", "journal-template.cls page geometry", "A section frame is structural source evidence."),
        record("line_numbers", line_numbers, bool(nested(spec, "body.line_numbers", False)) and package_contains(package_text, "tempTWOEnableLineNumbers", "\\linenumbers"), "Word section property or visible template instruction", "journal-template.cls \\tempTWOEnableLineNumbers", "Line numbers need both a source decision and an executable class hook.", "critical"),
        record("page_furniture", furniture_seen, bool(nested(spec, "page.header_footer_evidence.parts", [])) and package_contains(package_text, "fancyhdr"), "Active Word header/footer text, rules, fields, or drawings", "journal-template.cls and page-furniture.tex", "Text and rules can map directly; image placement remains render-confirmed."),
        record("title", title_seen, role_has_visible_spans(spec, "front_matter.title_style") and package_contains(package_text, "\\maketitle"), "Visible first-page title candidate and its run formatting", "journal-template.cls \\maketitle", "A title style is insufficient unless it is a direct visible exemplar.", "critical"),
        record("abstract", abstract_seen, role_has_visible_spans(spec, "abstracts.style") and package_contains(package_text, "abstract"), "Visible abstract label/content paragraph(s)", "journal-template.cls abstract environment", "Keep label and content spans separate when they differ."),
        record("keywords", keyword_seen, role_has_visible_spans(spec, "abstracts.keyword_style") or package_contains(package_text, "keyword"), "Visible keyword/index-term paragraph", "journal-template.cls keyword helper", "Retain the original label and local run emphasis."),
        record("headings", bool(headings), bool(nested(spec, "body.heading_styles", {})) and package_contains(package_text, "titlesec"), "Used heading candidates and outline levels", "journal-template.cls heading commands", "Do not map instruction prose or reference entries as headings."),
        record("text_box_format_spans", text_box_spans > 0, text_box_spans > 0 and bool(nested(spec, "assets.text_boxes", [])) and package_contains(package_text, "Optional text-box candidates", "journaltextbox"), f"{text_box_spans} text-box run-format span(s)", "textboxes.tex candidate", "Preserve local text-box typography in an editable candidate. Activate page placement only after render confirmation.", "critical"),
        record("omml_equations", bool(equations), equation_mapped, f"{len(equations)} Word OMML equation sample(s)", "equations.tex candidate", equation_reason, "critical"),
        record("tables", bool(tables), bool(nested(spec, "tables.layout_evidence", {})) and package_contains(package_text, "journaltable"), "Word table grid, merges, width, and nearby caption", "journal-template.cls table helpers", "Table geometry and captions need separate evidence."),
        record("table_cell_format_spans", table_cell_spans > 0, table_cell_spans > 0 and table_cell_replayed, f"{table_cell_spans} selected-table run-format span(s)", "main.tex representative table fixture", table_cell_reason, "critical"),
        record("figures", bool(drawings or captions), bool(nested(spec, "figures.layout_evidence", {})) and package_contains(package_text, "journalfigure"), "Word drawings, dimensions, and nearby caption", "journal-template.cls figure helpers and assets/", "Do not infer float placement from Word anchor state alone."),
        record("notes", bool(document.get("footnote_count") or document.get("endnote_count")), package_contains(package_text, "\\footnote") or bool(nested(spec, "footnotes", {})), "Visible Word footnotes/endnotes", "journal-template.cls note setup", "Separator nodes alone are not source evidence."),
        record("references", reference_seen, bool(nested(spec, "references.style_evidence.source", "")) and package_contains(package_text, "thebibliography"), "Visible reference/instruction evidence", "journal-template.cls bibliography setup and references.bib", "Entry typography and citation backend remain separate decisions."),
        record("appendix", appendix_seen, bool(nested(spec, "appendices.enabled", False)) and package_contains(package_text, "appendix"), "Visible appendix boundary or content", "journal-template.cls appendix helper", "Counter behavior needs a compile check."),
    ]
    ledger_audit = audit_format_ledger(format_ledger, spec, package_text)
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    gaps = sorted((item for item in features if item["status"] == "needs_mapping"), key=lambda item: (order.get(str(item["priority"]), 9), item["feature"]))
    ledger_gaps = ledger_audit.get("priority_gaps", []) if isinstance(ledger_audit, dict) else []
    all_gaps = gaps + ledger_gaps
    return {
        "schema_version": 2,
        "purpose": "Source-visible feature and paragraph/run role coverage before render calibration",
        "source_kind": document.get("kind", "unknown"),
        "package_checked": str(package_dir) if package_dir else None,
        "format_ledger_checked": bool(ledger_audit),
        "summary": {
            "mapped": sum(item["status"] == "mapped" for item in features),
            "needs_mapping": len(all_gaps),
            "not_observable": sum(item["status"] == "not_observable" for item in features),
            "feature_needs_mapping": len(gaps),
            "observed_run_format_spans": spans,
            "observed_text_box_run_format_spans": text_box_spans,
            "observed_table_cell_run_format_spans": table_cell_spans,
            "ledger_roles_mapped": ledger_audit["summary"]["mapped"] if ledger_audit else None,
            "ledger_roles_needing_mapping": ledger_audit["summary"]["needs_mapping"] if ledger_audit else None,
            "ledger_roles_pending_visual_confirmation": ledger_audit["summary"]["pending_visual_confirmation"] if ledger_audit else None,
        },
        "features": features,
        "ledger_role_audit": ledger_audit,
        "priority_gaps": all_gaps,
        "next_action": "Resolve ledger and feature priority gaps from source evidence before tuning PDF spacing." if all_gaps else "Compile and use same-content PDF comparison to verify mapped features.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_inventory")
    parser.add_argument("template_spec")
    parser.add_argument("--package", help="Generated package directory to inspect")
    parser.add_argument("--format-ledger", help="word_format_ledger.json to reconcile role evidence with the spec and package; auto-discovered from --package when available")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    package = Path(args.package).resolve() if args.package else None
    ledger_path = Path(args.format_ledger).resolve() if args.format_ledger else ((package / "word_format_ledger.json") if package and (package / "word_format_ledger.json").is_file() else None)
    ledger = load(ledger_path) if ledger_path and ledger_path.is_file() else None
    report = build_coverage(load(Path(args.source_inventory)), load(Path(args.template_spec)), package, ledger)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
