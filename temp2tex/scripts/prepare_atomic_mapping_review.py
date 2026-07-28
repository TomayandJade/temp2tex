#!/usr/bin/env python3
"""Create a model-facing review queue for Word paragraph/run mapping decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_atomic_mapping import FINAL_STATUSES, is_system_aggregate_evidence_id, load_json, starter


SCHEMA_VERSION = "temp2tex.atomic-mapping-review.v2"

# These are review hints, not automatic decisions. The strict auditor still
# checks that a human/model-selected token exists in the declared file.
ROLE_TOKEN_HINTS: dict[str, list[tuple[str, str]]] = {
    "front_matter.article_type": [("main.tex", r"\articletype"), ("journal-template.cls", r"\newcommand{\articletype}")],
    "front_matter.title": [("main.tex", r"\title"), ("journal-template.cls", r"\maketitle")],
    "front_matter.author": [("main.tex", r"\author")],
    "front_matter.affiliation": [("main.tex", r"\affiliation")],
    "front_matter.metadata": [("main.tex", r"\journalmetadata"), ("journal-template.cls", r"\newcommand{\journalmetadata}")],
    "front_matter.abstract": [("main.tex", r"\begin{abstract}"), ("journal-template.cls", "abstract")],
    "front_matter.keywords": [("main.tex", r"\tempTwoTexKeywords"), ("journal-template.cls", "keyword")],
    "front_matter.english_title": [("main.tex", r"\englishtitle")],
    "front_matter.english_author": [("main.tex", r"\englishauthor")],
    "front_matter.english_affiliation": [("main.tex", r"\englishaffiliation")],
    "front_matter.english_abstract": [("main.tex", r"\englishabstract")],
    "front_matter.english_keywords": [("main.tex", r"\englishkeywords")],
    "heading.level0": [("journal-template.cls", r"\section")],
    "heading.level1": [("journal-template.cls", r"\subsection")],
    "heading.level2": [("journal-template.cls", r"\subsubsection")],
    "heading.level3": [("journal-template.cls", r"\paragraph")],
    "heading.level4": [("journal-template.cls", r"\subparagraph")],
    "body.list_system": [("journal-template.cls", r"\newenvironment{journalitemize}"), ("journal-template.cls", r"\newenvironment{journalenumerate}")],
    "body.list_item": [("main.tex", r"\item"), ("journal-template.cls", r"\item")],
    "equation.system": [("journal-template.cls", r"\newenvironment{journalequation}"), ("journal-template.cls", "equation")],
    "equation.instance": [("equations.tex", "temp2tex-source-equation-candidates"), ("main.tex", r"\begin{journalequation}")],
    "block.decoration": [("journal-template.cls", r"\newenvironment{journalblock}"), ("main.tex", r"\begin{journalblock}")],
    "body.paragraph": [("journal-template.cls", r"\setlength{\parindent}"), ("journal-template.cls", r"\journalbody")],
    "paragraph.layout": [("main.tex", r"\journalblankparagraph"), ("journal-template.cls", r"\newcommand{\journalblankparagraph}")],
    "front_matter.metadata_table": [("journal-template.cls", r"\maketitle")],
    "cover.structure": [("journal-template.cls", r"\journalcover"), ("cover.tex", r"\begin{journalcover}")],
    "toc.structure": [("main.tex", r"\tableofcontents")],
    "toc.layout": [("journal-template.cls", r"\journaltoctabstops"), ("main.tex", r"\tableofcontents")],
    "page.frame": [("journal-template.cls", r"\geometry{")],
    "page.columns": [("journal-template.cls", r"\journalstartbodycolumns"), ("main.tex", r"\journalstartbodycolumns")],
    "page.text_grid": [("text-grid.tex", "Source evidence"), ("journal-template.cls", r"\journaltextgrid")],
    "page.numbering": [("journal-template.cls", r"\journalpagenumbering"), ("page-numbering.tex", r"\journalpagenumbering")],
    "line.numbering": [("journal-template.cls", r"\journallinenumbering"), ("line-numbering.tex", r"\journallinenumbering")],
    "paragraph.tab_stops": [("tab-stops.tex", "Source evidence"), ("journal-template.cls", r"\journaltabstops")],
    "paragraph.drop_cap": [("drop-caps.tex", r"\journaldropcap"), ("journal-template.cls", r"\journaldropcap")],
    "paragraph.direction": [("paragraph-direction.tex", "Source evidence"), ("journal-template.cls", r"\journalparagraphdirection")],
    "paragraph.break_policy": [("paragraph-break-policy.tex", "Source evidence"), ("journal-template.cls", r"\journalparagraphbreakpolicy")],
    "run.character_effects": [("character-effects.tex", "Source evidence"), ("journal-template.cls", r"\journalcharactereffects")],
    "run.character_styles": [("character-styles.tex", "Source evidence"), ("journal-template.cls", r"\journalcharacterstyle")],
    "run.script_language": [("script-language.tex", "Source evidence"), ("journal-template.cls", r"\journalscriptlanguage")],
    "document.theme": [("word-theme.tex", "Theme definition"), ("journal-template.cls", r"\journalthemeformat")],
    "word.unmodeled_format": [("unmodeled-word-properties.json", "properties"), ("journal-template.cls", r"\journalunmodeledformatproperties")],
    "footnote.system": [("journal-template.cls", r"\footnote")],
    "endnote.system": [("journal-template.cls", r"\journalendnote")],
    "references.system": [("journal-template.cls", r"\begin{thebibliography}"), ("main.tex", r"\begin{thebibliography}")],
    "appendix.system": [("journal-template.cls", r"\journalappendix"), ("main.tex", r"\journalappendix")],
    "table.structure": [("journal-template.cls", r"\journaltablewidthspec"), ("journal-template.cls", r"\journaltableheaderrow")],
    "table.cell": [("main.tex", r"\begin{journaltable}"), ("journal-template.cls", r"\journaltableheadercell")],
    "table.caption": [("journal-template.cls", r"\journaltable")],
    "figure.placement": [("journal-template.cls", r"\journalfigurewidth"), ("journal-template.cls", r"\journalfigurerepresentativewidth")],
    "figure.caption": [("journal-template.cls", r"\journalfigure")],
    "references.heading": [("journal-template.cls", "thebibliography")],
    "references.entry": [("journal-template.cls", "thebibliography")],
    "appendix.heading": [("journal-template.cls", r"\journalappendix")],
    "back_matter.declaration": [("journal-template.cls", r"\journaldeclaration")],
    "back_matter.license": [("journal-template.cls", r"\journallicense")],
    "back_matter.author_bio": [("journal-template.cls", r"\journalauthorbio")],
    "running_furniture": [("journal-template.cls", "fancyhdr")],
    "footnote.content": [("journal-template.cls", r"\footnote")],
    "endnote.content": [("journal-template.cls", r"\journalendnote")],
    "floating_text": [("main.tex", r"\journaltextbox"), ("journal-template.cls", r"\journaltextbox")],
}

# Keep the queue aligned with reconstruction dependencies rather than the
# alphabetic spelling of a role. The group key remains the stable identity.
ROLE_PRIORITY = {
    "front_matter.title": 10,
    "front_matter.author": 20,
    "front_matter.affiliation": 30,
    "front_matter.metadata": 35,
    "front_matter.abstract": 40,
    "front_matter.keywords": 50,
    "front_matter.english_title": 60,
    "front_matter.english_author": 70,
    "front_matter.english_affiliation": 80,
    "front_matter.english_abstract": 90,
    "front_matter.english_keywords": 100,
    "front_matter.metadata_table": 105,
    "cover.structure": 108,
    "toc.structure": 115,
    "toc.layout": 116,
    "page.frame": 120,
    "page.columns": 130,
    "page.text_grid": 135,
    "page.numbering": 140,
    "line.numbering": 145,
    "paragraph.tab_stops": 150,
    "paragraph.drop_cap": 155,
    "paragraph.direction": 157,
    "paragraph.break_policy": 158,
    "run.character_effects": 160,
    "run.character_styles": 162,
    "run.script_language": 162,
    "document.theme": 163,
    "word.unmodeled_format": 165,
    "footnote.system": 315,
    "endnote.system": 325,
    "references.system": 500,
    "appendix.system": 520,
    "running_furniture": 110,
    "heading.level0": 200,
    "heading.level1": 210,
    "heading.level2": 220,
    "heading.level3": 230,
    "heading.level4": 240,
    "body.list_system": 280,
    "body.list_item": 290,
    "body.paragraph": 300,
    "paragraph.layout": 305,
    "footnote.content": 310,
    "endnote.content": 320,
    "equation.system": 350,
    "equation.instance": 360,
    "block.decoration": 370,
    "table.caption": 400,
    "table.cell": 405,
    "table.structure": 405,
    "figure.caption": 410,
    "figure.placement": 415,
    "floating_text": 420,
    "references.heading": 500,
    "references.entry": 510,
    "appendix.heading": 520,
    "back_matter.declaration": 530,
    "back_matter.license": 540,
    "back_matter.author_bio": 550,
    "guidance.instruction": 900,
}


def role_priority(roles: list[str]) -> int:
    """Return a stable dependency-aware priority for a review group."""
    if not roles:
        return 800
    return min(ROLE_PRIORITY.get(role, 700) for role in roles)


def package_token_hints(package: Path | None, role: str) -> list[dict[str, Any]]:
    hints = []
    for relative_file, token in ROLE_TOKEN_HINTS.get(role, []):
        present = None
        if package:
            candidate = package / relative_file
            present = candidate.is_file() and token in candidate.read_text(encoding="utf-8", errors="replace")
        hints.append({"latex_file": relative_file, "latex_token": token, "present": present})
    return hints


def object_render_check(decision: dict[str, Any]) -> dict[str, Any] | None:
    """Describe the next source-relative PDF check for one observable object.

    Word XML cannot prove PDF page rectangles or that a phrase remains unique
    after rendering. The record therefore emits source-backed *candidates*,
    not an approved anchor map. The agent must retain only candidates that
    survive the same-content PDF uniqueness check.
    """
    kind = str(decision.get("kind") or "")
    contexts = [item for item in decision.get("context_samples") or [] if isinstance(item, dict)]
    context = contexts[0] if contexts else {}
    relation = context.get("caption_relation") if isinstance(context.get("caption_relation"), dict) else {}
    position = str(relation.get("position") or "unknown")
    confidence = str(relation.get("confidence") or "unknown")
    caption_text = str(relation.get("caption_text") or "").strip()
    confirmed_caption = position in {"above", "below"} and confidence in {"adjacent", "nearby", "confirmed"} and bool(caption_text)

    def source_paragraph_evidence_id(value: object) -> str | None:
        return f"p{value:04d}" if isinstance(value, int) and value >= 0 else None

    def object_evidence_id(prefix: str, ordinal: object, suffix: str) -> str | None:
        if not isinstance(ordinal, int) or ordinal < 1:
            return None
        expected = f"{prefix}{ordinal:03d}.{suffix}"
        return next((str(item) for item in decision.get("evidence_ids") or [] if str(item).endswith(expected)), None)

    def anchor_contract_candidates(prefix: str, anchor_key_prefix: str, ordinal_key: str, suffix: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        candidates = []
        for item in contexts:
            local_relation = item.get("caption_relation") if isinstance(item.get("caption_relation"), dict) else {}
            local_text = str(local_relation.get("caption_text") or "").strip()
            local_position = str(local_relation.get("position") or "unknown")
            local_confidence = str(local_relation.get("confidence") or "unknown")
            ordinal = item.get(ordinal_key)
            evidence_id = object_evidence_id(prefix, ordinal, suffix)
            caption_evidence_id = source_paragraph_evidence_id(local_relation.get("caption_paragraph_index"))
            if not (
                evidence_id
                and local_text
                and local_position in {"above", "below"}
                and local_confidence in {"adjacent", "nearby", "confirmed"}
            ):
                continue
            source_evidence_ids = [evidence_id]
            if caption_evidence_id:
                source_evidence_ids.append(caption_evidence_id)
            candidates.append({
                "key": f"{anchor_key_prefix}_{ordinal}",
                "phrases": [local_text],
                "source_evidence_ids": source_evidence_ids,
                "position": local_position,
                "requires_pdf_uniqueness_check": True,
            })
        phrase_counts: dict[str, int] = {}
        for candidate in candidates:
            phrase = str((candidate.get("phrases") or [""])[0]).strip()
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
        accepted = [
            candidate for candidate in candidates
            if phrase_counts.get(str((candidate.get("phrases") or [""])[0]).strip(), 0) == 1
        ]
        ambiguous = [
            candidate for candidate in candidates
            if phrase_counts.get(str((candidate.get("phrases") or [""])[0]).strip(), 0) > 1
        ]
        return accepted, ambiguous

    figure_candidates, figure_ambiguities = anchor_contract_candidates("figure.d", "figure", "drawing_ordinal", "placement")
    table_candidates, table_ambiguities = anchor_contract_candidates("table.t", "table", "index", "structure")

    if kind == "drawing_placement":
        return {
            "comparison_model": "flow_relative",
            "required_checks": [
                "image frame box width, height, aspect ratio, and source-relative placement",
                "caption presence, above/below order, typography, and object-to-caption/outside spacing",
                "wrap/anchor behavior and the immediately adjacent paragraph flow",
            ],
            "ignore": ["raster image interior pixels"],
            "caption_anchor": caption_text if confirmed_caption else None,
            "caption_status": "source_confirmed" if confirmed_caption else "needs_rendered_context_selection",
            "anchor_contract_candidates": figure_candidates,
            "anchor_contract_ambiguities": figure_ambiguities,
            "contract_instruction": "Choose a unique visible caption or adjacent manuscript phrase from the same-content PDFs. Bind the object/caption relation to that context and require both on the same page. Do not create an absolute page rectangle for an inline body drawing.",
        }
    if kind == "table_structure":
        return {
            "comparison_model": "flow_relative",
            "required_checks": [
                "table width, column grid, merges, rules, cell padding, header style, and row-break behavior",
                "caption presence, above/below order, typography, and table-to-caption/outside spacing",
                "the preceding/following paragraph boundaries recorded in Word flow context",
            ],
            "ignore": [],
            "caption_anchor": caption_text if confirmed_caption else None,
            "caption_status": "source_confirmed" if confirmed_caption else "needs_rendered_context_selection",
            "anchor_contract_candidates": table_candidates,
            "anchor_contract_ambiguities": table_ambiguities,
            "contract_instruction": "Choose a unique visible caption or nearby non-generic manuscript phrase from the same-content PDFs. Compare table/caption flow relative to that context; never mask table text or rules.",
        }
    if kind in {"furniture_placement", "text_box_placement", "vml_placement"}:
        return {
            "comparison_model": "page_fixed",
            "required_checks": [
                "first/default/even page variant, page-relative box position, dimensions, rules, and overlap",
                "visible furniture text and artwork frame geometry",
            ],
            "ignore": ["raster image interior pixels"],
            "caption_anchor": None,
            "caption_status": "not_applicable",
            "contract_instruction": "After rendering the Word reference, bind a unique furniture phrase or artwork frame to the correct page rectangle. Do not let body-flow changes excuse a page-fixed mismatch.",
        }
    if kind in {"page_frame", "page_columns"}:
        return {
            "comparison_model": "full_document",
            "required_checks": [
                "page size, margins, body text box, column count, column width, column gap, and section transition",
            ],
            "ignore": [],
            "caption_anchor": None,
            "caption_status": "not_applicable",
            "contract_instruction": "Use a full same-content contract with multiple body anchors. Do not derive page calibration from an isolated object or first-page zone.",
        }
    return None


def short_text(value: object, limit: int = 260) -> str:
    """Keep local Word context useful without turning a review batch into a transcript."""
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def role_labels(value: object) -> list[str]:
    """Return compact role labels for local Word context cards."""
    return [
        str(item.get("role") or "")
        for item in value if isinstance(item, dict) and str(item.get("role") or "")
    ] if isinstance(value, list) else []


def word_context_index(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Recover local paragraph context omitted by older ledger decisions.

    Mapping decisions intentionally retain only immutable evidence IDs and
    values. The review queue may safely derive read-only neighboring context
    from the same ledger so a model can distinguish an affiliation, instruction
    line, caption, or body paragraph without expanding the source authority.
    """
    index: dict[str, dict[str, Any]] = {}
    for collection in ("paragraphs", "ancillary_units"):
        paragraphs = [item for item in ledger.get(collection) or [] if isinstance(item, dict)]
        for position, paragraph in enumerate(paragraphs):
            evidence_id = str(paragraph.get("evidence_id") or "")
            if not evidence_id:
                continue
            container = str(paragraph.get("container") or "document_flow")
            in_table_cell = bool(paragraph.get("in_table_cell"))
            before = []
            after = []
            for neighbor in reversed(paragraphs[max(0, position - 2):position]):
                if (str(neighbor.get("container") or "document_flow") != container
                        or bool(neighbor.get("in_table_cell")) != in_table_cell):
                    break
                text = short_text(neighbor.get("text"))
                if text:
                    before.append({
                        "evidence_id": str(neighbor.get("evidence_id") or ""),
                        "text": text,
                        "roles": role_labels(neighbor.get("role_candidates")),
                    })
            for neighbor in paragraphs[position + 1:position + 3]:
                if (str(neighbor.get("container") or "document_flow") != container
                        or bool(neighbor.get("in_table_cell")) != in_table_cell):
                    break
                text = short_text(neighbor.get("text"))
                if text:
                    after.append({
                        "evidence_id": str(neighbor.get("evidence_id") or ""),
                        "text": text,
                        "roles": role_labels(neighbor.get("role_candidates")),
                    })
            existing = paragraph.get("context") if isinstance(paragraph.get("context"), dict) else {}
            direct_format = paragraph.get("direct_format") if isinstance(paragraph.get("direct_format"), dict) else {}
            index[evidence_id] = {
                **existing,
                "source_part": collection,
                "paragraph_evidence_id": evidence_id,
                "paragraph_index": paragraph.get("index"),
                "style_id": paragraph.get("style_id"),
                "style_name": paragraph.get("style_name"),
                "in_table_cell": in_table_cell,
                "paragraph_text": short_text(paragraph.get("text"), 420),
                "paragraph_direct_format": direct_format.get("paragraph") or {},
                "preceding_paragraphs": before,
                "following_paragraphs": after,
            }
    return index


def hydrate_context(decision: dict[str, Any], context_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Attach source-local, non-authoritative context to a review decision."""
    contexts = [item for item in decision.get("context_samples") or [] if isinstance(item, dict) and item]
    known = {
        str(item.get("paragraph_evidence_id") or item.get("evidence_id") or "")
        for item in contexts
    }
    for evidence_id in decision.get("evidence_ids") or []:
        parent_id = str(evidence_id).split(".r", 1)[0]
        card = context_index.get(parent_id)
        if card and parent_id not in known:
            contexts.append(card)
            known.add(parent_id)
    return {**decision, "context_samples": contexts[:5]}


def group_record(decision: dict[str, Any], package: Path | None) -> dict[str, Any]:
    candidates = [item for item in decision.get("role_candidates") or [] if isinstance(item, dict)]
    roles = [str(item.get("role") or "") for item in candidates if item.get("role")]
    confidence = sorted({str(item.get("confidence") or "candidate") for item in candidates})
    role_hints = {role: package_token_hints(package, role) for role in roles}
    status = str(decision.get("status") or "pending")
    if status.strip().lower() in FINAL_STATUSES:
        action = (
            "Audit this final disposition against the local Word context, exact direct/object bindings, "
            "and active package token. Reopen it only when that audit finds a source or owner conflict; "
            "do not reclassify it merely because the review queue is regenerated."
        )
    elif not candidates:
        action = "Classify the source unit before mapping it; do not borrow a nearby role."
    elif roles == ["guidance.instruction"]:
        action = "Classify the text as guidance with a specific guidance_kind, or split it if it contains a visible manuscript exemplar."
    elif roles == ["front_matter.metadata"]:
        action = "Keep publication dates, DOI, correspondence notices, classifications, and similar front-matter metadata separate from title/author content. Map to an existing editable metadata interface, or add a dedicated class/main interface before claiming the source unit is mapped."
    elif roles == ["body.list_system"]:
        action = "Map the source list definition before its items: preserve label family, start/restart behavior, levels, left/hanging indentation, and nesting in editable journal list environments. Do not treat a generic itemize wrapper as proof of fidelity."
    elif roles == ["body.list_item"]:
        action = "Map this visible list paragraph to the source-backed journal list interface and retain its level/context. Do not reclassify its number as a heading or absorb it into ordinary body text."
    elif roles == ["paragraph.layout"]:
        action = "Map this empty Word paragraph only as a local layout boundary. Preserve its direct paragraph spacing, indentation, break/tab/anchor context, and immediate neighboring source paragraphs through an editable journalblankparagraph-style helper or an explicit gap. Do not change global body leading or insert arbitrary vspace to conceal it; confirm the local boundary in a same-content render."
    elif roles == ["equation.system"]:
        action = "Map the equation system before formula samples: preserve display versus inline policy, counter/tag format, observed number placement, paragraph alignment, and appendix-counter interaction in an editable class environment. A numbered amsmath fixture alone is not proof of the source rule."
    elif roles == ["equation.instance"]:
        action = "Map this exact OMML structure to its editable equation candidate, or leave an explicit manual-translation/unresolved record. Retain display context, adjacent number sample, and local paragraph formatting; never replace unsupported math with plausible plain text."
    elif roles == ["block.decoration"]:
        action = "Design or select a source-specific editable block interface before mapping this paragraph. Preserve border sides, line style/width/color, shading/fill, padding, frame/anchor behavior, and surrounding spacing. Do not silently replace it with an arbitrary colored box."
    elif roles == ["page.text_grid"]:
        action = "Map Word document-grid behavior separately from ordinary line spacing. Preserve each section's docGrid type, linePitch/charSpace, and any paragraph/style snap-to-grid, auto-spacing, kinsoku, punctuation, or vertical-text override. Do not enable a document-wide LaTeX baseline grid or change CJK spacing without a same-content source render."
    elif roles == ["page.numbering"]:
        action = "Map Word page-number formatting before applying page furniture: preserve the section boundary, format, start/restart value, and any chapter-number component. Use an editable page-numbering helper and do not turn a section override into a document-wide setting without rendered confirmation."
    elif roles == ["line.numbering"]:
        action = "Map Word line-number policy separately from merely enabling lineno: preserve each section's countBy interval, start number, distance from text, and restart semantics. Use the editable class helper plus source-labeled candidates, and do not flatten a new-page/new-section restart into a global running rule without rendered confirmation."
    elif roles == ["paragraph.tab_stops"]:
        action = "Map each visible Word tab layout to its semantic role before writing any LaTeX tab setting. Preserve tab type, position, leader, and local paragraph context. Do not apply a document-wide tab default or reuse TOC settings for author, metadata, body, or header-like layouts."
    elif roles == ["paragraph.drop_cap"]:
        action = "Map Word drop-cap semantics as one visual unit: preserve drop versus margin mode, line count, anchor/wrap properties, first visible letter, and the following body text. Use the editable journaldropcap interface only at the confirmed source boundary; do not enlarge an arbitrary initial merely because a framePr exists."
    elif roles == ["paragraph.direction"]:
        action = "Map paragraph bidi/text-direction only in the source role. Preserve paragraph scope, style/container, direct/effective direction values, alignment, and start/end indent consequences. Do not make the whole document RTL or vertical from one table, footer, or style; require a same-content role-matched render before activating a direction interface."
    elif roles == ["paragraph.break_policy"]:
        action = "Map automatic-hyphen and word-wrap overrides only in their source paragraph role. Preserve scope, style/container, direct/effective policy, and the affected text-flow context. Do not change document-wide TeX hyphenation or wrapping from one style/table/furniture rule; require same-content line-break and pagination confirmation before activation."
    elif roles == ["run.character_effects"]:
        action = "Map each visible character-effect span in its semantic role. Preserve small/all caps, highlight, run shading, text border, kerning threshold, hidden state, character spacing, scale, baseline position, outline/shadow/emboss/imprint separately. Do not replace these with one document-wide visual rule or treat a compiling plain-text fixture as evidence of fidelity."
    elif roles == ["run.character_styles"]:
        action = "Map each visible Word rStyle reference to its semantic role. Preserve the character-style ID, resolved effective font/colour/underline/effect formatting, and local span boundary. Do not replace it with a document-wide font rule, and do not call a named style render-verified until a same-content page confirms its role and geometry."
    elif roles == ["run.script_language"]:
        action = "Map Word language, complex-script bold/italic, complex-script flag, and RTL direction only in their source role. Preserve run scope, container, style boundary, direct/effective values, and raw span provenance. Do not turn repeated language aliases into a global Babel/polyglossia/fontspec or RTL policy; require a role-matched same-content render before enabling any engine, font, direction, or hyphenation rule."
    elif roles == ["document.theme"]:
        action = "Map each used Word theme color/font alias to its semantic role. Preserve the theme alias, tint/shade, raw theme palette/font definition, and local span or style boundary. Do not replace it with a generic Office palette or global LaTeX font selection; render-confirm every applied journal color or font choice."
    elif roles == ["word.unmodeled_format"]:
        action = "Classify every unmodeled OOXML format-property node before claiming fidelity. Decide whether it affects a visible source role, has a documented default, is non-format metadata, or needs an explicit gap. Do not ignore a high-frequency property merely because the generic package compiles."
    elif roles == ["toc.layout"]:
        action = "Map TOC entry geometry separately from enabling the TOC: preserve level indentation, right-tab position, leader pattern, and page-number alignment in an editable class interface. Do not assume the default LaTeX dotted leader matches Word evidence."
    elif len(candidates) == 1 and confidence == ["source"]:
        action = "Confirm the source role and select one existing editable owner/token. Preserve local run formatting unless all role-matched evidence agrees."
    else:
        action = "Resolve the semantic role from the text and local context before selecting any LaTeX owner; split this group if its samples are mixed."
    return {
        "group_key": str(decision.get("group_key") or ""),
        "status": status,
        "evidence_count": len(decision.get("evidence_ids") or []),
        "evidence_ids": decision.get("evidence_ids") or [],
        "scope": str(decision.get("source_scope") or ""),
        "container": str(decision.get("container") or ""),
        "kind": str(decision.get("kind") or ""),
        "roles": roles,
        "role_priority": role_priority(roles),
        "confidence": confidence,
        "role_candidates": candidates,
        "required_format_binding_paths": decision.get("required_format_binding_paths") or [],
        "required_format_binding_values": decision.get("required_format_binding_values") or {},
        "required_object_format_binding_paths": decision.get("required_object_format_binding_paths") or [],
        "required_object_format_binding_values": decision.get("required_object_format_binding_values") or {},
        "text_samples": decision.get("text_samples") or [],
        "context_samples": decision.get("context_samples") or [],
        "latex_token_hints": role_hints,
        "render_check": object_render_check(decision),
        "next_action": action,
    }


def batch_template(report: dict[str, Any]) -> dict[str, Any]:
    """Create a deliberately incomplete, evidence-bound update draft.

    The merger rejects it until the model replaces every pending status with a
    final disposition. It contains no evidence IDs or role candidates, so a
    bounded batch cannot rewrite source evidence.
    """
    updates = []
    for group in report["groups"]:
        if group["status"].strip().lower() in FINAL_STATUSES:
            continue
        updates.append({
            "group_key": group["group_key"],
            "status": "pending",
            "role": "",
            "latex_owner": "",
            "latex_file": "",
            "latex_token": "",
            "format_bindings": [
                {
                    "source_path": path,
                    "source_value": value,
                    "latex_file": "",
                    "latex_token": "",
                    "mapping_reason": "",
                }
                for path, value in sorted((group.get("required_format_binding_values") or {}).items())
            ],
            "object_format_bindings": [
                {
                    "source_path": path,
                    "source_value": value,
                    "latex_file": "",
                    "latex_token": "",
                    "mapping_reason": "",
                }
                for path, value in sorted((group.get("required_object_format_binding_values") or {}).items())
            ],
            "guidance_kind": "",
            "reason": "",
        })
    return {
        "schema_version": "temp2tex.atomic-mapping-batch.v1",
        "ledger_fingerprint": report["ledger_fingerprint"],
        "instructions": "Replace every pending entry in this bounded batch with a final disposition. Use unresolved with a concise reason when a defensible role, owner, or render behavior is not yet known; do not leave a batch pending while seeking a perfect mapping. For a mapped/default group whose review sheet lists direct_format paths, complete every prefilled format_bindings object. For a table, drawing, page-frame, or furniture layout group, also complete every prefilled object_format_bindings object. Each binding keeps its exact source_path and source_value and needs latex_file, an executable latex_token, and a concise mapping_reason. Remove fields that do not apply. Do not add evidence IDs, role candidates, or unknown fields. The guarded merger rejects incomplete entries.",
        "updates": updates,
    }


def markdown_escape(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ").strip()


def review_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Atomic Mapping Review Queue",
        "",
        "This queue organizes Word paragraph/run evidence for model review. It does not approve any mapping automatically.",
        "Choose a final disposition in `atomic_mapping_decisions.json`, then rerun `audit_atomic_mapping.py --strict` against the generated package.",
        "For a bounded batch, first disposition every selected group. `unresolved` is a valid final state with a concise reason when evidence is insufficient; `pending` is not a handoff state.",
        "",
        "## Summary",
        "",
        f"- Decision groups: {summary['decision_groups']}",
        f"- Evidence units: {summary['evidence_units']}",
        f"- Pending groups: {summary['pending_groups']}",
        f"- Finalized groups: {summary['final_groups']}",
        f"- Source-single-role groups: {summary['source_single_role_groups']}",
        f"- Semantic/context review groups: {summary['context_review_groups']}",
        "",
    ]
    selection = report.get("selection")
    if isinstance(selection, dict):
        roles = selection.get("roles") or []
        lines.extend([
            "## Semantic Selection",
            "",
            f"- Requested roles: {', '.join(f'`{role}`' for role in roles) or 'all roles'}",
            f"- Matching groups: {selection['matching_groups']} of {selection['total_decision_groups']} total decision groups",
            "- This is a review-scope filter only. It does not approve a role or omit unmatched source evidence from the ledger.",
            "",
        ])
        if selection.get("pending_only"):
            lines.insert(-1, f"- Pending-only work mode: {selection['matching_groups']} of {selection['matching_before_status_filter']} groups in this scope remain unresolved.")
    batch = report.get("batch")
    if isinstance(batch, dict):
        lines.extend([
            "## Batch Scope",
            "",
            f"- Batch: {batch['index']} of {batch['count']}",
            f"- Stable group range: {batch['start']} to {batch['end']}",
            f"- Groups in this file: {batch['selected_groups']} of {batch['total_groups']} selected groups ({batch['total_all_groups']} in the full queue)",
            "- Apply reviewed updates only with `apply_atomic_mapping_batch.py`; do not edit evidence IDs or candidate roles.",
            "- The companion batch draft contains only pending group keys. Fill a final disposition for every key; use unresolved plus a reason for a real gap, remove inapplicable fields, then merge it through the guarded tool.",
            "",
        ])
    lines.extend([
        "## Review Order",
        "",
        "1. Resolve title, author, affiliation, abstract, keywords, and page furniture before body candidates.",
        "2. Treat caption/table-cell/drawing evidence as its own role; do not flatten it into body text.",
        "3. Classify instruction/example prose as guidance only with a concrete guidance kind and reason.",
        "4. For mapped/default decisions, verify the selected package-local file and token before strict audit.",
        "5. Keep unresolved evidence visible. It blocks a full-fidelity claim and all PDF micro-calibration.",
        "6. For mapped/default groups with direct Word formatting, bind every listed `direct_format` path to a package-local LaTeX token; a generic role token alone is insufficient.",
        "",
        "## Groups",
        "",
        "| Group | Units | Scope | Candidate roles | Confidence | Status |",
        "| --- | ---: | --- | --- | --- | --- |",
    ])
    for group in report["groups"]:
        lines.append(
            f"| `{group['group_key']}` | {group['evidence_count']} | {markdown_escape(group['scope'])}/{markdown_escape(group['kind'])} | "
            f"{markdown_escape(', '.join(group['roles']) or 'unclassified')} | {markdown_escape(', '.join(group['confidence']) or 'unknown')} | {markdown_escape(group['status'])} |"
        )
    for group in report["groups"]:
        lines.extend([
            "",
            f"### `{group['group_key']}`",
            "",
            f"- Evidence: {', '.join(f'`{item}`' for item in group['evidence_ids'])}",
            f"- Container: `{group['scope']}` / `{group['container']}` / `{group['kind']}`",
            f"- Required review: {group['next_action']}",
            "- Samples:",
        ])
        if group["required_format_binding_paths"]:
            values = group["required_format_binding_values"]
            binding_text = ", ".join(
                f"`{path}` = `{json.dumps(values.get(path), ensure_ascii=False)}`"
                for path in group["required_format_binding_paths"]
            )
            lines.append("- Required direct-format bindings: " + binding_text)
        if group["required_object_format_binding_paths"]:
            values = group["required_object_format_binding_values"]
            binding_text = ", ".join(
                f"`{path}` = `{json.dumps(values.get(path), ensure_ascii=False)}`"
                for path in group["required_object_format_binding_paths"]
            )
            lines.append("- Required object-layout bindings: " + binding_text)
        for sample in group["text_samples"][:5]:
            lines.append(f"  - {markdown_escape(str(sample))}")
        contexts = [item for item in group.get("context_samples") or [] if isinstance(item, dict)]
        if contexts:
            lines.append("- Local Word context (read-only):")
            for context in contexts[:3]:
                style = "/".join(str(context.get(key) or "") for key in ("style_id", "style_name") if context.get(key)) or "no named style"
                lines.append(
                    f"  - `{context.get('paragraph_evidence_id') or 'unknown'}` "
                    f"style `{markdown_escape(style)}`, table-cell `{context.get('in_table_cell')}`: "
                    f"{markdown_escape(str(context.get('paragraph_text') or ''))}"
                )
                preceding = context.get("preceding_paragraphs") if isinstance(context.get("preceding_paragraphs"), list) else []
                following = context.get("following_paragraphs") if isinstance(context.get("following_paragraphs"), list) else []
                if preceding:
                    lines.append("    - Before: " + "; ".join(markdown_escape(str(item.get("text") or "")) for item in preceding))
                if following:
                    lines.append("    - After: " + "; ".join(markdown_escape(str(item.get("text") or "")) for item in following))
                direct = context.get("paragraph_direct_format") if isinstance(context.get("paragraph_direct_format"), dict) else {}
                if direct:
                    lines.append("    - Parent paragraph direct format: `" + markdown_escape(json.dumps(direct, ensure_ascii=False, sort_keys=True)) + "`")
        if group["latex_token_hints"]:
            lines.append("- Package evidence candidates (hints only):")
            for role, hints in group["latex_token_hints"].items():
                hint_text = ", ".join(
                    f"`{item['latex_file']}` `{item['latex_token']}` ({'present' if item['present'] else 'missing' if item['present'] is False else 'not checked'})"
                    for item in hints
                ) or "no generic token hint"
                lines.append(f"  - `{role}`: {hint_text}")
        render_check = group.get("render_check")
        if isinstance(render_check, dict):
            lines.append(f"- Render model: `{render_check['comparison_model']}`")
            lines.append("- Render checks: " + "; ".join(render_check["required_checks"]))
            if render_check.get("ignore"):
                lines.append("- Ignore in visual metric: " + "; ".join(render_check["ignore"]))
            if render_check.get("caption_anchor"):
                lines.append(f"- Source-confirmed caption anchor: `{render_check['caption_anchor']}`")
            else:
                lines.append(f"- Caption anchor status: `{render_check['caption_status']}`")
            for candidate in render_check.get("anchor_contract_candidates") or []:
                if not isinstance(candidate, dict):
                    continue
                lines.append(
                    "- Candidate object anchor: `"
                    + str(candidate.get("key") or "")
                    + "` -> phrases `"
                    + "; ".join(str(value) for value in candidate.get("phrases") or [])
                    + "`; source evidence `"
                    + ", ".join(str(value) for value in candidate.get("source_evidence_ids") or [])
                    + "`. Confirm uniqueness in both PDFs before adding it to the anchor contract."
                )
            ambiguities = [candidate for candidate in render_check.get("anchor_contract_ambiguities") or [] if isinstance(candidate, dict)]
            if ambiguities:
                lines.append(
                    "- Do not auto-create anchors for these source-ambiguous object/caption relations: `"
                    + ", ".join(str(candidate.get("key") or "") for candidate in ambiguities)
                    + "`. The same caption phrase attaches to multiple source objects; select a unique rendered context or leave the relation unresolved."
                )
            lines.append(f"- Contract instruction: {render_check['contract_instruction']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("format_ledger", help="word_format_ledger.json")
    parser.add_argument("--decisions", help="atomic_mapping_decisions.json; defaults to a generated starter")
    parser.add_argument("--package", help="Generated LaTeX package for non-binding token hints")
    parser.add_argument("--output", required=True, help="Output atomic_mapping_review.md")
    parser.add_argument("--json-output", help="Optional machine-readable review report")
    parser.add_argument("--batch-template-output", help="Optional evidence-bound JSON update draft for the selected batch")
    parser.add_argument(
        "--roles",
        help="Comma-separated source-backed role names to review as one semantic work slice; batching, if requested, applies after this filter",
    )
    parser.add_argument(
        "--evidence-ids",
        help="Comma-separated exact Word evidence IDs to review; combine with --roles only when every selected group must satisfy both filters",
    )
    parser.add_argument(
        "--pending-only",
        action="store_true",
        help="Expose only non-final groups for an active mapping batch; omit to audit final dispositions as well",
    )
    parser.add_argument("--batch-size", type=int, help="Stable number of decision groups to expose per review batch")
    parser.add_argument("--batch-index", type=int, default=1, help="One-based batch index when --batch-size is set")
    args = parser.parse_args()

    ledger = load_json(Path(args.format_ledger))
    decisions = load_json(Path(args.decisions)) if args.decisions else starter(ledger)
    raw_groups = decisions.get("decisions") if isinstance(decisions, dict) else None
    if not isinstance(raw_groups, list):
        raise SystemExit("Decision file must contain a decisions list")
    package = Path(args.package).resolve() if args.package else None
    context_index = word_context_index(ledger)
    all_groups = [
        group_record(hydrate_context(item, context_index), package)
        for item in raw_groups
        if isinstance(item, dict)
        # Legacy decision files can retain aggregate groups created before the
        # child-level system queue existed. They are audited only through
        # system_format_triage.json and must not re-enter a normal mapping batch.
        and not (
            isinstance(item.get("evidence_ids"), list)
            and item.get("evidence_ids")
            and all(is_system_aggregate_evidence_id(str(evidence_id or "")) for evidence_id in item.get("evidence_ids"))
        )
    ]
    all_groups.sort(key=lambda item: (
        0 if item["roles"] and item["confidence"] == ["source"] else 1,
        item["role_priority"],
        item["group_key"],
    ))
    selected_groups = all_groups
    selection = None
    if args.roles:
        requested_roles = sorted({role.strip() for role in args.roles.split(",") if role.strip()})
        if not requested_roles:
            raise SystemExit("--roles must contain at least one non-empty role name")
        requested_role_set = set(requested_roles)
        selected_groups = [
            item for item in all_groups
            if requested_role_set.intersection(item["roles"])
        ]
        if not selected_groups:
            available_roles = sorted({role for item in all_groups for role in item["roles"]})
            available_text = ", ".join(available_roles) or "none"
            raise SystemExit(
                "No decision groups match --roles. Available roles in this ledger: "
                f"{available_text}"
            )
        selection = {
            "roles": requested_roles,
            "matching_groups": len(selected_groups),
            "total_decision_groups": len(all_groups),
        }

    if args.evidence_ids:
        requested_evidence_ids = sorted({item.strip() for item in args.evidence_ids.split(",") if item.strip()})
        if not requested_evidence_ids:
            raise SystemExit("--evidence-ids must contain at least one non-empty evidence ID")
        requested_evidence_id_set = set(requested_evidence_ids)
        selected_groups = [
            item for item in selected_groups
            if requested_evidence_id_set.intersection(str(evidence_id) for evidence_id in item["evidence_ids"])
        ]
        if not selected_groups:
            raise SystemExit("No decision groups match --evidence-ids. Recheck the current ledger/audit fingerprint and exact source evidence IDs.")
        if selection is None:
            selection = {
                "roles": [],
                "matching_groups": len(selected_groups),
                "total_decision_groups": len(all_groups),
            }
        selection["evidence_ids"] = requested_evidence_ids
        selection["matching_groups"] = len(selected_groups)

    if args.pending_only:
        groups_before_status_filter = len(selected_groups)
        selected_groups = [
            item for item in selected_groups
            if item["status"].strip().lower() not in FINAL_STATUSES
        ]
        if not selected_groups:
            raise SystemExit(
                "No pending decision groups match this scope. Omit --pending-only to audit final "
                "dispositions, or select a role with pending source evidence."
            )
        if selection is None:
            selection = {
                "roles": [],
                "matching_groups": len(selected_groups),
                "total_decision_groups": len(all_groups),
            }
        selection.update({
            "pending_only": True,
            "matching_before_status_filter": groups_before_status_filter,
            "matching_groups": len(selected_groups),
        })

    groups = selected_groups
    batch = None
    if args.batch_size is not None:
        if args.batch_size <= 0:
            raise SystemExit("--batch-size must be positive")
        batch_count = max(1, (len(selected_groups) + args.batch_size - 1) // args.batch_size)
        if args.batch_index < 1 or args.batch_index > batch_count:
            raise SystemExit(f"--batch-index must be between 1 and {batch_count}")
        start = (args.batch_index - 1) * args.batch_size
        end = min(start + args.batch_size, len(selected_groups))
        groups = selected_groups[start:end]
        batch = {
            "index": args.batch_index,
            "count": batch_count,
            "start": start + 1,
            "end": end,
            "selected_groups": len(groups),
            "total_groups": len(selected_groups),
            "total_all_groups": len(all_groups),
        }
    report = {
        "schema_version": SCHEMA_VERSION,
        "ledger_fingerprint": ledger.get("evidence_fingerprint"),
        "package_checked": str(package) if package else None,
        "summary": {
            "decision_groups": len(groups),
            "total_decision_groups": len(all_groups),
            "evidence_units": sum(item["evidence_count"] for item in groups),
            "pending_groups": sum(item["status"] == "pending" for item in groups),
            "final_groups": sum(item["status"].strip().lower() in FINAL_STATUSES for item in groups),
            "source_single_role_groups": sum(bool(item["roles"]) and item["confidence"] == ["source"] for item in groups),
            "context_review_groups": sum(not item["roles"] or item["confidence"] != ["source"] for item in groups),
        },
        "groups": groups,
    }
    if batch:
        report["batch"] = batch
    if selection:
        report["selection"] = selection
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(review_markdown(report), encoding="utf-8")
    if args.json_output:
        json_output = Path(args.json_output)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.batch_template_output:
        template_output = Path(args.batch_template_output)
        template_output.parent.mkdir(parents=True, exist_ok=True)
        template_output.write_text(json.dumps(batch_template(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
