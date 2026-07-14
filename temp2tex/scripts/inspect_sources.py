#!/usr/bin/env python3
"""Inspect journal template sources and write a source inventory."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import posixpath
import re
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_R_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
WP14_NS = "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
WPS_NS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": W_NS, "r": R_NS, "wp": WP_NS, "a": A_NS, "m": M_NS}
KNOWN_HEADINGS = {
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
    "appendix",
    "appendices",
    "author statement",
}
OPENXML_WORD_SUFFIXES = {".docx", ".docm", ".dotx", ".dotm"}


def qn(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_openxml_word_package(path: Path) -> bool:
    """Recognize Word OpenXML by package contents, not a download suffix."""
    if not zipfile.is_zipfile(path):
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
        return "[Content_Types].xml" in names and "word/document.xml" in names
    except (OSError, zipfile.BadZipFile):
        return False


def invalid_openxml_word_details(path: Path) -> dict:
    """Explain why a file claiming to be OpenXML Word is not inspectable."""
    try:
        prefix = path.read_bytes()[:4096]
    except OSError as exc:
        reason = f"Word payload could not be read: {exc}"
        detected = "unreadable"
    else:
        lowered = prefix.lstrip().lower()
        if lowered.startswith((b"<!doctype html", b"<html", b"<?xml")) and b"html" in lowered:
            reason = "File contains HTML rather than an OpenXML Word package."
            detected = "html"
        elif prefix.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
            reason = (
                "File uses an OLE compound payload rather than readable OpenXML; "
                "it may be encrypted, protected, or mislabeled."
            )
            detected = "ole-compound"
        elif zipfile.is_zipfile(path):
            reason = "ZIP payload is missing [Content_Types].xml or word/document.xml."
            detected = "incomplete-zip"
        else:
            reason = "File is not a valid ZIP-based OpenXML Word package."
            detected = "unknown-binary"
    return {
        "kind": "invalid-word",
        "valid_word_payload": False,
        "detected_payload": detected,
        "error": reason,
        "source_claim": path.suffix.lower().lstrip("."),
    }


def tool_candidates(name: str) -> list[str]:
    candidates = []
    if name == "soffice":
        candidates.extend([
            r"D:\LibreOffice\program\soffice.exe",
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ])
    try:
        proc = subprocess.run(["where.exe", name], text=True, capture_output=True, timeout=10)
        if proc.returncode == 0:
            candidates.extend(line.strip() for line in proc.stdout.splitlines() if line.strip())
    except Exception:
        pass
    unique = []
    for item in candidates:
        if item and item not in unique and Path(item).exists():
            unique.append(item)
    return unique


def text_of(node: ET.Element, *, exclude_textboxes: bool = False) -> str:
    """Read Word text while optionally excluding floating/text-box descendants."""
    pieces: list[str] = []

    def visit(current: ET.Element, inside_textbox: bool = False) -> None:
        in_textbox = inside_textbox or current.tag == f"{{{W_NS}}}txbxContent"
        if current.tag == f"{{{W_NS}}}t" and not (exclude_textboxes and in_textbox):
            pieces.append(current.text or "")
        for child in current:
            visit(child, in_textbox)

    visit(node)
    return re.sub(r"\s+", " ", "".join(pieces)).strip()


def caption_kind(text: str, style_name: str | None = None) -> tuple[str | None, str | None]:
    """Classify visible caption paragraphs without treating guidance prose as captions."""
    value = str(text or "").strip()
    style = str(style_name or "").lower().replace("_", " ")
    semantic_table = bool(re.search(r"\btable\s+(?:caption|title)\b|\bcaption\s+table\b", style))
    semantic_figure = bool(re.search(r"\b(?:figure|fig)\s+caption\b|\bcaption\s+(?:figure|fig)\b", style))
    instruction_like = any(marker in value.lower() for marker in (
        "example of a figure", "example of a table", "styles applied", "your figure",
        "your table", "you must", "please insert", "please remove", "should be placed",
    ))
    if re.match(r"^\s*(?:(?:table\b|tab\.)\s*(?:\d+|[ivxlcdm]+)(?:[.:]\s|\s|$)|表\s*(?:\d+|[A-Za-z]))", value, re.I):
        if instruction_like and not semantic_table:
            return None, None
        return "table", "visible label"
    if re.match(r"^\s*(?:(?:figure\b|fig\.)\s*(?:\d+|[ivxlcdm]+)(?:[.:]\s|\s|$)|(?:图|圖)\s*(?:\d+|[A-Za-z]))", value, re.I):
        if instruction_like and not semantic_figure:
            return None, None
        return "figure", "visible label"
    if semantic_table:
        return "table", "semantic Word style"
    if semantic_figure:
        return "figure", "semantic Word style"
    return None, None


def nearest_caption_relation(captions: list[dict], kind: str, start: int, end: int) -> dict:
    candidates = []
    for caption in captions:
        if caption.get("kind") != kind:
            continue
        # Caption-like text inside a table cell can be a header or note. It
        # does not prove the order of an external LaTeX caption.
        if caption.get("in_table_cell"):
            continue
        index = int(caption.get("paragraph_index") or 0)
        if start <= index <= end:
            position = "inside"
            distance = 0
        elif index < start:
            position = "above"
            distance = start - index
        else:
            position = "below"
            distance = index - end
        candidates.append((distance, index, position, caption))
    if not candidates:
        return {"position": "unknown", "confidence": "not_detected"}
    distance, index, position, caption = min(candidates, key=lambda item: (item[0], item[1]))
    confidence = "adjacent" if distance <= 2 else "nearby" if distance <= 5 else "distant"
    return {
        "position": position,
        "paragraph_distance": distance,
        "caption_paragraph_index": index,
        "caption_text": caption.get("text"),
        "caption_style_id": caption.get("style_id"),
        "caption_style_name": caption.get("style_name"),
        "classification_source": caption.get("classification_source"),
        "confidence": confidence,
    }


def textbox_geometry(root: ET.Element, box: ET.Element) -> dict:
    """Retain source geometry for an anchored Word text box.

    Text-box text is not enough to reconstruct a template: the same caption
    can be a right-side callout, a full-width label, or a footer note. Keep
    the native EMU offsets and the relative coordinate systems so a later
    render-confirmed LaTeX candidate can make an explicit placement choice.
    """
    parents = {child: parent for parent in root.iter() for child in parent}
    current = box
    anchor = None
    shape = None
    while current in parents:
        current = parents[current]
        local = current.tag.split("}")[-1]
        if local in {"anchor", "inline"} and current.tag.startswith(f"{{{WP_NS}}}"):
            anchor = current
        if current.tag == f"{{{WPS_NS}}}wsp":
            shape = current
    if anchor is None:
        return {}

    extent = anchor.find("wp:extent", NS)
    pos_h = anchor.find("wp:positionH", NS)
    pos_v = anchor.find("wp:positionV", NS)
    doc_pr = anchor.find("wp:docPr", NS)
    wrap = next((child for child in anchor if child.tag.split("}")[-1].startswith("wrap")), None)
    body_pr = shape.find(f"{{{WPS_NS}}}bodyPr") if shape is not None else None
    c_nv = shape.find(f"{{{WPS_NS}}}cNvSpPr") if shape is not None else None

    def offset(node: ET.Element | None, name: str) -> str | None:
        return node.findtext(f"wp:{name}", namespaces=NS) if node is not None else None

    geometry = {
        "anchor_type": "anchor" if anchor.tag == f"{{{WP_NS}}}anchor" else "inline",
        "width_emu": extent.attrib.get("cx") if extent is not None else None,
        "height_emu": extent.attrib.get("cy") if extent is not None else None,
        "horizontal_relative_to": pos_h.attrib.get("relativeFrom") if pos_h is not None else None,
        "horizontal_alignment": offset(pos_h, "align"),
        "horizontal_offset_emu": offset(pos_h, "posOffset"),
        "vertical_relative_to": pos_v.attrib.get("relativeFrom") if pos_v is not None else None,
        "vertical_alignment": offset(pos_v, "align"),
        "vertical_offset_emu": offset(pos_v, "posOffset"),
        "wrap_type": wrap.tag.split("}")[-1] if wrap is not None else None,
        "distance_top_emu": anchor.attrib.get("distT"),
        "distance_bottom_emu": anchor.attrib.get("distB"),
        "distance_left_emu": anchor.attrib.get("distL"),
        "distance_right_emu": anchor.attrib.get("distR"),
        "relative_height": anchor.attrib.get("relativeHeight"),
        "behind_doc": anchor.attrib.get("behindDoc"),
        "allow_overlap": anchor.attrib.get("allowOverlap"),
        "docpr_id": doc_pr.attrib.get("id") if doc_pr is not None else None,
        "docpr_name": doc_pr.attrib.get("name") if doc_pr is not None else None,
        "is_text_box": c_nv.attrib.get("txBox") == "1" if c_nv is not None else None,
        "body_left_inset_emu": body_pr.attrib.get("lIns") if body_pr is not None else None,
        "body_top_inset_emu": body_pr.attrib.get("tIns") if body_pr is not None else None,
        "body_right_inset_emu": body_pr.attrib.get("rIns") if body_pr is not None else None,
        "body_bottom_inset_emu": body_pr.attrib.get("bIns") if body_pr is not None else None,
    }
    # Word sometimes stores relative sizing as wp14 children rather than a
    # fixed extent. Preserve it without interpreting percentage zero values.
    rel_h = anchor.find(f"{{{WP14_NS}}}sizeRelH")
    rel_v = anchor.find(f"{{{WP14_NS}}}sizeRelV")
    if rel_h is not None:
        geometry["relative_width_from"] = rel_h.attrib.get("relativeFrom")
        geometry["relative_width_pct"] = rel_h.findtext(f"{{{WP14_NS}}}pctWidth")
    if rel_v is not None:
        geometry["relative_height_from"] = rel_v.attrib.get("relativeFrom")
        geometry["relative_height_pct"] = rel_v.findtext(f"{{{WP14_NS}}}pctHeight")
    return {key: value for key, value in geometry.items() if value not in (None, "")}


def drawing_geometry(node: ET.Element) -> dict:
    """Extract placement evidence for a body/header image drawing."""
    extent = node.find("wp:extent", NS)
    pos_h = node.find("wp:positionH", NS)
    pos_v = node.find("wp:positionV", NS)
    wrap = next((child for child in node if child.tag.split("}")[-1].startswith("wrap")), None)

    def offset(parent: ET.Element | None, local: str) -> str | None:
        return parent.findtext(f"wp:{local}", namespaces=NS) if parent is not None else None

    values = {
        "anchor_type": "anchor" if node.tag == f"{{{WP_NS}}}anchor" else "inline",
        "width_emu": extent.attrib.get("cx") if extent is not None else None,
        "height_emu": extent.attrib.get("cy") if extent is not None else None,
        "horizontal_relative_to": pos_h.attrib.get("relativeFrom") if pos_h is not None else None,
        "horizontal_alignment": offset(pos_h, "align"),
        "horizontal_offset_emu": offset(pos_h, "posOffset"),
        "vertical_relative_to": pos_v.attrib.get("relativeFrom") if pos_v is not None else None,
        "vertical_alignment": offset(pos_v, "align"),
        "vertical_offset_emu": offset(pos_v, "posOffset"),
        "wrap_type": wrap.tag.split("}")[-1] if wrap is not None else None,
        "distance_top_emu": node.attrib.get("distT"),
        "distance_bottom_emu": node.attrib.get("distB"),
        "distance_left_emu": node.attrib.get("distL"),
        "distance_right_emu": node.attrib.get("distR"),
        "relative_height": node.attrib.get("relativeHeight"),
        "behind_doc": node.attrib.get("behindDoc"),
        "allow_overlap": node.attrib.get("allowOverlap"),
    }
    return {key: value for key, value in values.items() if value not in (None, "")}


def text_box_samples(root: ET.Element | None, part: str) -> list[dict]:
    """Capture non-flow Word/VML text as evidence without promoting it to body text."""
    if root is None:
        return []
    samples = []
    seen: set[tuple[str, str, str]] = set()
    seen_texts: set[str] = set()
    for index, box in enumerate(root.findall(".//w:txbxContent", NS), 1):
        paragraphs = []
        for paragraph in box.findall(".//w:p", NS):
            text = text_of(paragraph)
            if text:
                paragraphs.append(text)
        text = " ".join(paragraphs).strip()
        if not text:
            continue
        geometry = textbox_geometry(root, box)
        # Some Word files expose the same shape through both w:txbxContent
        # and a drawingML text body. Prefer the representation that carries
        # anchor geometry instead of counting it twice.
        if not geometry and text in seen_texts:
            continue
        key = ("word_text_box", text, json.dumps(geometry, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        seen_texts.add(text)
        samples.append({
            "index": index,
            "kind": "word_text_box",
            "part": part,
            "text": text[:500],
            "paragraph_count": len(paragraphs),
            "geometry": geometry,
            "requires_visual_review": True,
        })
    # DrawingML text boxes do not always expose a w:txbxContent subtree.
    for index, body in enumerate(root.findall(".//a:txBody", NS), 1):
        text = re.sub(r"\s+", " ", "".join(node.text or "" for node in body.findall(".//a:t", NS))).strip()
        if not text:
            continue
        geometry = textbox_geometry(root, body)
        if not geometry and text in seen_texts:
            continue
        key = ("drawingml_text_box", text, json.dumps(geometry, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        seen_texts.add(text)
        samples.append({
            "index": index,
            "kind": "drawingml_text_box",
            "part": part,
            "text": text[:500],
            "paragraph_count": None,
            "geometry": geometry,
            "requires_visual_review": True,
        })
    return samples


def equation_samples(root: ET.Element | None, part: str) -> list[dict]:
    """Extract OMML equation context without attempting lossy math conversion."""
    if root is None:
        return []
    parents = {child: parent for parent in root.iter() for child in parent}
    samples = []
    for index, math in enumerate(root.findall(".//m:oMath", NS), 1):
        current = math
        paragraph = table_cell = None
        inside_textbox = False
        in_math_paragraph = False
        while current in parents:
            current = parents[current]
            if current.tag == f"{{{W_NS}}}p" and paragraph is None:
                paragraph = current
            elif current.tag == f"{{{W_NS}}}tc" and table_cell is None:
                table_cell = current
            elif current.tag == f"{{{W_NS}}}txbxContent":
                inside_textbox = True
            elif current.tag == f"{{{M_NS}}}oMathPara":
                in_math_paragraph = True
        math_text = re.sub(
            r"\s+",
            " ",
            "".join(node.text or "" for node in math.findall(".//m:t", NS)),
        ).strip()
        word_text = text_of(paragraph, exclude_textboxes=True) if paragraph is not None else ""
        number_matches = re.findall(r"\((?:[A-Za-z]+\.)?\d+(?:\.\d+)*[A-Za-z]?\)", word_text)
        # Display equations are normally their own OMML paragraph, or a Word
        # paragraph containing only an equation plus a parenthesized number.
        display_like = bool(in_math_paragraph or not word_text or re.fullmatch(r"\s*(?:\([^)]*\))?\s*", word_text))
        samples.append({
            "index": index,
            "part": part,
            "sample_text": math_text[:300],
            "word_text_outside_math": word_text[:300],
            "display_like": display_like,
            "number_samples": number_matches[:3],
            "in_table_cell": table_cell is not None,
            "in_text_box": inside_textbox,
            "requires_math_translation": bool(math_text),
        })
    return samples


def attr_val(node: ET.Element | None, name: str = "val") -> str | None:
    if node is None:
        return None
    return node.attrib.get(qn(name))


def read_docx_xml(zf: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        return ET.fromstring(zf.read(name))
    except KeyError:
        return None


def attrs(node: ET.Element | None) -> dict[str, str]:
    if node is None:
        return {}
    return {key.split("}")[-1]: value for key, value in node.attrib.items()}


def direct_format(ppr: ET.Element | None, rpr: ET.Element | None) -> dict:
    """Capture direct OOXML formatting without guessing inherited values."""
    fonts = attrs(rpr.find("w:rFonts", NS) if rpr is not None else None)
    bold_node = rpr.find("w:b", NS) if rpr is not None else None
    italic_node = rpr.find("w:i", NS) if rpr is not None else None
    font = {
        "family": fonts.get("ascii") or fonts.get("hAnsi"),
        "east_asia_family": fonts.get("eastAsia"),
        # Some Word templates specify the effective size only through szCs.
        # Preserve the ordinary Latin size when present, otherwise retain that
        # source-backed complex-script fallback instead of guessing 12pt.
        "size_half_points": (
            attr_val(rpr.find("w:sz", NS)) or attr_val(rpr.find("w:szCs", NS))
        ) if rpr is not None else None,
        "bold": None if bold_node is None else attr_val(bold_node) not in {"0", "false", "off"},
        "italic": None if italic_node is None else attr_val(italic_node) not in {"0", "false", "off"},
        "color": attr_val(rpr.find("w:color", NS)) if rpr is not None else None,
    }
    spacing = attrs(ppr.find("w:spacing", NS) if ppr is not None else None)
    indent = attrs(ppr.find("w:ind", NS) if ppr is not None else None)
    paragraph = {
        "alignment": attr_val(ppr.find("w:jc", NS)) if ppr is not None else None,
        "space_before_twips": spacing.get("before"),
        "space_after_twips": spacing.get("after"),
        "line_spacing": spacing.get("line"),
        "line_spacing_rule": spacing.get("lineRule"),
        "left_indent_twips": indent.get("left") or indent.get("start"),
        "right_indent_twips": indent.get("right") or indent.get("end"),
        "first_line_twips": indent.get("firstLine"),
        "hanging_twips": indent.get("hanging"),
        "keep_with_next": ppr.find("w:keepNext", NS) is not None if ppr is not None else None,
        "page_break_before": ppr.find("w:pageBreakBefore", NS) is not None if ppr is not None else None,
        "outline_level": attr_val(ppr.find("w:outlineLvl", NS)) if ppr is not None else None,
    }
    return {
        "font": {key: value for key, value in font.items() if value is not None},
        "paragraph": {key: value for key, value in paragraph.items() if value is not None},
    }


def uniform_run_font_evidence(paragraph: ET.Element) -> dict:
    """Return character formatting only when every visible run agrees.

    Word commonly stores a bold abstract or keyword line on ``w:rPr`` rather
    than on the paragraph style.  Promoting the first run is unsafe because a
    label such as ``Abstract:`` may be bold while the value is regular.  A
    uniform run summary preserves the paragraph-wide case without promoting
    local mixed formatting.
    """
    fonts = []
    for run in paragraph.findall("./w:r", NS):
        text = text_of(run).strip()
        if not text:
            continue
        rpr = run.find("./w:rPr", NS)
        font = direct_format(None, rpr).get("font", {}) if rpr is not None else {}
        fonts.append(font)
    if not fonts:
        return {}
    signatures = {json.dumps(font, sort_keys=True, ensure_ascii=False) for font in fonts}
    if len(signatures) != 1 or not fonts[0]:
        return {
            "uniform": False,
            "run_count": len(fonts),
            "distinct_font_count": len(signatures),
        }
    return {
        "uniform": True,
        "run_count": len(fonts),
        "font": fonts[0],
        "source": "uniform direct Word run character formatting",
    }


def paragraph_break_types(paragraph: ET.Element) -> list[str]:
    """Record explicit Word paragraph breaks that affect reading order."""
    values = []
    for node in paragraph.findall(".//w:br", NS):
        value = attr_val(node, "type") or "line"
        if value not in values:
            values.append(value)
    ppr = paragraph.find("w:pPr", NS)
    if ppr is not None and ppr.find("w:pageBreakBefore", NS) is not None:
        if "page" not in values:
            values.append("page")
    return values


def merge_format(*formats: dict | None) -> dict:
    """Merge Word defaults, basedOn styles, and direct overrides by role."""
    result: dict[str, dict] = {"font": {}, "paragraph": {}}
    for item in formats:
        if not isinstance(item, dict):
            continue
        for role in ("font", "paragraph"):
            value = item.get(role)
            if isinstance(value, dict):
                result[role].update({key: val for key, val in value.items() if val is not None})
    return {role: value for role, value in result.items() if value}


def inspect_header_footer_part(zf: zipfile.ZipFile, name: str) -> dict:
    root = read_docx_xml(zf, name)
    kind = "header" if Path(name).name.lower().startswith("header") else "footer"
    paragraphs = []
    drawings = []
    rules = []
    text_boxes = text_box_samples(root, name)
    if root is not None:
        for paragraph in root.findall(".//w:p", NS):
            text = text_of(paragraph)
            tokens = []
            field_state = None
            field_code = []
            for run in paragraph.findall("./w:r", NS):
                for node in list(run):
                    local = node.tag.split("}")[-1]
                    if local == "fldChar":
                        field_type = attr_val(node, "fldCharType")
                        if field_type == "begin":
                            field_state, field_code = "code", []
                        elif field_type == "separate":
                            code = "".join(field_code).upper()
                            if "NUMPAGES" in code:
                                tokens.append({"kind": "page_count_field"})
                            elif "PAGE" in code:
                                tokens.append({"kind": "page_field"})
                            field_state = "result"
                        elif field_type == "end":
                            field_state = None
                    elif local == "instrText":
                        if field_state == "code":
                            field_code.append(node.text or "")
                    elif local == "tab":
                        tokens.append({"kind": "tab"})
                    elif local == "t" and field_state != "result":
                        tokens.append({"kind": "text", "value": node.text or ""})
            for field in paragraph.findall("./w:fldSimple", NS):
                code = (attr_val(field, "instr") or "").upper()
                if "NUMPAGES" in code:
                    tokens.append({"kind": "page_count_field"})
                elif "PAGE" in code:
                    tokens.append({"kind": "page_field"})
            ppr = paragraph.find("w:pPr", NS)
            rpr = ppr.find("w:rPr", NS) if ppr is not None else None
            if rpr is None:
                rpr = paragraph.find("./w:r/w:rPr", NS)
            if text or tokens:
                paragraphs.append({
                    "text": text[:220],
                    "alignment": attr_val(paragraph.find("./w:pPr/w:jc", NS)) or "left",
                    "tokens": tokens,
                    "direct_format": direct_format(ppr, rpr),
                })
            alignment = attr_val(paragraph.find("./w:pPr/w:jc", NS)) or "left"
            bottom = paragraph.find("./w:pPr/w:pBdr/w:bottom", NS)
            if bottom is not None and attr_val(bottom) not in {None, "none", "nil"}:
                rules.append({"edge": "bottom", "value": attr_val(bottom), "size_eighth_points": attr_val(bottom, "sz"), "color": attr_val(bottom, "color")})
            for node in paragraph.findall(".//wp:inline", NS) + paragraph.findall(".//wp:anchor", NS):
                extent = node.find("wp:extent", NS)
                blip = node.find(".//a:blip", NS)
                rel_id = blip.attrib.get(f"{{{R_NS}}}embed") if blip is not None else None
                if not rel_id:
                    continue
                position_h = node.find("wp:positionH", NS)
                position_v = node.find("wp:positionV", NS)
                drawings.append({
                    "relationship_id": rel_id,
                    "drawing_type": "anchor" if node.tag == f"{{{WP_NS}}}anchor" else "inline",
                    "width_emu": extent.attrib.get("cx") if extent is not None else None,
                    "height_emu": extent.attrib.get("cy") if extent is not None else None,
                    "alignment": alignment,
                    "horizontal_relative_to": position_h.attrib.get("relativeFrom") if position_h is not None else "paragraph",
                    "horizontal_alignment": position_h.findtext("wp:align", namespaces=NS) if position_h is not None else alignment,
                    "horizontal_offset_emu": position_h.findtext("wp:posOffset", namespaces=NS) if position_h is not None else None,
                    "vertical_relative_to": position_v.attrib.get("relativeFrom") if position_v is not None else "paragraph",
                    "vertical_alignment": position_v.findtext("wp:align", namespaces=NS) if position_v is not None else None,
                    "vertical_offset_emu": position_v.findtext("wp:posOffset", namespaces=NS) if position_v is not None else None,
                    "geometry": drawing_geometry(node),
                })
    return {
        "part": name,
        "kind": kind,
        "text_samples": [item["text"] for item in paragraphs[:20]],
        "paragraphs": paragraphs[:20],
        "embedded_relationship_ids": [item["relationship_id"] for item in drawings],
        "drawings": drawings,
        "text_boxes": text_boxes,
        "rules": rules,
    }


def relationship_targets(zf: zipfile.ZipFile, part: str) -> dict[str, str]:
    rel_name = posixpath.join(posixpath.dirname(part), "_rels", f"{posixpath.basename(part)}.rels")
    root = read_docx_xml(zf, rel_name)
    if root is None:
        return {}
    mapping = {}
    for relationship in root.findall(f"{{{PACKAGE_R_NS}}}Relationship"):
        rel_id = relationship.attrib.get("Id")
        target = relationship.attrib.get("Target")
        if rel_id and target:
            mapping[rel_id] = posixpath.normpath(posixpath.join(posixpath.dirname(part), target))
    return mapping


def numbering_definitions(zf: zipfile.ZipFile) -> dict[str, dict]:
    """Map Word numId/level pairs to visible list-format and indentation evidence."""
    root = read_docx_xml(zf, "word/numbering.xml")
    if root is None:
        return {}
    abstract_levels: dict[str, dict[str, dict]] = {}
    for abstract in root.findall("w:abstractNum", NS):
        abstract_id = attr_val(abstract, "abstractNumId")
        if not abstract_id:
            continue
        levels = {}
        for level in abstract.findall("w:lvl", NS):
            level_id = attr_val(level, "ilvl") or "0"
            ppr = level.find("w:pPr", NS)
            ind = attrs(ppr.find("w:ind", NS) if ppr is not None else None)
            levels[level_id] = {
                "number_format": attr_val(level.find("w:numFmt", NS)) or "decimal",
                "level_text": attr_val(level.find("w:lvlText", NS)),
                "start": attr_val(level.find("w:start", NS)),
                "left_indent_twips": ind.get("left") or ind.get("start"),
                "hanging_twips": ind.get("hanging"),
            }
        abstract_levels[abstract_id] = levels
    definitions = {}
    for number in root.findall("w:num", NS):
        num_id = attr_val(number, "numId")
        abstract_id = attr_val(number.find("w:abstractNumId", NS))
        if num_id and abstract_id:
            definitions[num_id] = abstract_levels.get(abstract_id, {})
    return definitions


def real_note_nodes(root: ET.Element | None, kind: str) -> list[ET.Element]:
    """Exclude Word separator and continuation note nodes, which use negative IDs."""
    if root is None:
        return []
    nodes = []
    for node in root.findall(f".//w:{kind}", NS):
        try:
            note_id = int(attr_val(node, "id") or "-1")
        except ValueError:
            continue
        if note_id >= 0:
            nodes.append(node)
    return nodes


def inspect_docx(path: Path) -> dict:
    with zipfile.ZipFile(path) as zf:
        document = read_docx_xml(zf, "word/document.xml")
        styles_xml = read_docx_xml(zf, "word/styles.xml")
        names = set(zf.namelist())
        list_definitions = numbering_definitions(zf)

        styles = []
        style_names = {}
        document_defaults = {}
        if styles_xml is not None:
            document_defaults = direct_format(
                styles_xml.find("./w:docDefaults/w:pPrDefault/w:pPr", NS),
                styles_xml.find("./w:docDefaults/w:rPrDefault/w:rPr", NS),
            )
            for style in styles_xml.findall(".//w:style", NS):
                sid = style.attrib.get(qn("styleId"))
                name = attr_val(style.find("w:name", NS))
                stype = style.attrib.get(qn("type"))
                style_num_pr = style.find("./w:pPr/w:numPr", NS)
                style_num_id = attr_val(style_num_pr.find("w:numId", NS)) if style_num_pr is not None else None
                style_level = attr_val(style_num_pr.find("w:ilvl", NS)) if style_num_pr is not None else None
                if sid:
                    style_names[sid] = name or sid
                styles.append({
                    "style_id": sid,
                    "name": name,
                    "type": stype,
                    "based_on_style_id": attr_val(style.find("w:basedOn", NS)),
                    "direct_format": direct_format(style.find("w:pPr", NS), style.find("w:rPr", NS)),
                    "list_num_pr": {
                        "num_id": style_num_id,
                        "level": style_level or "0",
                    } if style_num_id is not None else None,
                })

        styles_by_id = {str(style.get("style_id")): style for style in styles if style.get("style_id")}
        resolving: set[str] = set()

        def resolved_style(style_id: str | None) -> dict:
            if not style_id or style_id not in styles_by_id:
                return document_defaults
            style = styles_by_id[style_id]
            cached = style.get("effective_format")
            if isinstance(cached, dict):
                return cached
            if style_id in resolving:
                return merge_format(document_defaults, style.get("direct_format"))
            resolving.add(style_id)
            parent = resolved_style(style.get("based_on_style_id"))
            resolved = merge_format(parent, style.get("direct_format"))
            resolving.discard(style_id)
            style["effective_format"] = resolved
            return resolved

        def style_list_evidence(style_id: str | None) -> dict | None:
            """Resolve numbering carried by a paragraph style, not only pPr."""
            seen: set[str] = set()
            current = style_id
            while current and current not in seen:
                seen.add(current)
                style = styles_by_id.get(current)
                if not isinstance(style, dict):
                    break
                list_num_pr = style.get("list_num_pr")
                if isinstance(list_num_pr, dict) and list_num_pr.get("num_id") is not None:
                    num_id = str(list_num_pr.get("num_id"))
                    level = str(list_num_pr.get("level") or "0")
                    return {
                        "num_id": num_id,
                        "level": level,
                        **list_definitions.get(num_id, {}).get(level, {}),
                        "source": "paragraph style numbering definition",
                    }
                style_name = str(style_names.get(current, "") or "").lower()
                if re.search(r"\blist\s+(?:number|bullet)\b|编号|项目符号", style_name):
                    number_format = "bullet" if ("bullet" in style_name or "项目符号" in style_name) else "decimal"
                    return {
                        "num_id": None,
                        "level": re.search(r"(?:2|3)$", style_name).group(0) if re.search(r"(?:2|3)$", style_name) else "0",
                        "number_format": number_format,
                        "level_text": "•" if number_format == "bullet" else "1.",
                        "source": "paragraph list style name; numbering.xml definition unavailable",
                    }
                current = str(style.get("based_on_style_id") or "") or None
            return None

        for style_id in styles_by_id:
            resolved_style(style_id)

        paragraphs = []
        headings = []
        front_matter = []
        body_drawings = []
        list_items = []
        text_boxes = text_box_samples(document, "word/document.xml")
        equations = equation_samples(document, "word/document.xml")
        document_paragraph_nodes = document.findall(".//w:p", NS) if document is not None else []
        paragraph_indices = {id(paragraph): idx for idx, paragraph in enumerate(document_paragraph_nodes, 1)}
        if document is not None:
            document_relationships = relationship_targets(zf, "word/document.xml")
            # document.xml is a tree, while a paragraph's visual role also
            # depends on its container. Keep table-cell context so downstream
            # role inference does not mistake an instruction cell for body
            # prose or a manuscript heading.
            document_parents = {
                child: parent
                for parent in document.iter()
                for child in parent
            }
            textbox_paragraph_ids = {
                id(paragraph)
                for box in document.findall(".//w:txbxContent", NS)
                for paragraph in box.findall(".//w:p", NS)
            }
            for idx, para in enumerate(document_paragraph_nodes, 1):
                if id(para) in textbox_paragraph_ids:
                    continue
                # A floating cover/title text box is layout evidence, not a
                # paragraph in manuscript reading order.
                txt = text_of(para, exclude_textboxes=True)
                sid = attr_val(para.find("./w:pPr/w:pStyle", NS))
                if sid is None and "Normal" in style_names:
                    sid = "Normal"
                sname = style_names.get(sid, sid)
                ppr = para.find("w:pPr", NS)
                paragraph_rpr = ppr.find("w:rPr", NS) if ppr is not None else None
                uniform_run = uniform_run_font_evidence(para)
                paragraph_direct = direct_format(ppr, paragraph_rpr)
                if paragraph_rpr is None and uniform_run.get("uniform"):
                    paragraph_direct = merge_format(
                        paragraph_direct,
                        {"font": uniform_run.get("font", {})},
                    )
                paragraph_effective = merge_format(
                    document_defaults,
                    resolved_style(sid),
                    paragraph_direct,
                )
                for node in para.findall(".//wp:inline", NS) + para.findall(".//wp:anchor", NS):
                    extent = node.find("wp:extent", NS)
                    blip = node.find(".//a:blip", NS)
                    rel_id = blip.attrib.get(f"{{{R_NS}}}embed") if blip is not None else None
                    if not rel_id:
                        continue
                    position_h = node.find("wp:positionH", NS)
                    position_v = node.find("wp:positionV", NS)
                    body_drawings.append({
                        "paragraph_index": idx,
                        "relationship_id": rel_id,
                        "part": document_relationships.get(rel_id, ""),
                        "drawing_type": "anchor" if node.tag == f"{{{WP_NS}}}anchor" else "inline",
                        "width_emu": extent.attrib.get("cx") if extent is not None else None,
                        "height_emu": extent.attrib.get("cy") if extent is not None else None,
                        "horizontal_alignment": position_h.findtext("wp:align", namespaces=NS) if position_h is not None else None,
                        "vertical_alignment": position_v.findtext("wp:align", namespaces=NS) if position_v is not None else None,
                        "geometry": drawing_geometry(node),
                        "paragraph_style_id": sid,
                        "paragraph_style_name": sname,
                        "paragraph_direct_format": paragraph_direct,
                        "paragraph_effective_format": paragraph_effective,
                    })
                if not txt:
                    continue
                # Word omits w:pStyle for paragraphs that inherit the Normal
                # style. Preserve that semantic role instead of treating body
                # paragraphs as unstyled evidence.
                num_pr = ppr.find("w:numPr", NS) if ppr is not None else None
                num_id = attr_val(num_pr.find("w:numId", NS)) if num_pr is not None else None
                list_level = attr_val(num_pr.find("w:ilvl", NS)) if num_pr is not None else None
                list_evidence = None
                if num_id is not None:
                    list_level = list_level or "0"
                    list_evidence = {
                        "num_id": num_id,
                        "level": list_level,
                        **list_definitions.get(num_id, {}).get(list_level, {}),
                    }
                else:
                    list_evidence = style_list_evidence(sid)
                    if list_evidence is not None:
                        num_id = list_evidence.get("num_id")
                        list_level = str(list_evidence.get("level") or "0")
                # Direct paragraph character properties define a paragraph-wide
                # baseline. When Word stores formatting only on runs, promote
                # it only if every visible run agrees; a first-run fallback
                # would incorrectly turn a bold label into a bold paragraph.
                current = para
                in_table_cell = False
                while current in document_parents:
                    current = document_parents[current]
                    if current.tag == f"{{{W_NS}}}tc":
                        in_table_cell = True
                        break
                item = {
                    "index": idx,
                    "style_id": sid,
                    "style_name": sname,
                    "text": txt[:220],
                    "direct_format": paragraph_direct,
                    "effective_format": paragraph_effective,
                    "list_evidence": list_evidence,
                    "in_table_cell": in_table_cell,
                }
                if uniform_run:
                    item["uniform_run_font_evidence"] = uniform_run
                break_types = paragraph_break_types(para)
                if break_types:
                    item["break_types"] = break_types
                    item["column_break"] = "column" in break_types
                # Reference lists, appendices, and declaration blocks commonly
                # occur after the first hundred paragraphs in journal templates.
                # Keep a bounded but sufficiently broad sample for role mapping.
                if len(paragraphs) < 300:
                    paragraphs.append(item)
                if list_evidence is not None:
                    list_items.append({
                        "paragraph_index": idx,
                        "text": txt[:220],
                        **list_evidence,
                    })
                style_key = f"{sid or ''} {sname or ''}".lower()
                key = f"{style_key} {txt[:80]}"
                normalized = re.sub(r"[^a-z ]+", "", txt.lower()).strip()
                outline_level = (item.get("effective_format") or {}).get("paragraph", {}).get("outline_level")
                # Only the Word style/outline carries semantic heading
                # evidence. Text such as "heading for acknowledgements" in a
                # style glossary table is instructional content, not a title.
                semantic_heading = "heading" in style_key or outline_level is not None
                if (
                    (not in_table_cell or semantic_heading)
                    and (
                        semantic_heading
                        or normalized in KNOWN_HEADINGS
                        or (
                            list_evidence is None
                            and re.match(r"^(\d+|[A-Z])(\.\d+)*[.)]?\s+\S+", txt)
                        )
                    )
                ):
                    headings.append(item)
                if any(token in key for token in ["title", "author", "abstract", "keyword", "highlight", "graphical"]):
                    front_matter.append(item)

        tables = []
        if document is not None:
            for idx, table in enumerate(document.findall(".//w:tbl", NS), 1):
                table_paragraph_indices = [
                    paragraph_indices[id(paragraph)]
                    for paragraph in table.findall(".//w:p", NS)
                    if id(paragraph) in paragraph_indices
                ]
                rows = table.findall(".//w:tr", NS)
                row_cells = [len(row.findall("./w:tc", NS)) for row in rows]
                cells = [text_of(cell)[:140] for cell in table.findall(".//w:tc", NS) if text_of(cell)]
                style_id = attr_val(table.find("./w:tblPr/w:tblStyle", NS))
                borders = table.findall("./w:tblPr/w:tblBorders/*", NS)
                active_borders = {
                    node.tag.rsplit("}", 1)[-1]
                    for node in borders
                    if str(attr_val(node, "val") or "single").lower() not in {"nil", "none"}
                }
                is_grid = bool({"left", "right", "insideH", "insideV"}.issubset(active_borders))
                if str(style_id or "").lower() in {"tablegrid", "gridtable"}:
                    is_grid = True
                first_row = rows[0] if rows else None
                header_cells = first_row.findall("./w:tc", NS) if first_row is not None else []
                header_fills = []
                header_alignments = []
                header_vertical_alignments = []
                header_bold = []
                for cell in header_cells:
                    cell_pr = cell.find("w:tcPr", NS)
                    shading = cell_pr.find("w:shd", NS) if cell_pr is not None else None
                    fill = attr_val(shading, "fill") if shading is not None else None
                    if fill and fill.lower() not in {"auto", "none", "ffffff"}:
                        header_fills.append(fill)
                    vertical = attr_val(cell_pr.find("w:vAlign", NS)) if cell_pr is not None else None
                    if vertical:
                        header_vertical_alignments.append(vertical)
                    paragraph = cell.find("./w:p", NS)
                    if paragraph is not None:
                        alignment = attr_val(paragraph.find("./w:pPr/w:jc", NS))
                        if alignment:
                            header_alignments.append(alignment)
                        rpr = paragraph.find("./w:pPr/w:rPr", NS)
                        if rpr is None:
                            rpr = paragraph.find("./w:r/w:rPr", NS)
                        bold = rpr.find("w:b", NS) if rpr is not None else None
                        if bold is not None and attr_val(bold) not in {"0", "false", "off"}:
                            header_bold.append(True)
                tr_pr = first_row.find("w:trPr", NS) if first_row is not None else None
                row_height = tr_pr.find("w:trHeight", NS) if tr_pr is not None else None
                tables.append({
                    "index": idx,
                    "first_paragraph_index": min(table_paragraph_indices) if table_paragraph_indices else None,
                    "last_paragraph_index": max(table_paragraph_indices) if table_paragraph_indices else None,
                    "rows": len(rows),
                    "max_columns": max(row_cells) if row_cells else 0,
                    "sample_cells": cells[:8],
                    "style_id": style_id,
                    "width_twips": attr_val(table.find("./w:tblPr/w:tblW", NS), "w"),
                    "width_type": attr_val(table.find("./w:tblPr/w:tblW", NS), "type"),
                    "alignment": attr_val(table.find("./w:tblPr/w:jc", NS)),
                    "layout": attr_val(table.find("./w:tblPr/w:tblLayout", NS), "type"),
                    "grid_column_widths_twips": [attr_val(column, "w") for column in table.findall("./w:tblGrid/w:gridCol", NS)],
                    "has_merged_cells": bool(table.findall(".//w:gridSpan", NS) or table.findall(".//w:vMerge", NS)),
                    "border_profile": "grid" if is_grid else "horizontal" if {"top", "bottom", "insideH"}.issubset(active_borders) else "none" if borders else "unknown",
                    "active_borders": sorted(active_borders),
                    "repeat_header": bool(tr_pr is not None and tr_pr.find("w:tblHeader", NS) is not None),
                    "header_fill": Counter(header_fills).most_common(1)[0][0] if header_fills else None,
                    "header_alignment": Counter(header_alignments).most_common(1)[0][0] if header_alignments else None,
                    "header_vertical_alignment": Counter(header_vertical_alignments).most_common(1)[0][0] if header_vertical_alignments else None,
                    "header_bold": bool(header_bold),
                    "header_row_height_twips": attr_val(row_height, "val"),
                    "header_row_height_rule": attr_val(row_height, "hRule"),
                })

        caption_candidates = []
        for paragraph in paragraphs:
            kind, classification_source = caption_kind(
                str(paragraph.get("text") or ""),
                str(paragraph.get("style_name") or ""),
            )
            if kind:
                caption_candidates.append({
                    "kind": kind,
                    "paragraph_index": paragraph.get("index"),
                    "text": paragraph.get("text"),
                    "style_id": paragraph.get("style_id"),
                    "style_name": paragraph.get("style_name"),
                    "in_table_cell": bool(paragraph.get("in_table_cell")),
                    "classification_source": classification_source,
                })
        for table in tables:
            start = table.get("first_paragraph_index")
            end = table.get("last_paragraph_index")
            if isinstance(start, int) and isinstance(end, int):
                table["caption_relation"] = nearest_caption_relation(caption_candidates, "table", start, end)
        for drawing in body_drawings:
            index = drawing.get("paragraph_index")
            if isinstance(index, int):
                drawing["caption_relation"] = nearest_caption_relation(caption_candidates, "figure", index, index)

        flow_paragraphs = [
            item for item in paragraphs
            if isinstance(item, dict) and not item.get("in_table_cell") and isinstance(item.get("index"), int)
        ]
        flow_by_index = {int(item["index"]): item for item in flow_paragraphs}

        def paragraph_side(item: dict | None, key: str):
            if not isinstance(item, dict):
                return None
            for owner in ("effective_format", "direct_format"):
                paragraph = (item.get(owner) or {}).get("paragraph", {})
                if paragraph.get(key) is not None:
                    return paragraph.get(key)
            return None

        def compact_flow_paragraph(item: dict | None) -> dict | None:
            if not isinstance(item, dict):
                return None
            return {
                "paragraph_index": item.get("index"),
                "style_id": item.get("style_id"),
                "style_name": item.get("style_name"),
                "text": item.get("text"),
                "space_before_twips": paragraph_side(item, "space_before_twips"),
                "space_after_twips": paragraph_side(item, "space_after_twips"),
            }

        def flow_neighbor_role(item: dict | None) -> str:
            if not isinstance(item, dict):
                return "missing"
            kind, _ = caption_kind(str(item.get("text") or ""), str(item.get("style_name") or ""))
            if kind:
                return "object_caption"
            style = f"{item.get('style_id') or ''} {item.get('style_name') or ''}".lower()
            if any(token in style for token in ("table footer", "table note", "figure note", "source note")):
                return "object_note"
            if any(token in style for token in ("title", "heading", "abstract", "keyword", "reference", "bibliography")):
                return "nonbody_role"
            return "body_text_candidate"

        def resolved_boundary(first, second) -> dict:
            values = []
            for value in (first, second):
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    pass
            return {
                "status": "source" if values else "missing",
                "resolved_pt": round(max(values) / 20.0, 3) if values else None,
                "rule": "use the larger available adjacent Word paragraph side and emit once",
            }

        def attach_outer_flow_context(item: dict, start: int, end: int, object_format: dict | None = None) -> None:
            object_start, object_end = start, end
            relation = item.get("caption_relation", {})
            caption_index = relation.get("caption_paragraph_index") if isinstance(relation, dict) else None
            if relation.get("confidence") == "adjacent" and relation.get("position") == "above" and isinstance(caption_index, int):
                start = min(start, caption_index)
            if relation.get("confidence") == "adjacent" and relation.get("position") == "below" and isinstance(caption_index, int):
                end = max(end, caption_index)
            previous = max((p for p in flow_paragraphs if int(p["index"]) < start), key=lambda p: int(p["index"]), default=None)
            following = min((p for p in flow_paragraphs if int(p["index"]) > end), key=lambda p: int(p["index"]), default=None)
            first_block = flow_by_index.get(start)
            last_block = flow_by_index.get(end)
            object_paragraph = {"effective_format": object_format or {}, "direct_format": object_format or {}}
            if first_block is None and start == object_start and object_format:
                first_block = object_paragraph
            if last_block is None and end == object_end and object_format:
                last_block = object_paragraph
            before = {
                "preceding_paragraph": compact_flow_paragraph(previous),
                "preceding_role": flow_neighbor_role(previous),
                "preceding_space_after_twips": paragraph_side(previous, "space_after_twips"),
                "block_space_before_twips": paragraph_side(first_block, "space_before_twips"),
            }
            before.update(resolved_boundary(before["preceding_space_after_twips"], before["block_space_before_twips"]))
            after = {
                "following_paragraph": compact_flow_paragraph(following),
                "following_role": flow_neighbor_role(following),
                "block_space_after_twips": paragraph_side(last_block, "space_after_twips"),
                "following_space_before_twips": paragraph_side(following, "space_before_twips"),
            }
            after.update(resolved_boundary(after["block_space_after_twips"], after["following_space_before_twips"]))
            item["outer_flow_context"] = {
                "block_start_paragraph_index": start,
                "block_end_paragraph_index": end,
                "before": before,
                "after": after,
                "source": "official Word paragraph flow around the object/caption block",
            }

        for table in tables:
            start = table.get("first_paragraph_index")
            end = table.get("last_paragraph_index")
            if isinstance(start, int) and isinstance(end, int):
                attach_outer_flow_context(table, start, end)
        for drawing in body_drawings:
            index = drawing.get("paragraph_index")
            if isinstance(index, int):
                attach_outer_flow_context(drawing, index, index, drawing.get("paragraph_effective_format"))

        toc_evidence = {"has_toc_field": False, "field_samples": [], "heading_samples": []}
        if document is not None:
            field_text = [node.text or "" for node in document.findall(".//w:instrText", NS)]
            field_text.extend(attr_val(node, "instr") or "" for node in document.findall(".//w:fldSimple", NS))
            toc_fields = [text.strip() for text in field_text if "TOC" in text.upper()]
            toc_evidence["has_toc_field"] = bool(toc_fields)
            toc_evidence["field_samples"] = toc_fields[:5]
            for paragraph in document.findall(".//w:p", NS):
                text = text_of(paragraph)
                normalized = text.strip().lower()
                if normalized in {"contents", "table of contents", "目录"}:
                    toc_evidence["heading_samples"].append(text[:120])

        sections = []
        settings = read_docx_xml(zf, "word/settings.xml")
        document_uses_mirrored_margins = bool(
            settings is not None and settings.find("w:mirrorMargins", NS) is not None
        )
        if document is not None:
            section_nodes = document.findall(".//w:sectPr", NS)
            previous_section_end = 0
            for idx, sect in enumerate(section_nodes, 1):
                size = sect.find("w:pgSz", NS)
                margins = sect.find("w:pgMar", NS)
                cols = sect.find("w:cols", NS)
                header_references = []
                footer_references = []
                for reference in sect.findall("w:headerReference", NS):
                    rel_id = reference.attrib.get(f"{{{R_NS}}}id")
                    header_references.append({"type": attr_val(reference, "type") or "default", "relationship_id": rel_id, "part": document_relationships.get(rel_id or "")})
                for reference in sect.findall("w:footerReference", NS):
                    rel_id = reference.attrib.get(f"{{{R_NS}}}id")
                    footer_references.append({"type": attr_val(reference, "type") or "default", "relationship_id": rel_id, "part": document_relationships.get(rel_id or "")})
                current = sect
                section_end = None
                while current in document_parents:
                    current = document_parents[current]
                    if current.tag == f"{{{W_NS}}}p":
                        section_end = paragraph_indices.get(id(current))
                        break
                if section_end is None:
                    section_end = len(document_paragraph_nodes)
                section_start = previous_section_end + 1
                if section_end < section_start:
                    section_end = section_start
                sections.append({
                    "index": idx,
                    "start_paragraph_index": section_start,
                    "end_paragraph_index": section_end,
                    "section_break_type": (
                        attr_val(sect.find("w:type", NS))
                        or ("final" if idx == len(section_nodes) else "nextPage")
                    ),
                    "page_width_twips": size.attrib.get(qn("w")) if size is not None else None,
                    "page_height_twips": size.attrib.get(qn("h")) if size is not None else None,
                    "orientation": size.attrib.get(qn("orient")) if size is not None else None,
                    "margins_twips": {k.split("}")[-1]: v for k, v in margins.attrib.items()} if margins is not None else {},
                    "header_distance_twips": attr_val(margins, "header"),
                    "footer_distance_twips": attr_val(margins, "footer"),
                    "gutter_twips": attr_val(margins, "gutter"),
                    "mirror_margins": document_uses_mirrored_margins or sect.find("w:mirrorMargins", NS) is not None,
                    "columns": cols.attrib.get(qn("num")) if cols is not None else None,
                    "column_space_twips": cols.attrib.get(qn("space")) if cols is not None else None,
                    "columns_equal_width": cols.attrib.get(qn("equalWidth")) if cols is not None else None,
                    "column_widths_twips": [
                        attr_val(column, "w")
                        for column in cols.findall("w:col", NS)
                        if attr_val(column, "w") is not None
                    ] if cols is not None else [],
                    "different_first_page": sect.find("w:titlePg", NS) is not None,
                    "header_references": header_references,
                    "footer_references": footer_references,
                })
                previous_section_end = section_end

            def source_section_index(paragraph_index: object) -> int | None:
                if not isinstance(paragraph_index, int):
                    return None
                for section in sections:
                    if int(section.get("start_paragraph_index") or 0) <= paragraph_index <= int(section.get("end_paragraph_index") or 0):
                        return int(section["index"])
                return None

            for table in tables:
                table["source_section_index"] = source_section_index(table.get("first_paragraph_index"))
            for drawing in body_drawings:
                drawing["source_section_index"] = source_section_index(drawing.get("paragraph_index"))
            for caption in caption_candidates:
                caption["source_section_index"] = source_section_index(caption.get("paragraph_index"))

        media = [{"path": name, "bytes": zf.getinfo(name).file_size} for name in sorted(names) if name.startswith("word/media/")]
        header_footer_parts = [
            inspect_header_footer_part(zf, name)
            for name in sorted(names)
            if re.fullmatch(r"word/(?:header|footer)\d+\.xml", name)
        ]
        footnotes = read_docx_xml(zf, "word/footnotes.xml")
        endnotes = read_docx_xml(zf, "word/endnotes.xml")
        def note_samples(nodes: list[ET.Element]) -> list[dict]:
            samples = []
            for note in nodes:
                for paragraph in note.findall(".//w:p", NS):
                    text = text_of(paragraph)
                    if not text:
                        continue
                    sid = attr_val(paragraph.find("./w:pPr/w:pStyle", NS))
                    ppr = paragraph.find("w:pPr", NS)
                    rpr = ppr.find("w:rPr", NS) if ppr is not None else None
                    if rpr is None:
                        rpr = paragraph.find("./w:r/w:rPr", NS)
                    direct = direct_format(ppr, rpr)
                    samples.append({
                        "style_id": sid,
                        "style_name": style_names.get(sid, sid),
                        "text": text[:220],
                        "direct_format": direct,
                        "effective_format": merge_format(document_defaults, resolved_style(sid), direct),
                    })
            return samples

        real_footnotes = real_note_nodes(footnotes, "footnote")
        real_endnotes = real_note_nodes(endnotes, "endnote")
        footnote_samples = note_samples(real_footnotes)
        endnote_samples = note_samples(real_endnotes)

    joined = " ".join(p["text"] for p in paragraphs[:80])
    joined += " " + " ".join(item["text"] for item in text_boxes[:20])
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", joined))
    latin_count = len(re.findall(r"[A-Za-z]", joined))
    if cjk_count:
        language_hint = "mixed" if latin_count >= 40 else "zh"
    else:
        language_hint = "en" if joined else "unknown"
    return {
        "kind": "docx",
        "language_hint": language_hint,
        "sections": sections,
        "document_defaults": document_defaults,
        "styles": styles[:120],
        "paragraph_samples": paragraphs,
        "heading_candidates": headings[:60],
        "front_matter_candidates": front_matter[:60],
        "tables": tables,
        "images": media,
        "body_drawings": body_drawings,
        "caption_candidates": caption_candidates,
        "text_boxes": text_boxes,
        "equations": equations,
        "list_items": list_items,
        "toc_evidence": toc_evidence,
        "header_footer_parts": header_footer_parts,
        "footnote_count": len(real_footnotes),
        "endnote_count": len(real_endnotes),
        "footnote_samples": footnote_samples[:30],
        "endnote_samples": endnote_samples[:30],
    }


def inspect_plain_text(text: str, kind: str) -> dict:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    paragraphs = []
    headings = []
    front_matter = []
    for idx, line in enumerate(lines[:160], 1):
        item = {"index": idx, "style_id": None, "style_name": "plain-text", "text": line[:220]}
        paragraphs.append(item)
        normalized = re.sub(r"[^a-z ]+", "", line.lower()).strip()
        key = line.lower()
        if normalized in KNOWN_HEADINGS or re.match(r"^(\d+|[A-Z])(\.\d+)*[.)]?\s+\S+", line):
            headings.append(item)
        if any(token in key for token in ["title", "author", "abstract", "keyword", "highlight", "graphical"]):
            front_matter.append(item)
    joined = " ".join(line for line in lines[:80])
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", joined))
    latin_count = len(re.findall(r"[A-Za-z]", joined))
    if cjk_count:
        language_hint = "mixed" if latin_count >= 40 else "zh"
    else:
        language_hint = "en" if joined else "unknown"
    return {
        "kind": kind,
        "language_hint": language_hint,
        "sections": [],
        "styles": [],
        "paragraph_samples": paragraphs,
        "heading_candidates": headings[:60],
        "front_matter_candidates": front_matter[:60],
        "tables": [],
        "images": [],
        "footnote_count": 0,
        "endnote_count": 0,
        "text_conversion": True,
    }


def run_soffice_convert(soffice: str, path: Path, target_format: str, outdir: Path) -> dict:
    cmd = [
        soffice,
        "--headless",
        "--convert-to",
        target_format,
        "--outdir",
        str(outdir),
        str(path),
    ]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=45)
        return {
            "ok": proc.returncode == 0,
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "cmd": cmd, "error": "LibreOffice conversion timed out"}


def inspect_legacy_word(path: Path) -> dict:
    details = {
        "kind": path.suffix.lower().lstrip("."),
        "note": "Legacy Word template. LibreOffice DOCX conversion was attempted for structural inspection.",
    }
    soffice_candidates = tool_candidates("soffice")
    if not soffice_candidates:
        details["conversion"] = {"ok": False, "error": "soffice not found"}
        return details
    with tempfile.TemporaryDirectory(prefix="temp2tex-word-") as tmp:
        tmpdir = Path(tmp)
        report = run_soffice_convert(soffice_candidates[0], path, "docx", tmpdir)
        converted = sorted(tmpdir.glob("*.docx"))
        details["conversion"] = dict(report, ok=report.get("ok") and bool(converted))
        if not converted:
            details["conversion"]["error"] = "No DOCX produced by LibreOffice"
            txt_report = run_soffice_convert(soffice_candidates[0], path, "txt", tmpdir)
            txt_files = sorted(tmpdir.glob("*.txt"))
            details["text_conversion"] = dict(txt_report, ok=txt_report.get("ok") and bool(txt_files))
            if not txt_files:
                details["text_conversion"]["error"] = "No TXT produced by LibreOffice"
                return details
            text = txt_files[0].read_text(encoding="utf-8", errors="replace")
            text_details = inspect_plain_text(text, path.suffix.lower().lstrip("."))
            text_details["conversion"] = details["conversion"]
            text_details["text_conversion"] = details["text_conversion"]
            return text_details
        converted_path = converted[0]
        converted_details = inspect_docx(converted_path)
        converted_details["kind"] = path.suffix.lower().lstrip(".")
        converted_details["converted_docx_name"] = converted_path.name
        converted_details["conversion"] = details["conversion"]
        return converted_details


def inspect_pdf(path: Path) -> dict:
    details = {"kind": "pdf", "page_count": None, "page_samples": [], "language_hint": "unknown"}
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(str(path))
        details["page_count"] = len(reader.pages)
        samples = []
        for idx, page in enumerate(reader.pages[:8], 1):
            box = page.mediabox
            text = re.sub(r"\s+", " ", (page.extract_text() or "")[:1000]).strip()
            samples.append({"index": idx, "width_pt": float(box.width), "height_pt": float(box.height), "text": text})
        details["page_samples"] = samples
        joined = " ".join(s["text"] for s in samples)
        details["language_hint"] = "zh" if re.search(r"[\u3400-\u9fff]", joined) else "en" if joined else "unknown"
    except Exception as exc:
        details["warning"] = f"Install pypdf for PDF text/page inspection: {exc}"
    return details


def inspect_file(path: Path) -> dict:
    info = {
        "path": str(path),
        "name": path.name,
        "suffix": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
    suffix = path.suffix.lower()
    try:
        if is_openxml_word_package(path):
            info["inspection"] = inspect_docx(path)
            info["detected_format"] = "openxml-word"
        elif suffix in OPENXML_WORD_SUFFIXES:
            info["inspection"] = invalid_openxml_word_details(path)
            info["detected_format"] = "invalid-word-payload"
        elif suffix == ".pdf":
            info["inspection"] = inspect_pdf(path)
        elif suffix in {".doc", ".dot", ".rtf"}:
            info["inspection"] = inspect_legacy_word(path)
        else:
            info["inspection"] = {"kind": "asset"}
    except Exception as exc:
        info["inspection_error"] = str(exc)
    return info


def iter_sources(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    allowed = {".doc", ".docx", ".docm", ".dot", ".dotx", ".dotm", ".pdf", ".rtf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".eps", ".svg", ".bst", ".csl", ".txt", ".html", ".htm"}
    return sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in allowed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Source file or directory")
    parser.add_argument("--output", "-o", default="source_inventory.json")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        print(f"source not found: {source}", file=sys.stderr)
        return 2

    files = [inspect_file(p.resolve()) for p in iter_sources(source)]
    inventory = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(source),
        "file_count": len(files),
        "files": files,
    }
    output = Path(args.output).expanduser().resolve()
    output.write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
