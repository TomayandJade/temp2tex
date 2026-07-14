#!/usr/bin/env python3
"""Render DOC/DOCX to reference PDF using the best available local renderer."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
    return proc.returncode, proc.stdout[-4000:], proc.stderr[-4000:]


def tool_candidates(name: str) -> list[str]:
    candidates = []
    preferred = [
        Path(r"D:\texlive\2025\bin\windows") / f"{name}.exe",
        Path(r"C:\Program Files\MiKTeX\miktex\bin\x64") / f"{name}.exe",
    ]
    candidates.extend(str(p) for p in preferred if p.exists())
    try:
        proc = subprocess.run(["where.exe", name], text=True, capture_output=True)
        if proc.returncode == 0:
            candidates.extend(line.strip() for line in proc.stdout.splitlines() if line.strip())
    except Exception:
        pass
    unique = []
    for item in candidates:
        if item not in unique:
            unique.append(item)
    unique.sort(key=lambda p: (0 if p.lower().endswith(".exe") else 1, 0 if "texlive" in p.lower() else 1, p.lower()))
    return unique


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


def render_with_libreoffice(source: Path, outdir: Path) -> dict:
    soffice = find_soffice()
    result = {"renderer": "libreoffice", "available": bool(soffice), "success": False}
    if not soffice:
        result["error"] = "soffice not found"
        return result
    target_pdf = outdir / f"{source.stem}.libreoffice.pdf"
    temp_dir = outdir / "libreoffice-out"
    temp_dir.mkdir(parents=True, exist_ok=True)
    code, stdout, stderr = run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(temp_dir), str(source)])
    result.update({"returncode": code, "stdout_tail": stdout, "stderr_tail": stderr})
    produced = temp_dir / f"{source.stem}.pdf"
    if code == 0 and produced.exists():
        if target_pdf.exists():
            target_pdf.unlink()
        produced.replace(target_pdf)
        result.update({"success": True, "pdf": str(target_pdf)})
    return result


def render_with_word(source: Path, outdir: Path) -> dict:
    result = {"renderer": "microsoft-word", "available": False, "success": False}
    try:
        import win32com.client  # type: ignore
    except Exception as exc:
        result["error"] = f"pywin32/Word COM unavailable: {exc}"
        return result

    target_pdf = outdir / f"{source.stem}.word.pdf"
    word = None
    doc = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        result["available"] = True
        word.Visible = False
        doc = word.Documents.Open(str(source))
        doc.ExportAsFixedFormat(str(target_pdf), 17)
        result.update({"success": target_pdf.exists(), "pdf": str(target_pdf)})
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass
    return result


def page_count(pdf: Path) -> int | None:
    try:
        from pypdf import PdfReader  # type: ignore
        return len(PdfReader(str(pdf)).pages)
    except Exception:
        pass
    candidates = tool_candidates("pdfinfo")
    if not candidates:
        return None
    try:
        proc = subprocess.run([candidates[0], str(pdf)], text=True, capture_output=True, timeout=20)
        for line in proc.stdout.splitlines():
            if line.lower().startswith("pages:"):
                return int(line.split(":", 1)[1].strip())
    except Exception:
        return None
    return None


def choose_best(results: list[dict]) -> dict | None:
    successful = [r for r in results if r.get("success") and r.get("pdf")]
    if not successful:
        return None
    for r in successful:
        r["page_count"] = page_count(Path(r["pdf"]))
    # Word generally preserves Word-native layout better; use LibreOffice only when Word is unavailable or failed.
    successful.sort(key=lambda r: (0 if r["renderer"] == "microsoft-word" else 1, r.get("page_count") is None))
    return successful[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Word DOC/DOCX/DOCM/DOT/DOTX/DOTM/RTF file")
    parser.add_argument("--outdir", default="reference-render")
    parser.add_argument("--prefer", choices=["auto", "word", "libreoffice"], default="auto")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        print(f"source not found: {source}", file=sys.stderr)
        return 2

    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    renderers = []
    if args.prefer == "word":
        renderers = [render_with_word, render_with_libreoffice]
    elif args.prefer == "libreoffice":
        renderers = [render_with_libreoffice, render_with_word]
    else:
        renderers = [render_with_word, render_with_libreoffice]

    results = [renderer(source, outdir) for renderer in renderers]
    best = choose_best(results)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "results": results,
        "selected_reference_pdf": best.get("pdf") if best else None,
        "selection_reason": "Best successful renderer available; Word is preferred for Word-native layout when both succeed." if best else "No renderer succeeded.",
    }
    report_path = outdir / "reference_render_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(report_path)
    return 0 if best else 1


if __name__ == "__main__":
    raise SystemExit(main())
