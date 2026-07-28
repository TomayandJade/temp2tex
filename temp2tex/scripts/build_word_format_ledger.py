#!/usr/bin/env python3
"""Create a paragraph-and-run format ledger from an OpenXML Word template."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from inspect_sources import (
    inspect_docx,
    invalid_openxml_word_details,
    is_openxml_word_package,
    run_soffice_convert,
    tool_candidates,
)


ROLE_OWNERS = {
    "front_matter.article_type": {"owner": "main.tex", "interface": "\\articletype{}"},
    "front_matter.title": {"owner": "main.tex", "interface": "\\title{} + \\maketitle"},
    "front_matter.author": {"owner": "main.tex", "interface": "\\author{}"},
    "front_matter.affiliation": {"owner": "main.tex", "interface": "\\affiliation{}"},
    "front_matter.abstract": {"owner": "main.tex + journal-template.cls", "interface": "abstract environment"},
    "front_matter.keywords": {"owner": "main.tex + journal-template.cls", "interface": "\\tempTwoTexKeywords{}"},
    "front_matter.metadata": {"owner": "main.tex", "interface": "editable front-matter metadata block"},
    "front_matter.english_title": {"owner": "main.tex", "interface": "\\englishtitle{}"},
    "front_matter.english_author": {"owner": "main.tex", "interface": "\\englishauthor{}"},
    "front_matter.english_affiliation": {"owner": "main.tex", "interface": "\\englishaffiliation{}"},
    "front_matter.english_abstract": {"owner": "main.tex", "interface": "\\englishabstract{}"},
    "front_matter.english_keywords": {"owner": "main.tex", "interface": "\\englishkeywords{}"},
    "heading.level0": {"owner": "journal-template.cls", "interface": "\\section"},
    "heading.level1": {"owner": "journal-template.cls", "interface": "\\subsection"},
    "heading.level2": {"owner": "journal-template.cls", "interface": "\\subsubsection"},
    "heading.level3": {"owner": "journal-template.cls", "interface": "\\paragraph"},
    "heading.level4": {"owner": "journal-template.cls", "interface": "\\subparagraph"},
    "body.list_system": {"owner": "journal-template.cls", "interface": "journalitemize/journalenumerate labels, counters, levels, and indentation"},
    "body.list_item": {"owner": "main.tex + journal-template.cls", "interface": "\\item in a journal list environment"},
    "equation.system": {"owner": "journal-template.cls", "interface": "journalequation environment, counter, tag, and display spacing settings"},
    "equation.instance": {"owner": "equations.tex + main.tex", "interface": "editable OMML conversion candidate or explicit manual-translation record"},
    "block.decoration": {"owner": "journal-template.cls + main.tex", "interface": "source-specific framed/shaded block environment or named macro"},
    "body.paragraph": {"owner": "journal-template.cls", "interface": "body font and paragraph settings"},
    "paragraph.layout": {"owner": "main.tex + journal-template.cls", "interface": "journalblankparagraph source-backed vertical-spacing or break helper"},
    "front_matter.metadata_table": {"owner": "journal-template.cls", "interface": "maketitle metadata block"},
    "cover.structure": {"owner": "cover.tex + journal-template.cls", "interface": "journalcover environment and first-page mode"},
    "toc.structure": {"owner": "main.tex", "interface": "tableofcontents and tocdepth"},
    "toc.layout": {"owner": "journal-template.cls + main.tex", "interface": "source-specific TOC indentation and leader/tab layout"},
    "page.frame": {"owner": "journal-template.cls", "interface": "geometry page size, margins, header/footer distances"},
    "page.columns": {"owner": "journal-template.cls + main.tex", "interface": "journal column helpers and source section transitions"},
    "page.text_grid": {"owner": "journal-template.cls + main.tex", "interface": "source-specific Word document-grid and local paragraph grid mapping"},
    "page.numbering": {"owner": "journal-template.cls + main.tex", "interface": "journalpagenumbering section-boundary helper"},
    "line.numbering": {"owner": "journal-template.cls + main.tex", "interface": "journallinenumbering and line-numbering.tex section candidates"},
    "paragraph.tab_stops": {"owner": "journal-template.cls + main.tex", "interface": "role-specific tab layout; no document-wide tab default"},
    "paragraph.drop_cap": {"owner": "journal-template.cls + main.tex", "interface": "journaldropcap with source-specific lines, gap, and following-text mapping"},
    "run.character_effects": {"owner": "journal-template.cls + main.tex", "interface": "role-specific local character-effect wrappers; no global visual default"},
    "run.character_styles": {"owner": "journal-template.cls + main.tex", "interface": "role-specific named Word character-style mapping with visible-span verification"},
    "document.theme": {"owner": "journal-template.cls + main.tex", "interface": "role-specific Word theme color/font alias mapping with render-confirmed LaTeX values"},
    "word.unmodeled_format": {"owner": "journal-template.cls + main.tex", "interface": "explicit source-property classification and role-specific mapping before fidelity claim"},
    "footnote.system": {"owner": "journal-template.cls", "interface": "footnote marker, numbering, separator, and placement settings"},
    "endnote.system": {"owner": "journal-template.cls", "interface": "endnote marker, numbering, and print location settings"},
    "references.system": {"owner": "journal-template.cls + main.tex", "interface": "bibliography backend, heading, numbering, and entry environment"},
    "appendix.system": {"owner": "journal-template.cls + main.tex", "interface": "appendix boundary, counters, and numbering helper"},
    "table.structure": {"owner": "journal-template.cls", "interface": "journaltable grid, width, and header helpers"},
    "table.cell": {"owner": "main.tex + journal-template.cls", "interface": "journaltable cell content and role-local table helpers"},
    "table.caption": {"owner": "journal-template.cls", "interface": "journaltable + caption setup"},
    "figure.placement": {"owner": "journal-template.cls", "interface": "journal figure width, placement, and flow helpers"},
    "figure.caption": {"owner": "journal-template.cls", "interface": "journalfigure + caption setup"},
    "references.heading": {"owner": "journal-template.cls", "interface": "bibliography heading"},
    "references.entry": {"owner": "journal-template.cls", "interface": "bibliography backend and entry layout"},
    "appendix.heading": {"owner": "journal-template.cls", "interface": "\\journalappendix + \\section"},
    "back_matter.declaration": {"owner": "journal-template.cls + main.tex", "interface": "\\journaldeclaration{label}{content}"},
    "back_matter.license": {"owner": "journal-template.cls + main.tex", "interface": "\\journallicense{content}"},
    "back_matter.author_bio": {"owner": "journal-template.cls + main.tex", "interface": "\\journalauthorbio{name}{content}"},
    "running_furniture": {"owner": "journal-template.cls", "interface": "header/footer definitions"},
    "footnote.content": {"owner": "main.tex + journal-template.cls", "interface": "\\footnote{} and footnote settings"},
    "endnote.content": {"owner": "main.tex + journal-template.cls", "interface": "endnote interface and settings"},
    "floating_text": {"owner": "main.tex + journal-template.cls", "interface": "named editable floating-text macro or asset"},
}

METADATA_KINDS = (
    "publication_id",
    "doi",
    "dates",
    "funding",
    "contributor_note",
    "editorial_note",
)
for _metadata_kind in METADATA_KINDS:
    ROLE_OWNERS[f"front_matter.metadata.{_metadata_kind}"] = {
        "owner": "main.tex + journal-template.cls",
        "interface": rf"\journalmetadata[{_metadata_kind}]{{\journalmetadatalabel[{_metadata_kind}]{{label}} value}}",
    }

AFFILIATION_MARKERS = ("大学", "学院", "研究所", "实验室", "单位", "地址", "邮编", "address", "university", "college", "institute", "laboratory", "department", "affiliation", "institution", "faculty", "üniversite", "fakülte", "bölüm")
ABSTRACT_MARKERS = ("摘要", "abstract", "öz")
KEYWORD_MARKERS = ("关键词", "关键字", "keywords", "key words", "index terms", "anahtar kelimeler")
REFERENCE_MARKERS = ("参考文献", "references", "bibliography")
APPENDIX_MARKERS = ("附录", "附錄", "appendix", "appendices")


METADATA_MARKERS = ("基金项目", "作者简介", "通讯作者", "收稿日期", "中图分类号", "doi", "funding", "corresponding author", "received", "accepted", "revised", "online", "published", "date of publication", "date of current version", "digital object identifier", "academic editor", "handling editor", "editor-in-chief", "email", "e-mail", "orcid", "journal homepage", "available online", "e-issn", "issn", "crossmark", "article info")
METADATA_INLINE_MARKERS = ("received:", "accepted:", "revised:", "published:", "/received", "/accepted", "/revised", "/published")
RUNNING_TITLE_MARKERS = ("short running-title", "short running title", "short title", "running title")
ARTICLE_TYPE_MARKERS = (
    "文章类型", "论文类型", "稿件类型", "文稿类型",
    "article type", "type of the paper", "paper type", "manuscript type",
    "article category", "article classification",
)
TITLE_PLACEHOLDER_MARKERS = ("论文标题", "文章标题", "稿件标题", "title", "title of", "article title", "paper title", "manuscript title", "makale başlığı", "başlık")
GUIDANCE_MARKERS = (
    "版心", "排版", "字体", "字号", "行距", "字数", "投稿", "本刊", "模板", "模版", "以下为", "请", "应采用", "一般应", "不应", "不必", "不得", "建议", "原则上", "以利于", "不能含", "replace", "delete", "insert", "please", "do not", "instruction", "template",
)
MIXED_FRONT_MATTER_GUIDANCE_MARKERS = (
    "不留空", "以逗号隔开", "姓前名后", "全部大写", "首字母", "均小写", "连字符", "宜多选", "以分号隔开", "个~", "个-", "个至",
    "these instructions", "use this document", "enter key words", "enter keywords", "key words or phrases", "separated by commas",
)
ENGLISH_INSTRUCTION_PATTERN = re.compile(
    r"\b(?:must|should|shall|please)\b|\b(?:do|should)\s+not\b|"
    r"\bnot\s+exceed\b|\buse\s+(?:this|the)\s+style\b|\b(?:font|size)\s*\d",
    re.IGNORECASE,
)
EDITORIAL_IMPERATIVE_PATTERN = re.compile(
    r"^\s*(?:(?:[*\u2020\u2021#]|[a-z]|\d+[.)])\s+)?(?:please|list|include|present|clearly|provide|enter|use|replace|delete|"
    r"authors?\s+are|bullets?\s+are|do\s+not|must|should|shall)\b",
    re.IGNORECASE,
)
EXAMPLE_HEADING_PATTERN = re.compile(
    r"^\s*(?:references?|bibliography)\s+examples?\b",
    re.IGNORECASE,
)
HIGHLIGHTS_LABEL_PATTERN = re.compile(r"^highlights?[*:.-]*$", re.IGNORECASE)
INLINE_PARENTHETICAL_INSTRUCTION_START = re.compile(
    r"\s+(?=\((?:use|please|do\s+not|should|must|enter|replace|delete)\b)",
    re.IGNORECASE,
)
PARENTHETICAL_TYPOGRAPHY_PATTERN = re.compile(
    r"(?:[初一二三四五六七八九十小]号|\d+(?:\.\d+)?\s*(?:pt|磅)|宋体|黑体|楷体|仿宋|Times New Roman)",
    re.IGNORECASE,
)


def normalized(value: str) -> str:
    return re.sub(r"\s+", "", value or "").lower()


def starts_with(value: str, markers: tuple[str, ...]) -> bool:
    compact = re.sub(r"^[*†‡•]+", "", normalized(value))
    return any(compact.startswith(normalized(marker)) for marker in markers)


def contains_marker(value: str, markers: tuple[str, ...]) -> bool:
    compact = normalized(value)
    return any(normalized(marker) in compact for marker in markers)


def is_metadata_line(text: str) -> bool:
    compact = normalized(text)
    doi_only = bool(re.match(r"^(?:https?://)?(?:dx\.)?doi\.org/|^10\.\d{4,9}/", compact))
    return doi_only or starts_with(text, METADATA_MARKERS) or (
        len(normalized(text)) <= 320 and contains_marker(text, METADATA_INLINE_MARKERS)
    )


def metadata_kind_for_line(text: str) -> str | None:
    """Return a typed metadata role only for an explicit leading label.

    Reference entries frequently contain DOI strings.  They are publication
    metadata only when the Word paragraph itself begins with a metadata label
    (or a bare DOI/DOI URL field), not when DOI occurs in body prose.
    """
    compact = re.sub(r"^[*\u2020\u2021#]+", "", normalized(text))
    if re.match(r"^(?:doi[:\uff1a]?|(?:https?://)?(?:dx\.)?doi\.org/|10\.\d{4,9}/)", compact):
        return "doi"
    if re.match(
        r"^(?:classification|classificat|article(?:id|number)|e?-?issn|coden|"
        r"\u4e2d\u56fe\u5206\u7c7b|\u6587\u732e\u6807\u8bc6|\u6587\u7ae0\u7f16\u53f7|\u5206\u7c7b\u53f7)",
        compact,
    ):
        return "publication_id"
    if re.match(
        r"^(?:received|accepted|revised|published|publicationdate|submitted|"
        r"\u6536\u7a3f|\u4fee\u56de|\u5f55\u7528|\u51fa\u7248\u65e5\u671f|\u6295\u7a3f\u65e5\u671f)",
        compact,
    ):
        return "dates"
    if re.match(r"^(?:funding|fundedby|grant|supportedby|\u57fa\u91d1|\u8d44\u52a9)", compact):
        return "funding"
    if re.match(
        r"^(?:authorbiography|authorinformation|authorcontribution|correspondence|"
        r"\u4f5c\u8005\u7b80\u4ecb|\u4f5c\u8005\u4fe1\u606f|\u4f5c\u8005\u8d21\u732e|\u901a\u4fe1\u8054\u7cfb\u4eba|\u901a\u8baf\u4f5c\u8005)",
        compact,
    ):
        return "contributor_note"
    if re.match(r"^(?:copyright|editorialnote|editor'snote|\u7248\u6743\u6240\u6709)", compact):
        return "editorial_note"
    return None


def is_running_title_line(text: str) -> bool:
    return starts_with(str(text or "").strip("<>[]() "), RUNNING_TITLE_MARKERS)


def is_article_type_line(text: str) -> bool:
    """Recognize a front-matter classification without promoting it to title."""
    return starts_with(text, ARTICLE_TYPE_MARKERS)


def is_highlights_label(text: str) -> bool:
    return bool(HIGHLIGHTS_LABEL_PATTERN.fullmatch(normalized(text)))


def is_title_placeholder(text: str) -> bool:
    return starts_with(text, TITLE_PLACEHOLDER_MARKERS)


def standalone_label_role(text: str) -> str | None:
    """Return a semantic role only for a run containing a bare visible label.

    This preserves a label such as ``ABSTRACT:`` when an adjacent run in the
    same Word paragraph is editorial guidance. It deliberately rejects labels
    with an example suffix, such as ``References Example:``, because those are
    scaffold text rather than a manuscript heading.
    """
    compact = normalized(text)
    for role, markers in (
        ("front_matter.abstract", ABSTRACT_MARKERS),
        ("front_matter.keywords", KEYWORD_MARKERS),
        ("references.heading", REFERENCE_MARKERS),
        ("appendix.heading", APPENDIX_MARKERS),
    ):
        for marker in markers:
            normalized_marker = normalized(marker)
            if not compact.startswith(normalized_marker):
                continue
            remainder = compact[len(normalized_marker):]
            if re.fullmatch(r"[:：.。\-–—]*", remainder or ""):
                return role
    return None


def has_explicit_red_format(paragraph: dict) -> bool:
    candidates = [paragraph.get("direct_format"), paragraph.get("effective_format")]
    candidates.extend(
        value
        for span in paragraph.get("format_spans") or []
        if isinstance(span, dict)
        for value in (span.get("direct_format"), span.get("effective_format"))
    )
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        color = str((candidate.get("font") or {}).get("color") or "").upper()
        if color in {"FF0000", "FFFF0000"}:
            return True
    return False


def guidance_evidence(paragraph: dict) -> dict | None:
    """Identify source-visible editorial instructions without discarding them."""
    text = str(paragraph.get("format_span_text") or paragraph.get("text") or "").strip()
    if not text or is_title_placeholder(text) or is_metadata_line(text):
        return None
    compact = normalized(text)
    matched = [marker for marker in GUIDANCE_MARKERS if normalized(marker) in compact]
    english_instruction = bool(
        ENGLISH_INSTRUCTION_PATTERN.search(text)
        or EDITORIAL_IMPERATIVE_PATTERN.search(text)
    )
    example_heading = bool(EXAMPLE_HEADING_PATTERN.search(text))
    strong_marker = any(marker in matched for marker in ("模板", "模版", "本刊", "投稿", "replace", "delete", "insert", "please", "do not", "instruction", "template"))
    parenthetical_typography = text.startswith(("（", "(", "[")) and bool(PARENTHETICAL_TYPOGRAPHY_PATTERN.search(text))
    parenthetical_note = text.startswith(("（", "(", "[")) and (has_explicit_red_format(paragraph) or bool(matched) or parenthetical_typography)
    if strong_marker or parenthetical_note or english_instruction or example_heading or len(matched) >= 2 or (has_explicit_red_format(paragraph) and matched):
        return {
            "classification": "editorial_instruction_candidate",
            "signals": (["explicit_red_format"] if has_explicit_red_format(paragraph) else [])
            + (["parenthetical_instruction"] if parenthetical_note else [])
            + (["parenthetical_typography"] if parenthetical_typography else [])
            + (["english_instruction_phrase"] if english_instruction else [])
            + (["example_heading"] if example_heading else [])
            + [f"marker:{marker}" for marker in matched[:6]],
            "reason": "Visible wording and/or red direct formatting indicate editorial guidance; retain it for semantic classification rather than using it as manuscript-role evidence.",
        }
    return None


def mixed_front_matter_guidance_evidence(span: dict) -> dict | None:
    """Identify an instruction run appended to an otherwise manuscript-like line."""
    text = str(span.get("format_span_text") or span.get("text") or "").strip()
    if not text or is_title_placeholder(text) or is_metadata_line(text):
        return None
    matched = [marker for marker in MIXED_FRONT_MATTER_GUIDANCE_MARKERS if normalized(marker) in normalized(text)]
    english_instruction = bool(ENGLISH_INSTRUCTION_PATTERN.search(text))
    example_heading = bool(EXAMPLE_HEADING_PATTERN.search(text))
    if not matched and not english_instruction and not example_heading:
        return None
    return {
        "classification": "inline_editorial_instruction_candidate",
        "signals": ([f"inline_marker:{marker}" for marker in matched[:4]]
                    + (["inline_english_instruction_phrase"] if english_instruction else [])
                    + (["inline_example_heading"] if example_heading else [])),
        "reason": "This run contains an explicit front-matter writing instruction appended to a manuscript exemplar; audit it separately from the surrounding title, author, or keyword content.",
    }


def split_inline_instruction_span(span: dict) -> list[dict]:
    """Split one Word run only when it visibly appends an instruction note.

    A Word run is not automatically a semantic unit.  When a title or author
    placeholder and an explicit parenthetical instruction share the exact
    same run formatting, retain two ledger spans with the same source format
    and explicit provenance rather than treating the instruction as content.
    """
    text = str(span.get("text") or "")
    match = INLINE_PARENTHETICAL_INSTRUCTION_START.search(text)
    if match is None:
        return [span]
    split_at = match.start()
    prefix, instruction = text[:split_at], text[split_at:]
    if not prefix.strip() or not instruction.strip():
        return [span]
    base_start = int(span.get("start") or 0)
    prefix_span = dict(span)
    prefix_span.update({
        "text": prefix,
        "end": base_start + split_at,
        "source_run_split": True,
        "source_run_offset_start": 0,
        "source_run_offset_end": split_at,
    })
    instruction_span = dict(span)
    instruction_span.update({
        "text": instruction,
        "start": base_start + split_at,
        "source_run_split": True,
        "source_run_offset_start": split_at,
        "source_run_offset_end": len(text),
    })
    return [prefix_span, instruction_span]


def mixed_front_matter_prefix_role(
    paragraph: dict,
    first_index: int | None,
    abstract_index: int | None,
) -> str | None:
    """Classify visible front-matter content preceding an instruction run.

    Word templates often keep an author exemplar and its ``Use this style``
    note in one paragraph.  The note is guidance, but it must not erase the
    preceding author/title/affiliation evidence or its run-level formatting.
    """
    index = int(paragraph.get("index") or 0)
    # Some official templates omit a visible title placeholder entirely. In
    # that case the pre-abstract window still contains valid author and
    # affiliation evidence; the missing title remains a separate sequence
    # review issue rather than erasing every preceding semantic span.
    if abstract_index is None or index >= abstract_index:
        return None
    if first_index is not None and index < first_index:
        return None
    prefix_parts: list[str] = []
    saw_instruction = False
    for span in paragraph.get("format_spans") or []:
        if not isinstance(span, dict):
            continue
        if mixed_front_matter_guidance_evidence(span):
            saw_instruction = True
            break
        prefix_parts.append(str(span.get("text") or ""))
    prefix = "".join(prefix_parts).strip()
    if not saw_instruction or not prefix:
        return None
    lower = prefix.lower()
    if is_title_placeholder(prefix):
        return "front_matter.title"
    if is_metadata_line(prefix):
        return "front_matter.metadata"
    if re.match(r"^\d+[.)]\s*\S+", prefix) or any(marker in lower for marker in AFFILIATION_MARKERS):
        return "front_matter.affiliation"
    if looks_like_author_line(prefix):
        return "front_matter.author"
    return None


def looks_like_author_line(text: str) -> bool:
    """Avoid using obvious name sequences as a fallback title anchor."""
    if is_metadata_line(text):
        return False
    compact = normalized(text)
    if len(compact) > 180 or not re.search(r"[,\uFF0C]", text):
        return False
    # Word author exemplars commonly use multi-word placeholder names such as
    # ``First Last Name*1, First Last Name2``. The earlier one-token pattern
    # missed these and let a trailing style note classify the whole line as
    # guidance. Require two comma-separated name-shaped spans instead.
    latin_names = re.findall(r"\b[A-Z][A-Za-z'-]{1,}(?:\s+[A-Z][A-Za-z'-]{1,}){1,3}\b", text)
    if len(latin_names) >= 2:
        return True
    if re.match(r"^[A-Za-z\u3400-\u9fff]{2,18}[0-9*\u2020\u2021]*\s*[,\uFF0C]", text.strip()):
        return True
    return bool(re.match(r"^[A-Z][A-Z .'-]{2,40}[0-9*\u2020\u2021]*\s*,", text.strip()))


def first_title_index(paragraphs: list[dict], abstract_index: int | None) -> int | None:
    """Choose a title anchor without letting an earlier generic field win.

    Templates often place journal citation, article type, DOI, or editorial
    metadata before a literal ``Title``/localized title placeholder. Search
    the whole pre-abstract region for explicit title evidence first; only use
    the first generic candidate when no explicit title field exists.
    """
    fallback_candidates: list[int] = []
    for paragraph in paragraphs:
        index = int(paragraph.get("index") or 0)
        if abstract_index is not None and index >= abstract_index:
            break
        text = str(paragraph.get("format_span_text") or paragraph.get("text") or "").strip()
        # A literal title placeholder can carry an inline typography note.
        # Its structural role must win before the note is classified as
        # guidance, otherwise the whole front-matter window loses its anchor.
        if is_title_placeholder(text):
            return index
        if not text or is_metadata_line(text) or is_running_title_line(text) or is_article_type_line(text) or is_highlights_label(text) or guidance_evidence(paragraph) or looks_like_author_line(text):
            continue
        if re.match(r"^\d+[.)]\s*\S+", text) or contains_marker(text, AFFILIATION_MARKERS):
            continue
        if len(text) <= 180:
            fallback_candidates.append(index)
    # Without an observed abstract boundary, an arbitrary Normal-style first
    # paragraph is often a highlights or author-instruction scaffold. Preserve
    # title inference for an explicit/used title style instead of guessing.
    return fallback_candidates[0] if abstract_index is not None and fallback_candidates else None


def heading_level(text: str) -> int | None:
    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?[.)]?\s*\S+", text.strip())
    if not match:
        return None
    return sum(group is not None for group in match.groups()[1:])


def word_heading_level(paragraph: dict) -> int | None:
    """Return a zero-based semantic heading level from Word style evidence."""
    style_name = str(paragraph.get("style_name") or "").strip().lower()
    style_id = str(paragraph.get("style_id") or "").strip().lower()
    for value in (style_name, style_id):
        match = re.search(r"(?:heading|heading[ _-]?level)[ _-]?(\d+)$", value)
        if match:
            return max(0, min(int(match.group(1)) - 1, 4))

    outline_level = ((paragraph.get("effective_format") or {}).get("paragraph") or {}).get("outline_level")
    try:
        if outline_level is not None:
            return max(0, min(int(outline_level), 4))
    except (TypeError, ValueError):
        pass
    return None


def latin_ratio(text: str) -> float:
    visible = [character for character in text if not character.isspace()]
    if not visible:
        return 0.0
    return sum(character.isascii() and character.isalpha() for character in visible) / len(visible)


def role_candidate(role: str, confidence: str, reason: str) -> dict:
    return {"role": role, "confidence": confidence, "reason": reason, **ROLE_OWNERS.get(role, {})}


def paragraph_roles(
    paragraph: dict,
    *,
    first_index: int | None,
    abstract_index: int | None,
    keyword_index: int | None,
    reference_index: int | None,
    appendix_index: int | None,
    heading_levels: dict[int, int],
    caption_kinds: dict[int, str],
    reference_entries: set[int],
    english_title_index: int | None,
    english_front_matter_end: int | None,
    mixed_prefix_role: str | None = None,
) -> list[dict]:
    index = int(paragraph.get("index") or 0)
    text = str(paragraph.get("format_span_text") or paragraph.get("text") or "").strip()
    if index in caption_kinds:
        return [role_candidate(f"{caption_kinds[index]}.caption", "source", "visible caption label and source paragraph index")]
    if paragraph.get("in_table_cell"):
        return [role_candidate("table.cell", "source", "visible Word table-cell paragraph")]
    if text.lower().startswith("copyright:"):
        return [role_candidate("back_matter.license", "source", "visible copyright or license notice")]
    if re.match(r"^the authors declare\b", text, flags=re.IGNORECASE):
        return [role_candidate("back_matter.declaration", "source", "visible author declaration")]
    metadata_kind = metadata_kind_for_line(text)
    if metadata_kind:
        return [role_candidate(
            f"front_matter.metadata.{metadata_kind}",
            "source",
            f"visible front-matter {metadata_kind} label with independent line, label-run, and value-run mapping",
        )]
    if is_metadata_line(text):
        return [role_candidate("front_matter.metadata", "source", "visible publication or author metadata label")]
    if is_highlights_label(text):
        return [role_candidate(
            "guidance.instruction",
            "source",
            "visible highlights scaffold label; retain it as author guidance rather than a manuscript-title anchor",
        )]
    guidance = guidance_evidence(paragraph)
    explicit_editorial_instruction = bool(EDITORIAL_IMPERATIVE_PATTERN.search(text))
    style_key = f"{paragraph.get('style_id') or ''} {paragraph.get('style_name') or ''}".lower()
    if "bio" in style_key:
        return [role_candidate("back_matter.author_bio", "source", "visible Word author-biography style")]
    if (
        not paragraph.get("in_table_cell")
        and not is_metadata_line(text)
        and not is_running_title_line(text)
        and not is_article_type_line(text)
        and not explicit_editorial_instruction
    ):
        if any(marker in style_key for marker in ("affiliation", "institute", "address")):
            return [role_candidate(
                "front_matter.affiliation",
                "candidate",
                "visible paragraph uses an affiliation-like Word style; confirm ordered front-matter context before final mapping",
            )]
        if "author" in style_key:
            return [role_candidate(
                "front_matter.author",
                "candidate",
                "visible paragraph uses an author-like Word style; confirm ordered front-matter context before final mapping",
            )]
        if "title" in style_key and "running" not in style_key:
            return [role_candidate(
                "front_matter.title",
                "candidate",
                "visible paragraph uses a title-like Word style; confirm manuscript-title semantics before final mapping",
            )]
    if guidance:
        if mixed_prefix_role:
            return [role_candidate(
                mixed_prefix_role,
                "candidate",
                "visible front-matter exemplar preceding a separate inline instruction run",
            )]
        return [role_candidate("guidance.instruction", "source", guidance["reason"])]
    if starts_with(text, REFERENCE_MARKERS):
        return [role_candidate("references.heading", "source", "visible references heading")]
    if starts_with(text, APPENDIX_MARKERS):
        return [role_candidate("appendix.heading", "source", "visible appendix heading")]
    if abstract_index is not None and index == abstract_index:
        return [role_candidate("front_matter.abstract", "source", "visible abstract label")]
    if starts_with(text, KEYWORD_MARKERS):
        return [role_candidate("front_matter.keywords", "source", "visible keyword label")]
    if reference_index is not None and index > reference_index and (appendix_index is None or index < appendix_index):
        # A bibliography entry can legitimately begin with a bare DOI. The
        # reference zone owns that paragraph before any front-matter metadata
        # classifier sees it.
        if index in reference_entries or paragraph.get("list_evidence") or re.match(r"^(?:\[?\d+\]?|10\.\d{4,9}/)\s*\S*", text):
            return [role_candidate("references.entry", "source", "reference-zone numbered or DOI-leading entry evidence")]
        return [role_candidate("references.entry", "candidate", "remaining visible reference-zone paragraph")]
    if is_running_title_line(text):
        return [role_candidate("front_matter.metadata", "source", "visible short or running title belongs to journal furniture rather than the manuscript title")]
    if is_article_type_line(text):
        return [role_candidate("front_matter.article_type", "source", "visible article or manuscript type label")]
    if abstract_index is not None and keyword_index is not None and abstract_index < index < keyword_index:
        # Chinese abstract paragraphs frequently continue until the keyword
        # label without repeating 摘要. Preserve that zone before treating the
        # continuation as ordinary body text.
        return [role_candidate("front_matter.abstract", "candidate", "continuation before the visible keyword label")]
    if first_index is not None and index == first_index:
        return [role_candidate("front_matter.title", "candidate", "conservative title-like front-matter anchor")]
    if abstract_index is not None and index < abstract_index:
        lower = text.lower()
        if re.match(r"^\d+[.)]\s*\S+", text):
            return [role_candidate("front_matter.affiliation", "candidate", "numbered pre-abstract affiliation line")]
        if any(marker in lower for marker in AFFILIATION_MARKERS):
            return [role_candidate("front_matter.affiliation", "candidate", "pre-abstract affiliation marker")]
        if len(text) <= 120:
            return [role_candidate("front_matter.author", "candidate", "short pre-abstract metadata paragraph")]
    in_english_front_matter = (
        english_title_index is not None
        and english_front_matter_end is not None
        and english_title_index <= index <= english_front_matter_end
    )
    if in_english_front_matter and index == english_title_index:
        return [role_candidate("front_matter.english_title", "candidate", "first English title-like paragraph after Chinese metadata")]
    if in_english_front_matter and index > english_title_index and latin_ratio(text) >= 0.45:
        lower = text.lower()
        if starts_with(text, ("abstract",)):
            return [role_candidate("front_matter.english_abstract", "source", "visible English abstract label")]
        if starts_with(text, ("keywords", "key words")):
            return [role_candidate("front_matter.english_keywords", "source", "visible English keyword label")]
        if any(marker in lower for marker in AFFILIATION_MARKERS):
            return [role_candidate("front_matter.english_affiliation", "candidate", "English affiliation marker")]
        if re.match(r"^\d+[.)]\s*\S+", text):
            return [role_candidate("front_matter.english_affiliation", "candidate", "numbered English affiliation line")]
        if len(text) <= 180:
            return [role_candidate("front_matter.english_author", "candidate", "short English metadata paragraph")]
    numbered_level = heading_level(text)
    if index in heading_levels or numbered_level is not None:
        level = heading_levels.get(index, numbered_level)
        level = 0 if level is None else min(level, 4)
        return [role_candidate(
            f"heading.level{level}",
            "source" if index in heading_levels else "candidate",
            "Word heading style or outline-level evidence" if index in heading_levels else "numbered visible paragraph",
        )]
    if paragraph.get("list_evidence"):
        return [role_candidate("body.list_item", "source", "official Word list paragraph with numbering and level evidence")]
    return [role_candidate("body.paragraph", "candidate", "remaining visible manuscript-flow paragraph")]


def zone_boundaries(paragraphs: list[dict]) -> dict[str, int | None]:
    boundaries = {"abstract": None, "keywords": None, "references": None, "appendix": None}
    for paragraph in paragraphs:
        index = int(paragraph.get("index") or 0)
        text = str(paragraph.get("format_span_text") or paragraph.get("text") or "")
        for name, markers in (("abstract", ABSTRACT_MARKERS), ("keywords", KEYWORD_MARKERS), ("references", REFERENCE_MARKERS), ("appendix", APPENDIX_MARKERS)):
            if boundaries[name] is not None:
                continue
            # Zone boundaries change the semantic interpretation of every
            # following paragraph. A prefix match would misclassify prose such
            # as "References to sections ..." as a bibliography heading.
            # Require either a standalone label or explicit Word heading
            # evidence before opening a document-wide zone.
            expected_role = {
                "abstract": "front_matter.abstract",
                "keywords": "front_matter.keywords",
                "references": "references.heading",
                "appendix": "appendix.heading",
            }[name]
            is_standalone_label = standalone_label_role(text) == expected_role
            has_heading_evidence = word_heading_level(paragraph) is not None
            if is_standalone_label or (has_heading_evidence and starts_with(text, markers)):
                boundaries[name] = index
    return boundaries


def zones(last_index: int, boundaries: dict[str, int | None]) -> list[dict]:
    abstract = boundaries["abstract"]
    keywords = boundaries["keywords"]
    references = boundaries["references"]
    appendix = boundaries["appendix"]
    result = []
    if abstract:
        result.append({"name": "front_matter", "start_index": 1, "end_index": max(1, abstract - 1)})
        result.append({"name": "abstract", "start_index": abstract, "end_index": (keywords - 1) if keywords and keywords > abstract else abstract})
    if keywords:
        result.append({"name": "keywords", "start_index": keywords, "end_index": (references - 1) if references and references > keywords else (appendix - 1) if appendix and appendix > keywords else last_index})
    body_start = (keywords + 1) if keywords else (abstract + 1) if abstract else 1
    body_end = (references - 1) if references else (appendix - 1) if appendix else last_index
    if body_end >= body_start:
        result.append({"name": "body", "start_index": body_start, "end_index": body_end})
    if references:
        result.append({"name": "references", "start_index": references, "end_index": (appendix - 1) if appendix and appendix > references else last_index})
    if appendix:
        result.append({"name": "appendix", "start_index": appendix, "end_index": last_index})
    return result


def front_matter_sequence_review(paragraphs: list[dict], abstract_index: int | None) -> dict:
    """Expose pre-abstract role order for semantic review before generation.

    This is intentionally an audit aid, not another automatic role classifier.
    A Word template can legitimately put publication metadata before its title,
    but a title after an author line or multiple title candidates must be
    reviewed instead of silently accepted as a final field mapping.
    """
    entries = []
    role_positions: dict[str, list[int]] = defaultdict(list)
    explicit_title_positions: list[int] = []
    candidate_role_entries: list[dict[str, object]] = []
    for paragraph in paragraphs:
        index = int(paragraph.get("index") or 0)
        if abstract_index is not None and index >= abstract_index:
            break
        candidate_records = [
            candidate
            for candidate in paragraph.get("role_candidates") or []
            if isinstance(candidate, dict) and str(candidate.get("role") or "").startswith("front_matter.")
        ]
        candidates = [str(candidate.get("role") or "") for candidate in candidate_records]
        if not candidates:
            continue
        if is_title_placeholder(str(paragraph.get("text") or "")):
            explicit_title_positions.append(index)
        for role in candidates:
            role_positions[role].append(index)
        entries.append({
            "index": index,
            "evidence_id": str(paragraph.get("evidence_id") or f"p{index:04d}"),
            "roles": candidates,
            "role_confidence": {
                str(candidate.get("role") or ""): str(candidate.get("confidence") or "candidate")
                for candidate in candidate_records
            },
            "text": str(paragraph.get("text") or "")[:240],
        })
        for candidate in candidate_records:
            if str(candidate.get("confidence") or "candidate") != "source":
                candidate_role_entries.append({
                    "index": index,
                    "evidence_id": str(paragraph.get("evidence_id") or f"p{index:04d}"),
                    "role": str(candidate.get("role") or ""),
                })

    checks = []
    title_positions = role_positions.get("front_matter.title", [])
    author_positions = role_positions.get("front_matter.author", [])
    article_type_positions = role_positions.get("front_matter.article_type", [])
    if not title_positions:
        checks.append({
            "code": "title_not_observed",
            "severity": "review",
            "reason": "No visible title candidate was identified before the abstract boundary.",
        })
    if author_positions and title_positions and min(author_positions) < min(title_positions):
        checks.append({
            "code": "author_before_title",
            "severity": "blocking",
            "reason": "An author candidate precedes the selected title candidate; confirm the field sequence before final mapping.",
        })
    if article_type_positions and title_positions and min(article_type_positions) > min(title_positions):
        checks.append({
            "code": "article_type_after_title",
            "severity": "review",
            "reason": "An article-type candidate follows the selected title. Publishers use both positions, so confirm its semantic placement before final layout calibration.",
        })
    if len(title_positions) > 1:
        checks.append({
            "code": "multiple_title_candidates",
            "severity": "review",
            "reason": "Multiple visible title candidates occur before the abstract boundary; identify title, subtitle, and bilingual variants explicitly.",
        })
    if len(explicit_title_positions) > 1:
        checks.append({
            "code": "multiple_explicit_title_fields",
            "severity": "review",
            "reason": "More than one literal or localized title placeholder occurs before the abstract boundary; classify bilingual title, subtitle, and repeated template instructions explicitly.",
        })
    if candidate_role_entries:
        check_items = ", ".join(
            f"{item['evidence_id']}:{item['role']}"
            for item in candidate_role_entries[:12]
        )
        checks.append({
            "code": "front_matter_candidate_roles_need_confirmation",
            "severity": "blocking",
            "reason": "Visible pre-abstract paragraphs have only candidate front-matter roles. Confirm their ordered manuscript fields before final mapping: " + check_items,
        })
    metadata_positions = [
        index
        for role, indexes in role_positions.items()
        if role == "front_matter.metadata" or role.startswith("front_matter.metadata.")
        for index in indexes
    ]
    if metadata_positions and title_positions and min(metadata_positions) < min(title_positions):
        checks.append({
            "code": "metadata_before_title",
            "severity": "information",
            "reason": "Publisher/editorial metadata precedes the title. Preserve its order; this alone is not a mapping error.",
        })
    return {
        "source": "ordered visible Word paragraphs before the abstract boundary",
        "abstract_boundary_index": abstract_index,
        "entries": entries[:40],
        "role_positions": dict(role_positions),
        "explicit_title_positions": explicit_title_positions,
        "candidate_role_entries": candidate_role_entries,
        "checks": checks,
        "requires_semantic_confirmation": any(check["severity"] == "blocking" for check in checks),
        "instruction": "When confirmation is required, do not promote automatic front-matter role candidates into final class mappings until title, author, affiliation, metadata, and bilingual/subtitle roles are explicitly resolved.",
    }


def safe_identifier(value: object) -> str:
    """Create a deterministic evidence-id component from an OOXML part/name."""
    result = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "unknown")).strip("_").lower()
    return result or "unknown"


def evidence_fingerprint(paragraphs: list[dict], ancillary: list[dict], object_evidence: list[dict]) -> str:
    """Bind downstream audits to the exact Word evidence set they reviewed."""
    payload = {
        "paragraphs": paragraphs,
        "ancillary_units": ancillary,
        "object_evidence": object_evidence,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def object_evidence_units(objects: dict) -> list[dict]:
    """Turn observable Word table and drawing geometry into audit units.

    Cell text remains in the paragraph ledger. These units carry only the
    object-level facts that LaTeX must own: grid/width/header structure for
    tables and image box, wrapping, caption relation, and flow for drawings.
    """
    units: list[dict] = []
    sections = objects.get("sections") or []
    if sections and isinstance(sections[0], dict):
        first = sections[0]
        first_variants = [
            reference
            for key in ("header_references", "footer_references")
            for reference in first.get(key, []) if isinstance(reference, dict) and reference.get("type") == "first"
        ]
        if first.get("different_first_page") or first_variants:
            units.append({
                "evidence_id": "cover.first_page.structure",
                "kind": "cover_structure",
                "text": "Word first section has a distinct first-page header/footer variant.",
                "has_direct_format": True,
                "format_signature": {"cover_structure": {"different_first_page": bool(first.get("different_first_page")), "first_page_references": first_variants}},
                "role_candidates": [role_candidate("cover.structure", "source", "official Word first-page section variant")],
                "context": {"section_index": first.get("index") or 1},
            })
    toc = objects.get("toc_evidence") if isinstance(objects.get("toc_evidence"), dict) else {}
    if toc.get("has_toc_field"):
        units.append({
            "evidence_id": "toc.field.structure",
            "kind": "toc_structure",
            "text": "Official Word TOC field: " + "; ".join(str(item) for item in (toc.get("field_samples") or [])[:3]),
            "has_direct_format": True,
            "format_signature": {"toc_structure": {"field_samples": toc.get("field_samples") or [], "heading_samples": toc.get("heading_samples") or [], "entry_tab_stops": toc.get("entry_tab_stops") or []}},
            "role_candidates": [role_candidate("toc.structure", "source", "official Word TOC field code")],
            "context": {"has_toc_field": True},
        })
    toc_tabs = toc.get("entry_tab_stops") if isinstance(toc.get("entry_tab_stops"), list) else []
    if toc_tabs:
        units.append({
            "evidence_id": "toc.entry-tabs.layout",
            "kind": "toc_layout",
            "text": f"Word TOC entry layout: {len(toc_tabs)} paragraph(s) with explicit tab stops/leaders.",
            "has_direct_format": True,
            "format_signature": {"toc_layout": {"entry_tab_stops": toc_tabs}},
            "role_candidates": [role_candidate("toc.layout", "source", "official Word TOC entry indentation, right-tab, and leader evidence")],
            "context": {"entry_tab_stops": toc_tabs[:12]},
        })
    page_numbering_sections = [
        section for section in sections
        if isinstance(section, dict) and isinstance(section.get("page_numbering"), dict) and section.get("page_numbering")
    ]
    if page_numbering_sections:
        numbering = [
            {"section_index": section.get("index"), **section.get("page_numbering", {})}
            for section in page_numbering_sections
        ]
        units.append({
            "evidence_id": "page.numbering.system",
            "kind": "page_numbering",
            "text": f"Word page-numbering system: {len(numbering)} section override(s).",
            "has_direct_format": True,
            "format_signature": {"page_numbering": {"sections": numbering}},
            "role_candidates": [role_candidate("page.numbering", "source", "official Word section page-number format, restart, and chapter-number evidence")],
            "context": {"sections": numbering},
        })
    text_grid = objects.get("text_grid_evidence") if isinstance(objects.get("text_grid_evidence"), dict) else {}
    if text_grid.get("present"):
        units.append({
            "evidence_id": "page.text-grid.system",
            "kind": "text_grid",
            "text": "Word document-grid and/or local paragraph/style/run grid override evidence.",
            "has_direct_format": True,
            "format_signature": {"text_grid": text_grid},
            "role_candidates": [role_candidate("page.text_grid", "source", "official Word docGrid and paragraph/style/run snap-to-grid or East Asian punctuation settings")],
            "context": {"sections": (text_grid.get("sections") or [])[:12], "paragraphs": (text_grid.get("paragraphs") or [])[:24], "styles": (text_grid.get("styles") or [])[:24], "run_groups": (text_grid.get("run_groups") or [])[:36]},
        })
    line_numbering = objects.get("line_numbering") if isinstance(objects.get("line_numbering"), dict) else {}
    line_number_sections = line_numbering.get("sections") if isinstance(line_numbering.get("sections"), list) else []
    if line_numbering.get("enabled") and line_number_sections:
        units.append({
            "evidence_id": "line.numbering.system",
            "kind": "line_numbering",
            "text": f"Word line-numbering system: {len(line_number_sections)} section override(s).",
            "has_direct_format": True,
            "format_signature": {"line_numbering": {"sections": line_number_sections}},
            "role_candidates": [role_candidate("line.numbering", "source", "official Word section line-number interval, start, distance, and restart evidence")],
            "context": {"sections": line_number_sections},
        })
    tab_stop_samples = objects.get("tab_stop_evidence") if isinstance(objects.get("tab_stop_evidence"), list) else []
    if tab_stop_samples:
        units.append({
            "evidence_id": "paragraph.tab-stops.system",
            "kind": "paragraph_tab_stops",
            "text": f"Word visible tab-stop layouts: {len(tab_stop_samples)} non-TOC paragraph(s).",
            "has_direct_format": True,
            "format_signature": {"paragraph_tab_stops": {"samples": tab_stop_samples}},
            "role_candidates": [role_candidate("paragraph.tab_stops", "source", "visible Word non-TOC tab characters with effective tab-stop definitions")],
            "context": {"samples": tab_stop_samples[:30]},
        })
    drop_cap_samples = objects.get("drop_cap_evidence") if isinstance(objects.get("drop_cap_evidence"), list) else []
    if drop_cap_samples:
        units.append({
            "evidence_id": "paragraph.drop-cap.system",
            "kind": "paragraph_drop_cap",
            "text": f"Word drop-cap layout: {len(drop_cap_samples)} visible paragraph(s).",
            "has_direct_format": True,
            "format_signature": {"paragraph_drop_cap": {"samples": drop_cap_samples}},
            "role_candidates": [role_candidate("paragraph.drop_cap", "source", "visible Word framePr dropCap and following paragraph evidence")],
            "context": {"samples": drop_cap_samples[:12]},
        })
    character_effect_samples = objects.get("character_effect_evidence") if isinstance(objects.get("character_effect_evidence"), list) else []
    if character_effect_samples:
        units.append({
            "evidence_id": "run.character-effects.system",
            "kind": "character_effects",
            "text": f"Word local character effects: {len(character_effect_samples)} visible run span(s) and/or named style rule(s).",
            "has_direct_format": True,
            "format_signature": {"character_effects": {"samples": character_effect_samples}},
            "role_candidates": [role_candidate("run.character_effects", "source", "visible Word run-level or named-style small caps, caps, highlight, shading, text border, kerning, hidden, spacing, scale, position, or text-effect evidence")],
            "context": {"samples": character_effect_samples[:60]},
        })
    character_style_samples = objects.get("character_style_evidence") if isinstance(objects.get("character_style_evidence"), list) else []
    if character_style_samples:
        units.append({
            "evidence_id": "run.character-styles.system",
            "kind": "character_styles",
            "text": f"Word character-style references: {len(character_style_samples)} visible run span(s).",
            "has_direct_format": True,
            "format_signature": {"character_styles": {"samples": character_style_samples}},
            "role_candidates": [role_candidate("run.character_styles", "source", "visible Word runs referencing named character styles with resolved effective formatting")],
            "context": {"samples": character_style_samples[:80]},
        })
    script_language = objects.get("script_language_evidence") if isinstance(objects.get("script_language_evidence"), dict) else {}
    script_language_groups = script_language.get("review_groups") if isinstance(script_language.get("review_groups"), list) else []
    if script_language.get("present") and script_language_groups:
        units.append({
            "evidence_id": "run.script-language.system",
            "kind": "script_language",
            "text": f"Word language, complex-script emphasis, and RTL direction: {script_language.get('raw_occurrence_count', len(script_language_groups))} run/style occurrence(s) in {len(script_language_groups)} review group(s).",
            "has_direct_format": True,
            "format_signature": {"script_language": script_language},
            "role_candidates": [role_candidate("run.script_language", "source", "visible Word run and named-style language, complex-script bold/italic, complex-script flag, and RTL direction evidence")],
            "context": {"groups": script_language_groups[:80]},
        })
    paragraph_direction = objects.get("paragraph_direction_evidence") if isinstance(objects.get("paragraph_direction_evidence"), dict) else {}
    paragraph_direction_groups = paragraph_direction.get("review_groups") if isinstance(paragraph_direction.get("review_groups"), list) else []
    if paragraph_direction.get("present") and paragraph_direction_groups:
        units.append({
            "evidence_id": "paragraph.direction.system",
            "kind": "paragraph_direction",
            "text": f"Word paragraph bidi/text direction: {paragraph_direction.get('raw_occurrence_count', len(paragraph_direction_groups))} paragraph/style occurrence(s) in {len(paragraph_direction_groups)} review group(s).",
            "has_direct_format": True,
            "format_signature": {"paragraph_direction": paragraph_direction},
            "role_candidates": [role_candidate("paragraph.direction", "source", "visible Word paragraph and named-style bidi/text-direction evidence affecting alignment, start/end indents, and flow")],
            "context": {"groups": paragraph_direction_groups[:80]},
        })
    paragraph_break_policy = objects.get("paragraph_break_policy_evidence") if isinstance(objects.get("paragraph_break_policy_evidence"), dict) else {}
    paragraph_break_policy_groups = paragraph_break_policy.get("review_groups") if isinstance(paragraph_break_policy.get("review_groups"), list) else []
    if paragraph_break_policy.get("present") and paragraph_break_policy_groups:
        units.append({
            "evidence_id": "paragraph.break-policy.system",
            "kind": "paragraph_break_policy",
            "text": f"Word paragraph automatic-hyphen/word-wrap policy: {paragraph_break_policy.get('raw_occurrence_count', len(paragraph_break_policy_groups))} paragraph/style occurrence(s) in {len(paragraph_break_policy_groups)} review group(s).",
            "has_direct_format": True,
            "format_signature": {"paragraph_break_policy": paragraph_break_policy},
            "role_candidates": [role_candidate("paragraph.break_policy", "source", "visible Word paragraph and named-style automatic-hyphen and word-wrap evidence affecting line breaks and page flow")],
            "context": {"groups": paragraph_break_policy_groups[:80]},
        })
    theme_formats = objects.get("theme_format_evidence") if isinstance(objects.get("theme_format_evidence"), dict) else {}
    theme_samples = theme_formats.get("samples") if isinstance(theme_formats.get("samples"), list) else []
    if theme_formats.get("present") and theme_samples:
        units.append({
            "evidence_id": "document.theme.system",
            "kind": "theme_format",
            "text": f"Word theme color/font references: {len(theme_samples)} visible run span(s) and/or named style rule(s).",
            "has_direct_format": True,
            "format_signature": {"theme_format": theme_formats},
            "role_candidates": [role_candidate("document.theme", "source", "official Word theme definition plus visible/theme-style color and font references")],
            "context": {"definition": theme_formats.get("definition") or {}, "samples": theme_samples[:80]},
        })
    unmodeled_properties = objects.get("unmodeled_format_properties") if isinstance(objects.get("unmodeled_format_properties"), dict) else {}
    unknown_property_records = unmodeled_properties.get("properties") if isinstance(unmodeled_properties.get("properties"), list) else []
    if unknown_property_records:
        units.append({
            "evidence_id": "word.unmodeled-format-properties.system",
            "kind": "unmodeled_format_properties",
            "text": f"Word OOXML format properties not yet modeled: {len(unknown_property_records)} node type(s).",
            "has_direct_format": True,
            "format_signature": {"unmodeled_format_properties": {"properties": unknown_property_records}},
            "role_candidates": [role_candidate("word.unmodeled_format", "source", "readable Word format-property nodes outside the current direct-format model")],
            "context": {"properties": unknown_property_records[:80]},
        })
    for note_kind in ("footnote", "endnote"):
        numbering = objects.get(f"{note_kind}_numbering") if isinstance(objects.get(f"{note_kind}_numbering"), dict) else {}
        references = objects.get(f"{note_kind}s") or []
        count = int(objects.get(f"{note_kind}_count") or 0)
        if not numbering and not references and not count:
            continue
        role = f"{note_kind}.system"
        units.append({
            "evidence_id": f"{note_kind}.system.structure",
            "kind": f"{note_kind}_system",
            "text": f"Word {note_kind} system: {count} note(s), marker {numbering.get('marker_style') or 'unknown'}, format {numbering.get('number_format') or 'unknown'}.",
            "has_direct_format": bool(numbering.get("explicit_number_format") or numbering.get("start") or numbering.get("restart") or references),
            "format_signature": {f"{note_kind}_system": {"count": count, "numbering": numbering, "reference_samples": references[:12]}},
            "role_candidates": [role_candidate(role, "source", f"official Word {note_kind} numbering and reference-marker evidence")],
            "context": {"note_count": count, "reference_count": len(references)},
        })
    boundaries = objects.get("boundaries") if isinstance(objects.get("boundaries"), dict) else {}
    reference_index = boundaries.get("references")
    appendix_index = boundaries.get("appendix")

    # A list paragraph is text evidence, but its numbering definition is a
    # separate reusable layout system. Keep it distinct so a generic \item
    # wrapper cannot silently satisfy a source-specific label/indent rule.
    list_groups: dict[str, list[dict]] = defaultdict(list)
    for item in objects.get("list_items") or []:
        if not isinstance(item, dict):
            continue
        paragraph_index = item.get("paragraph_index")
        if not isinstance(paragraph_index, int):
            continue
        in_reference_zone = (
            isinstance(reference_index, int)
            and paragraph_index > reference_index
            and (not isinstance(appendix_index, int) or paragraph_index < appendix_index)
        )
        if in_reference_zone:
            # Reference-entry numbering belongs to references.system, not the
            # manuscript body list contract.
            continue
        num_id = item.get("num_id")
        style_id = item.get("style_id")
        key = f"num:{num_id}" if num_id not in (None, "") else f"style:{style_id or 'unnamed'}"
        list_groups[key].append(item)
    for key, items in sorted(list_groups.items()):
        level_definitions: dict[str, dict] = {}
        for item in items:
            level = str(item.get("level") or "0")
            level_definitions.setdefault(level, {
                field: item.get(field)
                for field in ("number_format", "level_text", "start", "left_indent_twips", "hanging_twips", "source")
                if item.get(field) is not None
            })
        number_formats = sorted({str(item.get("number_format") or "unknown") for item in items})
        kind = "itemize" if number_formats and set(number_formats) == {"bullet"} else "enumerate"
        identifier = safe_identifier(key)
        units.append({
            "evidence_id": f"list.{identifier}.system",
            "kind": "list_system",
            "text": f"Word list {key}: {len(items)} item(s), levels {', '.join(sorted(level_definitions, key=lambda value: int(value) if value.isdigit() else value)) or 'unknown'}, formats {', '.join(number_formats)}.",
            "has_direct_format": any(bool(definition) for definition in level_definitions.values()),
            "format_signature": {"list_system": {
                "list_key": key,
                "kind": kind,
                "number_formats": number_formats,
                "level_definitions": level_definitions,
                "item_count": len(items),
            }},
            "role_candidates": [role_candidate("body.list_system", "source", "official Word numbering definition, level labels, and indentation evidence")],
            "context": {
                "list_key": key,
                "paragraph_indexes": [item["paragraph_index"] for item in items],
                "sample_text": [str(item.get("text") or "")[:160] for item in items[:6]],
                "in_table_cell_count": sum(bool(item.get("in_table_cell")) for item in items),
            },
        })
    equations = [item for item in objects.get("equations") or [] if isinstance(item, dict)]
    if equations:
        display_equations = [item for item in equations if item.get("display_like")]
        number_samples = [number for item in display_equations for number in item.get("number_samples") or []]
        statuses = sorted({str(item.get("translation_status") or "not_convertible") for item in equations})
        units.append({
            "evidence_id": "equation.system.structure",
            "kind": "equation_system",
            "text": f"Word OMML equation system: {len(equations)} equation(s), {len(display_equations)} display-like, numbering samples {', '.join(number_samples[:8]) or 'not observed'}.",
            "has_direct_format": bool(number_samples or any(item.get("paragraph_direct_format") for item in equations)),
            "format_signature": {"equation_system": {
                "equation_count": len(equations),
                "display_equation_count": len(display_equations),
                "number_samples": number_samples[:12],
                "translation_statuses": statuses,
            }},
            "role_candidates": [role_candidate("equation.system", "source", "official Word OMML display, numbering, and paragraph-layout evidence")],
            "context": {"equation_indexes": [item.get("index") for item in equations], "paragraph_indexes": [item.get("paragraph_index") for item in equations]},
        })
        for ordinal, equation in enumerate(equations, start=1):
            index = int(equation.get("index") or ordinal)
            translation_status = str(equation.get("translation_status") or "not_convertible")
            units.append({
                "evidence_id": f"equation.e{index:03d}.instance",
                "kind": "equation_instance",
                "text": f"Word OMML equation {index}: {str(equation.get('sample_text') or '')[:180] or 'no extractable math text'} ({translation_status}).",
                "has_direct_format": bool(equation.get("paragraph_direct_format") or equation.get("number_samples") or equation.get("display_like")),
                "format_signature": {"equation_instance": {
                    "display_like": bool(equation.get("display_like")),
                    "number_samples": equation.get("number_samples") or [],
                    "paragraph_direct_format": equation.get("paragraph_direct_format") or {},
                    "translation_status": translation_status,
                    "latex_candidate": equation.get("latex"),
                    "unsupported_nodes": equation.get("unsupported_nodes") or [],
                    "source_structure": equation.get("structure") or [],
                }},
                "role_candidates": [role_candidate("equation.instance", "source", "official Word OMML formula structure and local display/numbering evidence")],
                "context": {
                    "equation_index": index,
                    "paragraph_index": equation.get("paragraph_index"),
                    "paragraph_style_id": equation.get("paragraph_style_id"),
                    "part": equation.get("part"),
                    "in_table_cell": bool(equation.get("in_table_cell")),
                    "in_text_box": bool(equation.get("in_text_box")),
                    "word_text_outside_math": equation.get("word_text_outside_math") or "",
                },
            })
    for paragraph in objects.get("paragraphs") or []:
        if not isinstance(paragraph, dict):
            continue
        index = paragraph.get("index")
        if not isinstance(index, int):
            continue
        effective = paragraph.get("effective_format") if isinstance(paragraph.get("effective_format"), dict) else {}
        direct = paragraph.get("direct_format") if isinstance(paragraph.get("direct_format"), dict) else {}
        effective_paragraph = effective.get("paragraph") if isinstance(effective.get("paragraph"), dict) else {}
        direct_paragraph = direct.get("paragraph") if isinstance(direct.get("paragraph"), dict) else {}
        decoration = {
            key: effective_paragraph.get(key)
            for key in ("borders", "shading", "frame")
            if effective_paragraph.get(key)
        }
        if not decoration:
            continue
        units.append({
            "evidence_id": f"block.p{index:04d}.decoration",
            "kind": "block_decoration",
            "text": f"Word paragraph {index} has visible block decoration: {', '.join(sorted(decoration))}.",
            "has_direct_format": bool(any(direct_paragraph.get(key) for key in decoration)),
            "format_signature": {"block_decoration": decoration},
            "role_candidates": [role_candidate("block.decoration", "source", "observable Word paragraph border, shading, or frame evidence")],
            "context": {
                "paragraph_index": index,
                "text_sample": str(paragraph.get("format_span_text") or paragraph.get("text") or "")[:220],
                "in_table_cell": bool(paragraph.get("in_table_cell")),
                "paragraph_role_candidates": paragraph.get("role_candidates") or [],
            },
        })
    if isinstance(reference_index, int):
        units.append({
            "evidence_id": "references.system.structure",
            "kind": "references_system",
            "text": f"Word reference section begins at paragraph {reference_index}; appendix boundary {appendix_index if isinstance(appendix_index, int) else 'not observed'}.",
            "has_direct_format": True,
            "format_signature": {"references_system": {"references_start": reference_index, "appendix_start": appendix_index}},
            "role_candidates": [role_candidate("references.system", "source", "visible official Word references boundary and list zone")],
            "context": {"references_start": reference_index, "appendix_start": appendix_index},
        })
    if isinstance(appendix_index, int):
        units.append({
            "evidence_id": "appendix.system.structure",
            "kind": "appendix_system",
            "text": f"Word appendix section begins at paragraph {appendix_index}; references boundary {reference_index if isinstance(reference_index, int) else 'not observed'}.",
            "has_direct_format": True,
            "format_signature": {"appendix_system": {"appendix_start": appendix_index, "references_start": reference_index}},
            "role_candidates": [role_candidate("appendix.system", "source", "visible official Word appendix boundary and counter scope")],
            "context": {"appendix_start": appendix_index, "references_start": reference_index},
        })
    for ordinal, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            continue
        index = int(section.get("index") or ordinal)
        frame = {
            key: section.get(key)
            for key in (
                "page_width_twips", "page_height_twips", "orientation", "margins_twips",
                "header_distance_twips", "footer_distance_twips", "gutter_twips", "mirror_margins",
            )
        }
        columns = {
            key: section.get(key)
            for key in ("columns", "column_space_twips", "columns_equal_width", "column_widths_twips", "section_break_type")
        }
        units.extend([
            {
                "evidence_id": f"page.s{index:03d}.frame",
                "kind": "page_frame",
                "text": f"Word section {index}: {frame.get('page_width_twips') or '?'} x {frame.get('page_height_twips') or '?'} twips page frame.",
                "has_direct_format": True,
                "format_signature": {"page_frame": frame},
                "role_candidates": [role_candidate("page.frame", "source", "official Word section page geometry and margin evidence")],
                "context": {"section_index": index, "start_paragraph_index": section.get("start_paragraph_index"), "end_paragraph_index": section.get("end_paragraph_index")},
            },
            {
                "evidence_id": f"page.s{index:03d}.columns",
                "kind": "page_columns",
                "text": f"Word section {index}: {columns.get('columns') or '1'} column(s), {columns.get('section_break_type') or 'continuous'} boundary.",
                "has_direct_format": True,
                "format_signature": {"page_columns": columns},
                "role_candidates": [role_candidate("page.columns", "source", "official Word column count, spacing, widths, and section-break flow")],
                "context": {"section_index": index, "start_paragraph_index": section.get("start_paragraph_index"), "end_paragraph_index": section.get("end_paragraph_index")},
            },
        ])
    for ordinal, table in enumerate(objects.get("tables") or [], start=1):
        if not isinstance(table, dict):
            continue
        index = int(table.get("index") or ordinal)
        relation = table.get("caption_relation") if isinstance(table.get("caption_relation"), dict) else {}
        start = table.get("first_paragraph_index")
        metadata_table = bool(isinstance(start, int) and start <= 20 and relation.get("confidence") in {None, "distant"})
        role = "front_matter.metadata_table" if metadata_table else "table.structure"
        structure = {
            key: table.get(key)
            for key in (
                "rows", "max_columns", "width_twips", "width_type", "alignment", "layout", "style_id", "style_evidence",
                "indent", "default_cell_margins", "positioning", "overlap", "shading",
                "grid_column_widths_twips", "has_merged_cells", "border_profile", "active_borders",
                "repeat_header", "header_fill", "header_alignment", "header_vertical_alignment",
                "header_bold", "header_bold_consensus", "header_effective_font", "header_font_consensus",
                "header_row_height_twips", "header_row_height_rule", "row_format_samples",
            )
        }
        units.append({
            "evidence_id": f"table.t{index:03d}.structure",
            "kind": "table_structure",
            "text": f"Word table {index}: {table.get('rows') or 0} rows x {table.get('max_columns') or 0} columns; {table.get('border_profile') or 'unknown'} borders.",
            "has_direct_format": any(value not in (None, [], False, "", "unknown") for value in structure.values()),
            "format_signature": {"table_structure": structure},
            "role_candidates": [role_candidate(role, "source", "observable Word table grid, width, border, margin, indentation, row-pagination, header, and merge evidence")],
            "context": {
                "table_index": index,
                "first_paragraph_index": start,
                "last_paragraph_index": table.get("last_paragraph_index"),
                "caption_relation": relation,
                "outer_flow_context": table.get("outer_flow_context") or {},
                "source_section_index": table.get("source_section_index"),
            },
        })
    for ordinal, drawing in enumerate(objects.get("body_drawings") or [], start=1):
        if not isinstance(drawing, dict):
            continue
        relation = drawing.get("caption_relation") if isinstance(drawing.get("caption_relation"), dict) else {}
        geometry = drawing.get("geometry") if isinstance(drawing.get("geometry"), dict) else {}
        placement = {
            "drawing_type": drawing.get("drawing_type"),
            "width_emu": drawing.get("width_emu"),
            "height_emu": drawing.get("height_emu"),
            "geometry": geometry,
            "paragraph_direct_format": drawing.get("paragraph_direct_format") or {},
            "paragraph_effective_format": drawing.get("paragraph_effective_format") or {},
        }
        units.append({
            "evidence_id": f"figure.d{ordinal:03d}.placement",
            "kind": "drawing_placement",
            "text": f"Word drawing {ordinal}: {drawing.get('drawing_type') or 'unknown'} {drawing.get('width_emu') or '?'} x {drawing.get('height_emu') or '?'} EMU; caption {relation.get('position') or 'unresolved'}.",
            "has_direct_format": bool(geometry or drawing.get("paragraph_direct_format")),
            "format_signature": {"drawing_placement": placement},
            "role_candidates": [role_candidate("figure.placement", "source", "observable Word drawing size, anchor/wrap state, caption relation, and surrounding flow")],
            "context": {
                "drawing_ordinal": ordinal,
                "relationship_id": drawing.get("relationship_id"),
                "part": drawing.get("part"),
                "paragraph_index": drawing.get("paragraph_index"),
                "caption_relation": relation,
                "outer_flow_context": drawing.get("outer_flow_context") or {},
                "source_section_index": drawing.get("source_section_index"),
            },
        })
    for ordinal, shape in enumerate(objects.get("document_vml_shapes") or [], start=1):
        if not isinstance(shape, dict):
            continue
        shapes = shape.get("shapes") if isinstance(shape.get("shapes"), list) else []
        if not shapes:
            continue
        units.append({
            "evidence_id": f"vml.d{ordinal:03d}.placement",
            "kind": "vml_placement",
            "text": f"Word VML object {ordinal}: {shape.get('image_part') or shape.get('ole_program') or 'shape group'}.",
            "has_direct_format": True,
            "format_signature": {"vml_placement": {"shapes": shapes, "image_part": shape.get("image_part"), "text_box_text": shape.get("text_box_text") or []}},
            "role_candidates": [
                role_candidate("figure.placement", "candidate", "VML image or shape geometry needs semantic review before figure mapping"),
                role_candidate("floating_text", "candidate", "VML shape may be a positioned text or cover element"),
            ],
            "context": {"part": shape.get("part"), "paragraph_index_in_part": shape.get("paragraph_index_in_part"), "image_relationship_id": shape.get("image_relationship_id")},
        })
    for ordinal, box in enumerate(objects.get("document_text_boxes") or [], start=1):
        if not isinstance(box, dict) or not isinstance(box.get("geometry"), dict):
            continue
        geometry = box.get("geometry") or {}
        if not geometry:
            continue
        units.append({
            "evidence_id": f"textbox.d{ordinal:03d}.placement",
            "kind": "text_box_placement",
            "text": f"Word text box {ordinal}: {str(box.get('text') or '')[:160] or 'no visible text'}.",
            "has_direct_format": True,
            "format_signature": {"text_box_placement": {"kind": box.get("kind"), "geometry": geometry}},
            "role_candidates": [role_candidate("floating_text", "source", "observable Word text-box geometry and non-flow placement")],
            "context": {"text_box_index": box.get("index") or ordinal, "part": box.get("part"), "requires_visual_review": bool(box.get("requires_visual_review"))},
        })
    def vml_line_signature(shape: dict) -> tuple[str, str, str, str] | None:
        """Return a stable signature for a VML line used as a rule fallback."""
        if not isinstance(shape, dict):
            return None
        kind = str(shape.get("kind") or shape.get("edge") or "").lower()
        if kind not in {"line", "drawing_line"}:
            return None
        start = str(shape.get("from") or "").strip().lower()
        end = str(shape.get("to") or "").strip().lower()
        weight = str(shape.get("strokeweight") or "").strip().lower()
        color = str(shape.get("strokecolor") or shape.get("color") or "").strip().lower()
        if not start or not end or not weight:
            return None
        return start, end, weight, color

    for part in objects.get("header_footer_parts") or []:
        if not isinstance(part, dict):
            continue
        part_name = safe_identifier(part.get("part"))
        fallback_rule_signatures = {
            signature
            for rule in (part.get("rules") or [])
            if isinstance(rule, dict)
            for signature in [vml_line_signature(rule.get("fallback_vml") or {})]
            if signature is not None
        }
        for kind, entries in (("drawing", part.get("drawings") or []), ("vml", part.get("vml_shapes") or []), ("text_box", part.get("text_boxes") or [])):
            for ordinal, entry in enumerate(entries, start=1):
                if not isinstance(entry, dict):
                    continue
                geometry = entry.get("geometry") if isinstance(entry.get("geometry"), dict) else {}
                shape_style = entry.get("shapes") if isinstance(entry.get("shapes"), list) else []
                if not geometry and not shape_style and kind != "drawing":
                    continue
                vml_signatures = [vml_line_signature(shape) for shape in shape_style]
                if (
                    kind == "vml"
                    and vml_signatures
                    and all(signature is not None and signature in fallback_rule_signatures for signature in vml_signatures)
                ):
                    # The DrawingML rule is already an atomic furniture_rule;
                    # this VML object is its compatibility serialization.
                    continue
                units.append({
                    "evidence_id": f"furniture.{part_name}.{kind}{ordinal:03d}.placement",
                    "kind": "furniture_placement",
                    "text": f"Word {part.get('kind') or 'furniture'} {kind} {ordinal} in {part.get('part') or 'unknown part'}.",
                    "has_direct_format": True,
                    "format_signature": {"furniture_placement": {"kind": kind, "geometry": geometry, "shapes": shape_style, "drawing": entry if kind == "drawing" else {}}},
                    "role_candidates": [role_candidate("running_furniture", "source", "observable Word header/footer visual object and placement")],
                    "context": {"part": part.get("part"), "furniture_kind": part.get("kind"), "object_index": ordinal},
                })
        for ordinal, rule in enumerate(part.get("rules") or [], start=1):
            if not isinstance(rule, dict):
                continue
            units.append({
                "evidence_id": f"furniture.{part_name}.rule{ordinal:03d}",
                "kind": "furniture_rule",
                "text": f"Word {part.get('kind') or 'furniture'} rule {ordinal} in {part.get('part') or 'unknown part'}.",
                "has_direct_format": True,
                "format_signature": {"furniture_rule": rule},
                "role_candidates": [role_candidate("running_furniture", "source", "observable Word header/footer border or DrawingML/VML line")],
                "context": {
                    "part": part.get("part"),
                    "furniture_kind": part.get("kind"),
                    "rule_index": ordinal,
                    "source": rule.get("source") or "paragraph_border",
                    "requires_visual_review": rule.get("edge") == "drawing_line",
                },
            })
    return units


def ancillary_record(
    paragraph: dict,
    *,
    evidence_id: str,
    container: str,
    role: str,
    context: dict,
) -> dict | None:
    """Normalize ancillary text or explicit blank-layout paragraphs for the ledger."""
    item = dict(paragraph)
    text = str(item.get("format_span_text") or item.get("text") or "").strip()
    layout_only = bool(item.get("layout_only"))
    if not text and not layout_only:
        return None
    item["evidence_id"] = evidence_id
    item["text"] = text
    item["layout_only"] = layout_only
    item["container"] = container
    item["context"] = context
    item["role_candidates"] = [
        role_candidate(
            "paragraph.layout" if layout_only else role,
            "source",
            f"empty {container} paragraph with explicit layout evidence" if layout_only else f"visible {container} evidence",
        )
    ]
    spans = []
    for span_number, span in enumerate(item.get("format_spans") or [], 1):
        record = dict(span)
        record["evidence_id"] = f"{evidence_id}.r{span_number:02d}"
        spans.append(record)
    item["format_spans"] = spans
    return item


def ancillary_units(inspection: dict) -> tuple[list[dict], list[dict]]:
    """Preserve visible non-body text and disclose any bounded source capture."""
    units: list[dict] = []
    capture_limitations: list[dict] = []

    for part in inspection.get("header_footer_parts") or []:
        if not isinstance(part, dict):
            continue
        part_id = safe_identifier(part.get("part"))
        kind = str(part.get("kind") or "header_footer")
        for number, paragraph in enumerate(part.get("paragraphs") or [], 1):
            if not isinstance(paragraph, dict):
                continue
            record = ancillary_record(
                paragraph,
                evidence_id=f"furniture.{part_id}.p{number:03d}",
                container=kind,
                role="running_furniture",
                context={"part": part.get("part"), "kind": kind},
            )
            if record:
                units.append(record)
        for box in part.get("text_boxes") or []:
            units.extend(text_box_units(box, part.get("part"), capture_limitations))

    for note_kind, role, key in (
        ("footnote", "footnote.content", "footnote_samples"),
        ("endnote", "endnote.content", "endnote_samples"),
    ):
        counters: dict[str, int] = defaultdict(int)
        for paragraph in inspection.get(key) or []:
            if not isinstance(paragraph, dict):
                continue
            note_id = safe_identifier(paragraph.get("note_id"))
            counters[note_id] += 1
            record = ancillary_record(
                paragraph,
                evidence_id=f"{note_kind}.{note_id}.p{counters[note_id]:03d}",
                container=note_kind,
                role=role,
                context={"note_id": paragraph.get("note_id"), "kind": note_kind},
            )
            if record:
                units.append(record)

    for box in inspection.get("text_boxes") or []:
        units.extend(text_box_units(box, "word/document.xml", capture_limitations))

    return units, capture_limitations


def text_box_units(box: object, fallback_part: object, capture_limitations: list[dict]) -> list[dict]:
    if not isinstance(box, dict):
        return []
    part = box.get("part") or fallback_part
    part_id = safe_identifier(part)
    box_id = int(box.get("index") or 0)
    if box.get("paragraphs_truncated"):
        capture_limitations.append({
            "area": "text_box",
            "part": part,
            "box_index": box.get("index"),
            "reason": "Text-box paragraph evidence was truncated; rebuild the ledger with full ancillary evidence.",
        })
    records = []
    for number, paragraph in enumerate(box.get("paragraphs") or [], 1):
        if not isinstance(paragraph, dict):
            continue
        record = ancillary_record(
            paragraph,
            evidence_id=f"textbox.{part_id}.b{box_id:03d}.p{number:03d}",
            container="text_box",
            role="floating_text",
            context={
                "part": part,
                "box_index": box.get("index"),
                "box_kind": box.get("kind"),
                "geometry": box.get("geometry") or {},
                "requires_visual_review": bool(box.get("requires_visual_review")),
            },
        )
        if record:
            records.append(record)
    return records


def build_ledger(source: Path) -> dict:
    inspection = inspect_docx(source, full_paragraph_evidence=True)
    paragraphs = list(inspection.get("paragraph_samples") or [])
    non_body_units, capture_limitations = ancillary_units(inspection)
    boundaries = zone_boundaries(paragraphs)
    first_index = first_title_index(paragraphs, boundaries["abstract"])
    heading_levels = {
        int(item.get("index") or 0): (word_heading_level(item) or 0)
        for item in inspection.get("heading_candidates") or []
    }
    heading_indexes = set(heading_levels)
    post_keyword_headings = [index for index in heading_indexes if boundaries["keywords"] is not None and index > boundaries["keywords"]]
    english_title_index = None
    english_front_matter_end = None
    if boundaries["keywords"] is not None:
        upper_bound = min(post_keyword_headings) if post_keyword_headings else (boundaries["references"] or 10**9)
        english_front_matter_end = upper_bound - 1
        for paragraph in paragraphs:
            index = int(paragraph.get("index") or 0)
            text = str(paragraph.get("format_span_text") or paragraph.get("text") or "")
            if boundaries["keywords"] < index < upper_bound and len(text) >= 20 and latin_ratio(text) >= 0.45 and not text.lower().startswith("doi"):
                english_title_index = index
                break
    caption_kinds = {
        int(item.get("paragraph_index") or 0): str(item.get("kind"))
        for item in inspection.get("caption_candidates") or []
        if str(item.get("kind")) in {"figure", "table"} and not bool(item.get("in_table_cell"))
    }
    reference_entries = {int(item.get("paragraph_index") or 0) for item in inspection.get("list_items") or []}
    role_index: dict[str, list[str]] = defaultdict(list)
    ledger_paragraphs = []
    for paragraph in paragraphs:
        item = dict(paragraph)
        index = int(item.get("index") or 0)
        item["evidence_id"] = f"p{index:04d}"
        item["text"] = str(item.get("format_span_text") or item.get("text") or "")
        spans = []
        for span in item.get("format_spans") or []:
            for fragment in split_inline_instruction_span(span if isinstance(span, dict) else {}):
                spans.append(dict(fragment))
        for span_number, record in enumerate(spans, 1):
            record["evidence_id"] = f"p{index:04d}.r{span_number:02d}"
        item["format_spans"] = spans
        if guidance := guidance_evidence(item):
            item["guidance_evidence"] = guidance
        mixed_prefix_role = mixed_front_matter_prefix_role(
            item,
            first_index=first_index,
            abstract_index=boundaries["abstract"],
        )
        item["role_candidates"] = paragraph_roles(
            item,
            first_index=first_index,
            abstract_index=boundaries["abstract"],
            keyword_index=boundaries["keywords"],
            reference_index=boundaries["references"],
            appendix_index=boundaries["appendix"],
            heading_levels=heading_levels,
            caption_kinds=caption_kinds,
            reference_entries=reference_entries,
            english_title_index=english_title_index,
            english_front_matter_end=english_front_matter_end,
            mixed_prefix_role=mixed_prefix_role,
        )
        if item.get("layout_only"):
            item["role_candidates"] = [
                role_candidate(
                    "paragraph.layout",
                    "source",
                    "empty Word paragraph with explicit paragraph layout, break, tab, or anchored-object evidence",
                )
            ]
        provisional_roles = {
            str(candidate.get("role"))
            for candidate in item["role_candidates"]
            if isinstance(candidate, dict)
        }
        review_inline_runs = bool(provisional_roles & {
            "front_matter.title",
            "front_matter.author",
            "front_matter.abstract",
            "front_matter.keywords",
            "front_matter.english_title",
            "front_matter.english_author",
            "front_matter.english_abstract",
            "front_matter.english_keywords",
        }) or "guidance.instruction" in provisional_roles
        inline_guidance_active = False
        substantive_content_seen = False
        for span in item["format_spans"]:
            if not isinstance(span, dict):
                continue
            span_text = str(span.get("text") or "")
            if label_role := standalone_label_role(span_text):
                if substantive_content_seen and label_role.startswith("front_matter."):
                    inline_guidance_active = True
                    span["guidance_evidence"] = {
                        "classification": "inline_repeated_label_instruction",
                        "signals": ["repeated_front_matter_label_after_content"],
                        "reason": "A repeated front-matter label appears after visible field content and begins an inline author instruction rather than a second structural field.",
                    }
                    span["role_candidates"] = [
                        role_candidate("guidance.instruction", "source", span["guidance_evidence"]["reason"])
                    ]
                    continue
                span["role_candidates"] = [
                    role_candidate(label_role, "source", "bare visible semantic label separated from adjacent Word guidance")
                ]
                continue
            if review_inline_runs:
                inline_guidance = mixed_front_matter_guidance_evidence(span)
                if inline_guidance:
                    inline_guidance_active = True
                elif inline_guidance_active and str(span.get("text") or "").strip():
                    inline_guidance = {
                        "classification": "inline_editorial_instruction_continuation",
                        "signals": ["continues_prior_inline_instruction"],
                        "reason": "This run continues a source-visible front-matter instruction that began earlier in the same paragraph; audit it separately from the surrounding manuscript-role label.",
                    }
                if inline_guidance:
                    span["guidance_evidence"] = inline_guidance
                    span["role_candidates"] = [
                        role_candidate("guidance.instruction", "source", inline_guidance["reason"])
                    ]
                elif mixed_prefix_role and not inline_guidance_active and str(span.get("text") or "").strip():
                    span["role_candidates"] = [
                        role_candidate(
                            mixed_prefix_role,
                            "candidate",
                            "visible front-matter exemplar span before a separate inline instruction run",
                        )
                    ]
            if span_text.strip() and not inline_guidance_active and not span.get("guidance_evidence"):
                substantive_content_seen = True
        for candidate in item["role_candidates"]:
            role_index[candidate["role"]].append(item["evidence_id"])
        ledger_paragraphs.append(item)
    sequence_review = front_matter_sequence_review(ledger_paragraphs, boundaries["abstract"])
    for item in non_body_units:
        for candidate in item.get("role_candidates") or []:
            role = candidate.get("role") if isinstance(candidate, dict) else None
            if role:
                role_index[str(role)].append(str(item["evidence_id"]))
    objects = {
        "tables": inspection.get("tables") or [],
        "body_drawings": inspection.get("body_drawings") or [],
        "document_text_boxes": inspection.get("text_boxes") or [],
        "document_vml_shapes": inspection.get("vml_shapes") or [],
        "header_footer_parts": inspection.get("header_footer_parts") or [],
        "sections": inspection.get("sections") or [],
        "line_numbering": inspection.get("line_numbering") or {},
        "text_grid_evidence": inspection.get("text_grid_evidence") or {},
        "tab_stop_evidence": inspection.get("tab_stop_evidence") or [],
        "drop_cap_evidence": inspection.get("drop_cap_evidence") or [],
        "character_effect_evidence": inspection.get("character_effect_evidence") or [],
        "character_style_evidence": inspection.get("character_style_evidence") or [],
        "script_language_evidence": inspection.get("script_language_evidence") or {},
        "paragraph_direction_evidence": inspection.get("paragraph_direction_evidence") or {},
        "paragraph_break_policy_evidence": inspection.get("paragraph_break_policy_evidence") or {},
        "theme_format_evidence": inspection.get("theme_format_evidence") or {},
        "unmodeled_format_properties": inspection.get("unmodeled_format_properties") or {},
        "toc_evidence": inspection.get("toc_evidence") or {},
        "boundaries": boundaries,
        "caption_candidates": inspection.get("caption_candidates") or [],
        "footnotes": inspection.get("footnote_references") or [],
        "endnotes": inspection.get("endnote_references") or [],
        "footnote_numbering": inspection.get("footnote_numbering") or {},
        "endnote_numbering": inspection.get("endnote_numbering") or {},
        "footnote_count": inspection.get("footnote_count") or 0,
        "endnote_count": inspection.get("endnote_count") or 0,
        "list_items": inspection.get("list_items") or [],
        "equations": inspection.get("equations") or [],
        "paragraphs": ledger_paragraphs,
    }
    object_evidence = object_evidence_units(objects)
    for item in object_evidence:
        for candidate in item.get("role_candidates") or []:
            role = candidate.get("role") if isinstance(candidate, dict) else None
            if role:
                role_index[str(role)].append(str(item["evidence_id"]))
    mappings = []
    for role, owner in ROLE_OWNERS.items():
        evidence = role_index.get(role, [])
        mappings.append({
            "role": role,
            **owner,
            "evidence_ids": evidence,
            "status": "evidence_found" if evidence else "needs_default_or_manual_evidence",
        })
    ledger = {
        "schema_version": "temp2tex.word-format-ledger.v3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "language_hint": inspection.get("language_hint"),
        "method": "every captured visible Word body, table-cell, header/footer, note, and text-box paragraph plus contiguous run-format span is retained before LaTeX mapping",
        "coverage": {
            "body_and_table_cell_paragraphs": len(ledger_paragraphs),
            "layout_only_body_and_table_cell_paragraphs": sum(bool(item.get("layout_only")) for item in ledger_paragraphs),
            "ancillary_paragraphs": len(non_body_units),
            "layout_only_ancillary_paragraphs": sum(bool(item.get("layout_only")) for item in non_body_units),
            "ancillary_containers": ["header", "footer", "footnote", "endnote", "text_box"],
            "capture_limitations": capture_limitations,
            "all_visible_text_units_captured": not capture_limitations,
            "observable_table_structure_units": sum(item.get("kind") == "table_structure" for item in object_evidence),
            "observable_drawing_placement_units": sum(item.get("kind") == "drawing_placement" for item in object_evidence),
            "observable_text_box_placement_units": sum(item.get("kind") == "text_box_placement" for item in object_evidence),
            "observable_vml_placement_units": sum(item.get("kind") == "vml_placement" for item in object_evidence),
            "observable_furniture_placement_units": sum(item.get("kind") == "furniture_placement" for item in object_evidence),
            "observable_cover_structure_units": sum(item.get("kind") == "cover_structure" for item in object_evidence),
            "observable_toc_structure_units": sum(item.get("kind") == "toc_structure" for item in object_evidence),
            "observable_toc_layout_units": sum(item.get("kind") == "toc_layout" for item in object_evidence),
            "observable_page_frame_units": sum(item.get("kind") == "page_frame" for item in object_evidence),
            "observable_page_column_units": sum(item.get("kind") == "page_columns" for item in object_evidence),
            "observable_page_numbering_units": sum(item.get("kind") == "page_numbering" for item in object_evidence),
            "observable_footnote_system_units": sum(item.get("kind") == "footnote_system" for item in object_evidence),
            "observable_endnote_system_units": sum(item.get("kind") == "endnote_system" for item in object_evidence),
            "observable_references_system_units": sum(item.get("kind") == "references_system" for item in object_evidence),
            "observable_appendix_system_units": sum(item.get("kind") == "appendix_system" for item in object_evidence),
            "observable_list_system_units": sum(item.get("kind") == "list_system" for item in object_evidence),
            "observable_equation_system_units": sum(item.get("kind") == "equation_system" for item in object_evidence),
            "observable_equation_instance_units": sum(item.get("kind") == "equation_instance" for item in object_evidence),
            "observable_block_decoration_units": sum(item.get("kind") == "block_decoration" for item in object_evidence),
            "all_observable_object_units_captured": True,
            "required_action_when_incomplete": "Resolve source capture limitations before treating the atomic mapping audit as complete.",
        },
        "boundaries": boundaries,
        "zones": zones(max((int(item.get("index") or 0) for item in paragraphs), default=0), boundaries),
        "front_matter_sequence_review": sequence_review,
        "paragraphs": ledger_paragraphs,
        "ancillary_units": non_body_units,
        "object_evidence": object_evidence,
        "mapping_queue": mappings,
        "objects": objects,
        "notes": [
            "Role candidates are evidence proposals, not final journal rules. Confirm each mapping against visible Word layout and official instructions.",
            "When front_matter_sequence_review requires semantic confirmation, resolve the ordered front-matter fields before generating or approving the class interface.",
            "Run formatting is local by default. Promote it to a whole-role format only when every visible run in the selected role agrees.",
            "Body artwork remains an asset candidate; compare its geometry and caption, not its manuscript-specific pixels.",
        ],
    }
    ledger["evidence_fingerprint"] = evidence_fingerprint(ledger_paragraphs, non_body_units, object_evidence)
    return ledger


def unavailable_word_ledger(source: Path, diagnosis: dict, conversion: dict | None = None) -> dict:
    """Retain an unusable Word source as explicit evidence instead of crashing.

    A publisher link sometimes saves an HTML error page, protected OLE payload,
    or another non-OpenXML file with a DOCX-looking name. The agent still needs
    a concrete handoff: preserve the original, seek an official replacement or
    PDF/web evidence, and never upgrade this record into Word-format coverage.
    """
    reason = str(diagnosis.get("error") or "Word payload could not be inspected.")
    source_kind = str(diagnosis.get("source_claim") or source.suffix.lower().lstrip(".") or "unknown")
    source_input = {
        "status": "unavailable",
        "source_kind": source_kind,
        "detected_payload": diagnosis.get("detected_payload") or "unknown",
        "reason": reason,
        "required_next_action": "Preserve this original file, obtain a valid official Word download when possible, and use official PDF/web evidence with documented defaults in the meantime.",
    }
    if conversion is not None:
        source_input["conversion_attempt"] = conversion
    mappings = [
        {
            "role": role,
            **owner,
            "evidence_ids": [],
            "status": "needs_default_or_manual_evidence",
        }
        for role, owner in ROLE_OWNERS.items()
    ]
    ledger = {
        "schema_version": "temp2tex.word-format-ledger.v3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "language_hint": "unknown",
        "source_input": source_input,
        "method": "No Word paragraph/run extraction was possible; this diagnostic preserves failed input triage and blocks Word-format fidelity claims.",
        "coverage": {
            "body_and_table_cell_paragraphs": 0,
            "ancillary_paragraphs": 0,
            "ancillary_containers": [],
            "capture_limitations": [{"scope": "source_payload", "reason": reason}],
            "all_visible_text_units_captured": False,
            "all_observable_object_units_captured": False,
            "required_action_when_incomplete": "Obtain an inspectable official Word payload or retain official PDF/web evidence and explicit defaults before treating any package as source-faithful.",
        },
        "boundaries": {"abstract": None, "keywords": None, "references": None, "appendix": None},
        "zones": [],
        "front_matter_sequence_review": {
            "source": "unavailable Word payload",
            "entries": [],
            "role_positions": {},
            "checks": [{"code": "word_payload_unavailable", "severity": "blocking", "reason": reason}],
            "requires_semantic_confirmation": False,
            "status": "not_available",
            "instruction": "Do not infer title, author, or other Word-specific front-matter roles from this unavailable payload.",
        },
        "paragraphs": [],
        "ancillary_units": [],
        "object_evidence": [],
        "mapping_queue": mappings,
        "objects": {"paragraphs": []},
        "notes": [
            "This is an input-diagnostic ledger, not a successful Word extraction.",
            "Do not use its empty role queue as evidence that the Word template has no formatting requirements.",
        ],
    }
    ledger["evidence_fingerprint"] = evidence_fingerprint([], [], [])
    return ledger


def build_ledger_from_word_source(source: Path, retained_docx: Path | None = None, retained_docx_relpath: str | None = None) -> dict:
    """Extract legacy Word through a temporary DOCX while retaining provenance."""
    if is_openxml_word_package(source):
        return build_ledger(source)
    if source.suffix.lower() in {".docx", ".docm", ".dotx", ".dotm"}:
        return unavailable_word_ledger(source, invalid_openxml_word_details(source))
    soffice_candidates = tool_candidates("soffice")
    if not soffice_candidates:
        return unavailable_word_ledger(source, {
            "source_claim": source.suffix.lower().lstrip("."),
            "detected_payload": "legacy-or-unknown",
            "error": "Source is not OpenXML and LibreOffice is unavailable for a temporary DOCX conversion.",
        })
    with tempfile.TemporaryDirectory(prefix="temp2tex-ledger-") as directory:
        temporary_root = Path(directory)
        conversion = run_soffice_convert(soffice_candidates[0], source, "docx", temporary_root)
        converted = sorted(temporary_root.glob("*.docx"))
        if not conversion.get("ok") or not converted or not is_openxml_word_package(converted[0]):
            detail = str(conversion.get("error") or conversion.get("stderr_tail") or "no valid DOCX produced")
            return unavailable_word_ledger(source, {
                "source_claim": source.suffix.lower().lstrip("."),
                "detected_payload": "legacy-or-unknown",
                "error": f"LibreOffice could not create an inspectable DOCX from the legacy source: {detail}",
            }, conversion)
        ledger = build_ledger(converted[0])
        derived_sha256 = file_sha256(converted[0])
        retained = False
        if retained_docx is not None:
            retained_docx.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(converted[0], retained_docx)
            retained = True
        ledger["source"] = str(source)
        ledger["source_conversion"] = {
            "status": "converted_for_inspection",
            "source_kind": source.suffix.lower().lstrip("."),
            "source_sha256": file_sha256(source),
            "converted_kind": "docx",
            "converter": "LibreOffice",
            "conversion": conversion,
            "derived_docx": {
                "retained": retained,
                "package_relative_path": retained_docx_relpath if retained else None,
                "sha256": derived_sha256,
            },
            "note": "The original legacy Word artifact remains the authority; the derived DOCX enabled structured paragraph/run extraction and must be checked against an original render before a source-fidelity claim.",
        }
        ledger["notes"].append(
            "Legacy Word evidence was extracted from a LibreOffice-derived DOCX. Retain the derived artifact with its hash and compare it with the original legacy render before a source-fidelity claim."
        )
        return ledger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Official DOC/DOCX/DOCM/DOT/DOTX/DOTM/RTF Word template")
    parser.add_argument("--output", required=True, help="Output word_format_ledger.json")
    parser.add_argument(
        "--retain-derived-docx",
        help="For legacy DOC/DOT/RTF, save the LibreOffice-derived inspection DOCX at this relative path inside the output directory.",
    )
    args = parser.parse_args()
    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        print("source not found", file=sys.stderr)
        return 2
    output = Path(args.output).expanduser().resolve()
    retained_docx = None
    retained_docx_relpath = None
    if args.retain_derived_docx:
        candidate = Path(args.retain_derived_docx)
        if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
            print("--retain-derived-docx must be a relative path inside the output directory", file=sys.stderr)
            return 2
        retained_docx_relpath = candidate.as_posix()
        retained_docx = output.parent / candidate
    try:
        ledger = build_ledger_from_word_source(source, retained_docx, retained_docx_relpath)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
