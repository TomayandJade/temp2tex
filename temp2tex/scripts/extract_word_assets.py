#!/usr/bin/env python3
"""Extract embedded Word media and record the document part that references it."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


R_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
OPENXML_SUFFIXES = {".docx", ".docm", ".dotx", ".dotm"}
LEGACY_WORD_SUFFIXES = {".doc", ".dot", ".rtf"}


def is_openxml_word_package(path: Path) -> bool:
    """Recognize DOCX-like bytes even when a publisher serves a legacy suffix."""
    if not zipfile.is_zipfile(path):
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
        return "[Content_Types].xml" in names and "word/document.xml" in names
    except (OSError, zipfile.BadZipFile):
        return False


def find_soffice() -> str | None:
    candidates = [
        shutil.which("soffice"),
        shutil.which("soffice.com"),
        shutil.which("soffice.exe"),
        r"D:\LibreOffice\program\soffice.exe",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def convert_legacy_word_to_docx(source: Path, outdir: Path) -> tuple[Path, dict]:
    soffice = find_soffice()
    if not soffice:
        raise ValueError("LibreOffice is required to extract assets from legacy DOC, DOT, or RTF files")
    cmd = [soffice, "--headless", "--convert-to", "docx", "--outdir", str(outdir), str(source)]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=45)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("LibreOffice asset conversion timed out") from exc
    converted = sorted(outdir.glob("*.docx"))
    if proc.returncode != 0 or not converted:
        detail = (proc.stderr or proc.stdout or "no DOCX produced").strip()[-500:]
        raise ValueError(f"LibreOffice could not convert legacy Word source to DOCX: {detail}")
    return converted[0], {
        "converter": "libreoffice",
        "command": cmd,
        "converted_docx": converted[0].name,
        "stdout_tail": proc.stdout[-1000:],
        "stderr_tail": proc.stderr[-1000:],
    }


def make_latex_compatible_preview(asset: Path) -> dict:
    """Create a PNG companion for media that XeLaTeX cannot include directly."""
    suffix = asset.suffix.lower()
    if suffix in {".tif", ".tiff"}:
        try:
            from PIL import Image
            with Image.open(asset) as image:
                converted = image.convert("RGB") if image.mode not in {"RGB", "RGBA"} else image.copy()
                preview = asset.with_suffix(".png")
                converted.save(preview, format="PNG")
            return {
                "latex_compatible": True,
                "latex_output": preview.name,
                "conversion": {
                    "converter": "Pillow",
                    "source_format": suffix.lstrip("."),
                },
            }
        except Exception as exc:
            return {
                "latex_compatible": False,
                "conversion_error": f"TIFF to PNG conversion unavailable: {exc}",
            }
    if suffix not in {".emf", ".wmf"}:
        return {"latex_compatible": suffix not in {".emf", ".wmf"}}
    soffice = find_soffice()
    if not soffice:
        return {
            "latex_compatible": False,
            "conversion_error": "LibreOffice is unavailable for EMF/WMF to PNG conversion",
        }
    cmd = [soffice, "--headless", "--convert-to", "png", "--outdir", str(asset.parent), str(asset)]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
    except subprocess.TimeoutExpired:
        return {"latex_compatible": False, "conversion_error": "EMF/WMF to PNG conversion timed out"}
    preview = asset.with_suffix(".png")
    if proc.returncode == 0 and preview.exists():
        return {
            "latex_compatible": True,
            "latex_output": preview.name,
            "conversion": {
                "converter": "libreoffice",
                "command": cmd,
                "stdout_tail": proc.stdout[-1000:],
                "stderr_tail": proc.stderr[-1000:],
            },
        }
    detail = (proc.stderr or proc.stdout or "no PNG produced").strip()[-500:]
    return {"latex_compatible": False, "conversion_error": detail}


def relationship_targets(archive: zipfile.ZipFile, part: str) -> dict[str, str]:
    rel_name = posixpath.join(posixpath.dirname(part), "_rels", f"{posixpath.basename(part)}.rels")
    try:
        root = ET.fromstring(archive.read(rel_name))
    except KeyError:
        return {}
    mapping: dict[str, str] = {}
    for rel in root.findall(f"{{{R_NS}}}Relationship"):
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rel_id and target:
            mapping[rel_id] = posixpath.normpath(posixpath.join(posixpath.dirname(part), target))
    return mapping


def embedded_ids(archive: zipfile.ZipFile, part: str) -> list[str]:
    try:
        root = ET.fromstring(archive.read(part))
    except KeyError:
        return []
    ids = []
    for blip in root.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip"):
        rel_id = blip.attrib.get(f"{{{DOC_R_NS}}}embed")
        if rel_id:
            ids.append(rel_id)
    return ids


def part_role(part: str) -> str:
    name = posixpath.basename(part).lower()
    if name.startswith("header"):
        return "header"
    if name.startswith("footer"):
        return "footer"
    return "body"


def extract_assets(word_source: Path, outdir: Path, manifest_name: str = "word_asset_manifest.json") -> Path:
    source = word_source.expanduser().resolve()
    suffix = source.suffix.lower()
    if not source.exists() or (not is_openxml_word_package(source) and suffix not in LEGACY_WORD_SUFFIXES):
        raise ValueError("word_source must be an existing DOCX, DOTX, DOTM, DOC, DOT, or RTF file")
    outdir = outdir.expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(manifest_name).expanduser()
    if not manifest_path.is_absolute():
        manifest_path = outdir / manifest_path

    records: dict[str, dict] = {}
    conversion: dict | None = None
    openxml_source = is_openxml_word_package(source)
    tempdir_context = tempfile.TemporaryDirectory(prefix="temp2tex-assets-") if not openxml_source else None
    try:
        archive_source = source
        if tempdir_context:
            archive_source, conversion = convert_legacy_word_to_docx(source, Path(tempdir_context.name))
        with zipfile.ZipFile(archive_source) as archive:
            names = set(archive.namelist())
            parts = ["word/document.xml"] + sorted(
                name for name in names if re.fullmatch(r"word/(?:header|footer)\d+\.xml", name)
            )
            for part in parts:
                targets = relationship_targets(archive, part)
                for rel_id in embedded_ids(archive, part):
                    target = targets.get(rel_id)
                    if not target or target not in names or not target.startswith("word/media/"):
                        continue
                    record = records.setdefault(target, {
                        "source_path": target,
                        "roles": [],
                        "referenced_by": [],
                    })
                    role = part_role(part)
                    if role not in record["roles"]:
                        record["roles"].append(role)
                    record["referenced_by"].append({"part": part, "relationship_id": rel_id})
            for media in sorted(name for name in names if name.startswith("word/media/")):
                records.setdefault(media, {"source_path": media, "roles": ["unplaced"], "referenced_by": []})

            for index, source_name in enumerate(sorted(records), 1):
                record = records[source_name]
                media_suffix = Path(source_name).suffix.lower() or ".bin"
                role = record["roles"][0] if record["roles"] else "asset"
                output_name = f"word-{role}-{index:02d}{media_suffix}"
                output = outdir / output_name
                output.write_bytes(archive.read(source_name))
                record["output"] = output_name
                record["bytes"] = output.stat().st_size
                record.update(make_latex_compatible_preview(output))
    finally:
        if tempdir_context:
            tempdir_context.cleanup()

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "word_source": str(source),
        "source_type": suffix.lstrip("."),
        "detected_format": "openxml-word" if openxml_source else "legacy-word-binary",
        "conversion": conversion,
        "asset_directory": str(outdir),
        "assets": [records[key] for key in sorted(records)],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("word_source", help="DOCX, DOTX, DOTM, DOC, DOT, or RTF template")
    parser.add_argument("--outdir", default="assets", help="Destination directory for extracted assets")
    parser.add_argument("--manifest", default="word_asset_manifest.json")
    args = parser.parse_args()
    try:
        manifest_path = extract_assets(Path(args.word_source), Path(args.outdir), args.manifest)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
