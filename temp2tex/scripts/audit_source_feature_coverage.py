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
    "front_matter.metadata": {"spec": "front_matter.metadata_style", "tokens": ("\\journalmetadata", "\\journalmetadatalabel")},
    "front_matter.english_title": {"spec": "front_matter.english_title_style", "tokens": ("\\englishtitle{",)},
    "front_matter.english_author": {"spec": "front_matter.english_author_style", "tokens": ("\\englishauthor{",)},
    "front_matter.english_affiliation": {"spec": "front_matter.english_affiliation_style", "tokens": ("\\englishaffiliation{",)},
    "front_matter.english_abstract": {"spec": "front_matter.english_abstract_style", "tokens": ("\\englishabstract{",)},
    "front_matter.english_keywords": {"spec": "front_matter.english_keywords_style", "tokens": ("\\englishkeywords{",)},
    "heading.level0": {"spec": "body.heading_styles.level0", "tokens": ("\\section{",)},
    "heading.level1": {"spec": "body.heading_styles.level1", "tokens": ("\\subsection{",)},
    "heading.level2": {"spec": "body.heading_styles.level2", "tokens": ("\\subsubsection{",)},
    "body.list_system": {"spec": "body.lists", "tokens": ("\\newenvironment{journalitemize}", "\\newenvironment{journalenumerate}")},
    "body.list_item": {"spec": "body.lists", "tokens": ("\\item",)},
    "equation.system": {"spec": "equations", "tokens": ("\\newenvironment{journalequation}",)},
    "equation.instance": {"spec": "equations.latex_candidates", "tokens": ("temp2tex-source-equation-candidates",), "allow_non_dict": True},
    "block.decoration": {"spec": "page.block_decorations", "tokens": ("\\newenvironment{journalblock}",)},
    "body.paragraph": {"spec": "page.source_body_style", "tokens": ("\\setlength{\\parindent}", "\\linespread{")},
    "front_matter.metadata_table": {"spec": "front_matter", "tokens": ("\\maketitle",)},
    "cover.structure": {"spec": "front_matter.cover_evidence", "tokens": ("\\journalcover",)},
    "toc.structure": {"spec": "body.toc_evidence", "tokens": ("\\tableofcontents",)},
    "toc.layout": {"spec": "body.toc_evidence", "tokens": ("\\journaltoctabstops",)},
    "page.frame": {"spec": "page", "tokens": ("\\geometry{",)},
    "page.columns": {"spec": "page", "tokens": ("\\journalstartbodycolumns",)},
    "page.text_grid": {"spec": "page.text_grid_evidence", "tokens": ("\\journaltextgrid",)},
    "page.numbering": {"spec": "page.numbering", "tokens": ("\\journalpagenumbering",)},
    "line.numbering": {"spec": "body.line_number_evidence", "tokens": ("\\journallinenumbering", "line-numbering.tex")},
    "paragraph.tab_stops": {"spec": "body.tab_stop_evidence", "tokens": ("\\journaltabstops",)},
    "paragraph.drop_cap": {"spec": "body.drop_cap_evidence", "tokens": ("\\journaldropcap", "drop-caps.tex")},
    "paragraph.direction": {"spec": "body.paragraph_direction_evidence", "tokens": ("\\journalparagraphdirection",)},
    "paragraph.break_policy": {"spec": "body.paragraph_break_policy_evidence", "tokens": ("\\journalparagraphbreakpolicy",)},
    "run.character_effects": {"spec": "body.character_effect_evidence", "tokens": ("\\journalcharactereffects",)},
    "run.character_styles": {"spec": "body.character_style_evidence", "tokens": ("\\journalcharacterstyle",)},
    "run.script_language": {"spec": "source_annotations.script_language_evidence", "tokens": ("\\journalscriptlanguage",)},
    "document.theme": {"spec": "source_annotations.theme_format_evidence", "tokens": ("\\journalthemeformat",)},
    "word.unmodeled_format": {"spec": "source_annotations.unmodeled_format_properties", "tokens": ("\\journalunmodeledformatproperties",)},
    "footnote.system": {"spec": "footnotes", "tokens": ("\\footnote",)},
    "endnote.system": {"spec": "endnotes", "tokens": ("\\journalendnote",)},
    "references.system": {"spec": "references", "tokens": ("\\begin{thebibliography}",)},
    "appendix.system": {"spec": "appendices", "tokens": ("\\journalappendix",)},
    "table.structure": {"spec": "tables.layout_evidence", "tokens": ("\\journaltablewidthspec", "\\journaltableheaderrow")},
    "table.caption": {"spec": "tables.caption_style", "tokens": ("\\begin{journaltable}", "\\caption{")},
    "figure.placement": {"spec": "figures.layout_evidence", "tokens": ("\\journalfigurewidth", "\\journalfigurerepresentativewidth")},
    "figure.caption": {"spec": "figures.caption_style", "tokens": ("\\begin{journalfigure}", "\\caption{")},
    "references.heading": {"spec": "references.style_evidence", "tokens": ("\\begin{thebibliography}",)},
    "references.entry": {"spec": "references.entry_style", "tokens": ("\\bibitem",)},
    "appendix.heading": {"spec": "appendices", "tokens": ("\\journalappendix",)},
    "running_furniture": {"spec": "page.header_footer_evidence", "tokens": ("fancyhdr",)},
    "footnote.content": {"spec": "footnotes", "tokens": ("\\footnote",)},
    "endnote.content": {"spec": "endnotes", "tokens": ("\\endnote",)},
    "floating_text": {"spec": "assets.text_boxes", "tokens": ("\\journaltextbox",), "allow_non_dict": True},
}

for _metadata_kind in (
    "publication_id",
    "doi",
    "dates",
    "funding",
    "contributor_note",
    "editorial_note",
):
    LEDGER_ROLE_AUDIT[f"front_matter.metadata.{_metadata_kind}"] = {
        "spec": f"front_matter.metadata_style.kind_styles.{_metadata_kind}",
        "tokens": ("\\journalmetadata", f"tempTwoMetadataFormat@{_metadata_kind}"),
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


def role_decision_state(value: Any, *, allow_non_dict: bool = False) -> str:
    """Classify a selected spec value without promoting weak evidence."""
    if allow_non_dict and isinstance(value, list):
        return "candidate" if value else "missing"
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
    for collection, source_scope in (("paragraphs", "body_or_table"), ("ancillary_units", "ancillary")):
        for paragraph in ledger.get(collection, []):
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
                    "source_scope": source_scope,
                    "container": str(paragraph.get("container") or "document_flow"),
                })
    for item in ledger.get("object_evidence", []):
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("evidence_id") or "")
        for candidate in item.get("role_candidates") or []:
            if not isinstance(candidate, dict) or not candidate.get("role"):
                continue
            paragraph_roles.setdefault(str(candidate["role"]), []).append({
                "evidence_id": evidence_id,
                "confidence": candidate.get("confidence", "candidate"),
                "source_scope": "object",
                "kind": item.get("kind"),
                "has_direct_format": bool(item.get("has_direct_format")),
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
        decision = role_decision_state(
            nested(spec, config["spec"], {}),
            allow_non_dict=bool(config.get("allow_non_dict")),
        )
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
        if role == "line.numbering":
            line_sections = nested(spec, "body.line_number_evidence.sections", [])
            missing = sorted({
                key
                for section in line_sections if isinstance(section, dict)
                for key in ("count_by", "start", "distance_twips", "restart")
                if section.get(key) in {None, ""} and key not in (section.get("implicit_defaults") or {})
            }) if isinstance(line_sections, list) else ["section settings"]
            if missing:
                audits.append({
                    "role": role,
                    "status": "needs_mapping",
                    "priority": "critical",
                    "evidence_ids": evidence_ids,
                    "spec_path": config["spec"],
                    "latex_owner": queue.get("owner"),
                    "reason": "Word line-numbering evidence omits explicit " + ", ".join(missing) + "; retain a documented default or source confirmation before mapping the system.",
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
    coverage = ledger.get("coverage")
    coverage = coverage if isinstance(coverage, dict) else {}
    capture_limitations = coverage.get("capture_limitations")
    capture_limitations = capture_limitations if isinstance(capture_limitations, list) else [{
        "area": "ledger_scope",
        "reason": "Ledger has no capture-limitations record. Rebuild it with the current format-ledger script.",
    }]
    capture_complete = (
        ledger.get("schema_version") == "temp2tex.word-format-ledger.v3"
        and bool(coverage.get("all_visible_text_units_captured"))
        and coverage.get("all_observable_object_units_captured") is True
        and not capture_limitations
    )
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
        "source_capture": {
            "complete": capture_complete,
            "limitations": capture_limitations,
            "body_or_table_paragraphs": coverage.get("body_and_table_cell_paragraphs"),
            "ancillary_paragraphs": coverage.get("ancillary_paragraphs"),
            "reason": (
                "The v3 ledger captured declared visible text containers plus observable table and drawing units."
                if capture_complete else
                "Source capture is incomplete or unversioned; do not use this coverage report to authorize visual calibration."
            ),
        },
    }


def build_coverage(
    inventory: dict[str, Any],
    spec: dict[str, Any],
    package_dir: Path | None = None,
    format_ledger: dict[str, Any] | None = None,
    atomic_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = document_from(inventory)
    package_text = ""
    if package_dir:
        for filename in ("journal-template.cls", "main.tex", "textboxes.tex", "textboxes-active.tex", "equations.tex", "page-numbering.tex", "line-numbering.tex", "tab-stops.tex", "drop-caps.tex", "character-effects.tex", "table-geometry.tex", "table-styles.tex"):
            path = package_dir / filename
            if path.is_file():
                package_text += "\n" + path.read_text(encoding="utf-8", errors="replace")
    paragraphs = [item for item in document.get("paragraph_samples", []) if isinstance(item, dict)]
    front = [item for item in document.get("front_matter_candidates", []) if isinstance(item, dict)]
    headings = document.get("heading_candidates", []) or []
    headers = [item for item in document.get("header_footer_parts", []) if isinstance(item, dict)]
    tables = document.get("tables", []) or []
    table_geometry_seen = any(
        isinstance(table, dict) and any(
            bool(table.get(key)) for key in ("indent", "default_cell_margins", "positioning", "overlap", "shading")
        )
        for table in tables
    ) or any(
        isinstance(table, dict) and any(
            isinstance(row, dict) and any(bool(row.get(key)) for key in ("height_twips", "cant_split", "repeat_header", "grid_after", "width_after"))
            for row in (table.get("row_format_samples") or [])
        )
        for table in tables
    )
    table_style_seen = any(isinstance(table, dict) and isinstance(table.get("style_evidence"), dict) for table in tables)
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
    line_number_structural = bool(nested(document, "line_numbering.enabled", False))
    line_numbers = line_number_structural or any("line number" in str(item.get("text") or "").lower() for item in paragraphs)
    line_number_sections = nested(spec, "body.line_number_evidence.sections", [])
    line_number_parameters_complete = bool(line_number_sections) and all(
        isinstance(section, dict)
        and all(
            section.get(key) not in {None, ""} or key in (section.get("implicit_defaults") or {})
            for key in ("count_by", "start", "distance_twips", "restart")
        )
        for section in line_number_sections
    )
    line_number_mapped = (
        bool(nested(spec, "body.line_numbers", False))
        and (not line_number_structural or line_number_parameters_complete)
        and package_contains(package_text, "tempTWOEnableLineNumbers", "\\linenumbers")
        and (
            not line_number_structural
            or package_contains(package_text, "\\journallinenumbering", "line-numbering.tex")
        )
    )
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
    script_language_evidence = document.get("script_language_evidence") if isinstance(document.get("script_language_evidence"), dict) else {}
    script_language_seen = bool(script_language_evidence.get("present"))
    script_language_mapped = script_language_seen and package_contains(package_text, "\\journalscriptlanguage")
    script_language_reason = (
        "A source-role LaTeX language/script interface is present; verify it with a role-matched same-content render before a fidelity claim."
        if script_language_mapped else
        "Word source evidence requires a role-local language, complex-script, or RTL interface. The commented candidate is not an active mapping."
    )
    paragraph_direction_evidence = document.get("paragraph_direction_evidence") if isinstance(document.get("paragraph_direction_evidence"), dict) else {}
    paragraph_direction_seen = bool(paragraph_direction_evidence.get("present"))
    paragraph_direction_mapped = paragraph_direction_seen and package_contains(package_text, "\\journalparagraphdirection")
    paragraph_direction_reason = (
        "A source-role LaTeX paragraph-direction interface is present; verify start/end indents, alignment, and line flow against a same-content render."
        if paragraph_direction_mapped else
        "Word paragraph bidi/text-direction evidence requires a role-local direction interface. A commented candidate is not an active paragraph mapping."
    )
    paragraph_break_policy_evidence = document.get("paragraph_break_policy_evidence") if isinstance(document.get("paragraph_break_policy_evidence"), dict) else {}
    paragraph_break_policy_seen = bool(paragraph_break_policy_evidence.get("present"))
    paragraph_break_policy_mapped = paragraph_break_policy_seen and package_contains(package_text, "\\journalparagraphbreakpolicy")
    paragraph_break_policy_reason = (
        "A source-role LaTeX paragraph break-policy interface is present; verify same-content line breaks and downstream pagination before a fidelity claim."
        if paragraph_break_policy_mapped else
        "Word hyphenation/wrap override requires a role-local break-policy interface. A commented candidate is not an active line-break mapping."
    )
    ledger_audit = audit_format_ledger(format_ledger, spec, package_text)
    source_capture_complete = bool(
        isinstance(ledger_audit, dict)
        and isinstance(ledger_audit.get("source_capture"), dict)
        and ledger_audit["source_capture"].get("complete")
    )
    ledger_fingerprint = format_ledger.get("evidence_fingerprint") if isinstance(format_ledger, dict) else None
    atomic_fingerprint = atomic_audit.get("ledger_fingerprint") if isinstance(atomic_audit, dict) else None
    atomic_fingerprint_matches = bool(ledger_fingerprint and atomic_fingerprint == ledger_fingerprint)
    atomic_audit_complete = bool(
        isinstance(atomic_audit, dict)
        and atomic_audit.get("audit_complete")
        and atomic_fingerprint_matches
    )
    atomic_reason = (
        "Every captured paragraph/run has an explicit disposition in the strict audit for this exact ledger."
        if atomic_audit_complete else
        "The supplied atomic audit belongs to different Word evidence; rerun it for the current ledger."
        if atomic_audit and ledger_fingerprint and atomic_fingerprint and not atomic_fingerprint_matches else
        "The supplied atomic audit matches this Word ledger but still has pending or invalid dispositions; complete it in strict mode before visual calibration."
        if atomic_audit and atomic_fingerprint_matches else
        "The supplied atomic audit has no ledger fingerprint; rebuild the ledger and rerun strict atomic audit before visual calibration."
        if atomic_audit and ledger_fingerprint else
        "Every captured paragraph/run needs an explicit disposition before any PDF micro-calibration; rerun the source-feature audit with --atomic-audit after strict atomic audit."
    )
    features = [
        record(
            "ledger_source_capture",
            bool(format_ledger),
            source_capture_complete,
            "word_format_ledger.json coverage record",
            "word_format_ledger.json",
            "A source ledger must explicitly capture body/table text and ancillary furniture, notes, and text boxes before coverage can authorize visual calibration.",
            "critical",
        ),
        record(
            "atomic_mapping_dispositions",
            bool(format_ledger),
            atomic_audit_complete,
            "atomic_mapping_audit.json strict unit-disposition result",
            "atomic_mapping_decisions.json and atomic_mapping_audit.json",
            atomic_reason,
            "critical",
        ),
        record("run_level_format_spans", spans > 0, spans > 0 and any(role_has_visible_spans(spec, path) for path in ("front_matter.title_style", "abstracts.label_style", "abstracts.style", "body.style")), f"{spans} contiguous visible Word run-format span(s)", "template_spec.json role evidence", "Visible spans must be retained before choosing class-level typography.", "critical"),
        record("run_script_language", script_language_seen, script_language_mapped, "Word visible run/named-style language, complex-script, and RTL evidence", "script-language.tex and journal-template.cls", script_language_reason, "high"),
        record("paragraph_direction", paragraph_direction_seen, paragraph_direction_mapped, "Word visible paragraph/named-style bidi and text-direction evidence", "paragraph-direction.tex and journal-template.cls", paragraph_direction_reason, "high"),
        record("paragraph_break_policy", paragraph_break_policy_seen, paragraph_break_policy_mapped, "Word visible paragraph/named-style automatic-hyphen and word-wrap evidence", "paragraph-break-policy.tex and journal-template.cls", paragraph_break_policy_reason, "high"),
        record("page_frame", bool(document.get("sections")), package_contains(package_text, "\\geometry{") or bool(nested(spec, "page.margins_mm", {})), "Word section page size, margins, and columns", "journal-template.cls page geometry", "A section frame is structural source evidence."),
        record("line_numbers", line_numbers, line_number_mapped, "Word section property or visible template instruction", "journal-template.cls and line-numbering.tex", "Line numbers need an executable class hook; explicit Word section settings also need preserved interval, start, distance, and restart candidates.", "critical"),
        record("page_furniture", furniture_seen, bool(nested(spec, "page.header_footer_evidence.parts", [])) and package_contains(package_text, "fancyhdr"), "Active Word header/footer text, rules, fields, or drawings", "journal-template.cls and page-furniture.tex", "Text and rules can map directly; image placement remains render-confirmed."),
        record("title", title_seen, role_has_visible_spans(spec, "front_matter.title_style") and package_contains(package_text, "\\maketitle"), "Visible first-page title candidate and its run formatting", "journal-template.cls \\maketitle", "A title style is insufficient unless it is a direct visible exemplar.", "critical"),
        record("abstract", abstract_seen, role_has_visible_spans(spec, "abstracts.style") and package_contains(package_text, "abstract"), "Visible abstract label/content paragraph(s)", "journal-template.cls abstract environment", "Keep label and content spans separate when they differ."),
        record("keywords", keyword_seen, role_has_visible_spans(spec, "abstracts.keyword_style") or package_contains(package_text, "keyword"), "Visible keyword/index-term paragraph", "journal-template.cls keyword helper", "Retain the original label and local run emphasis."),
        record("headings", bool(headings), bool(nested(spec, "body.heading_styles", {})) and package_contains(package_text, "titlesec"), "Used heading candidates and outline levels", "journal-template.cls heading commands", "Do not map instruction prose or reference entries as headings."),
        record("text_box_format_spans", text_box_spans > 0, text_box_spans > 0 and bool(nested(spec, "assets.text_boxes", [])) and package_contains(package_text, "Optional text-box candidates", "journaltextbox"), f"{text_box_spans} text-box run-format span(s)", "textboxes.tex candidate", "Preserve local text-box typography in an editable candidate. Activate page placement only after render confirmation.", "critical"),
        record("omml_equations", bool(equations), equation_mapped, f"{len(equations)} Word OMML equation sample(s)", "equations.tex candidate", equation_reason, "critical"),
        record("tables", bool(tables), bool(nested(spec, "tables.layout_evidence", {})) and package_contains(package_text, "journaltable"), "Word table grid, merges, width, and nearby caption", "journal-template.cls table helpers", "Table geometry and captions need separate evidence."),
        record("table_geometry", table_geometry_seen, package_contains(package_text, "Source evidence for the selected Word table's local geometry"), "Word table indentation, cell margins, row pagination, and positioning constraints", "table-geometry.tex candidate", "Keep geometry local to the matching table role; no global tabular padding or float-placement rule is implied.", "critical"),
        record("table_style", table_style_seen, package_contains(package_text, "Source evidence for the selected Word table style"), "Word table-style inheritance and conditional table formatting", "table-styles.tex candidate", "A style name or conditional rule remains table-local evidence until a matching rendered table region confirms the LaTeX implementation.", "critical"),
        record("table_cell_format_spans", table_cell_spans > 0, table_cell_spans > 0 and table_cell_replayed, f"{table_cell_spans} selected-table run-format span(s)", "main.tex representative table fixture", table_cell_reason, "critical"),
        record("figures", bool(drawings or captions), bool(nested(spec, "figures.layout_evidence", {})) and package_contains(package_text, "journalfigure"), "Word drawings, dimensions, and nearby caption", "journal-template.cls figure helpers and assets/", "Do not infer float placement from Word anchor state alone."),
        record("notes", bool(document.get("footnote_count") or document.get("endnote_count")), package_contains(package_text, "\\footnote") or bool(nested(spec, "footnotes", {})), "Visible Word footnotes/endnotes", "journal-template.cls note setup", "Separator nodes alone are not source evidence."),
        record("references", reference_seen, bool(nested(spec, "references.style_evidence.source", "")) and package_contains(package_text, "thebibliography"), "Visible reference/instruction evidence", "journal-template.cls bibliography setup and references.bib", "Entry typography and citation backend remain separate decisions."),
        record("appendix", appendix_seen, bool(nested(spec, "appendices.enabled", False)) and package_contains(package_text, "appendix"), "Visible appendix boundary or content", "journal-template.cls appendix helper", "Counter behavior needs a compile check."),
    ]
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    gaps = sorted((item for item in features if item["status"] == "needs_mapping"), key=lambda item: (order.get(str(item["priority"]), 9), item["feature"]))
    ledger_gaps = ledger_audit.get("priority_gaps", []) if isinstance(ledger_audit, dict) else []
    all_gaps = gaps + ledger_gaps
    return {
        "schema_version": 3,
        "purpose": "Source-visible feature and paragraph/run role coverage before render calibration",
        "source_kind": document.get("kind", "unknown"),
        "package_checked": str(package_dir) if package_dir else None,
        "format_ledger_checked": bool(ledger_audit),
        "atomic_mapping_audit_checked": bool(atomic_audit),
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
            "ledger_source_capture_complete": source_capture_complete if ledger_audit else None,
            "atomic_mapping_audit_complete": atomic_audit_complete if format_ledger else None,
            "atomic_mapping_audit_matches_ledger": atomic_fingerprint_matches if format_ledger else None,
        },
        "features": features,
        "ledger_role_audit": ledger_audit,
        "atomic_mapping_audit": {
            "present": bool(atomic_audit),
            "audit_complete": atomic_audit_complete if format_ledger else None,
            "fidelity_complete": bool(isinstance(atomic_audit, dict) and atomic_audit.get("fidelity_complete")) if format_ledger else None,
            "ledger_fingerprint": ledger_fingerprint,
            "audit_ledger_fingerprint": atomic_fingerprint,
            "ledger_fingerprint_matches": atomic_fingerprint_matches if format_ledger else None,
        },
        "priority_gaps": all_gaps,
        "next_action": "Resolve ledger and feature priority gaps from source evidence before tuning PDF spacing." if all_gaps else "Compile and use same-content PDF comparison to verify mapped features.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_inventory")
    parser.add_argument("template_spec")
    parser.add_argument("--package", help="Generated package directory to inspect")
    parser.add_argument("--format-ledger", help="word_format_ledger.json to reconcile role evidence with the spec and package; auto-discovered from --package when available")
    parser.add_argument("--atomic-audit", help="atomic_mapping_audit.json from the strict unit-disposition audit; auto-discovered from --package when available")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    package = Path(args.package).resolve() if args.package else None
    ledger_path = Path(args.format_ledger).resolve() if args.format_ledger else ((package / "word_format_ledger.json") if package and (package / "word_format_ledger.json").is_file() else None)
    ledger = load(ledger_path) if ledger_path and ledger_path.is_file() else None
    atomic_path = Path(args.atomic_audit).resolve() if args.atomic_audit else ((package / "atomic_mapping_audit.json") if package and (package / "atomic_mapping_audit.json").is_file() else None)
    atomic_audit = load(atomic_path) if atomic_path and atomic_path.is_file() else None
    report = build_coverage(load(Path(args.source_inventory)), load(Path(args.template_spec)), package, ledger, atomic_audit)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
