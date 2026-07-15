#!/usr/bin/env python3
"""Create a paragraph-and-run format ledger from an OpenXML Word template."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from inspect_sources import inspect_docx, is_openxml_word_package


ROLE_OWNERS = {
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
    "body.paragraph": {"owner": "journal-template.cls", "interface": "body font and paragraph settings"},
    "table.caption": {"owner": "journal-template.cls", "interface": "journaltable + caption setup"},
    "figure.caption": {"owner": "journal-template.cls", "interface": "journalfigure + caption setup"},
    "references.heading": {"owner": "journal-template.cls", "interface": "bibliography heading"},
    "references.entry": {"owner": "journal-template.cls", "interface": "bibliography backend and entry layout"},
    "appendix.heading": {"owner": "journal-template.cls", "interface": "\\journalappendix + \\section"},
}

AFFILIATION_MARKERS = ("大学", "学院", "研究所", "实验室", "单位", "地址", "邮编", "university", "college", "institute", "laboratory", "department")
ABSTRACT_MARKERS = ("摘要", "abstract")
KEYWORD_MARKERS = ("关键词", "关键字", "keywords", "key words")
REFERENCE_MARKERS = ("参考文献", "references", "bibliography")
APPENDIX_MARKERS = ("附录", "附錄", "appendix", "appendices")


def normalized(value: str) -> str:
    return re.sub(r"\s+", "", value or "").lower()


def starts_with(value: str, markers: tuple[str, ...]) -> bool:
    return any(normalized(value).startswith(normalized(marker)) for marker in markers)


def heading_level(text: str) -> int | None:
    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?[.)]?\s*\S+", text.strip())
    if not match:
        return None
    return sum(group is not None for group in match.groups()[1:])


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
    heading_indexes: set[int],
    caption_kinds: dict[int, str],
    reference_entries: set[int],
    english_title_index: int | None,
) -> list[dict]:
    index = int(paragraph.get("index") or 0)
    text = str(paragraph.get("format_span_text") or paragraph.get("text") or "").strip()
    if index in caption_kinds:
        return [role_candidate(f"{caption_kinds[index]}.caption", "source", "visible caption label and source paragraph index")]
    if starts_with(text, REFERENCE_MARKERS):
        return [role_candidate("references.heading", "source", "visible references heading")]
    if starts_with(text, APPENDIX_MARKERS):
        return [role_candidate("appendix.heading", "source", "visible appendix heading")]
    if abstract_index is not None and index == abstract_index:
        return [role_candidate("front_matter.abstract", "source", "visible abstract label")]
    if starts_with(text, KEYWORD_MARKERS):
        return [role_candidate("front_matter.keywords", "source", "visible keyword label")]
    if abstract_index is not None and keyword_index is not None and abstract_index < index < keyword_index:
        # Chinese abstract paragraphs frequently continue until the keyword
        # label without repeating 摘要. Preserve that zone before treating the
        # continuation as ordinary body text.
        return [role_candidate("front_matter.abstract", "candidate", "continuation before the visible keyword label")]
    if reference_index is not None and index > reference_index and (appendix_index is None or index < appendix_index):
        if index in reference_entries or paragraph.get("list_evidence"):
            return [role_candidate("references.entry", "source", "reference-zone list evidence")]
    if first_index is not None and index == first_index:
        return [role_candidate("front_matter.title", "candidate", "first visible manuscript paragraph")]
    if abstract_index is not None and index < abstract_index:
        lower = text.lower()
        if re.match(r"^\d+[.)]\s*\S+", text):
            return [role_candidate("front_matter.affiliation", "candidate", "numbered pre-abstract affiliation line")]
        if any(marker in lower for marker in AFFILIATION_MARKERS):
            return [role_candidate("front_matter.affiliation", "candidate", "pre-abstract affiliation marker")]
        if len(text) <= 120:
            return [role_candidate("front_matter.author", "candidate", "short pre-abstract metadata paragraph")]
    if english_title_index is not None and index == english_title_index:
        return [role_candidate("front_matter.english_title", "candidate", "first English title-like paragraph after Chinese metadata")]
    if english_title_index is not None and index > english_title_index and latin_ratio(text) >= 0.45:
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
    level = heading_level(text)
    if index in heading_indexes or level is not None:
        level = 0 if level is None else min(level, 2)
        return [role_candidate(f"heading.level{level}", "source" if index in heading_indexes else "candidate", "Word heading evidence" if index in heading_indexes else "numbered visible paragraph")]
    return [role_candidate("body.paragraph", "candidate", "remaining visible manuscript-flow paragraph")]


def zone_boundaries(paragraphs: list[dict]) -> dict[str, int | None]:
    boundaries = {"abstract": None, "keywords": None, "references": None, "appendix": None}
    for paragraph in paragraphs:
        index = int(paragraph.get("index") or 0)
        text = str(paragraph.get("format_span_text") or paragraph.get("text") or "")
        for name, markers in (("abstract", ABSTRACT_MARKERS), ("keywords", KEYWORD_MARKERS), ("references", REFERENCE_MARKERS), ("appendix", APPENDIX_MARKERS)):
            if boundaries[name] is None and starts_with(text, markers):
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


def build_ledger(source: Path) -> dict:
    inspection = inspect_docx(source, full_paragraph_evidence=True)
    paragraphs = list(inspection.get("paragraph_samples") or [])
    first_index = next((int(item.get("index") or 0) for item in paragraphs if str(item.get("format_span_text") or item.get("text") or "").strip()), None)
    boundaries = zone_boundaries(paragraphs)
    heading_indexes = {int(item.get("index") or 0) for item in inspection.get("heading_candidates") or []}
    post_keyword_headings = [index for index in heading_indexes if boundaries["keywords"] is not None and index > boundaries["keywords"]]
    english_title_index = None
    if boundaries["keywords"] is not None:
        upper_bound = min(post_keyword_headings) if post_keyword_headings else (boundaries["references"] or 10**9)
        for paragraph in paragraphs:
            index = int(paragraph.get("index") or 0)
            text = str(paragraph.get("format_span_text") or paragraph.get("text") or "")
            if boundaries["keywords"] < index < upper_bound and len(text) >= 20 and latin_ratio(text) >= 0.45 and not text.lower().startswith("doi"):
                english_title_index = index
                break
    caption_kinds = {
        int(item.get("paragraph_index") or 0): str(item.get("kind"))
        for item in inspection.get("caption_candidates") or []
        if str(item.get("kind")) in {"figure", "table"}
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
        for span_number, span in enumerate(item.get("format_spans") or [], 1):
            record = dict(span)
            record["evidence_id"] = f"p{index:04d}.r{span_number:02d}"
            spans.append(record)
        item["format_spans"] = spans
        item["role_candidates"] = paragraph_roles(
            item,
            first_index=first_index,
            abstract_index=boundaries["abstract"],
            keyword_index=boundaries["keywords"],
            reference_index=boundaries["references"],
            appendix_index=boundaries["appendix"],
            heading_indexes=heading_indexes,
            caption_kinds=caption_kinds,
            reference_entries=reference_entries,
            english_title_index=english_title_index,
        )
        for candidate in item["role_candidates"]:
            role_index[candidate["role"]].append(item["evidence_id"])
        ledger_paragraphs.append(item)
    mappings = []
    for role, owner in ROLE_OWNERS.items():
        evidence = role_index.get(role, [])
        mappings.append({
            "role": role,
            **owner,
            "evidence_ids": evidence,
            "status": "evidence_found" if evidence else "needs_default_or_manual_evidence",
        })
    return {
        "schema_version": "temp2tex.word-format-ledger.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "language_hint": inspection.get("language_hint"),
        "method": "every visible Word paragraph and contiguous run-format span is retained before LaTeX mapping",
        "boundaries": boundaries,
        "zones": zones(max((int(item.get("index") or 0) for item in paragraphs), default=0), boundaries),
        "paragraphs": ledger_paragraphs,
        "mapping_queue": mappings,
        "objects": {
            "tables": inspection.get("tables") or [],
            "body_drawings": inspection.get("body_drawings") or [],
            "caption_candidates": inspection.get("caption_candidates") or [],
            "footnotes": inspection.get("footnote_references") or [],
            "endnotes": inspection.get("endnote_references") or [],
        },
        "notes": [
            "Role candidates are evidence proposals, not final journal rules. Confirm each mapping against visible Word layout and official instructions.",
            "Run formatting is local by default. Promote it to a whole-role format only when every visible run in the selected role agrees.",
            "Body artwork remains an asset candidate; compare its geometry and caption, not its manuscript-specific pixels.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Official DOCX/DOCM/DOTX/DOTM Word template")
    parser.add_argument("--output", required=True, help="Output word_format_ledger.json")
    args = parser.parse_args()
    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        print("source not found", file=sys.stderr)
        return 2
    if not is_openxml_word_package(source):
        print("source must be a valid OpenXML Word package; convert legacy DOC/DOT first", file=sys.stderr)
        return 2
    ledger = build_ledger(source)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
