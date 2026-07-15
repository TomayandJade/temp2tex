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

from omml_to_latex import convert_omml


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_R_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
WP14_NS = "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
WPS_NS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
V_NS = "urn:schemas-microsoft-com:vml"
O_NS = "urn:schemas-microsoft-com:office:office"
NS = {"w": W_NS, "r": R_NS, "wp": WP_NS, "a": A_NS, "m": M_NS, "v": V_NS, "o": O_NS}
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
    """Read current Word text while optionally excluding floating/text-box descendants."""
    pieces: list[str] = []

    def visit(current: ET.Element, inside_textbox: bool = False, deleted: bool = False) -> None:
        in_textbox = inside_textbox or current.tag == f"{{{W_NS}}}txbxContent"
        removed = deleted or current.tag in {f"{{{W_NS}}}del", f"{{{W_NS}}}moveFrom"}
        if current.tag == f"{{{W_NS}}}t" and not removed and not (exclude_textboxes and in_textbox):
            pieces.append(current.text or "")
        for child in current:
            visit(child, in_textbox, removed)

    visit(node)
    return re.sub(r"\s+", " ", "".join(pieces)).strip()


def vml_shape_samples(root: ET.Element | None, part: str, relationships: dict[str, str]) -> list[dict]:
    """Retain compatibility VML assets and geometry without auto-applying placement."""
    if root is None:
        return []
    parents = {child: parent for parent in root.iter() for child in parent}
    paragraph_indexes = {id(node): index for index, node in enumerate(root.findall(".//w:p", NS), 1)}
    samples = []
    for index, pict in enumerate(root.findall(".//w:pict", NS), 1):
        current, paragraph_index = pict, None
        while current in parents:
            current = parents[current]
            if current.tag == f"{{{W_NS}}}p":
                paragraph_index = paragraph_indexes.get(id(current))
                break
        image = pict.find(".//v:imagedata", NS)
        rel_id = image.attrib.get(f"{{{R_NS}}}id") if image is not None else None
        shapes = []
        for node in pict.iter():
            if node.tag not in {f"{{{V_NS}}}shape", f"{{{V_NS}}}rect", f"{{{V_NS}}}line", f"{{{V_NS}}}group"}:
                continue
            style = {}
            for item in str(node.attrib.get("style") or "").split(";"):
                if ":" in item:
                    key, value = (part.strip() for part in item.split(":", 1))
                    if key and value:
                        style[key] = value
            shapes.append({"id": node.attrib.get("id"), "kind": node.tag.rsplit("}", 1)[-1], "type": node.attrib.get("type"), "style": style})
        ole = pict.find(".//o:OLEObject", NS)
        samples.append({
            "index": index, "part": part, "paragraph_index_in_part": paragraph_index,
            "image_relationship_id": rel_id, "image_part": relationships.get(rel_id or ""),
            "image_title": image.attrib.get(f"{{{O_NS}}}title") if image is not None else None,
            "text_box_text": [text_of(node)[:500] for node in pict.findall(".//w:txbxContent", NS)],
            "ole_program": ole.attrib.get("ProgID") if ole is not None else None,
            "shapes": shapes[:12],
            "source": "official Word VML compatibility drawing; placement is render-confirmed evidence only",
        })
    return samples


def content_control_samples(root: ET.Element | None, part: str) -> list[dict]:
    """Retain Word content-control semantics without treating them as body roles."""
    if root is None:
        return []
    paragraph_indexes = {id(node): index for index, node in enumerate(root.findall(".//w:p", NS), 1)}
    parents = {child: parent for parent in root.iter() for child in parent}
    controls = []
    control_types = (
        "richText", "text", "comboBox", "dropDownList", "date", "checkbox",
        "group", "picture", "docPartObj", "docPartList",
    )
    for index, control in enumerate(root.findall(".//w:sdt", NS), 1):
        properties = control.find("w:sdtPr", NS)
        current = control
        paragraph_index = None
        while current in parents:
            current = parents[current]
            if current.tag == f"{{{W_NS}}}p":
                paragraph_index = paragraph_indexes.get(id(current))
                break
        if paragraph_index is None:
            contained_paragraph = control.find(".//w:p", NS)
            if contained_paragraph is not None:
                paragraph_index = paragraph_indexes.get(id(contained_paragraph))
        kind = next(
            (name for name in control_types if properties is not None and properties.find(f"w:{name}", NS) is not None),
            "unknown",
        )
        controls.append({
            "index": index,
            "part": part,
            "paragraph_index_in_part": paragraph_index,
            "type": kind,
            "tag": attr_val(properties.find("w:tag", NS)) if properties is not None else None,
            "alias": attr_val(properties.find("w:alias", NS)) if properties is not None else None,
            "id": attr_val(properties.find("w:id", NS)) if properties is not None else None,
            "lock": attr_val(properties.find("w:lock", NS)) if properties is not None else None,
            "placeholder": (
                attr_val(properties.find("./w:placeholder/w:docPart", NS))
                if properties is not None else None
            ),
            "showing_placeholder": bool(
                properties is not None and properties.find("w:showingPlcHdr", NS) is not None
            ),
            "visible_text": text_of(control)[:500],
            "source": "official Word structured document tag; semantic metadata is evidence only",
        })
    return controls


def comment_samples(comments_root: ET.Element | None, document: ET.Element | None) -> list[dict]:
    """Retain Word comment guidance and body anchors without making it visible text."""
    if comments_root is None:
        return []
    anchors: dict[str, dict[str, list[int]]] = {}
    if document is not None:
        for paragraph_index, paragraph in enumerate(document.findall(".//w:p", NS), 1):
            for name, key in (("commentRangeStart", "start"), ("commentRangeEnd", "end"), ("commentReference", "reference")):
                for node in paragraph.findall(f".//w:{name}", NS):
                    comment_id = attr_val(node, "id")
                    if comment_id is not None:
                        anchors.setdefault(comment_id, {"start": [], "end": [], "reference": []})[key].append(paragraph_index)
    comments = []
    for index, comment in enumerate(comments_root.findall("w:comment", NS), 1):
        comment_id = attr_val(comment, "id")
        anchor = anchors.get(comment_id or "", {"start": [], "end": [], "reference": []})
        comments.append({
            "index": index,
            "id": comment_id,
            "author": attr_val(comment, "author"),
            "initials": attr_val(comment, "initials"),
            "date": attr_val(comment, "date"),
            "text": text_of(comment)[:1000],
            "anchor_paragraph_indexes": anchor,
            "source": "official Word comment; guidance evidence only and never manuscript body text",
        })
    return comments


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


def text_box_samples(root: ET.Element | None, part: str, paragraph_evidence=None) -> list[dict]:
    """Capture non-flow Word/VML text as evidence without promoting it to body text."""
    if root is None:
        return []
    samples = []
    seen: set[tuple[str, str, str]] = set()
    seen_texts: set[str] = set()
    for index, box in enumerate(root.findall(".//w:txbxContent", NS), 1):
        paragraphs = []
        paragraph_records = []
        for paragraph in box.findall(".//w:p", NS):
            text = text_of(paragraph)
            if text:
                paragraphs.append(text)
                if paragraph_evidence is not None:
                    record = paragraph_evidence(paragraph)
                else:
                    ppr = paragraph.find("w:pPr", NS)
                    span_ledger = paragraph_format_spans(paragraph, direct_format(ppr, None))
                    record = {
                        "text": text[:220],
                        "direct_format": direct_format(ppr, None),
                        "effective_format": direct_format(ppr, None),
                        "format_spans": span_ledger["spans"],
                        "format_span_text": span_ledger["text"],
                    }
                if isinstance(record, dict):
                    paragraph_records.append(record)
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
            "paragraphs": paragraph_records[:12],
            "paragraphs_truncated": len(paragraph_records) > 12,
            "geometry": geometry,
            "requires_visual_review": True,
        })
    # DrawingML text boxes do not always expose a w:txbxContent subtree.
    for index, body in enumerate(root.findall(".//a:txBody", NS), 1):
        paragraph_records = []
        paragraphs = []
        for paragraph in body.findall("./a:p", NS):
            span_ledger = drawingml_paragraph_format_spans(paragraph)
            text = str(span_ledger.get("text") or "").strip()
            if not text:
                continue
            paragraphs.append(text)
            paragraph_records.append({
                "text": text[:220],
                "direct_format": {"font": {}, "paragraph": {}},
                "effective_format": {"font": {}, "paragraph": {}},
                "format_spans": span_ledger["spans"],
                "format_span_text": span_ledger["text"],
            })
        text = " ".join(paragraphs).strip()
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
            "paragraph_count": len(paragraph_records),
            "paragraphs": paragraph_records[:12],
            "paragraphs_truncated": len(paragraph_records) > 12,
            "geometry": geometry,
            "requires_visual_review": True,
        })
    return samples


def equation_samples(root: ET.Element | None, part: str) -> list[dict]:
    """Extract OMML context plus conservative, source-visible LaTeX candidates."""
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
        conversion = convert_omml(math)
        samples.append({
            "index": index,
            "part": part,
            "sample_text": math_text[:300],
            "word_text_outside_math": word_text[:300],
            "display_like": display_like,
            "number_samples": number_matches[:3],
            "in_table_cell": table_cell is not None,
            "in_text_box": inside_textbox,
            **conversion,
            "requires_math_translation": conversion.get("translation_status") != "converted",
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


def on_off_element_value(element: ET.Element | None) -> bool | None:
    """Read OOXML on/off elements without treating an explicit zero as true."""
    if element is None:
        return None
    return str(attr_val(element) or "1").strip().lower() not in {"0", "false", "off", "no"}


def direct_format(ppr: ET.Element | None, rpr: ET.Element | None) -> dict:
    """Capture direct OOXML formatting without guessing inherited values."""
    fonts = attrs(rpr.find("w:rFonts", NS) if rpr is not None else None)
    bold_node = rpr.find("w:b", NS) if rpr is not None else None
    italic_node = rpr.find("w:i", NS) if rpr is not None else None
    underline_node = rpr.find("w:u", NS) if rpr is not None else None
    strike_node = rpr.find("w:strike", NS) if rpr is not None else None
    double_strike_node = rpr.find("w:dstrike", NS) if rpr is not None else None
    vertical_align_node = rpr.find("w:vertAlign", NS) if rpr is not None else None
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
        "underline": (
            None if underline_node is None
            else (attr_val(underline_node) or "single").lower()
        ),
        "strike": None if strike_node is None else on_off_element_value(strike_node),
        "double_strike": None if double_strike_node is None else on_off_element_value(double_strike_node),
        "vertical_align": attr_val(vertical_align_node) if vertical_align_node is not None else None,
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
        "keep_with_next": on_off_element_value(ppr.find("w:keepNext", NS)) if ppr is not None else None,
        "page_break_before": on_off_element_value(ppr.find("w:pageBreakBefore", NS)) if ppr is not None else None,
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
    # Reading-order records include accepted insertions but exclude deleted or
    # moved-from revision text, matching the visible source paragraph.
    for run, _ in paragraph_run_records(paragraph):
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


def visible_run_text(run: ET.Element) -> str:
    """Return visible text emitted by one Word run, excluding field instructions."""
    pieces = []
    for node in list(run):
        local = node.tag.rsplit("}", 1)[-1]
        if local in {"t", "delText"}:
            pieces.append(node.text or "")
        elif local == "tab":
            pieces.append("\t")
        elif local in {"br", "cr"}:
            pieces.append("\n")
        elif local == "noBreakHyphen":
            pieces.append("-")
        elif local == "softHyphen":
            pieces.append("\u00ad")
    return "".join(pieces)


def paragraph_run_records(
    paragraph: ET.Element,
    hyperlink_targets: dict[str, str] | None = None,
) -> list[tuple[ET.Element, str | None]]:
    """Return visible Word runs in reading order with an optional link target."""
    records: list[tuple[ET.Element, str | None]] = []
    targets = hyperlink_targets or {}

    def visit(node: ET.Element, current_target: str | None = None) -> None:
        for child in node:
            if child.tag in {f"{{{W_NS}}}del", f"{{{W_NS}}}moveFrom"}:
                continue
            if child.tag == f"{{{W_NS}}}hyperlink":
                rel_id = child.attrib.get(f"{{{R_NS}}}id")
                target = targets.get(rel_id) if rel_id else None
                visit(child, target or current_target)
            elif child.tag == f"{{{W_NS}}}r":
                records.append((child, current_target))
            else:
                visit(child, current_target)

    visit(paragraph)
    return records


def paragraph_format_spans(
    paragraph: ET.Element,
    paragraph_effective: dict,
    hyperlink_targets: dict[str, str] | None = None,
) -> dict:
    """Preserve ordered Word run formatting instead of collapsing mixed runs.

    Word has no sentence node and one visible word may be split across runs by
    fields, revisions, hyperlinks, or local typography.  The ledger therefore
    records contiguous run text with character offsets in ``text``.  Callers
    can use the dominant span for a role while retaining bold labels, italics,
    colours, and superscripts as local evidence.
    """
    spans = []
    cursor = 0
    for run, hyperlink_target in paragraph_run_records(paragraph, hyperlink_targets):
        text = visible_run_text(run)
        if not text:
            continue
        rpr = run.find("w:rPr", NS)
        direct = direct_format(None, rpr) if rpr is not None else {}
        effective = merge_format(paragraph_effective, direct)
        signature = json.dumps(
            {
                "direct_format": direct,
                "effective_format": effective,
                "hyperlink_target": hyperlink_target,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        if spans and spans[-1]["signature"] == signature and spans[-1]["end"] == cursor:
            spans[-1]["text"] += text
            spans[-1]["end"] += len(text)
        else:
            spans.append({
                "start": cursor,
                "end": cursor + len(text),
                "text": text,
                "direct_format": direct,
                "effective_format": effective,
                **({"hyperlink_target": hyperlink_target} if hyperlink_target else {}),
                "signature": signature,
            })
        cursor += len(text)
    for span in spans:
        span.pop("signature", None)
    return {"text": "".join(span["text"] for span in spans), "spans": spans}


def drawingml_run_text(run: ET.Element) -> str:
    """Return visible DrawingML run text, retaining explicit breaks and tabs."""
    pieces = []
    for node in list(run):
        local = node.tag.rsplit("}", 1)[-1]
        if local == "t":
            pieces.append(node.text or "")
        elif local == "br":
            pieces.append("\n")
        elif local == "tab":
            pieces.append("\t")
    return "".join(pieces)


def drawingml_direct_format(rpr: ET.Element | None) -> dict:
    """Capture direct DrawingML text formatting without borrowing Word styles."""
    if rpr is None:
        return {"font": {}, "paragraph": {}}
    latin = rpr.find("a:latin", NS)
    east_asia = rpr.find("a:ea", NS)
    fill = rpr.find("a:solidFill", NS)
    color = fill.find("a:srgbClr", NS) if fill is not None else None
    baseline = str(rpr.attrib.get("baseline") or "").strip()
    try:
        baseline_value = int(baseline)
    except ValueError:
        baseline_value = 0
    font = {
        "family": latin.attrib.get("typeface") if latin is not None else None,
        "east_asia_family": east_asia.attrib.get("typeface") if east_asia is not None else None,
        "size_half_points": (
            str(round(int(rpr.attrib["sz"]) / 50))
            if str(rpr.attrib.get("sz") or "").isdigit()
            else None
        ),
        "bold": str(rpr.attrib.get("b") or "").lower() in {"1", "true", "on"},
        "italic": str(rpr.attrib.get("i") or "").lower() in {"1", "true", "on"},
        "color": color.attrib.get("val") if color is not None else None,
        "underline": str(rpr.attrib.get("u") or "").lower() or None,
        "strike": str(rpr.attrib.get("strike") or "").lower() not in {"", "none", "nostrike"},
        "vertical_align": "superscript" if baseline_value > 0 else ("subscript" if baseline_value < 0 else None),
    }
    # Omitted DrawingML flags are unspecified, not false. Keep false only
    # when the source explicitly writes the flag so a later inheritance layer
    # can distinguish absence from a direct override.
    if "b" not in rpr.attrib:
        font.pop("bold")
    if "i" not in rpr.attrib:
        font.pop("italic")
    if "strike" not in rpr.attrib:
        font.pop("strike")
    return {
        "font": {key: value for key, value in font.items() if value not in (None, "")},
        "paragraph": {},
    }


def drawingml_paragraph_format_spans(paragraph: ET.Element) -> dict:
    """Preserve contiguous DrawingML run formatting inside a shape paragraph."""
    spans = []
    cursor = 0
    for run in list(paragraph):
        local = run.tag.rsplit("}", 1)[-1]
        if local not in {"r", "fld"}:
            continue
        text = drawingml_run_text(run)
        if not text:
            continue
        direct = drawingml_direct_format(run.find("a:rPr", NS))
        signature = json.dumps({"direct_format": direct, "effective_format": direct}, sort_keys=True)
        if spans and spans[-1]["signature"] == signature and spans[-1]["end"] == cursor:
            spans[-1]["text"] += text
            spans[-1]["end"] += len(text)
        else:
            spans.append({
                "start": cursor,
                "end": cursor + len(text),
                "text": text,
                "direct_format": direct,
                "effective_format": direct,
                "signature": signature,
            })
        cursor += len(text)
    for span in spans:
        span.pop("signature", None)
    return {"text": "".join(span["text"] for span in spans), "spans": spans}


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
    part_relationships = relationship_targets(zf, name)
    if root is not None:
        for paragraph in root.findall(".//w:p", NS):
            text = text_of(paragraph)
            tokens = []
            field_state = None
            field_code = []
            for run, _ in paragraph_run_records(paragraph, part_relationships):
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
                paragraph_direct = direct_format(ppr, rpr)
                # The representative paragraph record may retain the first run
                # for older furniture mapping. Span inheritance must exclude
                # that run so its bold/italic state is not imposed on siblings.
                span_ledger = paragraph_format_spans(
                    paragraph,
                    direct_format(ppr, None),
                    part_relationships,
                )
                paragraphs.append({
                    "text": text[:220],
                    "alignment": attr_val(paragraph.find("./w:pPr/w:jc", NS)) or "left",
                    "tokens": tokens,
                    "direct_format": paragraph_direct,
                    "format_spans": span_ledger["spans"],
                    "format_span_text": span_ledger["text"],
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
        "vml_shapes": vml_shape_samples(root, name, part_relationships),
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
            if str(relationship.attrib.get("TargetMode") or "").lower() == "external":
                mapping[rel_id] = target
            else:
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


def note_numbering_evidence(settings: ET.Element | None, kind: str) -> dict:
    """Read explicit Word note numbering settings without guessing marker style."""
    properties = settings.find(f"w:{kind}Pr", NS) if settings is not None else None
    number_format = attr_val(properties.find("w:numFmt", NS)) if properties is not None else None
    latex_marker_styles = {
        "decimal": "arabic",
        "lowerLetter": "alph",
        "upperLetter": "Alph",
        "lowerRoman": "roman",
        "upperRoman": "Roman",
        "chicago": "fnsymbol",
    }
    return {
        "number_format": number_format or "decimal",
        "marker_style": latex_marker_styles.get(number_format or "decimal", "source-not-mapped"),
        "start": attr_val(properties.find("w:numStart", NS)) if properties is not None else None,
        "restart": attr_val(properties.find("w:numRestart", NS)) if properties is not None else None,
        "position": attr_val(properties.find("w:pos", NS)) if properties is not None else None,
        "explicit_number_format": number_format is not None,
        "source": (
            f"official Word settings.xml {kind}Pr numFmt"
            if number_format is not None
            else f"Word default {kind} numbering; no explicit numFmt"
        ),
    }


def note_reference_samples(
    document: ET.Element | None,
    note_nodes: list[ET.Element],
    kind: str,
) -> list[dict]:
    """Link visible body note references to their Word note text and local marker format."""
    if document is None:
        return []
    note_by_id = {attr_val(node, "id"): node for node in note_nodes}
    parents = {child: parent for parent in document.iter() for child in parent}
    samples = []
    reference_name = f"{kind}Reference"
    for paragraph_index, paragraph in enumerate(document.findall(".//w:p", NS), 1):
        anchor_text = text_of(paragraph)[:300]
        for reference in paragraph.findall(f".//w:{reference_name}", NS):
            note_id = attr_val(reference, "id")
            current = reference
            run = None
            while current in parents:
                current = parents[current]
                if current.tag == f"{{{W_NS}}}r":
                    run = current
                    break
            rpr = run.find("w:rPr", NS) if run is not None else None
            note = note_by_id.get(note_id)
            samples.append({
                "id": note_id,
                "paragraph_index": paragraph_index,
                "anchor_text": anchor_text,
                "in_table_cell": any(parent.tag == f"{{{W_NS}}}tc" for parent in parents_for(paragraph, parents)),
                "marker_direct_format": direct_format(None, rpr) if rpr is not None else {"font": {}, "paragraph": {}},
                "note_text": text_of(note)[:1000] if note is not None else None,
                "note_found": note is not None,
                "source": f"official Word body {reference_name} linked by note id",
            })
    return samples


def parents_for(node: ET.Element, parents: dict[ET.Element, ET.Element]) -> list[ET.Element]:
    """Return ancestors in order for compact structural tests."""
    result = []
    current = node
    while current in parents:
        current = parents[current]
        result.append(current)
    return result


def inspect_docx(
    path: Path,
    *,
    full_paragraph_evidence: bool = False,
) -> dict:
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

        document_relationships = relationship_targets(zf, "word/document.xml")
        vml_shapes = vml_shape_samples(document, "word/document.xml", document_relationships)
        paragraphs = []
        headings = []
        front_matter = []
        body_drawings = []
        list_items = []
        def textbox_paragraph_evidence(paragraph: ET.Element) -> dict:
            sid = attr_val(paragraph.find("./w:pPr/w:pStyle", NS))
            if sid is None and "Normal" in style_names:
                sid = "Normal"
            ppr = paragraph.find("w:pPr", NS)
            uniform_run = uniform_run_font_evidence(paragraph)
            paragraph_direct = direct_format(ppr, None)
            if uniform_run.get("uniform"):
                paragraph_direct = merge_format(
                    paragraph_direct,
                    {"font": uniform_run.get("font", {})},
                )
            paragraph_effective = merge_format(
                document_defaults,
                resolved_style(sid),
                paragraph_direct,
            )
            span_base = merge_format(
                document_defaults,
                resolved_style(sid),
                direct_format(ppr, None),
            )
            span_ledger = paragraph_format_spans(
                paragraph,
                span_base,
                document_relationships,
            )
            full_text = text_of(paragraph)
            return {
                "text": full_text if full_paragraph_evidence else full_text[:220],
                "style_id": sid,
                "style_name": style_names.get(sid, sid),
                "direct_format": paragraph_direct,
                "effective_format": paragraph_effective,
                "format_spans": span_ledger["spans"],
                "format_span_text": span_ledger["text"],
            }

        text_boxes = text_box_samples(document, "word/document.xml", textbox_paragraph_evidence)
        equations = equation_samples(document, "word/document.xml")
        document_paragraph_nodes = document.findall(".//w:p", NS) if document is not None else []
        paragraph_indices = {id(paragraph): idx for idx, paragraph in enumerate(document_paragraph_nodes, 1)}
        if document is not None:
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
                paragraph_direct = direct_format(ppr, None)
                if uniform_run.get("uniform"):
                    paragraph_direct = merge_format(
                        paragraph_direct,
                        {"font": uniform_run.get("font", {})},
                    )
                paragraph_effective = merge_format(
                    document_defaults,
                    resolved_style(sid),
                    paragraph_direct,
                )
                span_ledger = paragraph_format_spans(
                    para,
                    paragraph_effective,
                    document_relationships,
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
                    "text": txt if full_paragraph_evidence else txt[:220],
                    "direct_format": paragraph_direct,
                    "effective_format": paragraph_effective,
                    "list_evidence": list_evidence,
                    "in_table_cell": in_table_cell,
                }
                if span_ledger["spans"]:
                    item["format_spans"] = span_ledger["spans"]
                    item["format_span_text"] = span_ledger["text"]
                if uniform_run:
                    item["uniform_run_font_evidence"] = uniform_run
                break_types = paragraph_break_types(para)
                if break_types:
                    item["break_types"] = break_types
                    item["column_break"] = "column" in break_types
                # Reference lists, appendices, and declaration blocks commonly
                # occur after the first hundred paragraphs in journal templates.
                # Keep a bounded but sufficiently broad sample for role mapping.
                if full_paragraph_evidence or len(paragraphs) < 300:
                    paragraphs.append(item)
                if list_evidence is not None:
                    list_items.append({
                        "paragraph_index": idx,
                        "text": txt if full_paragraph_evidence else txt[:220],
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
                table_style_id = attr_val(table.find("./w:tblPr/w:tblStyle", NS))
                borders = table.findall("./w:tblPr/w:tblBorders/*", NS)
                active_borders = {
                    node.tag.rsplit("}", 1)[-1]
                    for node in borders
                    if str(attr_val(node, "val") or "single").lower() not in {"nil", "none"}
                }
                is_grid = bool({"left", "right", "insideH", "insideV"}.issubset(active_borders))
                if str(table_style_id or "").lower() in {"tablegrid", "gridtable"}:
                    is_grid = True
                first_row = rows[0] if rows else None
                header_cells = first_row.findall("./w:tc", NS) if first_row is not None else []
                header_fills = []
                header_alignments = []
                header_vertical_alignments = []
                header_bold = []
                header_cells_fully_bold = []
                header_cell_samples = []
                cell_format_samples = []
                header_fonts = []
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
                        style_id = attr_val(paragraph.find("./w:pPr/w:pStyle", NS))
                        if style_id is None and "Normal" in style_names:
                            style_id = "Normal"
                        ppr = paragraph.find("w:pPr", NS)
                        alignment = attr_val(paragraph.find("./w:pPr/w:jc", NS))
                        if alignment:
                            header_alignments.append(alignment)
                        rpr = ppr.find("w:rPr", NS) if ppr is not None else None
                        if rpr is None:
                            rpr = paragraph.find("./w:r/w:rPr", NS)
                        uniform_run = uniform_run_font_evidence(paragraph)
                        paragraph_direct = direct_format(ppr, None)
                        if uniform_run.get("uniform"):
                            paragraph_direct = merge_format(
                                paragraph_direct,
                                {"font": uniform_run.get("font", {})},
                            )
                        span_base = merge_format(
                            document_defaults,
                            resolved_style(style_id),
                            direct_format(ppr, None),
                        )
                        span_ledger = paragraph_format_spans(
                            paragraph,
                            span_base,
                            document_relationships,
                        )
                        header_cell_samples.append({
                            "text": text_of(cell)[:220],
                            "style_id": style_id,
                            "style_name": style_names.get(style_id, style_id),
                            "direct_format": paragraph_direct,
                            "effective_format": span_base,
                            "format_spans": span_ledger["spans"],
                            "format_span_text": span_ledger["text"],
                        })
                        if len(span_ledger["spans"]) == 1:
                            font = span_ledger["spans"][0].get("effective_format", {}).get("font", {})
                            if isinstance(font, dict) and font:
                                header_fonts.append(font)
                        span_fonts = [
                            span.get("effective_format", {}).get("font", {})
                            for span in span_ledger["spans"]
                            if isinstance(span, dict)
                        ]
                        header_cells_fully_bold.append(
                            bool(span_fonts) and all(
                                isinstance(font, dict) and font.get("bold") is True
                                for font in span_fonts
                            )
                        )
                        bold = rpr.find("w:b", NS) if rpr is not None else None
                        if bold is not None and attr_val(bold) not in {"0", "false", "off"}:
                            header_bold.append(True)
                for row_index, row in enumerate(rows, 1):
                    for column_index, cell in enumerate(row.findall("./w:tc", NS), 1):
                        cell_pr = cell.find("w:tcPr", NS)
                        shading = cell_pr.find("w:shd", NS) if cell_pr is not None else None
                        merge = cell_pr.find("w:vMerge", NS) if cell_pr is not None else None
                        grid_span = cell_pr.find("w:gridSpan", NS) if cell_pr is not None else None
                        cell_paragraphs = []
                        for paragraph_index, paragraph in enumerate(cell.findall("./w:p", NS), 1):
                            style_id = attr_val(paragraph.find("./w:pPr/w:pStyle", NS))
                            if style_id is None and "Normal" in style_names:
                                style_id = "Normal"
                            ppr = paragraph.find("w:pPr", NS)
                            rpr = ppr.find("w:rPr", NS) if ppr is not None else None
                            if rpr is None:
                                rpr = paragraph.find("./w:r/w:rPr", NS)
                            uniform_run = uniform_run_font_evidence(paragraph)
                            paragraph_direct = direct_format(ppr, None)
                            if uniform_run.get("uniform"):
                                paragraph_direct = merge_format(
                                    paragraph_direct,
                                    {"font": uniform_run.get("font", {})},
                                )
                            paragraph_effective = merge_format(
                                document_defaults,
                                resolved_style(style_id),
                                paragraph_direct,
                            )
                            span_ledger = paragraph_format_spans(
                                paragraph,
                                paragraph_effective,
                                document_relationships,
                            )
                            cell_paragraphs.append({
                                "paragraph_index": paragraph_index,
                                "text": text_of(paragraph)[:220],
                                "style_id": style_id,
                                "style_name": style_names.get(style_id, style_id),
                                "direct_format": paragraph_direct,
                                "effective_format": paragraph_effective,
                                "format_spans": span_ledger["spans"],
                                "format_span_text": span_ledger["text"],
                            })
                        cell_format_samples.append({
                            "row_index": row_index,
                            "column_index": column_index,
                            "text": text_of(cell)[:320],
                            "fill": attr_val(shading, "fill") if shading is not None else None,
                            "vertical_alignment": attr_val(cell_pr.find("w:vAlign", NS)) if cell_pr is not None else None,
                            "grid_span": attr_val(grid_span, "val") if grid_span is not None else None,
                            "vertical_merge": (
                                attr_val(merge, "val") if merge is not None and attr_val(merge, "val") is not None
                                else "continue" if merge is not None else None
                            ),
                            "paragraph_count": len(cell_paragraphs),
                            "paragraphs": cell_paragraphs[:4],
                            "paragraphs_truncated": len(cell_paragraphs) > 4,
                        })
                tr_pr = first_row.find("w:trPr", NS) if first_row is not None else None
                row_height = tr_pr.find("w:trHeight", NS) if tr_pr is not None else None
                header_font = {}
                header_font_consensus = False
                if header_fonts:
                    signatures = Counter(
                        json.dumps(font, ensure_ascii=False, sort_keys=True)
                        for font in header_fonts
                    )
                    header_font_consensus = len(header_fonts) == len(header_cells) and len(signatures) == 1
                    if header_font_consensus:
                        header_font = json.loads(signatures.most_common(1)[0][0])
                header_bold_consensus = (
                    len(header_cells_fully_bold) == len(header_cells)
                    and bool(header_cells_fully_bold)
                    and all(header_cells_fully_bold)
                )
                tables.append({
                    "index": idx,
                    "first_paragraph_index": min(table_paragraph_indices) if table_paragraph_indices else None,
                    "last_paragraph_index": max(table_paragraph_indices) if table_paragraph_indices else None,
                    "rows": len(rows),
                    "max_columns": max(row_cells) if row_cells else 0,
                    "sample_cells": cells[:8],
                    "style_id": table_style_id,
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
                    "header_bold_consensus": header_bold_consensus,
                    "header_effective_font": header_font,
                    "header_font_consensus": header_font_consensus,
                    "header_cell_samples": header_cell_samples[:12],
                    "cell_format_samples": cell_format_samples[:96],
                    "cell_format_samples_truncated": len(cell_format_samples) > 96,
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
                line_numbers = sect.find("w:lnNumType", NS)
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
                    "line_numbering": {
                        "enabled": line_numbers is not None,
                        "count_by": attr_val(line_numbers, "countBy") if line_numbers is not None else None,
                        "start": attr_val(line_numbers, "start") if line_numbers is not None else None,
                        "distance_twips": attr_val(line_numbers, "distance") if line_numbers is not None else None,
                        "restart": attr_val(line_numbers, "restart") if line_numbers is not None else None,
                    },
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
        comments = read_docx_xml(zf, "word/comments.xml")
        def note_samples(nodes: list[ET.Element]) -> list[dict]:
            samples = []
            for note in nodes:
                note_id = attr_val(note, "id")
                for paragraph in note.findall(".//w:p", NS):
                    text = text_of(paragraph)
                    if not text:
                        continue
                    sid = attr_val(paragraph.find("./w:pPr/w:pStyle", NS))
                    ppr = paragraph.find("w:pPr", NS)
                    rpr = ppr.find("w:rPr", NS) if ppr is not None else None
                    if rpr is None:
                        rpr = paragraph.find("./w:r/w:rPr", NS)
                    uniform_run = uniform_run_font_evidence(paragraph)
                    direct = direct_format(ppr, None)
                    if uniform_run.get("uniform"):
                        direct = merge_format(direct, {"font": uniform_run.get("font", {})})
                    effective = merge_format(document_defaults, resolved_style(sid), direct)
                    span_ledger = paragraph_format_spans(
                        paragraph,
                        effective,
                        document_relationships,
                    )
                    samples.append({
                        "note_id": note_id,
                        "style_id": sid,
                        "style_name": style_names.get(sid, sid),
                        "text": text[:220],
                        "direct_format": direct,
                        "effective_format": effective,
                        "format_spans": span_ledger["spans"],
                        "format_span_text": span_ledger["text"],
                    })
            return samples

        real_footnotes = real_note_nodes(footnotes, "footnote")
        real_endnotes = real_note_nodes(endnotes, "endnote")
        footnote_samples = note_samples(real_footnotes)
        endnote_samples = note_samples(real_endnotes)
        footnote_numbering = note_numbering_evidence(settings, "footnote")
        endnote_numbering = note_numbering_evidence(settings, "endnote")
        footnote_references = note_reference_samples(document, real_footnotes, "footnote")
        endnote_references = note_reference_samples(document, real_endnotes, "endnote")
        content_controls = content_control_samples(document, "word/document.xml")
        for name in sorted(item for item in names if re.fullmatch(r"word/(?:header|footer)\d+\.xml", item)):
            content_controls.extend(content_control_samples(read_docx_xml(zf, name), name))
        content_controls.extend(content_control_samples(footnotes, "word/footnotes.xml"))
        content_controls.extend(content_control_samples(endnotes, "word/endnotes.xml"))
        comments_evidence = comment_samples(comments, document)

    joined = " ".join(p["text"] for p in paragraphs[:80])
    joined += " " + " ".join(item["text"] for item in text_boxes[:20])
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", joined))
    latin_count = len(re.findall(r"[A-Za-z]", joined))
    if cjk_count:
        language_hint = "mixed" if latin_count >= 40 else "zh"
    else:
        language_hint = "en" if joined else "unknown"
    revision_evidence = {
        "insertions": len(document.findall(".//w:ins", NS)) if document is not None else 0,
        "deletions_ignored": len(document.findall(".//w:del", NS)) if document is not None else 0,
        "moves_from_ignored": len(document.findall(".//w:moveFrom", NS)) if document is not None else 0,
        "source": "official Word tracked-revision XML; deleted and moved-from text excluded from visible evidence",
    }
    return {
        "kind": "docx",
        "paragraph_evidence_mode": "full" if full_paragraph_evidence else "sampled",
        "language_hint": language_hint,
        "sections": sections,
        "line_numbering": {
            "enabled": any(bool(section.get("line_numbering", {}).get("enabled")) for section in sections),
            "sections": [
                {
                    "section_index": section.get("index"),
                    **(section.get("line_numbering") or {}),
                }
                for section in sections
                if bool((section.get("line_numbering") or {}).get("enabled"))
            ],
            "source": "official Word section line-numbering properties",
        },
        "tracked_revisions": revision_evidence,
        "content_controls": content_controls[:80],
        "comments": comments_evidence[:40],
        "document_defaults": document_defaults,
        "styles": styles[:120],
        "paragraph_samples": paragraphs,
        "heading_candidates": headings[:60],
        "front_matter_candidates": front_matter[:60],
        "tables": tables,
        "images": media,
        "body_drawings": body_drawings,
        "vml_shapes": vml_shapes[:100],
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
        "footnote_numbering": footnote_numbering,
        "endnote_numbering": endnote_numbering,
        "footnote_references": footnote_references[:40],
        "endnote_references": endnote_references[:40],
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
