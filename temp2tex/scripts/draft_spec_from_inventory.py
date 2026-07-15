#!/usr/bin/env python3
"""Draft template_spec.json from source_inventory.json and optional official notes."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
import re
from pathlib import Path


KNOWN_SECTION_TITLES = {
    "abstract",
    "introduction",
    "materials and methods",
    "methods",
    "methodology",
    "results",
    "discussion",
    "conclusions",
    "conclusion",
    "acknowledgements",
    "acknowledgments",
    "references",
    "author statement",
}


def read_text(path: Path | None) -> str:
    if not path:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def first_docx(inventory: dict) -> dict | None:
    word_suffixes = {".docx", ".docm", ".dotx", ".dotm", ".doc", ".dot", ".rtf"}
    for item in inventory.get("files", []):
        inspection = item.get("inspection", {})
        kind = str(inspection.get("kind") or "").lower()
        has_structure = bool(
            inspection.get("paragraph_samples")
            or inspection.get("sections")
            or inspection.get("styles")
        )
        if item.get("suffix") in word_suffixes and (
            kind == "docx" or (kind in {"doc", "dot", "rtf"} and has_structure)
        ):
            return item
    return None


def inaccessible_word_fallbacks(inventory: dict, inventory_path: Path) -> list[dict]:
    """Expose declared Word files that could not supply structural evidence."""
    fallbacks = []
    word_suffixes = {".docx", ".docm", ".dotx", ".dotm", ".doc", ".dot", ".rtf"}
    for item in inventory.get("files", []):
        if item.get("suffix") not in word_suffixes:
            continue
        inspection = item.get("inspection", {}) if isinstance(item.get("inspection"), dict) else {}
        kind = str(inspection.get("kind") or "").lower()
        error = item.get("inspection_error") or inspection.get("error")
        conversion = inspection.get("conversion") if isinstance(inspection.get("conversion"), dict) else {}
        converted_structure = bool(
            inspection.get("paragraph_samples")
            or inspection.get("sections")
            or inspection.get("styles")
        )
        unavailable = kind == "invalid-word" or bool(error) or (
            kind in {"doc", "dot", "rtf"}
            and not converted_structure
            and conversion.get("ok") is False
        )
        if not unavailable:
            continue
        reason = str(error or conversion.get("error") or "Word structure could not be inspected.")
        fallbacks.append({
            "area": "source.word_payload",
            "missing_requirement": f"Word source `{item.get('name', 'unknown')}` supplied no usable structural evidence: {reason}",
            "fallback_used": "Use accessible official web/PDF evidence and documented language defaults; do not claim Word-only formatting was reproduced.",
            "source_checked": str(item.get("path") or inventory_path),
            "latex_location": "template_spec.json / format_gap_log.md",
        })
    return fallbacks


def twips_to_mm(value: str | None, default: float) -> float:
    try:
        return round(int(value) * 25.4 / 1440, 2)
    except Exception:
        return default


def collect_docx_text(docx_item: dict | None) -> str:
    if not docx_item:
        return ""
    inspection = docx_item.get("inspection", {})
    parts = []
    for key in ["paragraph_samples", "heading_candidates", "front_matter_candidates"]:
        for para in inspection.get(key, []):
            parts.append(str(para.get("text", "")))
    for table in inspection.get("tables", []):
        parts.extend(str(cell) for cell in table.get("sample_cells", []))
    for text_box in inspection.get("text_boxes", []):
        parts.append(str(text_box.get("text", "")))
    return "\n".join(parts)


def representative_section(docx_item: dict | None, columns: str | None = None) -> dict | None:
    """Select the repeated manuscript-body frame rather than blindly using page one."""
    if not docx_item:
        return None
    sections = docx_item.get("inspection", {}).get("sections", [])
    sections = [section for section in sections if isinstance(section, dict)]
    if not sections:
        return None
    candidates = sections
    if columns == "double":
        double_sections = [section for section in sections if (twips_int(section.get("columns")) or 1) >= 2]
        if double_sections:
            candidates = double_sections

    def signature(section: dict) -> tuple:
        margins = section.get("margins_twips", {}) if isinstance(section.get("margins_twips"), dict) else {}
        return (
            section.get("page_width_twips"), section.get("page_height_twips"),
            margins.get("top"), margins.get("right"), margins.get("bottom"), margins.get("left"),
            section.get("header_distance_twips"), section.get("footer_distance_twips"),
            section.get("gutter_twips"), section.get("columns"), section.get("column_space_twips"),
        )

    counts = Counter(signature(section) for section in candidates)
    best_count = max(counts.values())
    # A later repeated section usually represents manuscript body geometry when
    # Word reserves section one for a title or cover page.
    for section in reversed(candidates):
        if counts[signature(section)] == best_count:
            return section
    return candidates[-1]


def infer_margins(docx_item: dict | None, columns: str | None = None) -> dict:
    default = {"top": 25, "right": 25, "bottom": 25, "left": 25}
    if not docx_item:
        return default
    section = representative_section(docx_item, columns)
    if not section:
        return default
    margins = section.get("margins_twips", {})
    return {
        "top": twips_to_mm(margins.get("top"), 25),
        "right": twips_to_mm(margins.get("right"), 25),
        "bottom": twips_to_mm(margins.get("bottom"), 25),
        "left": twips_to_mm(margins.get("left"), 25),
    }


def infer_page_frame(docx_item: dict | None, columns: str | None = None) -> dict:
    """Keep section-level Word geometry distinct from paragraph formatting."""
    default = {
        "header_distance_mm": None,
        "footer_distance_mm": None,
        "gutter_mm": None,
        "mirror_margins": False,
    }
    if not docx_item:
        return default
    section = representative_section(docx_item, columns)
    if not section:
        return default
    return {
        "header_distance_mm": twips_to_mm(section.get("header_distance_twips"), None),
        "footer_distance_mm": twips_to_mm(section.get("footer_distance_twips"), None),
        "gutter_mm": twips_to_mm(section.get("gutter_twips"), None),
        "mirror_margins": bool(section.get("mirror_margins", False)),
    }


def infer_column_sep_mm(docx_item: dict | None, columns: str) -> float | None:
    if columns != "double" or not docx_item:
        return None
    section = representative_section(docx_item, columns)
    if not section:
        return 6
    space = twips_int(section.get("column_space_twips"))
    return twips_to_mm(space, 6) if space else 6


def twips_int(value) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def infer_paper(docx_item: dict | None, columns: str | None = None) -> str:
    if not docx_item:
        return "a4paper"
    section = representative_section(docx_item, columns)
    if not section:
        return "a4paper"
    width = twips_int(section.get("page_width_twips"))
    height = twips_int(section.get("page_height_twips"))
    if not width or not height:
        return "a4paper"
    pair = sorted([width, height])
    if abs(pair[0] - 12240) <= 120 and abs(pair[1] - 15840) <= 120:
        return "letterpaper"
    if abs(pair[0] - 11906) <= 160 and abs(pair[1] - 16838) <= 160:
        return "a4paper"
    return "custom" if width and height else "a4paper"


def infer_paper_dimensions_mm(docx_item: dict | None, columns: str | None = None) -> dict | None:
    """Preserve Word page dimensions for journal trim sizes outside A4/Letter."""
    if not docx_item or infer_paper(docx_item, columns) != "custom":
        return None
    section = representative_section(docx_item, columns)
    if not section:
        return None
    width = twips_int(section.get("page_width_twips"))
    height = twips_int(section.get("page_height_twips"))
    if not width or not height:
        return None
    return {
        "width_mm": round(width * 25.4 / 1440, 2),
        "height_mm": round(height * 25.4 / 1440, 2),
        "source": "official Word section page dimensions",
    }


def infer_columns(docx_item: dict | None, evidence: str) -> str:
    # The actual Word section is stronger evidence than a publisher page that
    # can mention historical or alternative templates in the same prose.
    if docx_item:
        sections = docx_item.get("inspection", {}).get("sections", [])
        for section in sections:
            columns = twips_int(section.get("columns"))
            if columns and columns >= 2:
                return "double"
        # An explicit section with omitted w:cols is Word's one-column default.
        if sections:
            return "single"
    # Use text only when there is no usable section geometry, and only for a
    # directive about the active manuscript rather than a historical option.
    current_two_column = re.search(
        r"\b(?:use|prepare|format|submit|manuscript)\b[^.]{0,90}\b(?:two|2|double)[ -]?column",
        evidence,
        flags=re.I,
    )
    if current_two_column:
        return "double"
    return "single"


def body_column_transition(docx_item: dict | None, columns: str) -> bool:
    """Detect a single-column title section followed by double-column body text."""
    if columns != "double" or not docx_item:
        return False
    sections = docx_item.get("inspection", {}).get("sections", [])
    if not sections:
        return False
    # In Word section properties, an omitted w:cols means the one-column
    # default.  A first omitted value followed by an explicit double-column
    # body section is therefore positive transition evidence, not an unknown
    # value.  Do not infer a transition unless the selected body section is
    # genuinely later; a one-section template remains whatever its section
    # declares.
    first_columns = twips_int(sections[0].get("columns")) or 1
    body = representative_section(docx_item, columns)
    body_columns = twips_int(body.get("columns")) if body else None
    body_index = twips_int(body.get("index")) if body else None
    first_index = twips_int(sections[0].get("index"))
    return (
        len(sections) > 1
        and first_columns == 1
        and (body_columns or 1) >= 2
        and body_index is not None
        and first_index is not None
        and body_index > first_index
    )


def section_flow_evidence(docx_item: dict | None) -> dict:
    """Preserve every Word section frame and break mode for later decisions."""
    sections = [] if not docx_item else docx_item.get("inspection", {}).get("sections", [])
    if not isinstance(sections, list):
        sections = []
    selected = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        selected.append({
            key: section.get(key)
            for key in (
                "index", "section_break_type", "page_width_twips", "page_height_twips",
                "orientation", "margins_twips", "columns", "column_space_twips",
                "columns_equal_width", "column_widths_twips", "different_first_page",
            )
            if section.get(key) is not None
        })
    return {
        "source": "official Word section properties",
        "sections": selected,
        "requires_manual_boundary_review": len(selected) > 1,
    }


def column_break_evidence(docx_item: dict | None) -> dict:
    """Preserve paragraph-level column breaks instead of flattening them."""
    paragraphs = [] if not docx_item else docx_item.get("inspection", {}).get("paragraph_samples", [])
    selected = []
    for paragraph in paragraphs if isinstance(paragraphs, list) else []:
        breaks = paragraph.get("break_types") if isinstance(paragraph, dict) else None
        if not isinstance(breaks, list) or "column" not in breaks:
            continue
        selected.append({
            "index": paragraph.get("index"),
            "style_name": paragraph.get("style_name"),
            "text": str(paragraph.get("text") or "")[:220],
            "break_types": breaks,
        })
    return {
        "source": "official Word paragraph break elements",
        "paragraphs": selected,
        "requires_manual_boundary_review": bool(selected),
    }


def representative_column_widths(docx_item: dict | None, columns: str | None) -> tuple[list, object]:
    """Keep inherited w:col widths when a later section omits child widths."""
    if not docx_item:
        return [], None
    sections = docx_item.get("inspection", {}).get("sections", [])
    candidates = [item for item in sections if isinstance(item, dict)]
    if columns == "double":
        double = [item for item in candidates if twips_int(item.get("columns")) and twips_int(item.get("columns")) >= 2]
        if double:
            candidates = double
    for item in candidates:
        widths = item.get("column_widths_twips")
        if isinstance(widths, list) and len(widths) >= 2:
            return widths, item.get("columns_equal_width")
    return [], None


def author_layout_evidence(author_style: dict) -> str:
    if not isinstance(author_style, dict):
        return "tabular"
    samples = [
        str(text).strip()
        for text in author_style.get("sample_texts", [])
        if str(text).strip()
    ]
    if not samples and str(author_style.get("sample_text") or "").strip():
        samples = [str(author_style.get("sample_text") or "").strip()]
    if author_style.get("sample_in_table_cells"):
        return "tabular"
    if len(samples) > 1:
        return "tabular"
    sample = samples[0] if samples else ""
    if sample and "\n" not in sample:
        return "inline"
    return "tabular"


def table_cell_body_candidates(paragraphs: list[dict]) -> list[dict]:
    """Admit genuine body-in-layout-table samples only as a guarded fallback."""
    excluded_style_terms = (
        "caption", "table", "figure", "footnote", "header", "footer",
        "title", "author", "abstract", "keyword", "instruction", "note",
    )
    excluded_text_prefixes = (
        "abstract", "keywords", "keyword", "references", "reference",
        "bibliography", "table ", "figure ", "fig. ", "instruction",
        "insert ", "replace ", "author ", "do not ", "note:",
    )
    candidates = []
    for paragraph in paragraphs:
        if not paragraph.get("in_table_cell") or paragraph.get("list_evidence"):
            continue
        text = str(paragraph.get("text") or "").strip()
        style_name = str(paragraph.get("style_name") or "").lower().replace("_", " ")
        if len(text) < 80 or any(term in style_name for term in excluded_style_terms):
            continue
        lowered = text.lower()
        if lowered.startswith(excluded_text_prefixes) or "instruction" in lowered:
            continue
        if " should " in f" {lowered} " and len(text) < 220:
            continue
        effective = paragraph.get("effective_format") or paragraph.get("direct_format") or {}
        if not (effective.get("font") or {}).get("size_half_points"):
            continue
        candidates.append(paragraph)
    return candidates


def reference_style_evidence(docx_item: dict | None, text_evidence: str) -> dict:
    """Prefer visible Word reference labels over generic publisher defaults."""
    paragraphs = [] if not docx_item else docx_item.get("inspection", {}).get("paragraph_samples", [])
    reference_samples = []
    seen_references = False
    for paragraph in paragraphs:
        text = str(paragraph.get("text") or "").strip()
        style_name = str(paragraph.get("style_name") or "").lower()
        if text.lower() in {"references", "reference", "bibliography", "参考文献"}:
            seen_references = True
            continue
        if seen_references or any(marker in style_name for marker in ("reference", "bibliograph", "citation")):
            if text:
                reference_samples.append(text)
    # Require a real label boundary. A value such as `349.23` in a table or
    # example must not be mistaken for a numbered bibliography entry.
    numeric_pattern = re.compile(r"^\s*(?:\[[1-9]\d{0,2}\]|[1-9]\d{0,2}[.)])(?=\s|[A-Z])")
    numeric_sample = next((item for item in reference_samples if numeric_pattern.match(item)), None)
    if numeric_sample:
        return {
            "style": "numeric",
            "source": "visible numbered Word reference entry",
            "sample": numeric_sample[:220],
            "confidence": "official-template",
        }
    # A parenthesized publication year directly after a surname-led entry is
    # stronger evidence for author-year citations than a generic reference
    # style name. Keep this deliberately narrow: unnumbered Vancouver-like
    # lists often contain bare years but not this author-date structure.
    author_year_pattern = re.compile(
        r"^\s*[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)?(?:\s*(?:,|&|and)\s*[A-Z][A-Za-z'\-]+)*.{0,100}\((?:18|19|20)\d{2}[a-z]?\)"
    )
    author_year_samples = [item for item in reference_samples if author_year_pattern.match(item)]
    if author_year_samples:
        return {
            "style": "author-year",
            "source": "visible surname-and-parenthesized-year Word reference entry",
            "sample": author_year_samples[0][:220],
            "confidence": "official-template",
        }
    if contains(text_evidence, "author-date", "author year", "author's surname", "surname and year"):
        return {
            "style": "author-year",
            "source": "official guide/template wording",
            "confidence": "official-guidance",
        }
    return {
        "style": "numeric",
        "source": "documented Temp2TeX default; no visible citation-system evidence",
        "confidence": "default",
    }


def header_footer_evidence(docx_item: dict | None) -> dict:
    parts = [] if not docx_item else docx_item.get("inspection", {}).get("header_footer_parts", [])
    sections = [] if not docx_item else docx_item.get("inspection", {}).get("sections", [])
    headers = [part for part in parts if part.get("kind") == "header"]
    footers = [part for part in parts if part.get("kind") == "footer"]
    by_part = {str(part.get("part")): part for part in parts}
    active_variants = []
    for section in sections:
        for kind, key in (("header", "header_references"), ("footer", "footer_references")):
            for reference in section.get(key, []):
                part = by_part.get(str(reference.get("part")))
                if part:
                    active_variants.append({
                        "section_index": section.get("index"),
                        "kind": kind,
                        "variant": reference.get("type", "default"),
                        "part": reference.get("part"),
                        "paragraphs": part.get("paragraphs", []),
                    })
    return {
        "parts": parts,
        "sections": sections,
        "has_header": bool(headers),
        "has_footer": bool(footers),
        "active_variants": active_variants,
        "source": "official Word header/footer XML parts",
        "confidence": "official-template" if parts else "no-source-evidence",
    }


def text_only_furniture_parts(furniture: dict) -> list[str]:
    """List active header/footer parts that contain deterministic text fields."""
    if not isinstance(furniture, dict):
        return []
    parts = furniture.get("parts")
    active = furniture.get("active_variants")
    if not isinstance(parts, list) or not isinstance(active, list) or not active:
        return []
    later = [
        item for item in active
        if isinstance(item, dict) and item.get("variant") != "first"
    ]
    selected_active = later or active
    referenced = {item.get("part") for item in selected_active if isinstance(item, dict)}
    safe_parts = set()
    for part in [
        part for part in parts
        if isinstance(part, dict) and part.get("part") in referenced
    ]:
        if (
            part.get("drawings")
            or part.get("embedded_relationship_ids")
            or part.get("text_boxes")
        ):
            continue
        if any(
            isinstance(paragraph, dict) and paragraph.get("tokens")
            for paragraph in (part.get("paragraphs") or [])
        ):
            safe_parts.add(str(part.get("part")))
    return sorted(safe_parts)


def text_only_furniture_evidence(furniture: dict) -> bool:
    return bool(text_only_furniture_parts(furniture))


def table_layout_evidence(docx_item: dict | None) -> dict:
    if not docx_item:
        return {}
    tables = docx_item.get("inspection", {}).get("tables", [])
    if not isinstance(tables, list) or not tables:
        return {}
    def relation_score(item: dict) -> int:
        relation = item.get("caption_relation", {})
        if not isinstance(relation, dict) or relation.get("position") not in {"above", "below"}:
            return 0
        confidence = {"adjacent": 2, "nearby": 1}.get(str(relation.get("confidence") or ""), 0)
        visible = 2 if relation.get("classification_source") == "visible label" else 0
        return confidence + visible

    def table_score(item: dict) -> tuple[int, int, int, int]:
        header_features = sum(
            bool(item.get(key))
            for key in (
                "repeat_header",
                "header_fill",
                "header_alignment",
                "header_vertical_alignment",
                "header_bold",
                "header_row_height_twips",
            )
        )
        area = int(item.get("rows") or 0) * int(item.get("max_columns") or 0)
        return relation_score(item), header_features, area, int(item.get("rows") or 0)

    # A small, visibly formatted template table is more useful than a large
    # unformatted data grid when reconstructing the journal's table contract.
    selected = max(tables, key=table_score)
    return {
        "source": "official Word table XML",
        "sample_index": selected.get("index"),
        "first_paragraph_index": selected.get("first_paragraph_index"),
        "last_paragraph_index": selected.get("last_paragraph_index"),
        "rows": selected.get("rows"),
        "max_columns": selected.get("max_columns"),
        "width_twips": selected.get("width_twips"),
        "width_type": selected.get("width_type"),
        "alignment": selected.get("alignment"),
        "layout": selected.get("layout"),
        "style_id": selected.get("style_id"),
        "grid_column_widths_twips": selected.get("grid_column_widths_twips", []),
        "has_merged_cells": bool(selected.get("has_merged_cells")),
        "border_profile": selected.get("border_profile", "unknown"),
        "active_borders": selected.get("active_borders", []),
        "repeat_header": bool(selected.get("repeat_header")),
        "header_fill": selected.get("header_fill"),
        "header_alignment": selected.get("header_alignment"),
        "header_vertical_alignment": selected.get("header_vertical_alignment"),
        "header_bold": bool(selected.get("header_bold")),
        "header_bold_consensus": bool(selected.get("header_bold_consensus")),
        "header_effective_font": selected.get("header_effective_font", {}),
        "header_font_consensus": bool(selected.get("header_font_consensus")),
        "header_cell_samples": selected.get("header_cell_samples", []),
        "cell_format_samples": selected.get("cell_format_samples", []),
        "cell_format_samples_truncated": bool(selected.get("cell_format_samples_truncated")),
        "header_row_height_twips": selected.get("header_row_height_twips"),
        "header_row_height_rule": selected.get("header_row_height_rule"),
        "caption_relation": selected.get("caption_relation", {}),
        "outer_flow_context": selected.get("outer_flow_context", {}),
        "source_section_index": selected.get("source_section_index"),
    }


def figure_layout_evidence(docx_item: dict | None) -> dict:
    if not docx_item:
        return {}
    drawings = docx_item.get("inspection", {}).get("body_drawings", [])
    if not isinstance(drawings, list) or not drawings:
        return {}
    def drawing_score(item: dict) -> tuple[int, int]:
        relation = item.get("caption_relation", {})
        relation_rank = 0
        if isinstance(relation, dict) and relation.get("position") in {"above", "below"}:
            relation_rank = {"adjacent": 2, "nearby": 1}.get(str(relation.get("confidence") or ""), 0)
            if relation.get("classification_source") == "visible label":
                relation_rank += 2
        area = int(item.get("width_emu") or 0) * int(item.get("height_emu") or 0)
        return relation_rank, area

    caption_attached = [
        item for item in drawings
        if isinstance(item.get("caption_relation"), dict)
        and item["caption_relation"].get("position") in {"above", "below"}
        and item["caption_relation"].get("confidence") in {"adjacent", "nearby"}
    ]
    drawing_types = sorted({str(item.get("drawing_type") or "unknown") for item in drawings})
    wrap_types = sorted({str((item.get("geometry") or {}).get("wrap_type") or "none") for item in drawings if isinstance(item, dict)})
    inline_unlabeled = [
        item for item in drawings
        if str(item.get("drawing_type") or "").lower() == "inline"
    ]
    if not caption_attached and not inline_unlabeled:
        # A large anchor can be a logo, text-box decoration, or illustration
        # unrelated to the manuscript figure contract. Retain short evidence
        # for later rendering, but do not let it set a journal-wide figure
        # width, span, or caption policy.
        candidates = sorted(drawings, key=drawing_score, reverse=True)[:5]
        return {
            "source": "official Word body drawing XML",
            "sample_count": len(drawings),
            "caption_attached_sample_count": 0,
            "selection_status": "no_caption_attached_body_figure",
            "selection_reason": "no external adjacent or nearby Word figure caption was found",
            "drawing_types": drawing_types,
            "wrap_types": wrap_types,
            "candidate_samples": [
                {
                    "paragraph_index": item.get("paragraph_index"),
                    "drawing_type": item.get("drawing_type"),
                    "width_emu": item.get("width_emu"),
                    "height_emu": item.get("height_emu"),
                    "caption_relation": item.get("caption_relation", {}),
                }
                for item in candidates
            ],
            "requires_visual_review": True,
        }

    if caption_attached:
        selected = max(caption_attached, key=drawing_score)
        selection_status = "caption_attached_body_figure"
        selection_reason = "selected an external adjacent or nearby Word figure caption relation"
    else:
        # An inline Word drawing participates in paragraph flow. It is usable
        # geometry evidence even when the template omits a matching caption,
        # but it cannot establish a caption order or LaTeX float policy.
        selected = max(inline_unlabeled, key=drawing_score)
        selection_status = "inline_unlabeled_body_figure"
        selection_reason = "selected an inline Word drawing for geometry only; no external adjacent or nearby caption was found"
    geometry = selected.get("geometry") if isinstance(selected.get("geometry"), dict) else {}
    return {
        "source": "official Word body drawing XML",
        "sample_count": len(drawings),
        "caption_attached_sample_count": len(caption_attached),
        "selection_status": selection_status,
        "selection_reason": selection_reason,
        "drawing_type": selected.get("drawing_type"),
        "drawing_types": drawing_types,
        "wrap_types": wrap_types,
        "width_emu": selected.get("width_emu"),
        "height_emu": selected.get("height_emu"),
        "horizontal_alignment": selected.get("horizontal_alignment"),
        "vertical_alignment": selected.get("vertical_alignment"),
        "anchor_geometry": geometry,
        "paragraph_index": selected.get("paragraph_index"),
        "paragraph_style_id": selected.get("paragraph_style_id"),
        "paragraph_style_name": selected.get("paragraph_style_name"),
        "paragraph_direct_format": selected.get("paragraph_direct_format", {}),
        "paragraph_effective_format": selected.get("paragraph_effective_format", {}),
        "caption_relation": selected.get("caption_relation", {}),
        "outer_flow_context": selected.get("outer_flow_context", {}),
        "source_section_index": selected.get("source_section_index"),
    }


def float_text_spacing_evidence(table_layout: dict, figure_layout: dict) -> dict:
    """Aggregate object-block outer boundaries without activating TeX lengths."""
    boundaries = []
    values = []
    for kind, layout in (("table", table_layout), ("figure", figure_layout)):
        context = layout.get("outer_flow_context", {}) if isinstance(layout, dict) else {}
        for side in ("before", "after"):
            boundary = context.get(side) if isinstance(context, dict) else None
            if not isinstance(boundary, dict):
                continue
            record = {"kind": kind, "side": side, **boundary}
            boundaries.append(record)
            neighbor_role = boundary.get("preceding_role") if side == "before" else boundary.get("following_role")
            try:
                if boundary.get("status") == "source" and neighbor_role == "body_text_candidate":
                    values.append(float(boundary.get("resolved_pt")))
            except (TypeError, ValueError):
                pass
    if values:
        ordered = sorted(values)
        middle = len(ordered) // 2
        resolved = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2.0
        return {
            "status": "source",
            "resolved_pt": round(resolved, 3),
            "eligible_boundary_count": len(values),
            "boundaries": boundaries,
            "source": "median of available Word object-block outer paragraph boundaries",
            "mapping": "candidate_only",
            "rule": "resolve each adjacent boundary once; do not merge caption/object spacing into float/text spacing",
        }
    return {
        "status": "default",
        "resolved_pt": 12.0,
        "eligible_boundary_count": 0,
        "boundaries": boundaries,
        "source": "conservative LaTeX journal fallback",
        "mapping": "candidate_only",
        "rule": "no source object-block outer boundary; keep ordinary LaTeX float spacing",
    }


def object_span_evidence(docx_item: dict | None, layout: dict, kind: str, document_columns: str) -> dict:
    """Classify an exemplar against its local Word section, not page-wide width alone."""
    if not docx_item or not isinstance(layout, dict) or not layout:
        return {"status": "unknown", "mode": "uncertain", "reason": "no source object geometry"}
    sections = docx_item.get("inspection", {}).get("sections", [])
    section_index = layout.get("source_section_index")
    section = next((item for item in sections if item.get("index") == section_index), None)
    if not isinstance(section, dict):
        return {"status": "unknown", "mode": "uncertain", "reason": "object could not be assigned to a Word section"}
    try:
        page_width = float(section.get("page_width_twips")) / 20.0
        margins = section.get("margins_twips") or {}
        usable_width = page_width - float(margins.get("left", 0)) / 20.0 - float(margins.get("right", 0)) / 20.0
        column_count = int(section.get("columns") or 1)
        column_gap = float(section.get("column_space_twips") or 0) / 20.0
    except (TypeError, ValueError, ZeroDivisionError):
        return {"status": "unknown", "mode": "uncertain", "reason": "local Word section dimensions are incomplete"}
    if kind == "figure":
        try:
            object_width = float(layout.get("width_emu")) / 12700.0
        except (TypeError, ValueError):
            object_width = 0.0
    else:
        try:
            object_width = float(layout.get("width_twips")) / 20.0 if str(layout.get("width_type") or "").lower() == "dxa" else 0.0
        except (TypeError, ValueError):
            object_width = 0.0
        if object_width <= 0:
            try:
                object_width = sum(float(value) for value in layout.get("grid_column_widths_twips", []) if value is not None) / 20.0
            except (TypeError, ValueError):
                object_width = 0.0
    evidence = {
        "status": "unknown",
        "mode": "uncertain",
        "source": "official Word object dimensions and local section columns",
        "source_section_index": section_index,
        "source_section_columns": column_count,
        "object_width_pt": round(object_width, 3) if object_width > 0 else None,
        "usable_width_pt": round(usable_width, 3) if usable_width > 0 else None,
    }
    if object_width <= 0 or usable_width <= 0:
        evidence["reason"] = "object width is automatic or unavailable"
        return evidence
    if column_count <= 1:
        ratio = object_width / usable_width
        evidence.update({
            "local_column_width_pt": round(usable_width, 3),
            "object_to_local_column_ratio": round(ratio, 4),
        })
        if document_columns == "double":
            evidence["reason"] = "exemplar belongs to a one-column Word section while the manuscript body is double-column"
            return evidence
        evidence.update({"status": "source", "mode": "single_column"})
        return evidence
    widths = []
    for value in section.get("column_widths_twips", []) or []:
        try:
            widths.append(float(value) / 20.0)
        except (TypeError, ValueError):
            pass
    local_column_width = max(widths) if widths else (usable_width - column_gap * (column_count - 1)) / column_count
    ratio = object_width / local_column_width if local_column_width > 0 else 0.0
    evidence.update({
        "local_column_width_pt": round(local_column_width, 3),
        "object_to_local_column_ratio": round(ratio, 4),
    })
    if 0 < ratio <= 1.08:
        evidence.update({"status": "source", "mode": "single_column"})
    elif 1.15 <= ratio and object_width <= usable_width * 1.08:
        evidence.update({"status": "source", "mode": "double_column"})
    else:
        evidence["reason"] = "object width lies in the ambiguity band between one-column and spanning geometry"
    return evidence


def caption_position_evidence(layout: dict, default: str, kind: str) -> tuple[str, dict]:
    relation = layout.get("caption_relation", {}) if isinstance(layout, dict) else {}
    position = relation.get("position") if isinstance(relation, dict) else None
    confidence = str(relation.get("confidence") or "") if isinstance(relation, dict) else ""
    if position in {"above", "below"} and confidence in {"adjacent", "nearby"}:
        return str(position), {
            "status": "source",
            "source": "official Word document-flow adjacency",
            "object_kind": kind,
            **relation,
        }
    reason = "no nearby, directionally unambiguous Word caption/object relation was detected"
    if isinstance(relation, dict) and relation.get("position") == "inside":
        reason = "caption-like text occurs inside the object container and does not prove an external caption order"
    elif confidence == "distant":
        reason = "nearest caption-like paragraph is too distant to attach safely to the selected object"
    return default, {
        "status": "default",
        "source": "Temp2TeX language-neutral journal default",
        "object_kind": kind,
        "reason": reason,
        "observed_relation": relation,
    }


def equation_layout_evidence(docx_item: dict | None) -> dict:
    """Keep OMML layout and numbering evidence separate from math conversion."""
    if not docx_item:
        return {"present": False, "source": "no Word document evidence"}
    samples = docx_item.get("inspection", {}).get("equations", [])
    if not isinstance(samples, list) or not samples:
        return {"present": False, "source": "no OMML equations found in official Word document"}
    body_samples = [sample for sample in samples if not sample.get("in_text_box")]
    display_samples = [sample for sample in body_samples if sample.get("display_like")]
    numbers = [number for sample in display_samples for number in sample.get("number_samples", [])]
    converted = [sample for sample in body_samples if sample.get("translation_status") == "converted"]
    partial = [sample for sample in body_samples if sample.get("translation_status") != "converted"]
    candidates = [
        {
            "index": sample.get("index"),
            "display_like": bool(sample.get("display_like")),
            "in_table_cell": bool(sample.get("in_table_cell")),
            "latex": sample.get("latex"),
            "translation_status": sample.get("translation_status"),
            "unsupported_nodes": sample.get("unsupported_nodes", []),
            "source_structure": sample.get("structure", []),
        }
        for sample in body_samples[:20]
    ]
    return {
        "present": True,
        "sample_count": len(body_samples),
        "display_sample_count": len(display_samples),
        "numbering": "numbered" if numbers else "unverified",
        "number_samples": numbers[:8],
        "table_cell_samples": sum(1 for sample in body_samples if sample.get("in_table_cell")),
        "source": "official Word OMML equation XML",
        "converted_sample_count": len(converted),
        "manual_translation_sample_count": len(partial),
        "latex_candidates": candidates,
        "requires_math_translation": bool(partial),
        "requires_visual_review": True,
    }


def note_style_evidence(docx_item: dict | None, kind: str) -> dict:
    if not docx_item:
        return {}
    samples = docx_item.get("inspection", {}).get(f"{kind}_samples", [])
    if not isinstance(samples, list) or not samples:
        return {}
    selected = max(samples, key=lambda item: len(str(item.get("text", ""))))
    return {
        "style_id": selected.get("style_id"),
        "style_name": selected.get("style_name"),
        "direct_format": selected.get("direct_format") or {},
        "effective_format": selected.get("effective_format") or selected.get("direct_format") or {},
        "sample_text": selected.get("text"),
        "source": f"official Word {kind}.xml paragraph",
    }


def footnote_style_evidence(docx_item: dict | None) -> dict:
    return note_style_evidence(docx_item, "footnote")


def endnote_style_evidence(docx_item: dict | None) -> dict:
    return note_style_evidence(docx_item, "endnote")


def list_layout_evidence(docx_item: dict | None) -> dict:
    """Select a visible Word list definition without applying it to body text."""
    if not docx_item:
        return {"present": False, "source": "no Word document evidence"}
    items = docx_item.get("inspection", {}).get("list_items", [])
    if not isinstance(items, list) or not items:
        return {"present": False, "source": "no visible Word numbered or bulleted paragraphs"}
    candidates = [item for item in items if str(item.get("number_format") or "").lower() not in {"none"}]
    selected = candidates[0] if candidates else items[0]
    number_format = str(selected.get("number_format") or "decimal").lower()
    kind = "itemize" if number_format in {"bullet", "none"} else "enumerate"
    levels = sorted({str(item.get("level") or "0") for item in items})
    return {
        "present": True,
        "kind": kind,
        "number_format": number_format,
        "level_text": selected.get("level_text"),
        "left_indent_twips": selected.get("left_indent_twips"),
        "hanging_twips": selected.get("hanging_twips"),
        "levels_seen": levels,
        "sample_count": len(items),
        "source": "official Word numbering.xml plus paragraph-level or style-level list evidence",
        "requires_visual_review": True,
    }


def cover_evidence(docx_item: dict | None) -> dict:
    if not docx_item:
        return {"mode": "not_detected", "source": "no Word section evidence"}
    sections = docx_item.get("inspection", {}).get("sections", [])
    if not isinstance(sections, list) or not sections:
        return {"mode": "not_detected", "source": "no Word section evidence"}
    first = sections[0]
    first_variants = [
        reference for key in ("header_references", "footer_references")
        for reference in first.get(key, []) if reference.get("type") == "first"
    ]
    if first.get("different_first_page") or first_variants:
        return {
            "mode": "candidate_first_page_variant",
            "source": "official Word first-page section variant",
            "different_first_page": bool(first.get("different_first_page")),
            "first_page_header_footer_parts": [item.get("part") for item in first_variants],
        }
    text_boxes = docx_item.get("inspection", {}).get("text_boxes", [])
    if isinstance(text_boxes, list) and text_boxes:
        return {
            "mode": "candidate_textbox_layout",
            "source": "official Word non-flow text box XML",
            "text_box_count": len(text_boxes),
            "requires_visual_review": True,
        }
    return {"mode": "not_detected", "source": "official Word first section"}


def toc_evidence(docx_item: dict | None) -> dict:
    if not docx_item:
        return {"enabled": False, "source": "no Word document evidence"}
    evidence = docx_item.get("inspection", {}).get("toc_evidence", {})
    has_field = bool(evidence.get("has_toc_field")) if isinstance(evidence, dict) else False
    headings = evidence.get("heading_samples", []) if isinstance(evidence, dict) else []
    fields = evidence.get("field_samples", []) if isinstance(evidence, dict) else []
    depth = None
    for field in fields:
        match = re.search(r"\\o\s+[\"']?(\d+)\s*-\s*(\d+)", str(field), flags=re.I)
        if match:
            try:
                depth = max(0, min(5, int(match.group(2))))
            except ValueError:
                pass
            break
    return {
        "enabled": has_field,
        "source": "official Word TOC field" if has_field else "no official Word TOC field",
        "field_samples": fields,
        "heading_samples": headings,
        "heading_only_candidate": bool(headings and not has_field),
        "depth": depth,
    }


def body_style_evidence(docx_item: dict | None) -> dict:
    if not docx_item:
        return {}
    inspection = docx_item.get("inspection", {})
    paragraphs = inspection.get("paragraph_samples", [])
    flow_long = [
        paragraph for paragraph in paragraphs
        if not paragraph.get("in_table_cell")
        and len(str(paragraph.get("text") or "").strip()) >= 80
        and not any(
            term in str(paragraph.get("style_name") or "").lower().replace("_", " ")
            for term in ("caption", "table", "figure", "footnote", "header", "footer", "title", "author", "abstract", "keyword", "reference", "bibliograph")
        )
        and not str(paragraph.get("text") or "").strip().lower().startswith(
            ("abstract", "keywords", "keyword", "references", "reference", "bibliography", "table ", "figure ", "fig. ", "insert ", "replace ", "instruction", "author ", "note:")
        )
        and (paragraph.get("effective_format") or paragraph.get("direct_format") or {}).get("font")
    ]
    table_body = table_cell_body_candidates(paragraphs)
    if table_body and not flow_long:
        # A few publisher templates place the whole manuscript in a layout
        # table. Use its body-like sample only when no ordinary-flow exemplar
        # exists; front matter and instruction cells remain excluded above.
        selected = max(table_body, key=lambda item: len(str(item.get("text") or "")))
        evidence = direct_paragraph_evidence(selected, "body")
        evidence["evidence_status"] = "table_cell_body_exemplar"
        evidence["source"] = "direct Word formatting on a body-like table-cell paragraph; no flow-body exemplar"
        return evidence
    usage: dict[str, int] = {}
    for paragraph in inspection.get("paragraph_samples", []):
        if paragraph.get("in_table_cell"):
            continue
        style_id = paragraph.get("style_id")
        if style_id:
            usage[str(style_id)] = usage.get(str(style_id), 0) + 1

    excluded = ("reference", "bibliograph", "bib", "caption", "footnote", "list", "table", "figure", "header", "footer")
    preferred = ("body", "main text", "article text", "text", "paragraph", "para", "normal")
    candidates = []
    for style in inspection.get("styles", []):
        if style.get("type") != "paragraph":
            continue
        style_id = str(style.get("style_id") or "")
        name = str(style.get("name") or "").lower().replace("_", " ")
        if any(term in name for term in excluded):
            continue
        score = 0
        for index, term in enumerate(preferred):
            if name == term:
                score = max(score, 100 - index)
            elif term in name:
                score = max(score, 80 - index)
        if score and usage.get(style_id, 0):
            candidates.append((score, usage[style_id], style))
    if candidates:
        selected = max(candidates, key=lambda item: (item[0], item[1]))[2]
        selected_format = selected.get("effective_format") or selected.get("direct_format") or {}
        if selected_format.get("font") or selected_format.get("paragraph"):
            named_evidence = {
                "style_id": selected.get("style_id"),
                "style_name": selected.get("name"),
                "direct_format": selected.get("direct_format") or {},
                "effective_format": selected_format,
            }
            # A named Normal/Body style can conflict with visible flow
            # formatting. Retain the named style as the ordinary default and
            # store the visible alternative for a same-content render probe;
            # local instructions must not silently redefine every manuscript.
            flow_groups: dict[str, list[dict]] = {}
            for paragraph in flow_long:
                effective = paragraph.get("effective_format") or paragraph.get("direct_format") or {}
                font = effective.get("font") or {}
                paragraph_format = effective.get("paragraph") or {}
                signature = repr((
                    font.get("family"), font.get("east_asia_family"), font.get("size_half_points"),
                    paragraph_format.get("line_spacing"), paragraph_format.get("line_spacing_rule"),
                ))
                flow_groups.setdefault(signature, []).append(paragraph)
            if flow_groups:
                dominant = max(
                    flow_groups.values(),
                    key=lambda items: (len(items), sum(len(str(item.get("text") or "")) for item in items)),
                )
                dominant_effective = dominant[0].get("effective_format") or dominant[0].get("direct_format") or {}
                dominant_font = dominant_effective.get("font") or {}
                selected_font = selected_format.get("font") or {}
                selected_paragraph = selected_format.get("paragraph") or {}
                dominant_paragraph = dominant_effective.get("paragraph") or {}
                font_conflict = any(
                    dominant_font.get(key) is not None
                    and dominant_font.get(key) != selected_font.get(key)
                    for key in ("family", "east_asia_family", "size_half_points")
                )
                paragraph_conflict = (
                    not selected_paragraph
                    and bool(dominant_paragraph)
                    and len(dominant) >= 2
                )
                selected_style_name = str(selected.get("name") or selected.get("style_id") or "").lower()
                generic_named_style = selected_style_name.replace("_", " ").strip() in {
                    "normal", "body", "body text", "default paragraph font"
                }
                dominant_style_names = [
                    str(item.get("style_name") or item.get("style_id") or "").lower().replace("_", " ").strip()
                    for item in dominant
                ]
                visible_generic_style = all(
                    name in {"", "normal", "body", "body text", "default paragraph font"}
                    for name in dominant_style_names
                )
                if generic_named_style and visible_generic_style and len(dominant) >= 2 and (font_conflict or paragraph_conflict):
                    visible = max(dominant, key=lambda item: len(str(item.get("text") or "")))
                    candidate = direct_paragraph_evidence(visible, "body")
                    named_evidence["evidence_status"] = "named_style_with_visible_flow_conflict"
                    named_evidence["visible_flow_override_candidate"] = candidate
                    named_evidence["visible_flow_override_reason"] = (
                        "dominant effective formatting across visible Word flow-body paragraphs; "
                        "requires same-content render confirmation before promotion"
                    )
            return named_evidence

    # A sparse publisher template can intentionally contain no article body
    # paragraphs while still defining a complete Normal/Body Text style. Keep
    # that named style as a template-style candidate instead of silently
    # replacing its metrics with generic LaTeX defaults. It is explicitly
    # marked unverified because it has no rendered body exemplar yet.
    template_candidates = []
    for style in inspection.get("styles", []):
        if style.get("type") != "paragraph":
            continue
        name = str(style.get("name") or "").lower().replace("_", " ")
        if any(term in name for term in excluded):
            continue
        score = 0
        for index, term in enumerate(preferred):
            if name == term:
                score = max(score, 100 - index)
            elif term in name:
                score = max(score, 80 - index)
        if score:
            template_candidates.append((score, style))
    if template_candidates:
        selected = max(template_candidates, key=lambda item: item[0])[1]
        selected_format = selected.get("effective_format") or selected.get("direct_format") or {}
        if selected_format.get("font") or selected_format.get("paragraph"):
            return {
                "style_id": selected.get("style_id"),
                "style_name": selected.get("name"),
                "direct_format": selected.get("direct_format") or {},
                "effective_format": selected_format,
                "evidence_status": "template_style_candidate",
                "source": "named body style in official Word template; no visible body exemplar",
            }

    # Many publisher DOCX files have only Normal as a paragraph style and put
    # the real body baseline in w:pPr/w:rPr. Do not choose the single longest
    # direct-formatted paragraph: abstracts and reference entries are often
    # longer than actual body prose. Start after the first credible manuscript
    # heading, then select the most frequently used direct-format signature.
    heading_indexes = []
    for candidate in inspection.get("heading_candidates", []):
        text = str(candidate.get("text", "")).strip()
        if not re.match(r"^1(?:[.)]|\s)\S+", text) or is_affiliation_like(text):
            continue
        heading_indexes.append(int(candidate.get("index") or 0))
    body_start = min((index for index in heading_indexes if index > 0), default=0)

    reference_markers = ("references", "reference", "bibliography", "参考文献", "参考资料")
    body_end = min(
        (
            int(paragraph.get("index") or 0)
            for paragraph in paragraphs
            if int(paragraph.get("index") or 0) > body_start
            and str(paragraph.get("text", "")).strip().lower() in reference_markers
        ),
        default=0,
    )

    excluded_prefixes = ("abstract", "keywords", "keyword", "references", "reference", "bibliography")
    body_candidates = [
        paragraph for paragraph in paragraphs
        if not paragraph.get("in_table_cell")
        and len(str(paragraph.get("text", "")).strip()) >= 80
        and int(paragraph.get("index") or 0) > body_start
        and (not body_end or int(paragraph.get("index") or 0) < body_end)
        and not str(paragraph.get("text", "")).strip().lower().startswith(excluded_prefixes)
        and (paragraph.get("effective_format") or paragraph.get("direct_format") or {}).get("font")
    ]
    if not body_candidates and body_start:
        # Some source samples are very short; retain the body boundary even if
        # it leaves only shorter direct-formatted prose.
        body_candidates = [
            paragraph for paragraph in paragraphs
            if not paragraph.get("in_table_cell")
            and int(paragraph.get("index") or 0) > body_start
            and (not body_end or int(paragraph.get("index") or 0) < body_end)
            and len(str(paragraph.get("text", "")).strip()) >= 30
            and (paragraph.get("effective_format") or paragraph.get("direct_format") or {}).get("font")
        ]
    if not body_candidates:
        return {}

    groups: dict[str, list[dict]] = {}
    for paragraph in body_candidates:
        effective = paragraph.get("effective_format") or paragraph.get("direct_format") or {}
        font = effective.get("font") or {}
        fmt = effective.get("paragraph") or {}
        signature = repr((
            font.get("family"), font.get("east_asia_family"), font.get("size_half_points"),
            font.get("bold"), fmt.get("alignment"), fmt.get("line_spacing"),
            fmt.get("line_spacing_rule"), fmt.get("first_line_twips"),
        ))
        groups.setdefault(signature, []).append(paragraph)
    selected_group = max(
        groups.values(),
        key=lambda items: (len(items), sum(len(str(item.get("text", ""))) for item in items)),
    )
    selected = max(selected_group, key=lambda item: len(str(item.get("text", ""))))
    return direct_paragraph_evidence(selected, "body")


def line_number_evidence(docx_item: dict | None, evidence: str) -> dict:
    """Prefer Word section properties over prose that merely mentions line numbers."""
    structural = docx_item.get("inspection", {}).get("line_numbering", {}) if docx_item else {}
    if isinstance(structural, dict) and structural.get("enabled"):
        return {
            "enabled": True,
            "status": "source",
            "source": structural.get("source", "official Word section line-numbering properties"),
            "sections": structural.get("sections", []),
        }
    mentioned = contains(evidence, "line numbering", "line numbers")
    return {
        "enabled": bool(mentioned),
        "status": "instruction" if mentioned else "not_detected",
        "source": "official template instruction text" if mentioned else "no Word line-numbering property or instruction found",
    }


def direct_paragraph_evidence(paragraph: dict, role: str) -> dict:
    """Represent direct paragraph formatting when a Word role has no style."""
    direct = paragraph.get("direct_format") or {}
    effective = paragraph.get("effective_format") or direct
    result = {
        "style_id": paragraph.get("style_id"),
        "style_name": paragraph.get("style_name"),
        "role": role,
        "direct_format": direct,
        "sample_direct_format": direct,
        "effective_format": effective,
        "sample_text": str(paragraph.get("text", ""))[:220],
        "sample_paragraph_index": paragraph.get("index"),
        "evidence_status": "visible_role_exemplar",
        "source": "direct Word paragraph formatting; no semantic paragraph style",
    }
    spans = paragraph.get("format_spans")
    if isinstance(spans, list) and spans:
        result["format_spans"] = spans
        result["format_span_text"] = paragraph.get("format_span_text", paragraph.get("text", ""))
    return result


def latin_text_ratio(text: str) -> float:
    visible = [character for character in text if not character.isspace()]
    if not visible:
        return 0.0
    return sum(character.isascii() and character.isalpha() for character in visible) / len(visible)


def english_front_matter_evidence(docx_item: dict | None) -> dict[str, dict]:
    """Recover bilingual role exemplars without borrowing Chinese front matter.

    Mixed-language Word templates often place the English title block after
    Chinese keywords and before the first numbered body heading. Select only
    those role-shaped paragraphs; Chinese funding/author-note paragraphs and
    later English prose are deliberately excluded.
    """
    if not docx_item:
        return {}
    paragraphs = [
        item for item in docx_item.get("inspection", {}).get("paragraph_samples", [])
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ]
    if not paragraphs:
        return {}
    chinese_keyword_index = next(
        (
            int(item.get("index") or 0)
            for item in paragraphs
            if str(item.get("text") or "").strip().startswith(("关键词", "关键字"))
        ),
        None,
    )
    if chinese_keyword_index is None:
        return {}
    heading_indexes = {
        int(item.get("index") or 0)
        for item in docx_item.get("inspection", {}).get("heading_candidates", [])
        if isinstance(item, dict) and not is_affiliation_like(str(item.get("text") or ""))
    }
    body_end = min((index for index in heading_indexes if index > chinese_keyword_index), default=10**9)
    window = [
        item for item in paragraphs
        if chinese_keyword_index < int(item.get("index") or 0) < body_end
        and latin_text_ratio(str(item.get("text") or "")) >= 0.45
    ]
    if not window:
        return {}
    abstract = next((item for item in window if str(item.get("text") or "").strip().lower().startswith("abstract")), None)
    abstract_index = int(abstract.get("index") or 0) if abstract else body_end
    title = next(
        (
            item for item in window
            if int(item.get("index") or 0) < abstract_index
            and len(str(item.get("text") or "").strip()) >= 20
            and not re.match(r"^\d+[.)]\s*", str(item.get("text") or "").strip())
        ),
        None,
    )
    title_index = int(title.get("index") or 0) if title else chinese_keyword_index
    affiliation_markers = ("university", "college", "institute", "department", "laboratory", "school")
    affiliation = next(
        (
            item for item in window
            if title_index < int(item.get("index") or 0) < abstract_index
            and (
                bool(re.match(r"^\d+[.)]\s*", str(item.get("text") or "").strip()))
                or any(marker in str(item.get("text") or "").lower() for marker in affiliation_markers)
            )
        ),
        None,
    )
    affiliation_index = int(affiliation.get("index") or 0) if affiliation else abstract_index
    author = next(
        (
            item for item in window
            if title_index < int(item.get("index") or 0) < affiliation_index
            and not any(marker in str(item.get("text") or "").lower() for marker in affiliation_markers)
        ),
        None,
    )
    keywords = next(
        (
            item for item in window
            if int(item.get("index") or 0) > abstract_index
            and str(item.get("text") or "").strip().lower().startswith(("keywords", "key words"))
        ),
        None,
    )
    selected = {
        "title": title,
        "author": author,
        "affiliation": affiliation,
        "abstract": abstract,
        "keywords": keywords,
    }
    return {
        name: direct_paragraph_evidence(paragraph, f"english_{name}")
        for name, paragraph in selected.items()
        if paragraph is not None
    }


def visible_reference_entry_evidence(docx_item: dict | None) -> dict:
    """Use the first actual reference-zone entry when no semantic style exists."""
    if not docx_item:
        return {}
    seen_heading = False
    markers = ("references", "reference", "bibliography", "参考文献", "参考资料")
    for paragraph in docx_item.get("inspection", {}).get("paragraph_samples", []):
        if not isinstance(paragraph, dict):
            continue
        text = str(paragraph.get("text") or "").strip()
        if not text:
            continue
        if text.lower() in markers or text.startswith(("参考文献", "参考资料")):
            seen_heading = True
            continue
        if seen_heading and len(text) >= 8:
            return direct_paragraph_evidence(paragraph, "reference_entry")
    return {}


def role_evidence_or_default(evidence: dict, role: str) -> dict:
    """Make missing role evidence explicit instead of leaving an opaque gap."""
    if isinstance(evidence, dict) and evidence:
        return evidence
    return {
        "role": role,
        "direct_format": {},
        "effective_format": {},
        "evidence_status": "default",
        "source": "no visible Word role exemplar or semantic style was found; use the documented default",
    }


def semantic_role_evidence(docx_item: dict | None, *role_terms: str) -> dict:
    """Use visible labels and first-page position only when style evidence is absent."""
    if not docx_item:
        return {}
    paragraphs = docx_item.get("inspection", {}).get("paragraph_samples", [])
    role_terms_lower = {term.lower() for term in role_terms}
    role = next(iter(role_terms_lower), "role")

    def text_of(item: dict) -> str:
        return str(item.get("text", "")).strip()

    if "abstract" in role_terms_lower:
        predicate = lambda text, index: text.lower().startswith("abstract") or text.startswith("\u6458\u8981")
    elif "keyword" in role_terms_lower:
        predicate = lambda text, index: (
            text.lower().lstrip().startswith(("keyword", "key word", "index term"))
            or text.lstrip().startswith("\u5173\u952e\u8bcd")
        )
    elif "title" in role_terms_lower:
        title_markers = {"title", "article title", "paper title", "manuscript title"}
        guidance_prefixes = (
            "highlights", "include ", "the title", "list all authors", "abstract",
            "keywords", "instructions", "please ", "a concise",
        )

        def title_score(item: dict) -> int:
            text = text_of(item)
            index = int(item.get("index") or 0)
            normalized = re.sub(r"\s+", " ", text.lower()).strip(" *")
            style_name = str(item.get("style_name") or "").lower()
            if index > 20 or not 6 <= len(text) <= 220:
                return 0
            if normalized in KNOWN_SECTION_TITLES or normalized in {"sections", "highlights", "template"}:
                return 0
            if "heading" in style_name or "keyword" in style_name or "caption" in style_name:
                return 0
            if normalized.startswith(guidance_prefixes) or any(
                marker in normalized for marker in ("submission instructions", "author instructions", "delete this instruction")
            ):
                return 0
            if normalized.startswith(("(", "[", "in order", "note:", "please ", "this template")):
                return 0
            if normalized in title_markers:
                return 1200
            if text.rstrip().endswith((".", ":", ";", "?", "!")):
                return 0
            score = 0
            if re.search(r"\b(?:your|paper|article|manuscript|full)\b.*\btitle\b", normalized):
                score += 500
            if "title" in style_name:
                score += 650
            font = (item.get("effective_format") or {}).get("font") or {}
            try:
                size = int(font.get("size_half_points") or 0)
            except (TypeError, ValueError):
                size = 0
            # A title with no semantic name needs genuinely title-like type:
            # early position plus at least 14pt. This avoids promoting normal
            # instructional prose, author notes, or a first body heading.
            if score == 0 and (index > 8 or size < 28):
                return 0
            score += min(max(size - 24, 0), 32) * 4
            if font.get("bold"):
                score += 80
            return score

        candidates = [(title_score(item), item) for item in paragraphs]
        candidates = [item for item in candidates if item[0] > 0]
        if candidates:
            return direct_paragraph_evidence(max(candidates, key=lambda item: item[0])[1], role)
        return {}
    elif "author" in role_terms_lower:
        author_noise = (
            "date of publication", "date of current version", "received", "accepted",
            "copyright", "corresponding author", "e-mail", "email", "abstract", "keywords",
            "作者简介", "通讯作者", "基金项目", "图表", "字体", "行距", "模板", "题目",
            "单位", "部门", "地址", "邮编", "省市", "大学", "学院", "研究所", "实验室",
        )
        chinese_author_sequence = re.compile(
            r"^(?:[\u3400-\u9fff]{2,4}\s*\d{0,2}\s*[,，、；;]\s*)+[\u3400-\u9fff]{2,4}"
        )

        def author_candidate(text: str, index: int) -> bool:
            lower = text.lower()
            if index > 24 or any(marker in lower for marker in author_noise):
                return False
            if text.startswith(("\u6458\u8981", "\u5173\u952e\u8bcd")):
                return False
            if chinese_author_sequence.search(text):
                return True
            # Retain the established English path, but require more than a
            # generic comma-separated instruction sentence.
            return bool(
                (" and " in lower or "," in text)
                and re.search(r"\b[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){1,3}\b", text)
            )

        predicate = author_candidate
    elif {"affiliation", "address", "institution"} & role_terms_lower:
        affiliation_markers = ("university", "college", "institute", "department", "\u5927\u5b66", "\u5b66\u9662", "\u7814\u7a76\u6240", "\u5355\u4f4d", "\u90ae\u7f16")
        predicate = lambda text, index: index <= 16 and any(marker in text.lower() for marker in affiliation_markers)
    else:
        return {}

    for paragraph in paragraphs:
        text = text_of(paragraph)
        if text and predicate(text, int(paragraph.get("index") or 0)):
            return direct_paragraph_evidence(paragraph, role)
    return {}


def semantic_style_name_score(name: str, role_terms: tuple[str, ...]) -> int:
    """Score a Word style name for a document role without matching noise."""
    normalized = " ".join(name.lower().replace("_", " ").replace("-", " ").split())
    requested = {term.lower() for term in role_terms}
    # Word ships EndNote, TOC, comment, and bibliography styles whose names
    # often contain words such as Title or Author but are not manuscript roles.
    reference_role = bool(requested & {"reference", "references", "bibliography"})
    noise = {"endnote", "footnote", "toc", "comment", "annotation", "index"}
    if not reference_role:
        noise.update({"bibliograph", "reference"})
    if any(marker in normalized for marker in noise):
        return 0
    if requested == {"title"}:
        # A table/figure/equation title is a caption role, never the article
        # title. Conversely, blank publisher templates often leave their
        # explicit Paper Title style unused, so retain it as strong evidence.
        if any(marker in normalized for marker in ("table", "figure", "fig ", "caption", "equation", "chart")):
            return 0
        if normalized == "title":
            return 1400
        if normalized in {"paper title", "article title", "manuscript title", "document title"}:
            return 1300
        if normalized.endswith(" title") or normalized.startswith("title "):
            return 900
    if requested == {"keyword"}:
        if normalized in {"keyword", "keywords", "key word", "key words", "index term", "index terms"}:
            return 1300
        if normalized.endswith((" keyword", " keywords", " key word", " key words", " index term", " index terms")):
            return 900
    score = 0
    for term in requested:
        if normalized == term:
            score = max(score, 1000)
        elif normalized.endswith(f" {term}") or normalized.startswith(f"{term} "):
            score = max(score, 900)
        elif term in normalized:
            score = max(score, 700)
    # Template-system prefixes such as MDPI_1.1_title are useful, but a
    # generic built-in Title should win when both have otherwise equal roles.
    # Apply the bonus only after a real role match.  A prefix-only score made
    # unrelated styles such as ``MDPI_1.6_affiliation`` look like valid title,
    # abstract, and caption candidates when the requested role was absent.
    if score and normalized.startswith(("mdpi ", "journal ", "article ", "manuscript ")):
        score += 25
    return score


def role_style_evidence(docx_item: dict | None, *role_terms: str) -> dict:
    """Return a role style; retain a named template candidate for sparse files."""
    if not docx_item:
        return {}
    inspection = docx_item.get("inspection", {})
    requested = {term.lower() for term in role_terms}
    role = str(role_terms[0]) if role_terms else "role"
    usage: dict[str, int] = {}
    for paragraph in inspection.get("paragraph_samples", []):
        style_id = paragraph.get("style_id")
        if style_id:
            usage[str(style_id)] = usage.get(str(style_id), 0) + 1
    candidates = []
    for style in inspection.get("styles", []):
        if style.get("type") != "paragraph":
            continue
        style_id = str(style.get("style_id") or "")
        name = str(style.get("name") or "")
        score = semantic_style_name_score(name, role_terms)
        used = usage.get(style_id, 0)
        title_candidate = requested == {"title"} and score >= 1300
        if score and (used or title_candidate):
            candidates.append((score, used, style))
    if not candidates:
        # In a blank template, an explicitly named ``Abstract`` or ``Author``
        # style is stronger evidence than a generic default. It is not a
        # rendered-layout claim, so consumers must retain its candidate status.
        template_candidates = []
        for style in inspection.get("styles", []):
            if style.get("type") != "paragraph":
                continue
            name = str(style.get("name") or "")
            score = semantic_style_name_score(name, role_terms)
            if score:
                template_candidates.append((score, style))
        if template_candidates:
            selected = max(template_candidates, key=lambda item: item[0])[1]
            return {
                "role": role,
                "style_id": selected.get("style_id"),
                "style_name": selected.get("name"),
                "direct_format": selected.get("direct_format") or {},
                "effective_format": selected.get("effective_format") or selected.get("direct_format") or {},
                "evidence_status": "template_style_candidate",
                "source": "named semantic style in official Word template; no visible role exemplar",
            }
        return semantic_role_evidence(docx_item, *role_terms)
    selected = max(candidates, key=lambda item: (item[0], item[1]))[2]
    selected_name = str(selected.get("name") or "").strip().lower()
    # A used Normal style is not semantic role evidence. Prefer an explicitly
    # labelled paragraph such as "摘要" or "Keywords" when direct formatting
    # carries the real layout.
    if selected_name in {"normal", "default paragraph font"}:
        direct = semantic_role_evidence(docx_item, *role_terms)
        if direct:
            return direct
    samples = [
        paragraph for paragraph in inspection.get("paragraph_samples", [])
        if paragraph.get("style_id") == selected.get("style_id")
    ]
    # Prefer the longest visible exemplar. A short label such as ``Abstract``
    # or ``Correspondence`` often has direct bold run formatting while the
    # paragraph style itself is regular; selecting it only because its XML has
    # more properties incorrectly promotes a local run override to the whole
    # role.
    sample = max(
        samples,
        key=lambda item: len(str(item.get("text") or "")),
        default={},
    )
    style_format = selected.get("effective_format") or selected.get("direct_format") or {}
    sample_format = sample.get("effective_format") or sample.get("direct_format") or {}
    effective_format = {
        key: dict(value)
        for key, value in style_format.items()
        if isinstance(value, dict)
    }
    # Paragraph properties are safe to merge because they describe the whole
    # paragraph. Font properties are different: Word can apply them to only a
    # label or one run. Use the sample font only when the named style has no
    # usable font baseline at all.
    style_font = style_format.get("font") if isinstance(style_format.get("font"), dict) else {}
    sample_font = sample_format.get("font") if isinstance(sample_format.get("font"), dict) else {}
    if not style_font and sample_font:
        effective_format["font"] = dict(sample_font)
    style_paragraph = style_format.get("paragraph") if isinstance(style_format.get("paragraph"), dict) else {}
    sample_paragraph = sample_format.get("paragraph") if isinstance(sample_format.get("paragraph"), dict) else {}
    if style_paragraph or sample_paragraph:
        effective_format["paragraph"] = {**style_paragraph, **sample_paragraph}
    result = {
        "role": role,
        "style_id": selected.get("style_id"),
        "style_name": selected.get("name"),
        "direct_format": selected.get("direct_format") or {},
        "sample_direct_format": sample.get("direct_format") or {},
        "effective_format": effective_format,
        "sample_text": str(sample.get("text") or "")[:220],
        "sample_paragraph_index": sample.get("index"),
        "sample_texts": [str(item.get("text") or "")[:220] for item in samples if str(item.get("text") or "").strip()][:12],
        "sample_count": len(samples),
        "sample_in_table_cells": any(item.get("in_table_cell") for item in samples),
    }
    selected_has_visible_sample = bool(str(sample.get("text", "")).strip())
    if selected_has_visible_sample:
        # A used semantic role is direct source evidence. Preserve its run
        # ledger so later class generation and coverage checks distinguish a
        # visible title/label from an unused named Word style.
        result.update({
            "evidence_status": "source",
            "source": "used semantic Word paragraph style with visible role exemplar",
            "format_spans": sample.get("format_spans") or [],
            "format_span_text": sample.get("format_span_text") or str(sample.get("text") or ""),
        })
    if requested == {"title"} and not selected_has_visible_sample:
        direct = semantic_role_evidence(docx_item, *role_terms)
        if direct:
            direct["evidence_status"] = "visible_role_exemplar"
            direct["source"] = "visible Word title exemplar with direct paragraph/run formatting"
            return direct
    if not usage.get(str(selected.get("style_id") or ""), 0) or (requested == {"title"} and not selected_has_visible_sample):
        result["evidence_status"] = "template_style_candidate"
        result["source"] = "named semantic title style in official Word template; no visible title exemplar"
    return result


def abstract_structure_evidence(docx_item: dict | None, fallback_style: dict) -> dict:
    """Separate an abstract label paragraph from its content paragraph."""
    if not docx_item:
        return {
            "label_mode": "default",
            "layout_mode": "block",
            "label": "Abstract:",
            "label_style": role_evidence_or_default({}, "abstract_label"),
            "content_style": fallback_style,
            "source": "no visible Word abstract structure; documented block-label default",
        }
    # Journal front matter is often implemented as a borderless Word layout
    # table. A visible label in a cell remains direct structure evidence.
    paragraphs = [
        item for item in docx_item.get("inspection", {}).get("paragraph_samples", [])
        if str(item.get("text") or "").strip()
    ]
    label_pattern = re.compile(r"^\s*(abstract|\u6458\u8981)\s*[:\uff1a]?\s*$", re.I)
    inline_delimited = re.compile(
        r"^\s*(abstract|\u6458\u8981)\s*([:\uff1a.\u2013\u2014-])\s*(\S.+)$",
        re.I,
    )
    inline_upper = re.compile(r"^\s*(ABSTRACT)\s+(\S.+)$")
    separate = next((item for item in paragraphs if label_pattern.match(str(item.get("text") or ""))), None)
    inline = next((
        item for item in paragraphs
        if inline_delimited.match(str(item.get("text") or ""))
        or inline_upper.match(str(item.get("text") or ""))
    ), None)
    if separate is not None:
        label_index = int(separate.get("index") or 0)
        content = next((
            item for item in paragraphs
            if label_index < int(item.get("index") or 0) <= label_index + 3
            and not label_pattern.match(str(item.get("text") or ""))
            and not str(item.get("text") or "").lower().lstrip().startswith(("keyword", "key word", "index term"))
            and not str(item.get("text") or "").lstrip().startswith("\u5173\u952e\u8bcd")
        ), None)
        return {
            "label_mode": "separate",
            "layout_mode": "block",
            "label": str(separate.get("text") or "Abstract").strip(),
            "label_style": direct_paragraph_evidence(separate, "abstract_label"),
            "content_style": direct_paragraph_evidence(content, "abstract") if content else fallback_style,
            "label_paragraph_index": separate.get("index"),
            "content_paragraph_index": content.get("index") if content else None,
            "source": "visible standalone Word abstract label and adjacent content paragraph",
        }
    if inline is not None:
        text = str(inline.get("text") or "").strip()
        delimited_match = inline_delimited.match(text)
        match = delimited_match or inline_upper.match(text)
        label = match.group(1) if match else "Abstract"
        if delimited_match:
            label += delimited_match.group(2)
        return {
            "label_mode": "inline",
            "layout_mode": "inline_label",
            "label": label,
            "label_style": direct_paragraph_evidence(inline, "abstract_label"),
            "content_style": direct_paragraph_evidence(inline, "abstract"),
            "label_paragraph_index": inline.get("index"),
            "content_paragraph_index": inline.get("index"),
            "source": "visible Word abstract label and content share one paragraph",
        }
    sample_text = str(fallback_style.get("sample_text") or "").strip()
    if sample_text:
        return {
            "label_mode": "none",
            "layout_mode": "block",
            "label": "",
            "label_style": role_evidence_or_default({}, "abstract_label"),
            "content_style": fallback_style,
            "content_paragraph_index": fallback_style.get("sample_paragraph_index"),
            "source": "visible Word abstract content has no defensible visible label",
        }
    return {
        "label_mode": "default",
        "layout_mode": "block",
        "label": "Abstract:",
        "label_style": role_evidence_or_default({}, "abstract_label"),
        "content_style": fallback_style,
        "source": "no visible Word abstract structure; documented block-label default",
    }


def role_spacing_twips(role: dict, key: str) -> int | None:
    for paragraph in (
        role.get("direct_format", {}).get("paragraph", {}),
        role.get("effective_format", {}).get("paragraph", {}),
    ) if isinstance(role, dict) else ():
        if not isinstance(paragraph, dict) or key not in paragraph:
            continue
        try:
            value = int(paragraph.get(key))
        except (TypeError, ValueError):
            continue
        if value >= 0:
            return value
    return None


def front_matter_boundary_evidence(previous: dict, following: dict, default_pt: float) -> dict:
    """Resolve one Word paragraph boundary once using its larger side."""
    previous_after = role_spacing_twips(previous, "space_after_twips")
    following_before = role_spacing_twips(following, "space_before_twips")
    values = [value for value in (previous_after, following_before) if value is not None]
    resolved_pt = max(values) / 20 if values else default_pt
    return {
        "status": "source" if values else "default",
        "previous_paragraph_index": previous.get("sample_paragraph_index") if isinstance(previous, dict) else None,
        "following_paragraph_index": following.get("sample_paragraph_index") if isinstance(following, dict) else None,
        "previous_space_after_twips": previous_after,
        "following_space_before_twips": following_before,
        "resolved_pt": round(resolved_pt, 3),
        "rule": "max(previous space-after, following space-before); emit once",
        "source": "official Word paragraph boundary" if values else "documented Temp2TeX front-matter default",
    }


def format_spacing_twips(format_evidence: dict, key: str) -> int | None:
    if not isinstance(format_evidence, dict):
        return None
    paragraph = format_evidence.get("paragraph")
    if not isinstance(paragraph, dict) or key not in paragraph:
        return None
    try:
        value = int(paragraph.get(key))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def caption_object_spacing_evidence(
    caption_style: dict,
    object_layout: dict,
    position: str,
    position_evidence: dict,
    default_pt: float = 4.0,
) -> dict:
    """Resolve only the two Word paragraph sides that face each other."""
    position = str(position or "").lower()
    source_position = (
        isinstance(position_evidence, dict)
        and position_evidence.get("status") == "source"
        and position in {"above", "below"}
    )
    caption_key = "space_after_twips" if position == "above" else "space_before_twips"
    object_key = "space_before_twips" if position == "above" else "space_after_twips"
    caption_outer_key = "space_before_twips" if position == "above" else "space_after_twips"
    caption_value = role_spacing_twips(caption_style, caption_key) if source_position else None
    caption_outer_value = role_spacing_twips(caption_style, caption_outer_key) if source_position else None
    object_value = None
    if source_position and isinstance(object_layout, dict):
        for format_key in ("paragraph_direct_format", "paragraph_effective_format"):
            object_value = format_spacing_twips(object_layout.get(format_key, {}), object_key)
            if object_value is not None:
                break
    values = [value for value in (caption_value, object_value) if value is not None]
    resolved_pt = max(values) / 20 if values else default_pt
    relation = object_layout.get("caption_relation", {}) if isinstance(object_layout, dict) else {}
    return {
        "status": "source" if values else "default",
        "position": position,
        "caption_paragraph_index": relation.get("caption_paragraph_index") if isinstance(relation, dict) else None,
        "object_paragraph_index": object_layout.get("paragraph_index") if isinstance(object_layout, dict) else None,
        "caption_facing_side": caption_key,
        "caption_facing_twips": caption_value,
        "object_facing_side": object_key,
        "object_facing_twips": object_value,
        "resolved_pt": round(resolved_pt, 3),
        "caption_outer_side": caption_outer_key,
        "caption_outer_twips": caption_outer_value,
        "outer_status": "source" if caption_outer_value is not None else "default",
        "outer_pt": round(caption_outer_value / 20, 3) if caption_outer_value is not None else 0.0,
        "rule": "max(caption facing-side spacing, object paragraph facing-side spacing); emit once",
        "source": (
            "official Word caption/object paragraph boundary"
            if values
            else "documented Temp2TeX caption/object gap default; source order or facing-side spacing unavailable"
        ),
    }


def visible_caption_evidence(docx_item: dict | None, kind: str) -> dict:
    """Prefer a visible table/figure caption over a broad named style candidate."""
    if not docx_item:
        return {}
    if kind == "table":
        pattern = re.compile(
            r"^\s*(?:(?:table\b|tab\.)\s*(?:\d+|[ivxlcdm]+)(?:[.:]\s|\s|$)|\u8868\s*(?:\d+|[A-Za-z]))",
            re.I,
        )
    else:
        pattern = re.compile(
            r"^\s*(?:(?:figure\b|fig\.)\s*(?:\d+|[ivxlcdm]+)(?:[.:]\s|\s|$)|(?:\u56fe|\u5716)\s*(?:\d+|[A-Za-z]))",
            re.I,
        )
    inspection = docx_item.get("inspection", {})
    inspected_candidates = inspection.get("caption_candidates")
    candidate_indexes = None
    if isinstance(inspected_candidates, list):
        candidate_indexes = {
            int(item.get("paragraph_index"))
            for item in inspected_candidates
            if item.get("kind") == kind
            and item.get("classification_source") == "visible label"
            and isinstance(item.get("paragraph_index"), int)
        }
    candidates = []
    for paragraph in inspection.get("paragraph_samples", []):
        text = str(paragraph.get("text") or "").strip()
        inspected_match = candidate_indexes is not None and paragraph.get("index") in candidate_indexes
        legacy_match = candidate_indexes is None and pattern.search(text)
        if text and not paragraph.get("list_evidence") and (inspected_match or legacy_match):
            candidates.append(paragraph)
    if not candidates:
        return {}
    selected = max(
        candidates,
        key=lambda item: (
            bool(item.get("direct_format")),
            len(str(item.get("text") or "")),
        ),
    )
    evidence = direct_paragraph_evidence(selected, f"{kind}_caption")
    evidence["source"] = f"visible official Word {kind} caption paragraph"
    evidence["evidence_status"] = "visible_role_exemplar"
    return evidence


def enrich_heading_from_instruction(evidence: dict, inspection: dict, paragraph: dict | None, level: int) -> dict:
    """Fill a missing heading size from nearby explicit Word template prose."""
    if not evidence:
        return evidence
    effective = copy.deepcopy(evidence.get("effective_format") or evidence.get("direct_format") or {})
    font = effective.setdefault("font", {})
    if font.get("size_half_points") is not None:
        return evidence
    if level == 0:
        role_pattern = r"\bheadings?\b"
        excluded = ("subhead", "tertiary", "third-level", "third level")
    elif level == 1:
        role_pattern = r"\bsubheads?|\bsubheadings?"
        excluded = ()
    elif level == 2:
        role_pattern = r"\btertiary\s+heads?|\bthird[- ]level\s+headings?"
        excluded = ()
    else:
        return evidence
    paragraphs = [item for item in inspection.get("paragraph_samples", []) if isinstance(item, dict)]
    selected_index = paragraph.get("index") if isinstance(paragraph, dict) else None
    nearby = []
    if isinstance(selected_index, int):
        nearby = [item for item in paragraphs if selected_index <= int(item.get("index") or -999) <= selected_index + 4]
    candidates = nearby + [item for item in paragraphs if item not in nearby]
    for item in candidates:
        text = str(item.get("text") or "").strip()
        lowered = text.lower()
        if any(token in lowered for token in excluded) or not re.search(role_pattern, text, flags=re.I):
            continue
        match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:pt|point)s?\b", text, flags=re.I)
        if not match:
            continue
        size_pt = float(match.group(1))
        if not 5 <= size_pt <= 72:
            continue
        font["size_half_points"] = str(int(size_pt * 2)) if size_pt * 2 == int(size_pt * 2) else str(size_pt * 2)
        enriched = copy.deepcopy(evidence)
        enriched["effective_format"] = effective
        enriched["instructional_format_evidence"] = {
            "font_size_pt": size_pt,
            "sample_text": text[:240],
            "paragraph_index": item.get("index"),
            "source": "explicit official Word template instruction near the heading exemplar",
        }
        enriched["source"] = str(enriched.get("source") or "official Word heading exemplar") + "; explicit nearby template instruction supplies font size"
        return enriched
    return evidence


def heading_style_evidence(docx_item: dict | None, level: int) -> dict:
    """Find a heading style, retaining outline-level candidates in sparse templates."""
    if not docx_item:
        return {}
    inspection = docx_item.get("inspection", {})
    abstract_index = first_abstract_paragraph_index(inspection)
    usage: dict[str, int] = {}
    for paragraph in inspection.get("paragraph_samples", []):
        style_id = paragraph.get("style_id")
        if style_id:
            usage[str(style_id)] = usage.get(str(style_id), 0) + 1
    candidates = []
    for style in inspection.get("styles", []):
        if style.get("type") != "paragraph":
            continue
        style_id = str(style.get("style_id") or "")
        direct = style.get("effective_format") or style.get("direct_format") or {}
        outline = direct.get("paragraph", {}).get("outline_level")
        name = str(style.get("name") or "").lower()
        if str(outline) == str(level) and usage.get(style_id, 0) and ("head" in name or "section" in name):
            candidates.append((usage[style_id], style))
    if not candidates:
        template_candidates = []
        for style in inspection.get("styles", []):
            if style.get("type") != "paragraph":
                continue
            direct = style.get("effective_format") or style.get("direct_format") or {}
            outline = direct.get("paragraph", {}).get("outline_level")
            name = str(style.get("name") or "").lower()
            if str(outline) == str(level) and ("head" in name or "section" in name):
                template_candidates.append(style)
        if template_candidates:
            selected = template_candidates[0]
            evidence = {
                "style_id": selected.get("style_id"),
                "style_name": selected.get("name"),
                "direct_format": selected.get("direct_format") or {},
                "effective_format": selected.get("effective_format") or selected.get("direct_format") or {},
                "evidence_status": "template_style_candidate",
                "source": "named heading style and Word outline level; no visible heading exemplar",
            }
            return enrich_heading_from_instruction(evidence, inspection, None, level)
        for paragraph in inspection.get("paragraph_samples", []):
            if paragraph.get("in_table_cell"):
                continue
            try:
                paragraph_index = int(paragraph.get("index") or 0)
            except (TypeError, ValueError):
                paragraph_index = 0
            # Numbered affiliations frequently appear before a Chinese abstract
            # in Word templates that use Normal for every paragraph.
            if abstract_index is not None and 0 < paragraph_index < abstract_index:
                continue
            text = str(paragraph.get("text", "")).strip()
            match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?[.)]?\s+\S+", text)
            if not match or is_affiliation_like(text):
                continue
            paragraph_level = 2 if match.group(3) else 1 if match.group(2) else 0
            if paragraph_level == level:
                evidence = direct_paragraph_evidence(paragraph, f"heading{level}")
                return enrich_heading_from_instruction(evidence, inspection, paragraph, level)
        return {}
    selected = max(candidates, key=lambda item: item[0])[1]
    evidence = {
        "style_id": selected.get("style_id"),
        "style_name": selected.get("name"),
        "direct_format": selected.get("direct_format") or {},
        "effective_format": selected.get("effective_format") or selected.get("direct_format") or {},
    }
    return enrich_heading_from_instruction(evidence, inspection, None, level)


def content_box_evidence(style_evidence: dict) -> dict | None:
    paragraph = style_evidence.get("effective_format", style_evidence.get("direct_format", {})).get("paragraph", {})
    left = twips_int(paragraph.get("left_indent_twips"))
    right = twips_int(paragraph.get("right_indent_twips"))
    if not any(value and value > 0 for value in (left, right)):
        return None
    return {
        "left_indent": f"{round((left or 0) / 20, 1)}pt",
        "right_indent": f"{round((right or 0) / 20, 1)}pt",
        "source_style_id": style_evidence.get("style_id"),
        "source_style_name": style_evidence.get("style_name"),
        "source": "direct Word paragraph indentation on a used journal style",
        "confidence": "official-template",
    }


def infer_font_size(
    docx_item: dict | None,
    evidence: str,
    columns: str,
    body_override: dict | None = None,
) -> float | int:
    body = body_override or body_style_evidence(docx_item)
    body_format = body.get("effective_format", body.get("direct_format", {}))
    half_points = body_format.get("font", {}).get("size_half_points")
    try:
        size = int(half_points) / 2
        if 8 <= size <= 12:
            return int(size) if size.is_integer() else size
    except (TypeError, ValueError):
        pass
    matches = re.findall(r"\b(8|9|10|11|12)\s*(?:pt|point|points)\b", evidence, flags=re.I)
    if matches:
        values = [int(item) for item in matches]
        for preferred in [10, 11, 12, 9, 8]:
            if preferred in values:
                return preferred
    return 10 if columns == "double" else 12


def infer_font_family(docx_item: dict | None, body_override: dict | None = None) -> str | None:
    """Return an explicitly declared body font, never a guessed publisher font."""
    body = body_override or body_style_evidence(docx_item)
    body_format = body.get("effective_format", body.get("direct_format", {}))
    family = body_format.get("font", {}).get("family")
    if not family:
        return None
    family = str(family).strip()
    return family or None


def infer_cjk_font_family(docx_item: dict | None, body_override: dict | None = None) -> str | None:
    """Retain an explicitly declared East Asian body font without applying it blindly."""
    body = body_override or body_style_evidence(docx_item)
    body_format = body.get("effective_format", body.get("direct_format", {}))
    family = body_format.get("font", {}).get("east_asia_family")
    if not family and docx_item:
        family = docx_item.get("inspection", {}).get("document_defaults", {}).get("font", {}).get("east_asia_family")
    if not family:
        return None
    family = str(family).strip()
    return family or None


def infer_line_spacing(
    docx_item: dict | None,
    evidence: str,
    columns: str,
    body_override: dict | None = None,
) -> float:
    body = body_override or body_style_evidence(docx_item)
    body_format = body.get("effective_format", body.get("direct_format", {}))
    paragraph = body_format.get("paragraph", {})
    try:
        line = int(paragraph.get("line_spacing"))
        rule = str(paragraph.get("line_spacing_rule") or "").lower()
        if rule in {"auto", "atleast"} and 160 <= line <= 480:
            return round(line / 240, 2)
    except (TypeError, ValueError):
        pass
    if contains(evidence, "double-spacing", "double spacing", "double-spaced", "double spaced"):
        return 2.0
    if contains(evidence, "single-spacing", "single spacing", "single-spaced", "single spaced"):
        return 1.0
    return 1.0 if columns == "double" else 1.15


def comment_body_format_directive(comments: list[dict], body_evidence: dict) -> dict | None:
    """Recover a narrowly-scoped body-format rule from an anchored comment.

    Word comments are normally non-binding guidance. This admits only an
    explicit role + numeric-format directive and refuses it if the selected
    visible/named body evidence supplies a conflicting value. The accepted
    directive is retained with its comment identity for later audit.
    """
    chinese_size_points = {"五": 10.5, "5": 10.5}
    effective = body_evidence.get("effective_format") or body_evidence.get("direct_format") or {}
    existing_font = effective.get("font") or {}
    existing_paragraph = effective.get("paragraph") or {}
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        text = re.sub(r"\s+", "", str(comment.get("text") or ""))
        anchors = comment.get("anchor_paragraph_indexes") or {}
        anchor_indexes = anchors.get("reference") or anchors.get("start") or []
        targets_body = bool(re.search(r"正文|主体文字|bodytext|maintext", text, flags=re.I))
        if not targets_body or not anchor_indexes:
            continue
        font: dict[str, str] = {}
        paragraph: dict[str, str] = {}
        font_size_pt = None
        if "宋体" in text:
            # Map the Chinese typeface name to the fontconfig/CTeX name while
            # retaining the original wording in the source record.
            font["east_asia_family"] = "SimSun"
        size_match = re.search(r"([五5])号(?:字|字体)?", text)
        if size_match:
            font_size_pt = chinese_size_points[size_match.group(1)]
            font["size_half_points"] = str(int(font_size_pt * 2))
        else:
            point_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:pt|磅)", text, flags=re.I)
            if point_match and ("字体" in text or "字号" in text or "font" in text.lower()):
                font_size_pt = float(point_match.group(1))
                if 5 <= font_size_pt <= 24:
                    font["size_half_points"] = str(int(round(font_size_pt * 2)))
        spacing_match = re.search(r"(?:行距|linespacing|leading)[^0-9]{0,8}(\d+(?:\.\d+)?)\s*(?:pt|磅)", text, flags=re.I)
        if spacing_match:
            spacing_pt = float(spacing_match.group(1))
            if 6 <= spacing_pt <= 72:
                paragraph["line_spacing"] = str(int(round(spacing_pt * 20)))
                paragraph["line_spacing_rule"] = "exact"
        if not font and not paragraph:
            continue
        conflicts = []
        expected_size = font.get("size_half_points")
        actual_size = existing_font.get("size_half_points")
        if expected_size and actual_size and str(expected_size) != str(actual_size):
            conflicts.append({"property": "font.size_half_points", "selected_body_value": actual_size, "comment_value": expected_size})
        expected_family = font.get("east_asia_family")
        actual_family = existing_font.get("east_asia_family")
        if expected_family and actual_family and str(expected_family).lower() != str(actual_family).lower():
            conflicts.append({"property": "font.east_asia_family", "selected_body_value": actual_family, "comment_value": expected_family})
        expected_line = paragraph.get("line_spacing")
        actual_line = existing_paragraph.get("line_spacing")
        actual_rule = str(existing_paragraph.get("line_spacing_rule") or "").lower()
        if expected_line and actual_line and actual_rule == "exact" and str(expected_line) != str(actual_line):
            conflicts.append({"property": "paragraph.line_spacing", "selected_body_value": actual_line, "comment_value": expected_line})
        status = "accepted" if not conflicts else "rejected_conflict"
        return {
            "status": status,
            "target_role": "body",
            "comment_id": str(comment.get("id") or ""),
            "comment_index": comment.get("index"),
            "anchor_paragraph_indexes": anchors,
            "instruction_text": str(comment.get("text") or ""),
            "parsed_format": {"font": font, "paragraph": paragraph},
            "conflict_check": {
                "selected_body_style": body_evidence.get("style_name"),
                "selected_body_style_id": body_evidence.get("style_id"),
                "conflicts": conflicts,
                "result": "no_conflict" if not conflicts else "conflict",
            },
        }
    return None


def apply_comment_body_format(body_evidence: dict, directive: dict | None) -> dict:
    """Apply a pre-validated comment directive without losing named-style evidence."""
    if not directive or directive.get("status") != "accepted":
        return body_evidence
    enriched = copy.deepcopy(body_evidence)
    parsed = directive.get("parsed_format") or {}
    for key in ("direct_format", "effective_format"):
        target = enriched.setdefault(key, {})
        for format_group in ("font", "paragraph"):
            additions = parsed.get(format_group) or {}
            if additions:
                target.setdefault(format_group, {}).update(additions)
    enriched["comment_format_evidence"] = directive
    enriched["source"] = (
        f"{body_evidence.get('source', 'selected official Word body evidence')}; "
        "supplemented by an anchored explicit Word formatting comment after conflict check"
    )
    return enriched


def body_paragraph_spacing_evidence(evidence: str) -> dict:
    """Keep explicit no-gap author guidance separate from a Word style default.

    Word templates often use a paragraph after-space to make instructional
    samples readable, while their prose explicitly says that manuscript body
    paragraphs continue without blank separation. That sentence is stronger
    evidence for the ordinary LaTeX body than a generic ``Normal`` style.
    """
    text = re.sub(r"\s+", " ", str(evidence or "")).strip()
    patterns = (
        r"[^.]{0,120}\bparagraphs?\b[^.]{0,120}\bonly\s+separated\s+by\s+(?:headings?|subheadings?|images?|figures?|tables?|formulae?|equations?)[^.]{0,120}",
        r"[^.]{0,120}\bparagraphs?\b[^.]{0,120}\b(?:without|with no)\s+(?:extra\s+)?(?:space|spacing|blank lines?)[^.]{0,120}",
        r"[^.]{0,120}\bdo\s+not\s+(?:leave|insert|add)\s+(?:an?\s+)?(?:blank line|extra\s+space)\s+(?:between|after)\s+paragraphs?[^.]{0,120}",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return {
                "status": "source",
                "paragraph_skip_pt": 0,
                "source": "explicit official template guidance for continuous body paragraphs",
                "matched_instruction": match.group(0).strip(),
                "mapping": "override generic Word body after-space with zero LaTeX paragraph skip",
            }
    return {
        "status": "not_detected",
        "source": "no explicit continuous-body-paragraph instruction was found",
    }


def infer_paragraph_indent(docx_item: dict | None, language: str) -> str:
    body = body_style_evidence(docx_item)
    body_format = body.get("effective_format", body.get("direct_format", {}))
    first_line = body_format.get("paragraph", {}).get("first_line_twips")
    try:
        points = int(first_line) / 20
        if 3 <= points <= 36:
            return f"{round(points, 1)}pt"
    except (TypeError, ValueError):
        pass
    return "2em" if language == "zh" else "1.5em"


def section_numbering_evidence(docx_item: dict | None) -> dict:
    """Infer only repeated visible first-level heading labels.

    A Word numbering definition can be unused or inherited through a list
    style. Repeated rendered heading labels are safer evidence for a general
    section-counter representation than raw numbering.xml alone.
    """
    headings = [] if not docx_item else docx_item.get("inspection", {}).get("heading_candidates", [])
    roman = []
    alpha = []
    for item in headings if isinstance(headings, list) else []:
        text = str(item.get("text") or "").strip()
        style_name = str(item.get("style_name") or "").lower()
        paragraph = ((item.get("effective_format") or {}).get("paragraph") or {})
        # The broad heading-candidate list can include bibliography entries
        # such as `J. Smith`. Require a semantic heading style or Word outline
        # level before treating a leading letter as a section label.
        if "heading" not in style_name and paragraph.get("outline_level") is None:
            continue
        match = re.match(r"^([IVXLCDM]+|[A-Z])[.)]\s+", text)
        if not match:
            continue
        label = match.group(1)
        if re.fullmatch(r"[IVXLCDM]+", label):
            roman.append(text)
        elif re.fullmatch(r"[A-Z]", label):
            alpha.append(text)
    if len(roman) >= 2:
        return {"profile": "roman", "source": "repeated visible Roman-numeral Word heading labels", "samples": roman[:3], "confidence": "official-template"}
    if len(alpha) >= 2:
        return {"profile": "alpha", "source": "repeated visible alphabetic Word heading labels", "samples": alpha[:3], "confidence": "official-template"}
    return {"profile": "arabic", "source": "documented Temp2TeX default; no repeated non-Arabic first-level heading labels", "confidence": "default"}


def contains(text: str, *needles: str) -> bool:
    lower = text.lower()
    return any(needle.lower() in lower for needle in needles)


def normalize_title(text: str) -> str:
    cleaned = re.sub(r"[*:]+$", "", text.strip())
    cleaned = re.sub(r"[^A-Za-z ]+", "", cleaned).strip().lower()
    return re.sub(r"\s+", " ", cleaned)


def is_affiliation_like(text: str) -> bool:
    """Keep numbered author affiliations out of the manuscript heading tree."""
    lower = text.lower()
    markers = (
        "university", "college", "institute", "laboratory", "department",
        "office", "\u5927\u5b66", "\u5b66\u9662", "\u7814\u7a76\u6240", "\u5b9e\u9a8c\u5ba4", "\u5355\u4f4d", "\u90ae\u7f16",
    )
    return any(marker in lower for marker in markers)


def first_abstract_paragraph_index(inspection: dict) -> int | None:
    """Find the visible abstract boundary before inferring numbered headings."""
    indexes = []
    for paragraph in inspection.get("paragraph_samples", []):
        text = str(paragraph.get("text") or "").strip().lower()
        if text.startswith(("abstract", "摘要", "中文摘要", "英文摘要")):
            try:
                index = int(paragraph.get("index") or 0)
            except (TypeError, ValueError):
                continue
            if index > 0:
                indexes.append(index)
    return min(indexes) if indexes else None


def build_sections(docx_item: dict | None) -> list[dict]:
    if not docx_item:
        return []
    paragraphs = docx_item.get("inspection", {}).get("paragraph_samples", [])
    sections: list[dict] = []
    current: dict | None = None
    seen_abstract = False

    for para in paragraphs:
        text = str(para.get("text", "")).strip()
        if not text:
            continue
        normalized = normalize_title(text)
        if text.lower().startswith("abstract") or text.startswith("\u6458\u8981"):
            seen_abstract = True
        numbered_match = re.match(r"^(?P<label>\d+(?:\.\d+)*|[A-Z])(?P<separator>[.)])?\s+(?P<body>\S.*)", text)
        number_level = numbered_match.group("label").count(".") if numbered_match else None
        numbered_keyword = ""
        if numbered_match:
            numbered_keyword = normalize_title(numbered_match.group("body")).split(" ", 1)[0]
        # A bare leading letter/number appears frequently in prose, equations,
        # and conversion tables. Use it as a heading fallback only when it has
        # an explicit separator or begins with a known manuscript section;
        # Word outline/style evidence remains the stronger path.
        is_numbered_title = bool(numbered_match) and bool(
            numbered_match.group("separator")
            or (numbered_match.group("label").isdigit() and numbered_keyword in KNOWN_SECTION_TITLES)
        )
        effective = para.get("effective_format") or para.get("direct_format") or {}
        outline = effective.get("paragraph", {}).get("outline_level")
        try:
            outline_level = int(outline)
        except (TypeError, ValueError):
            outline_level = None
        style_name = str(para.get("style_name") or "").lower().replace("_", " ")
        style_match = re.search(r"(?:heading|head|section)\s*([1-5])\b", style_name)
        style_level = int(style_match.group(1)) - 1 if style_match else None
        heading_level = outline_level if outline_level is not None and 0 <= outline_level <= 4 else style_level
        scaffold_noise = any(marker in style_name for marker in ("reference", "ref ", "ref_", "bibliograph", "citation", "caption", "equation", "table", "figure", "footnote"))
        if numbered_match and numbered_match.group("label").isalpha():
            # Letter-prefixed bibliography entries (for example "J. Smith")
            # are common. Treat alphabetic labels as headings only when Word
            # supplies explicit heading/outline evidence.
            is_numbered_title = heading_level is not None
        if scaffold_noise:
            is_numbered_title = False
        front_role = any(marker in style_name for marker in ("title", "author", "affiliation", "address", "abstract", "keyword"))
        is_outline_heading = heading_level is not None and len(text) <= 180 and not is_affiliation_like(text) and not front_role and not scaffold_noise
        is_title = (
            normalized in KNOWN_SECTION_TITLES
            or normalized == "highlights"
            or is_outline_heading
            or (seen_abstract and is_numbered_title and not is_affiliation_like(text))
        )
        if is_title:
            if current:
                sections.append(current)
            title = re.sub(r"[*:]+$", "", text).strip()
            current = {
                "title": title,
                "level": max(0, min(4, heading_level if heading_level is not None else number_level or 0)),
                "paragraphs": [],
            }
            continue
        if current is None:
            current = {"title": "Template Front Matter", "paragraphs": []}
        current["paragraphs"].append(text)

    if current:
        sections.append(current)
    return sections


def section_paragraphs(sections: list[dict], title: str) -> list[str]:
    target = normalize_title(title)
    for section in sections:
        if normalize_title(str(section.get("title", ""))) == target:
            return [str(p) for p in section.get("paragraphs", []) if str(p).strip()]
    return []


def first_section_paragraphs(sections: list[dict], titles: tuple[str, ...]) -> list[str]:
    """Return paragraphs for the first explicitly named section in source order."""
    for title in titles:
        paragraphs = section_paragraphs(sections, title)
        if paragraphs:
            return paragraphs
    return []


def keyword_label_from_evidence(keyword_style: dict, language: str) -> str:
    """Preserve a visible Word keyword label instead of standardizing it."""
    samples = []
    if isinstance(keyword_style, dict):
        sample = str(keyword_style.get("sample_text") or "").strip()
        if sample:
            samples.append(sample)
        values = keyword_style.get("sample_texts", [])
        if isinstance(values, list):
            samples.extend(str(value).strip() for value in values if str(value).strip())
    pattern = re.compile(
        r"^\s*((?:keywords?|key\s+words?|index\s+terms?|\u5173\u952e\u8bcd))\s*([:\uff1a\-\u2013\u2014]?)",
        re.I,
    )
    for sample in samples:
        match = pattern.match(sample)
        if not match:
            continue
        label = match.group(1)
        punctuation = match.group(2) or ("\uff1a" if label == "\u5173\u952e\u8bcd" else ":")
        return f"{label}{punctuation}"
    return "\u5173\u952e\u8bcd\uff1a" if language == "zh" else "Keywords:"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", help="source_inventory.json")
    parser.add_argument("--notes", help="Official guide notes text file")
    parser.add_argument("--output", default="template_spec.json")
    parser.add_argument("--journal-name", default=None)
    parser.add_argument("--publisher", default=None)
    args = parser.parse_args()

    inventory_path = Path(args.inventory).expanduser().resolve()
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    notes = read_text(Path(args.notes).expanduser().resolve() if args.notes else None)
    docx = first_docx(inventory)
    docx_text = collect_docx_text(docx)
    source_names = "\n".join(str(item.get("name", "")) for item in inventory.get("files", []))
    evidence = f"{notes}\n{source_names}\n{docx_text}"
    language = docx.get("inspection", {}).get("language_hint", "en") if docx else "en"
    journal_name = args.journal_name or ("Ecological Indicators" if contains(evidence, "Ecological Indicators") else "Journal Template")
    publisher = args.publisher or ("Elsevier" if contains(evidence, "Elsevier") else "")
    columns = infer_columns(docx, evidence)
    body_columns_start_after_front_matter = body_column_transition(docx, columns)
    style_evidence = body_style_evidence(docx)
    abstract_style_evidence = role_evidence_or_default(role_style_evidence(docx, "abstract"), "abstract")
    keyword_style_evidence = role_evidence_or_default(role_style_evidence(docx, "keyword"), "keywords")
    title_style_evidence = role_evidence_or_default(role_style_evidence(docx, "title"), "title")
    author_style_evidence = role_evidence_or_default(role_style_evidence(docx, "author"), "author")
    affiliation_style_evidence = role_evidence_or_default(
        role_style_evidence(docx, "affiliation", "address", "institution"),
        "affiliation",
    )
    table_caption_style_evidence = role_evidence_or_default(
        visible_caption_evidence(docx, "table") or role_style_evidence(docx, "table caption", "caption"),
        "table_caption",
    )
    figure_caption_style_evidence = role_evidence_or_default(
        visible_caption_evidence(docx, "figure") or role_style_evidence(docx, "figure caption", "caption"),
        "figure_caption",
    )
    table_note_style_evidence = role_style_evidence(docx, "table footer", "table note")
    reference_entry_style_evidence = (
        role_style_evidence(docx, "references", "reference", "bibliography")
        or visible_reference_entry_evidence(docx)
    )
    english_front_matter_styles = english_front_matter_evidence(docx)
    heading_style_evidences = {
        f"level{level}": heading_style_evidence(docx, level)
        for level in range(5)
    }
    header_footer = header_footer_evidence(docx)
    header_footer["safe_text_parts"] = text_only_furniture_parts(header_footer)
    page_frame = infer_page_frame(docx, columns)
    representative_page_section = representative_section(docx, columns)
    column_widths_twips, columns_equal_width = representative_column_widths(docx, columns)
    column_breaks = column_break_evidence(docx)
    representative_page_section = representative_section(docx, columns)
    word_media = docx.get("inspection", {}).get("images", []) if docx else []
    vml_shapes = docx.get("inspection", {}).get("vml_shapes", []) if docx else []
    if docx:
        for part in docx.get("inspection", {}).get("header_footer_parts", []):
            if isinstance(part, dict):
                vml_shapes.extend(part.get("vml_shapes", []))
    table_layout = table_layout_evidence(docx)
    figure_layout = figure_layout_evidence(docx)
    if table_layout:
        table_layout["span_evidence"] = object_span_evidence(docx, table_layout, "table", columns)
        table_layout["span_mode"] = table_layout["span_evidence"].get("mode", "uncertain")
    if figure_layout:
        figure_layout["span_evidence"] = object_span_evidence(docx, figure_layout, "figure", columns)
        figure_layout["span_mode"] = figure_layout["span_evidence"].get("mode", "uncertain")
    table_caption_position, table_caption_evidence = caption_position_evidence(table_layout, "above", "table")
    figure_caption_position, figure_caption_evidence = caption_position_evidence(figure_layout, "below", "figure")
    table_caption_spacing = caption_object_spacing_evidence(
        table_caption_style_evidence,
        table_layout,
        table_caption_position,
        table_caption_evidence,
    )
    figure_caption_spacing = caption_object_spacing_evidence(
        figure_caption_style_evidence,
        figure_layout,
        figure_caption_position,
        figure_caption_evidence,
    )
    float_spacing_evidence = float_text_spacing_evidence(table_layout, figure_layout)
    equation_layout = equation_layout_evidence(docx)
    list_layout = list_layout_evidence(docx)
    footnote_style = footnote_style_evidence(docx)
    endnote_style = endnote_style_evidence(docx)
    footnote_count = int(docx.get("inspection", {}).get("footnote_count", 0) or 0) if docx else 0
    endnote_count = int(docx.get("inspection", {}).get("endnote_count", 0) or 0) if docx else 0
    footnote_numbering = docx.get("inspection", {}).get("footnote_numbering", {}) if docx else {}
    endnote_numbering = docx.get("inspection", {}).get("endnote_numbering", {}) if docx else {}
    footnote_references = docx.get("inspection", {}).get("footnote_references", []) if docx else []
    endnote_references = docx.get("inspection", {}).get("endnote_references", []) if docx else []
    cover = cover_evidence(docx)
    toc = toc_evidence(docx)
    line_numbering = line_number_evidence(docx, evidence)
    fallbacks = inaccessible_word_fallbacks(inventory, inventory_path)
    content_controls = docx.get("inspection", {}).get("content_controls", []) if docx else []
    comments_evidence = docx.get("inspection", {}).get("comments", []) if docx else []
    body_comment_directive = comment_body_format_directive(comments_evidence, style_evidence)
    style_evidence = apply_comment_body_format(style_evidence, body_comment_directive)
    font_size = infer_font_size(docx, evidence, columns, style_evidence)
    font_family = infer_font_family(docx, style_evidence)
    cjk_font_family = infer_cjk_font_family(docx, style_evidence)

    text_boxes = docx.get("inspection", {}).get("text_boxes", []) if docx else []
    if text_boxes:
        fallbacks.append({
            "area": "front_matter.text_boxes",
            "missing_requirement": "Word text-box placement cannot be reconstructed from text order alone.",
            "fallback_used": "Retained non-flow text-box content as source evidence; did not promote it into manuscript body flow.",
            "source_checked": str(inventory_path),
            "latex_location": "template_spec.json / format_gap_log.md",
        })

    references_evidence = reference_style_evidence(docx, evidence)
    references_style = references_evidence["style"]
    abstract_limit = 250 if contains(notes, "250 words") else 400 if contains(evidence, "400 words") else None
    keyword_max = 7 if contains(notes, "1 to 7 keywords", "1 to 7") else 6 if contains(evidence, "maximum of six keywords") else None

    if abstract_limit is None:
        fallbacks.append({
            "area": "abstracts.word_limit",
            "missing_requirement": "No abstract word limit found in official notes or template text.",
            "fallback_used": "English default: concise abstract without hard word limit in LaTeX.",
            "source_checked": str(inventory_path),
            "latex_location": "main.tex",
        })
    if equation_layout.get("present") and equation_layout.get("numbering") == "unverified":
        fallbacks.append({
            "area": "equations.numbering",
            "missing_requirement": "Official Word OMML samples do not expose a reliable display-equation number pattern.",
            "fallback_used": "Generated an editable numbered LaTeX equation fixture; verify display and number placement against a rendered source page.",
            "source_checked": str(inventory_path),
            "latex_location": "journal-template.cls / main.tex",
        })
    if list_layout.get("present"):
        fallbacks.append({
            "area": "body.lists",
            "missing_requirement": "Word list label spacing and multi-level restart behavior need same-content PDF confirmation.",
            "fallback_used": "Exposed editable journalitemize/journalenumerate interfaces using the first visible Word list evidence.",
            "source_checked": str(inventory_path),
            "latex_location": "journal-template.cls / main.tex",
        })
    if figure_layout.get("selection_status") in {"no_caption_attached_body_figure", "inline_unlabeled_body_figure"}:
        fallbacks.append({
            "area": "figures.layout_evidence",
            "missing_requirement": "Word body drawings exist, but none has an external adjacent or nearby figure-caption relation.",
            "fallback_used": "An inline drawing may supply geometry only; anchored candidates remain evidence-only. Do not promote caption order or a float policy without same-content PDF confirmation.",
            "source_checked": str(inventory_path),
            "latex_location": "template_spec.json / journal-template.cls / format_gap_log.md",
        })

    sections = build_sections(docx)
    highlight_guidance = section_paragraphs(sections, "Highlights")
    english_abstract_guidance = first_section_paragraphs(sections, ("Abstract", "English Abstract"))
    chinese_abstract_guidance = first_section_paragraphs(sections, ("\u6458\u8981", "\u4e2d\u6587\u6458\u8981"))
    # Mixed templates normally present the Chinese abstract first. Preserve both
    # samples instead of allowing the English heading to overwrite it.
    if language == "zh":
        abstract_guidance = chinese_abstract_guidance or english_abstract_guidance
    elif language == "mixed":
        abstract_guidance = chinese_abstract_guidance or english_abstract_guidance
    else:
        abstract_guidance = english_abstract_guidance or chinese_abstract_guidance
    abstract_structure = abstract_structure_evidence(docx, abstract_style_evidence)
    abstract_style_evidence = abstract_structure["content_style"]
    abstract_label_style_evidence = abstract_structure["label_style"]
    abstract_content_box = content_box_evidence(abstract_style_evidence)
    abstract_entry_style = (
        abstract_label_style_evidence
        if abstract_structure["label_mode"] in {"separate", "default"}
        else abstract_style_evidence
    )
    front_matter_boundaries = {
        "title_to_author": front_matter_boundary_evidence(title_style_evidence, author_style_evidence, 8),
        "author_to_affiliation": front_matter_boundary_evidence(author_style_evidence, affiliation_style_evidence, 6),
        "affiliation_to_abstract": front_matter_boundary_evidence(affiliation_style_evidence, abstract_entry_style, 12),
        "abstract_to_keywords": front_matter_boundary_evidence(abstract_style_evidence, keyword_style_evidence, 6),
    }
    if abstract_structure["label_mode"] == "separate":
        front_matter_boundaries["abstract_label_to_content"] = front_matter_boundary_evidence(
            abstract_label_style_evidence, abstract_style_evidence, 4
        )
    section_numbering = section_numbering_evidence(docx)
    keyword_label = keyword_label_from_evidence(keyword_style_evidence, language)
    spec = {
        "journal": {
            "name": journal_name,
            "publisher": publisher,
            "source_urls": [],
            "language": language if language in {"zh", "mixed"} else "en",
            "short_title": journal_name,
        },
        "source_annotations": {
            "content_controls": content_controls[:80],
            "comments": comments_evidence[:40],
            "comment_format_directives": [body_comment_directive] if body_comment_directive else [],
            "instruction": (
                "Use control metadata and Word comments as supporting template evidence. "
                "Do not emit comment text into manuscript body content or claim it is visible source text. "
                "An explicit anchored formatting directive is adopted only after its target role, parsed value, and conflict check are recorded."
            ),
        },
        "document": {
            "paper": infer_paper(docx, columns),
            "paper_dimensions_mm": infer_paper_dimensions_mm(docx, columns),
            "columns": columns,
            "font_size_pt": font_size,
            "font_family": font_family,
            "font_family_mode": "evidence_only" if font_family else "default",
            "cjk_font_family": cjk_font_family,
            "cjk_font_mode": "evidence_only" if cjk_font_family else "default",
            "engine": "xelatex",
            "class_strategy": "cls",
        },
        "page": {
            "margins_mm": infer_margins(docx, columns),
            **page_frame,
            "representative_section_index": representative_page_section.get("index") if representative_page_section else None,
            "representative_section_source": "most frequent manuscript-body Word section frame",
            "representative_section_index": representative_page_section.get("index") if representative_page_section else None,
            "representative_section_source": "most frequent manuscript-body Word section frame",
            "section_flow": section_flow_evidence(docx),
            "line_spacing": infer_line_spacing(docx, evidence, columns, style_evidence),
            "body_paragraph_spacing_evidence": body_paragraph_spacing_evidence(evidence),
            "paragraph_indent": infer_paragraph_indent(docx, language),
            "column_sep_mm": infer_column_sep_mm(docx, columns),
            "column_widths_twips": column_widths_twips,
            "columns_equal_width": columns_equal_width,
            "source_body_style": style_evidence,
            "header_footer_profile": "source-backed-custom" if header_footer["parts"] else "empty",
            "header_footer_evidence": header_footer,
            "first_page_style": "fancy" if header_footer["active_variants"] else "empty",
            "header_footer_auto_apply": False,
            "header_footer_text_auto_apply": text_only_furniture_evidence(header_footer),
            "first_page_furniture_auto_apply": False,
            "float_spacing_evidence": float_spacing_evidence,
        },
        "front_matter": {
            "title": True,
            "authors": True,
            "affiliations": True,
            "corresponding_author": True,
            "body_column_transition_after_front_matter": body_columns_start_after_front_matter,
            "present_address_footnotes": contains(evidence, "present address", "permanent address"),
            "highlights": contains(evidence, "highlights"),
            "highlights_guidance": highlight_guidance,
            "graphical_abstract": contains(evidence, "graphical abstract"),
            "cover_mode": cover.get("mode", "not_detected"),
            "cover_evidence": cover,
            "column_break_evidence": column_breaks,
            "title_style": title_style_evidence,
            "author_style": author_style_evidence,
            "author_layout": author_layout_evidence(author_style_evidence),
            "affiliation_style": affiliation_style_evidence,
            "english_title_style": role_evidence_or_default(english_front_matter_styles.get("title", {}), "english_title"),
            "english_author_style": role_evidence_or_default(english_front_matter_styles.get("author", {}), "english_author"),
            "english_affiliation_style": role_evidence_or_default(english_front_matter_styles.get("affiliation", {}), "english_affiliation"),
            "english_abstract_style": role_evidence_or_default(english_front_matter_styles.get("abstract", {}), "english_abstract"),
            "english_keywords_style": role_evidence_or_default(english_front_matter_styles.get("keywords", {}), "english_keywords"),
            "spacing_boundaries": front_matter_boundaries,
        },
        "abstracts": {
            "english": language != "zh",
            "chinese": language in {"zh", "mixed"},
            "keywords": True,
            "word_limit": abstract_limit,
            "keyword_max": keyword_max,
            "source_text": " ".join(abstract_guidance[:2]) if abstract_guidance else None,
            "english_source_text": (
                " ".join(english_abstract_guidance[:2])
                if language == "mixed" and english_abstract_guidance
                else None
            ),
            "content_box": abstract_content_box,
            "style": abstract_style_evidence,
            "label_style": abstract_label_style_evidence,
            "keyword_style": keyword_style_evidence,
            "keyword_label": keyword_label,
            "label": abstract_structure["label"],
            "label_mode": abstract_structure["label_mode"],
            "label_paragraph_index": abstract_structure.get("label_paragraph_index"),
            "content_paragraph_index": abstract_structure.get("content_paragraph_index"),
            "layout_mode": abstract_structure["layout_mode"],
            "layout_evidence": abstract_structure["source"],
        },
        "body": {
            "section_numbering": "I, I.1, I.1.1" if section_numbering["profile"] == "roman" else "A, A.1, A.1.1" if section_numbering["profile"] == "alpha" else "1, 1.1, 1.1.1",
            "section_numbering_evidence": section_numbering,
            "toc": toc["enabled"],
            "toc_evidence": toc,
            "lists": list_layout,
            "toc_depth": toc.get("depth"),
            "line_numbers": line_numbering["enabled"],
            "line_number_evidence": line_numbering,
            "sections": sections,
            "content_box": content_box_evidence(style_evidence),
            "keyword_content_box": content_box_evidence(keyword_style_evidence),
            "heading_styles": heading_style_evidences,
        },
        "tables": {
            "caption_position": table_caption_position,
            "caption_position_evidence": table_caption_evidence,
            "caption_spacing_evidence": table_caption_spacing,
            "notes": True,
            "booktabs": True,
            "avoid_vertical_rules": contains(evidence, "avoid vertical rules"),
            "caption_style": table_caption_style_evidence,
            "note_style": table_note_style_evidence,
            "layout_evidence": table_layout,
        },
        "figures": {
            "caption_position": figure_caption_position,
            "caption_position_evidence": figure_caption_evidence,
            "caption_spacing_evidence": figure_caption_spacing,
            "separate_files_required": contains(evidence, "separate files", "separate file"),
            "included_in_text": contains(evidence, "included in the text"),
            "subfigures": True,
            "caption_style": figure_caption_style_evidence,
            "layout_evidence": figure_layout,
        },
        "equations": equation_layout,
        "references": {
            "style": references_style,
            "style_evidence": references_evidence,
            "bib_engine": "thebibliography",
            "official_bst": None,
            "entry_style": reference_entry_style_evidence,
        },
        "footnotes": {
            "enabled": bool(footnote_style) or bool(footnote_references),
            "style": footnote_style,
            "marker_style": footnote_numbering.get("marker_style", "source-not-extracted"),
            "marker_evidence": footnote_numbering,
            "reference_evidence": footnote_references[:40],
            "count_in_template": footnote_count,
        },
        "endnotes": {
            "enabled": bool(endnote_style) or bool(endnote_references),
            "style": endnote_style,
            "count_in_template": endnote_count,
            "placement": "source-not-extracted",
            "marker_evidence": endnote_numbering,
            "reference_evidence": endnote_references[:40],
        },
        "appendices": {
            "enabled": contains(evidence, "appendix", "appendices"),
            "numbering": "A, B; Eq. (A.1); Table A.1; Fig. A.1",
        },
        "statements": {
            "acknowledgements_before_references": contains(evidence, "acknowledgements", "acknowledgments"),
            "credit_author_statement": contains(evidence, "credit", "author statement"),
            "declaration_of_competing_interest": contains(evidence, "competing interest"),
            "data_availability": contains(evidence, "data availability", "data statement"),
        },
        "assets": {
            "word_media": word_media,
            "vml_shapes": vml_shapes[:100],
            "header_footer_parts": header_footer["parts"],
            "text_boxes": text_boxes,
            "extraction_required": bool(word_media),
        },
        "fallbacks": fallbacks,
    }

    output = Path(args.output).expanduser().resolve()
    output.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
