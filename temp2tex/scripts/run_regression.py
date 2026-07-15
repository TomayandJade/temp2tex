#!/usr/bin/env python3
"""Run Temp2TeX journal-template regression cases.

When official LaTeX exists, the runner compares two normalized LaTeX projects:
1. The official LaTeX template with the fixed regression body injected.
2. The Temp2TeX-generated LaTeX template, generated from the official Word/DOCX
   template, with the same fixed regression body injected.

When official LaTeX is absent or cannot produce a local comparison PDF but an
official Word source exists, the runner falls back to comparing the rendered
Word template PDF against the compiled Temp2TeX-generated template PDF. It
keeps the comparison mode explicit instead of weakening the official-LaTeX gate.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import ssl
import statistics
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SKILL_ROOT / "scripts"
STRESS_PREAMBLE = SKILL_ROOT / "assets" / "regression" / "stress_preamble.tex"
STRESS_BODY = SKILL_ROOT / "assets" / "regression" / "stress_body.tex"
STRESS_BODY_ELSARTICLE = SKILL_ROOT / "assets" / "regression" / "stress_body_elsarticle.tex"
STRESS_BODY_ICCK = SKILL_ROOT / "assets" / "regression" / "stress_body_icck.tex"
STRESS_BODY_IMSART = SKILL_ROOT / "assets" / "regression" / "stress_body_imsart.tex"
STRESS_BODY_CORE = SKILL_ROOT / "assets" / "regression" / "stress_body_core.tex"
STRESS_BODY_SACJ = SKILL_ROOT / "assets" / "regression" / "stress_body_sacj.tex"
STRESS_BODY_MSR = SKILL_ROOT / "assets" / "regression" / "stress_body_msr.tex"
STRESS_BODY_TIIS = SKILL_ROOT / "assets" / "regression" / "stress_body_tiis.tex"
WORD_SOURCE_EXTENSIONS = {".docx", ".docm", ".doc", ".dotx", ".dot", ".dotm", ".rtf"}
CHALLENGE_MARKERS = (
    "captcha",
    "cloudflare",
    "cf-chl-",
    "perfdrive",
    "radware",
    "just a moment",
    "verify you are human",
    "enable javascript and cookies",
    "access denied",
    "botmanager_support",
)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict] = []
        self._current_href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = {k.lower(): v for k, v in attrs}
        href = attrs_dict.get("href")
        if href:
            self._current_href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current_href is not None:
            self.links.append({"href": self._current_href, "text": " ".join(self._text).strip()})
            self._current_href = None
            self._text = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_name(value: str) -> str:
    value = unquote(value)
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return value[:140] or "download"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_command(cmd: list[str], cwd: Path | None = None, timeout: int = 180) -> dict:
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
        return {
            "cmd": cmd,
            "cwd": str(cwd) if cwd else None,
            "returncode": proc.returncode,
            "duration_seconds": round(time.time() - start, 3),
            "stdout_tail": proc.stdout[-6000:],
            "stderr_tail": proc.stderr[-6000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "cwd": str(cwd) if cwd else None,
            "returncode": 124,
            "duration_seconds": round(time.time() - start, 3),
            "stdout_tail": (exc.stdout or "")[-6000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": f"Timed out after {timeout} seconds.",
        }


def tool_candidates(name: str) -> list[str]:
    candidates: list[str] = []
    for base in [
        Path(r"D:\texlive\2025\bin\windows"),
        Path(r"C:\Program Files\MiKTeX\miktex\bin\x64"),
        Path(r"C:\Users\60247\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin"),
    ]:
        for suffix in [".exe", ".cmd", ""]:
            candidate = base / f"{name}{suffix}"
            if candidate.exists():
                candidates.append(str(candidate))
    try:
        proc = subprocess.run(["where.exe", name], text=True, capture_output=True, timeout=10)
        if proc.returncode == 0:
            candidates.extend(line.strip() for line in proc.stdout.splitlines() if line.strip())
    except Exception:
        pass
    unique: list[str] = []
    for item in candidates:
        if item not in unique:
            unique.append(item)
    return unique


def normalize_download_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host in {"docs.google.com", "www.docs.google.com"} and parsed.path.startswith("/document/d/"):
        parts = parsed.path.split("/")
        if len(parts) >= 4 and parts[3]:
            return urlunparse(("https", "docs.google.com", f"/document/d/{parts[3]}/export", "", "format=docx", ""))
    if host in {"drive.google.com", "www.drive.google.com"}:
        query = parse_qs(parsed.query)
        file_id = None
        if parsed.path.startswith("/file/d/"):
            parts = parsed.path.split("/")
            if len(parts) >= 4:
                file_id = parts[3]
        elif "id" in query and query["id"]:
            file_id = query["id"][0]
        if file_id:
            return urlunparse(("https", "drive.google.com", "/uc", "", urlencode({"export": "download", "id": file_id}), ""))
    clean_path = quote(parsed.path, safe="/:@%")
    clean_query = quote(parsed.query, safe="=&?/:;+,%")
    return urlunparse((parsed.scheme, parsed.netloc, clean_path, parsed.params, clean_query, parsed.fragment))


def fetch_url(url: str, timeout: int = 45) -> tuple[bytes | None, dict]:
    normalized_url = normalize_download_url(url)
    errors: list[str] = []

    def make_request() -> Request:
        return Request(normalized_url, headers={"User-Agent": "Mozilla/5.0 Temp2TeX regression runner"})

    for attempt in range(1, 4):
        try:
            with urlopen(make_request(), timeout=timeout) as resp:
                data = resp.read()
                return data, {
                    "url": url,
                    "normalized_url": normalized_url,
                    "ok": True,
                    "status": getattr(resp, "status", None),
                    "content_type": resp.headers.get("content-type", ""),
                    "content_disposition": resp.headers.get("content-disposition", ""),
                    "final_url": resp.geturl(),
                    "bytes": len(data),
                    "attempts": attempt,
                }
        except Exception as exc:
            errors.append(str(exc))
            if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
                if attempt < 3:
                    time.sleep(min(2 * attempt, 5))
                    continue
                break
            try:
                with urlopen(make_request(), timeout=timeout, context=ssl._create_unverified_context()) as resp:
                    data = resp.read()
                    return data, {
                        "url": url,
                        "normalized_url": normalized_url,
                        "ok": True,
                        "status": getattr(resp, "status", None),
                        "content_type": resp.headers.get("content-type", ""),
                        "content_disposition": resp.headers.get("content-disposition", ""),
                        "final_url": resp.geturl(),
                        "bytes": len(data),
                        "attempts": attempt,
                        "warning": "retried with unverified TLS context after certificate verification failed",
                    }
            except Exception as retry_exc:
                errors.append(str(retry_exc))
                if attempt < 3:
                    time.sleep(min(2 * attempt, 5))
                    continue
                break
    return None, {"url": url, "normalized_url": normalized_url, "ok": False, "error": errors[-1] if errors else "download failed", "attempts": len(errors), "errors": errors}


def filename_from_download(url: str, headers: dict, fallback: str) -> str:
    disposition = headers.get("content_disposition") or ""
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', disposition, flags=re.I)
    if match:
        return safe_name(match.group(1))
    parsed = urlparse(headers.get("final_url") or url)
    name = Path(parsed.path).name
    if name:
        return safe_name(name)
    return safe_name(fallback)


def inspect_payload(data: bytes, content_type: str = "") -> dict:
    """Identify the downloaded artifact from bytes, not its URL suffix."""
    sample = data[:65536]
    lowered = sample.lower()
    text_sample = sample.decode("utf-8", errors="ignore").lower()
    challenge_markers = [marker for marker in CHALLENGE_MARKERS if marker in text_sample]
    looks_html = (
        "html" in content_type.lower()
        or lowered.lstrip().startswith((b"<!doctype html", b"<html", b"<head", b"<body"))
    )

    if challenge_markers and looks_html:
        return {
            "kind": "challenge_html",
            "valid": False,
            "challenge_markers": challenge_markers,
            "reason": "download returned an anti-bot or access-challenge HTML page",
        }
    if looks_html:
        return {"kind": "html", "valid": True, "challenge_markers": [], "reason": None}
    if sample.startswith(b"%PDF"):
        return {"kind": "pdf", "valid": True, "challenge_markers": [], "reason": None}
    if sample.startswith(b"{\\rtf"):
        return {"kind": "rtf", "valid": True, "challenge_markers": [], "reason": None}
    if sample.startswith(b"\xd0\xcf\x11\xe0"):
        return {"kind": "ole_word", "valid": True, "challenge_markers": [], "reason": None}
    if sample.startswith(b"PK\x03\x04"):
        try:
            import io

            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = {name.replace("\\", "/").lower() for name in zf.namelist()}
                content_types = zf.read("[Content_Types].xml").lower() if "[content_types].xml" in names else b""
            if "[content_types].xml" in names and any(name.startswith("word/") for name in names):
                kind = "word_openxml"
                openxml_role = "template" if b"wordprocessingml.template.main+xml" in content_types else "document"
            else:
                kind = "zip"
                openxml_role = None
            return {
                "kind": kind,
                "openxml_role": openxml_role,
                "valid": True,
                "challenge_markers": [],
                "reason": None,
            }
        except zipfile.BadZipFile:
            return {
                "kind": "broken_zip",
                "valid": False,
                "challenge_markers": [],
                "reason": "payload has a ZIP signature but cannot be opened as a ZIP archive",
            }

    latex_signal = any(
        token in text_sample
        for token in ("\\documentclass", "\\begin{document}", "\\providesclass", "\\providespackage", "\\entry")
    )
    if latex_signal:
        return {"kind": "latex_text", "valid": True, "challenge_markers": [], "reason": None}
    return {"kind": "unknown", "valid": bool(data), "challenge_markers": [], "reason": None}


def validate_artifact_payload(data: bytes, classification: str, content_type: str = "") -> dict:
    result = inspect_payload(data, content_type=content_type)
    kind = result["kind"]
    if len(data) < 128:
        return {**result, "valid": False, "reason": "downloaded payload is too small to be a template artifact"}
    if not result.get("valid"):
        return result
    if classification == "word" and kind not in {"word_openxml", "ole_word", "rtf", "zip"}:
        return {
            **result,
            "valid": False,
            "reason": f"expected a Word template or archive, detected {kind}",
        }
    if classification == "latex" and kind not in {"zip", "latex_text"}:
        return {
            **result,
            "valid": False,
            "reason": f"expected a LaTeX source file or archive, detected {kind}",
        }
    return result


def extension_for_payload(kind: str, classification: str) -> str:
    if kind == "word_openxml":
        return ".docx"
    if kind == "ole_word":
        return ".doc"
    if kind == "rtf":
        return ".rtf"
    if kind == "zip":
        return ".zip"
    if kind == "latex_text":
        return ".tex"
    if kind == "pdf":
        return ".pdf"
    return ".bin" if classification not in {"word", "latex"} else f".{classification}"


def normalize_artifact_filename(name: str, validation: dict, classification: str) -> str:
    expected = extension_for_payload(str(validation.get("kind") or "unknown"), classification)
    path = Path(name)
    known_suffixes = WORD_SOURCE_EXTENSIONS | {".zip", ".tex", ".cls", ".sty", ".bst", ".pdf", ".rtf"}
    if path.suffix.lower() not in known_suffixes:
        return safe_name(f"{path.stem or classification}{expected}")
    if validation.get("kind") == "word_openxml":
        is_template = validation.get("openxml_role") == "template"
        expected_suffix = ".dotx" if is_template else ".docx"
        allowed_suffixes = {".dotx", ".dotm"} if is_template else {".docx"}
        if path.suffix.lower() not in allowed_suffixes:
            return safe_name(f"{path.stem}{expected_suffix}")
    if validation.get("kind") == "zip" and path.suffix.lower() != ".zip":
        return safe_name(f"{path.stem}.zip")
    return safe_name(name)


def capture_source_pages(case: dict, pages_dir: Path, skip_network: bool) -> tuple[list[dict], list[dict]]:
    page_reports: list[dict] = []
    discovered: list[dict] = []
    if skip_network:
        return page_reports, discovered
    for idx, url in enumerate(case.get("source_page_urls", []), 1):
        data, report = fetch_url(url)
        if data:
            page_validation = inspect_payload(data, content_type=report.get("content_type", ""))
            report["payload_validation"] = page_validation
            if page_validation.get("kind") == "challenge_html":
                report["http_ok"] = report.get("ok")
                report["ok"] = False
                report["error"] = page_validation.get("reason")
        page_reports.append(report)
        if not data or not report.get("ok"):
            continue
        suffix = ".html"
        filename = f"source-page-{idx:02d}{suffix}"
        page_path = pages_dir / filename
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_bytes(data)
        content_type = (report.get("content_type") or "").lower()
        text = ""
        if "html" in content_type or data[:100].lower().find(b"<html") >= 0:
            text = data.decode("utf-8", errors="replace")
            parser = LinkParser()
            parser.feed(text)
            for item in parser.links:
                href = item.get("href", "")
                if not href or href.startswith("#") or href.lower().startswith("mailto:"):
                    continue
                absolute = urljoin(url, html.unescape(href))
                text_label = html.unescape(item.get("text", ""))
                discovered.append({
                    "source_page": url,
                    "url": absolute,
                    "text": text_label,
                    "classification": classify_link(absolute, text_label),
                })
            notes = html_to_text(text)
            write_text(pages_dir / f"source-page-{idx:02d}.txt", notes[:60000])
    return page_reports, discovered


def html_to_text(markup: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", markup)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def classify_link(url: str, label: str) -> str:
    haystack = f"{url} {label}".lower()
    word_score = 0
    latex_score = 0
    if any(token in haystack for token in [".docx", ".docm", ".doc", ".dotx", ".dotm", ".dot"]):
        word_score += 3
    if re.search(r"\b(ms|microsoft)\s+word\b|\bword\s+template\b|\bword\b", haystack):
        word_score += 3
    if any(token in haystack for token in [".tex", ".cls", ".sty", ".bst", "overleaf", "tex template", "latex template", "latex package", "latex files"]):
        latex_score += 3
    if "latex" in haystack and any(token in haystack for token in ["template", "package", ".zip", "download"]):
        latex_score += 2
    if ".zip" in haystack and any(token in haystack for token in ["latex", "template", "package"]):
        latex_score += 2
    if "download" in haystack and "template" in haystack:
        word_score += 1
        latex_score += 1
    if word_score and word_score >= latex_score:
        return "word"
    if latex_score:
        return "latex"
    return "other"


def add_explicit_links(case: dict, discovered: list[dict]) -> list[dict]:
    result = list(discovered)
    if case.get("doc_template_url"):
        result.insert(0, {
            "source_page": "manifest.doc_template_url",
            "url": case["doc_template_url"],
            "text": "manifest DOC/DOCX template",
            "classification": "word",
        })
    if case.get("latex_template_url"):
        result.insert(0, {
            "source_page": "manifest.latex_template_url",
            "url": case["latex_template_url"],
            "text": "manifest LaTeX template",
            "classification": "latex",
        })
    return result


def should_download(url: str, classification: str) -> bool:
    lower = url.lower()
    if "overleaf.com" in lower and "/read/" not in lower and "/project/" not in lower:
        return False
    clean_url = lower.split("?", 1)[0]
    if "#" in clean_url and not any(clean_url.endswith(ext) for ext in [".zip", ".docx", ".docm", ".doc", ".dotx", ".dotm", ".dot", ".tex", ".cls", ".sty", ".bst"]):
        return False
    if any(clean_url.endswith(ext) for ext in [".zip", ".docx", ".docm", ".doc", ".dotx", ".dotm", ".dot", ".tex", ".cls", ".sty", ".bst"]):
        return True
    if classification in {"word", "latex"}:
        return True
    return False


def download_artifacts(
    links: list[dict],
    downloads_dir: Path,
    skip_network: bool,
    max_valid_per_kind: int | None = None,
    fetch_timeout: int = 90,
) -> list[dict]:
    reports: list[dict] = []
    if skip_network:
        return reports
    seen: set[tuple[str, str]] = set()
    selected: list[dict] = []
    for kind in ["word", "latex"]:
        for item in links:
            if item.get("classification") != kind:
                continue
            url = item["url"]
            key = (kind, url)
            if key in seen or not should_download(url, kind):
                continue
            seen.add(key)
            selected.append(item)
            if len([x for x in selected if x.get("classification") == kind]) >= 4:
                break
    valid_counts = {"word": 0, "latex": 0}
    for item in selected:
        kind = item.get("classification", "download")
        if max_valid_per_kind is not None and valid_counts.get(kind, 0) >= max_valid_per_kind:
            continue
        url = item["url"]
        data, report = fetch_url(url, timeout=fetch_timeout)
        report["classification"] = item.get("classification")
        report["link_text"] = item.get("text", "")
        if data:
            validation = validate_artifact_payload(
                data,
                item.get("classification", "other"),
                content_type=report.get("content_type", ""),
            )
            report["payload_validation"] = validation
            if not validation.get("valid"):
                report["http_ok"] = report.get("ok")
                report["ok"] = False
                report["error"] = validation.get("reason")
                reports.append(report)
                continue
            name = filename_from_download(url, report, item.get("classification", "download"))
            if "." not in Path(name).name:
                inferred = infer_extension(report.get("content_type", ""), item.get("classification", "download"), data)
                name += inferred
            name = normalize_artifact_filename(name, validation, item.get("classification", "download"))
            target = downloads_dir / item.get("classification", "download") / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            report["local_path"] = str(target)
            report["sha256"] = sha256_file(target)
            if report.get("ok"):
                valid_counts[kind] = valid_counts.get(kind, 0) + 1
        reports.append(report)
    return reports


def latex_cache_dir(outdir: Path, case_id: str) -> Path:
    """Return the corpus-level, source-artifact cache for one case."""
    return outdir.parent / "official_sources" / safe_name(case_id) / "latex"


def restore_cached_latex_artifacts(case: dict, outdir: Path, downloads_dir: Path) -> list[dict]:
    """Restore immutable official LaTeX artifacts for an offline iteration.

    A regression iteration must not silently fall back from an official-LaTeX
    golden merely because `--skip-network` starts with an empty output folder.
    This cache contains only downloaded source artifacts, never compiled PDFs
    or normalized projects, and every restored file is re-hashed in the case
    source manifest.
    """
    cache_dir = latex_cache_dir(outdir, str(case.get("case_id") or ""))
    if not cache_dir.exists():
        return []
    target_root = downloads_dir / "latex"
    reports: list[dict] = []
    for source in sorted(cache_dir.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(cache_dir)
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and sha256_file(target) == sha256_file(source):
            reports.append({"ok": True, "cached": True, "deduplicated": True, "source": str(source), "local_path": str(target), "sha256": sha256_file(target)})
            continue
        shutil.copy2(source, target)
        reports.append({"ok": True, "cached": True, "source": str(source), "local_path": str(target), "sha256": sha256_file(target)})
    return reports


def cache_latex_artifacts(case: dict, outdir: Path, downloads_dir: Path) -> list[dict]:
    """Persist downloaded official LaTeX source artifacts for later offline runs."""
    source_root = downloads_dir / "latex"
    if not source_root.exists():
        return []
    cache_dir = latex_cache_dir(outdir, str(case.get("case_id") or ""))
    reports: list[dict] = []
    for source in sorted(source_root.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(source_root)
        target = cache_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or sha256_file(target) != sha256_file(source):
            shutil.copy2(source, target)
        reports.append({"ok": True, "cached": True, "source": str(source), "cache_path": str(target), "sha256": sha256_file(target)})
    return reports


def infer_extension(content_type: str, classification: str, data: bytes | None = None) -> str:
    ct = content_type.lower()
    sample = data[:8] if data else b""
    if sample.startswith(b"PK\x03\x04"):
        return ".docx" if classification == "word" else ".zip"
    if sample.startswith(b"\xd0\xcf\x11\xe0"):
        return ".doc"
    if sample.startswith(b"{\\rtf"):
        return ".rtf"
    if sample.startswith(b"%PDF"):
        return ".pdf"
    if "wordprocessingml" in ct:
        return ".docx"
    if "msword" in ct:
        return ".doc"
    if "zip" in ct:
        return ".zip"
    if "tex" in ct or classification == "latex":
        return ".tex"
    return ".bin"


def copy_local_word_inputs(case: dict, inputs_dir: Path) -> list[dict]:
    copied: list[dict] = []
    for item in case.get("local_word_paths", []):
        src = Path(item)
        if not src.exists():
            copied.append({"source": item, "ok": False, "error": "local path not found"})
            continue
        validation = validate_artifact_payload(src.read_bytes(), "word")
        if not validation.get("valid"):
            copied.append({
                "source": item,
                "ok": False,
                "error": validation.get("reason"),
                "payload_validation": validation,
            })
            continue
        target = inputs_dir / "word" / src.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append({
            "source": str(src),
            "ok": True,
            "local_path": str(target),
            "sha256": sha256_file(target),
            "payload_validation": validation,
        })
    return copied


def copy_word_candidate(src: Path, word_dir: Path) -> dict:
    validation = validate_artifact_payload(src.read_bytes(), "word")
    if not validation.get("valid"):
        return {
            "source": str(src),
            "ok": False,
            "error": validation.get("reason"),
            "payload_validation": validation,
        }
    word_dir.mkdir(parents=True, exist_ok=True)
    target = word_dir / src.name
    index = 1
    while target.exists():
        try:
            if sha256_file(target) == sha256_file(src):
                return {
                    "source": str(src),
                    "ok": True,
                    "local_path": str(target),
                    "sha256": sha256_file(target),
                    "deduplicated": True,
                    "payload_validation": validation,
                }
        except OSError:
            pass
        target = word_dir / f"{src.stem}-{index}{src.suffix}"
        index += 1
    shutil.copy2(src, target)
    return {
        "source": str(src),
        "ok": True,
        "local_path": str(target),
        "sha256": sha256_file(target),
        "payload_validation": validation,
    }


def collect_downloaded_word_sources(downloads_dir: Path, inputs_dir: Path) -> list[dict]:
    reports: list[dict] = []
    word_dir = inputs_dir / "word"
    extract_root = inputs_dir / "word_extracted"
    if not downloads_dir.exists():
        return reports
    for src in sorted(downloads_dir.rglob("*")):
        if not src.is_file():
            continue
        suffix = src.suffix.lower()
        if suffix in WORD_SOURCE_EXTENSIONS:
            reports.append(copy_word_candidate(src, word_dir))
            continue
        if suffix != ".zip":
            continue
        case_extract_dir = extract_root / safe_name(src.stem)
        extractions = safe_extract_zip_recursive(src, case_extract_dir)
        copied = []
        for candidate in sorted(case_extract_dir.rglob("*")):
            if candidate.is_file() and candidate.suffix.lower() in WORD_SOURCE_EXTENSIONS:
                copied.append(copy_word_candidate(candidate, word_dir))
        reports.append({
            "source_zip": str(src),
            "ok": any(item.get("ok") for item in extractions),
            "extractions": extractions,
            "copied_word_candidates": copied,
        })
    return reports


def safe_extract_zip(path: Path, outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    outdir_resolved = outdir.resolve()
    extracted: list[str] = []
    sanitized: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []

    def sanitize_member_name(name: str) -> tuple[Path | None, dict | None]:
        normalized = name.replace("\\", "/")
        raw_parts = [part for part in normalized.split("/") if part and part != "."]
        if not raw_parts:
            return None, {"file": name, "reason": "empty path"}
        if raw_parts[0] == "__MACOSX" or raw_parts[-1] == ".DS_Store":
            return None, {"file": name, "reason": "macOS metadata"}
        if any(part == ".." for part in raw_parts):
            return None, {"file": name, "reason": "unsafe path traversal"}

        safe_parts = []
        changed = False
        for index, part in enumerate(raw_parts):
            safe_part = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", part)
            safe_part = safe_part.strip().rstrip(".")
            if not safe_part:
                safe_part = "file" if index == len(raw_parts) - 1 else "dir"
            if safe_part != part:
                changed = True
            safe_parts.append(safe_part)
        if changed:
            return Path(*safe_parts), {"from": name, "to": str(Path(*safe_parts))}
        return Path(*safe_parts), None

    try:
        with zipfile.ZipFile(path) as zf:
            for member in zf.infolist():
                relative_path, note = sanitize_member_name(member.filename)
                if relative_path is None:
                    if note:
                        skipped.append(note)
                    continue
                if note:
                    sanitized.append(note)
                destination = (outdir / relative_path).resolve()
                try:
                    destination.relative_to(outdir_resolved)
                except ValueError:
                    skipped.append({"file": member.filename, "reason": "unsafe resolved path"})
                    continue
                if member.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                try:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as source, destination.open("wb") as target:
                        shutil.copyfileobj(source, target)
                    extracted.append(str(relative_path))
                except Exception as exc:
                    errors.append({"file": member.filename, "error": str(exc)})
        return {
            "ok": bool(extracted),
            "archive": str(path),
            "outdir": str(outdir),
            "files": extracted[:200],
            "sanitized": sanitized[:200],
            "skipped": skipped[:200],
            "errors": errors[:50],
        }
    except Exception as exc:
        return {
            "ok": False,
            "archive": str(path),
            "error": str(exc),
            "files": extracted,
            "sanitized": sanitized[:200],
            "skipped": skipped[:200],
            "errors": errors[:50],
        }


def safe_extract_zip_recursive(path: Path, outdir: Path, max_depth: int = 3) -> list[dict]:
    reports: list[dict] = []

    def visit(zip_path: Path, target_dir: Path, depth: int) -> None:
        report = safe_extract_zip(zip_path, target_dir)
        report["depth"] = depth
        reports.append(report)
        if not report.get("ok") or depth >= max_depth:
            return
        for nested in sorted(target_dir.rglob("*.zip")):
            if nested.resolve() == zip_path.resolve():
                continue
            nested_target = nested.parent / safe_name(nested.stem)
            visit(nested, nested_target, depth + 1)

    visit(path, outdir, 0)
    return reports


def prepare_official_latex_sources(downloads_dir: Path, latex_root: Path, preferred_patterns: list[str] | None = None) -> tuple[list[dict], Path | None]:
    reports: list[dict] = []
    latex_files = list((downloads_dir / "latex").rglob("*")) if (downloads_dir / "latex").exists() else []
    direct_tex_root = latex_root / "direct"
    for src in latex_files:
        if not src.is_file():
            continue
        lower = src.name.lower()
        if lower.endswith(".zip"):
            reports.extend(safe_extract_zip_recursive(src, latex_root / safe_name(src.stem)))
        else:
            # A direct official package may ship its graphics, bibliography
            # databases, fonts, or data beside the source files. Keep every
            # non-archive artifact under its relative path so class-file
            # dependencies are not mistaken for an official compile failure.
            direct_tex_root.mkdir(parents=True, exist_ok=True)
            target = direct_tex_root / src.relative_to(downloads_dir / "latex")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            reports.append({"ok": True, "archive": str(src), "outdir": str(direct_tex_root), "files": [str(target.relative_to(direct_tex_root))]})
    main_tex = find_main_tex(latex_root, preferred_patterns=preferred_patterns)
    return reports, main_tex


def find_main_tex(root: Path, preferred_patterns: list[str] | None = None) -> Path | None:
    if not root.exists():
        return None
    candidates = []
    for tex in root.rglob("*.tex"):
        try:
            text = tex.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "\\documentclass" not in text or "\\begin{document}" not in text:
            continue
        name = tex.name.lower()
        score = 0
        for index, pattern in enumerate(preferred_patterns or []):
            if pattern.lower() in str(tex).lower():
                score += 1000 - index
        if name in {"main.tex", "sample.tex", "template.tex", "article.tex", "elsarticle-template.tex"}:
            score += 40
        if any(token in name for token in ["sample", "template", "main", "article", "manuscript"]):
            score += 20
        score += min(len(text) // 1000, 30)
        score -= len(tex.relative_to(root).parts)
        candidates.append((score, tex))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], str(item[1]).lower()))
    return candidates[0][1]


def choose_body_path(preamble: str, source: str, adapter: str | None) -> tuple[Path, str]:
    selected = (adapter or "auto").lower()
    if selected == "auto" and re.search(r"\\documentclass(?:\[[^\]]*\])?\{elsarticle\}", preamble):
        selected = "elsarticle"
    if selected == "auto" and re.search(r"\\documentclass(?:\[[^\]]*\])?\{ICCKjournal\}", preamble):
        selected = "icck"
    if selected == "auto" and re.search(r"\\documentclass(?:\[[^\]]*\])?\{(?:imsart|baltzer)\}", preamble):
        selected = "imsart"
    if selected == "auto" and re.search(r"\\documentclass(?:\[[^\]]*\])?\{sacjsub\}", preamble, re.IGNORECASE):
        selected = "sacj"
    if selected == "auto" and re.search(r"\\documentclass(?:\[[^\]]*\])?\{MSRarticle\}", preamble, re.IGNORECASE):
        selected = "msr"
    if selected == "auto" and re.search(r"\\documentclass(?:\[[^\]]*\])?\{TIIS\}", preamble, re.IGNORECASE):
        selected = "tiis"
    if selected == "auto" and re.search(r"\\documentclass(?:\[[^\]]*\])?\{ieeeaccess\}", preamble, re.IGNORECASE):
        selected = "ieeeaccess"
    if selected == "auto" and all(token in source for token in (r"\begin{frontmatter}", r"\begin{aug}", r"\kwd")):
        selected = "imsart"
    if selected == "elsarticle":
        return STRESS_BODY_ELSARTICLE, "elsarticle"
    if selected == "icck":
        return STRESS_BODY_ICCK, "icck"
    if selected in {"imsart", "baltzer", "frontmatter-aug"}:
        return STRESS_BODY_IMSART, "imsart"
    if selected == "sacj":
        return STRESS_BODY_SACJ, "sacj"
    if selected == "msr":
        return STRESS_BODY_MSR, "msr"
    if selected == "tiis":
        return STRESS_BODY_TIIS, "tiis"
    if selected == "ieeeaccess":
        return STRESS_BODY, "ieeeaccess"
    return STRESS_BODY, "generic"


def load_stress_body(body_path: Path, adapter_used: str) -> str:
    body = body_path.read_text(encoding="utf-8")
    if adapter_used in {"sacj", "msr", "tiis"}:
        body = f"{body.rstrip()}\n\n{STRESS_BODY_CORE.read_text(encoding='utf-8').lstrip()}"
    if adapter_used == "ieeeaccess":
        # IEEE Access requires DOI metadata in the title block. The official
        # sample supplies it in its body, which normalized regression replaces.
        # It also requires \EOD after the final paragraph.
        body = "\\doi{10.1109/ACCESS.2026.0000000}\n" + body.rstrip() + "\n\\EOD\n"
    return body


def inject_normalized_stress_body(source: str, stress_body: str) -> tuple[str, str]:
    """Preserve a source-backed one-column front-matter/two-column body transition."""
    if r"\twocolumn[" not in source:
        return stress_body, "none"
    prefix, marker, body = stress_body.partition(r"\tempTwoTexBodyBegin")
    if not marker or not body.strip():
        return stress_body, "none"
    return (
        rf"\twocolumn[" + "\n" + prefix.rstrip() + "\n]\n\n"
        + marker + body,
        "twocolumn_front_matter",
    )


def project_supports_journalfigure(root: Path) -> bool:
    candidate = root / "journal-template.cls"
    if not candidate.exists():
        return False
    try:
        return r"\newenvironment{journalfigure}" in candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def project_supports_journaltable(root: Path) -> bool:
    candidate = root / "journal-template.cls"
    if not candidate.exists():
        return False
    try:
        return r"\newenvironment{journaltable}" in candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def project_supports_journalappendix(root: Path) -> bool:
    """Return true only when the generated class activates a verified boundary."""
    candidate = root / "journal-template.cls"
    if not candidate.exists():
        return False
    try:
        source = candidate.read_text(encoding="utf-8", errors="replace")
        marker = r"\newcommand{\journalappendix}"
        if marker not in source:
            return False
        prefix = source.split(marker, 1)[1].split(r"\appendix", 1)[0]
        return r"\clearpage" in prefix
    except OSError:
        return False


def adapt_stress_appendix_interface(stress_body: str, source_root: Path) -> tuple[str, bool]:
    """Exercise the generated class's editable appendix boundary when available."""
    if not project_supports_journalappendix(source_root):
        return stress_body, False
    adapted = stress_body.replace(r"\appendix", r"\journalappendix", 1)
    return adapted, adapted != stress_body


def project_supports_journalbackmatter(root: Path) -> bool:
    """Return true only when the generated class activates a verified boundary."""
    candidate = root / "journal-template.cls"
    if not candidate.exists():
        return False
    try:
        source = candidate.read_text(encoding="utf-8", errors="replace")
        marker = r"\newcommand{\journalbackmatter}"
        if marker not in source:
            return False
        definition = source.split(marker, 1)[1].splitlines()[0]
        return r"\clearpage" in definition
    except OSError:
        return False


def adapt_stress_backmatter_interface(stress_body: str, source_root: Path) -> tuple[str, bool]:
    """Exercise the generated class's editable pre-statements boundary."""
    if not project_supports_journalbackmatter(source_root):
        return stress_body, False
    marker = r"\section*{Acknowledgements}"
    adapted = stress_body.replace(marker, r"\journalbackmatter" + "\n" + marker, 1)
    return adapted, adapted != stress_body


def adapt_stress_figure_interface(stress_body: str, source_root: Path) -> tuple[str, bool]:
    """Exercise the generated package's editable figure policy when available."""
    if not project_supports_journalfigure(source_root):
        return stress_body, False
    adapted = re.sub(r"\\begin\{figure\}(\[[^\]]*\])?", r"\\begin{journalfigure}\1", stress_body)
    adapted = adapted.replace(r"\end{figure}", r"\end{journalfigure}")
    return adapted, adapted != stress_body


def adapt_stress_table_interface(stress_body: str, source_root: Path) -> tuple[str, bool]:
    """Exercise a generated package's editable table wrapper when available."""
    if not project_supports_journaltable(source_root):
        return stress_body, False
    adapted = re.sub(r"\\begin\{table\}(\[[^\]]*\])?", r"\\begin{journaltable}\1", stress_body)
    adapted = adapted.replace(r"\end{table}", r"\end{journaltable}")
    return adapted, adapted != stress_body


NORMALIZED_METADATA_COMMANDS = {
    "title",
    "author",
    "affiliation",
    "date",
    "maketitle",
    "shorttitle",
    "shortauthors",
    "titlerunning",
    "authorrunning",
    "articletitle",
    "correspondingauthor",
    "email",
    "address",
    "institute",
    "affil",
}


TEMP2TEX_REGRESSION_HOOKS = r"""% Preserve generated Temp2TeX class behavior during fixture injection.
% Official LaTeX classes receive harmless no-op definitions instead.
\providecommand{\tempTWOEnableLineNumbers}{}
\providecommand{\journalstartbodycolumns}{}
"""


def apply_temp2tex_regression_hooks(body: str) -> tuple[str, bool]:
    """Invoke generated-class hooks that the fixed fixture would otherwise skip."""
    marker = r"\tempTwoTexBodyBegin"
    if marker not in body:
        return body, False
    return body.replace(marker, r"\journalstartbodycolumns" + "\n" + marker, 1), True


def strip_source_front_matter_metadata(preamble: str) -> tuple[str, list[str]]:
    """Remove source example metadata before injecting the fixed manuscript.

    Generated packages and official LaTeX examples commonly define title,
    author, and affiliation values before ``\begin{document}``. Keeping those
    calls while adding the stress body creates duplicate affiliations or stale
    author notes, so it compares different manuscripts. Only commands that
    start a preamble line are removed; class/package definitions containing a
    same-named macro remain untouched.
    """
    lines = preamble.splitlines(keepends=True)
    kept: list[str] = []
    removed: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"^\s*\\([A-Za-z@]+)(?:\*)?(?=\s|\{|$)", line)
        command = match.group(1).lower() if match else ""
        if command not in NORMALIZED_METADATA_COMMANDS:
            kept.append(line)
            index += 1
            continue
        removed.append(command)
        depth = 0
        consumed = False
        while index < len(lines):
            current = lines[index]
            depth += current.count("{") - current.count("}")
            consumed = True
            index += 1
            # Commands without an argument, such as \maketitle, end on the
            # first line; braced commands end after their balanced group.
            if (depth <= 0 and ("{" not in line or consumed)):
                break
        while index < len(lines) and not lines[index].strip():
            index += 1
    return "".join(kept), removed


def make_normalized_project(src_root: Path, main_tex: Path, dest_root: Path, adapter: str | None = None) -> tuple[Path | None, dict]:
    if dest_root.exists():
        shutil.rmtree(dest_root)
    shutil.copytree(src_root, dest_root)
    try:
        rel_main = main_tex.resolve().relative_to(src_root.resolve())
    except ValueError:
        rel_main = Path(main_tex.name)
        shutil.copy2(main_tex, dest_root / rel_main)
    dest_original = dest_root / rel_main
    normalized_main = dest_original.parent / "temp2tex_regression_main.tex"
    try:
        source = dest_original.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return None, {"ok": False, "error": str(exc)}
    match = re.search(r"\\begin\s*\{\s*document\s*\}", source)
    if not match:
        return None, {"ok": False, "error": "missing \\begin{document}"}
    begin = match.group(0)
    preamble, stripped_metadata = strip_source_front_matter_metadata(source[:match.start()])
    body_path, adapter_used = choose_body_path(preamble, source, adapter)
    stress_preamble = STRESS_PREAMBLE.read_text(encoding="utf-8")
    stress_body = load_stress_body(body_path, adapter_used)
    stress_body, journalfigure_adapter = adapt_stress_figure_interface(stress_body, src_root)
    stress_body, journaltable_adapter = adapt_stress_table_interface(stress_body, src_root)
    stress_body, journalbackmatter_adapter = adapt_stress_backmatter_interface(stress_body, src_root)
    stress_body, journalappendix_adapter = adapt_stress_appendix_interface(stress_body, src_root)
    injected_body, structural_wrapper = inject_normalized_stress_body(source, stress_body)
    injected_body, temp2tex_body_hook = apply_temp2tex_regression_hooks(injected_body)
    normalized = f"{preamble}\n\n% Temp2TeX regression preamble injection\n{stress_preamble}\n\n{begin}\n{TEMP2TEX_REGRESSION_HOOKS}\n\\tempTWOEnableLineNumbers\n\n% Temp2TeX regression body injection\n{injected_body}\n\n\\end{{document}}\n"
    normalized_main.write_text(normalized, encoding="utf-8")
    return normalized_main, {
        "ok": True,
        "source_root": str(src_root),
        "source_main": str(main_tex),
        "normalized_root": str(dest_root),
        "normalized_main": str(normalized_main),
        "adapter": adapter_used,
        "stress_body": str(body_path),
        "structural_wrapper": structural_wrapper,
        "journalfigure_adapter": journalfigure_adapter,
        "journaltable_adapter": journaltable_adapter,
        "journalbackmatter_adapter": journalbackmatter_adapter,
        "journalappendix_adapter": journalappendix_adapter,
        "temp2tex_body_hook": temp2tex_body_hook,
        "stripped_source_metadata_commands": stripped_metadata,
    }


def compile_latex(main_tex: Path, report_path: Path, engine: str | None = None) -> dict:
    cmd = [sys.executable, str(SCRIPT_DIR / "compile_latex_package.py"), str(main_tex), "--output", str(report_path)]
    if engine:
        cmd.extend(["--engine", engine])
    result = run_command(
        cmd,
        cwd=main_tex.parent,
        timeout=240,
    )
    report = {"success": False, "command": result}
    if report_path.exists():
        try:
            report.update(read_json(report_path))
        except Exception as exc:
            report["read_error"] = str(exc)
    return report


def infer_official_compile_engine(main_tex: Path) -> str:
    """Select a compatible engine for an official golden without touching output.

    Temp2TeX packages deliberately default to XeLaTeX for CJK safety. Official
    publisher packages are independent evidence: some still use PDFTeX-only
    primitives in a class or local style file. Detect that narrow case so an
    otherwise valid official golden is not discarded and replaced by a weaker
    Word fallback.
    """
    pdftex_markers = (r"\pdfobj", r"\pdfextension", r"\pdfliteral", r"\pdfcatalog")
    try:
        candidates = [main_tex, *main_tex.parent.rglob("*.cls"), *main_tex.parent.rglob("*.sty")]
        for path in candidates:
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(marker in text for marker in pdftex_markers):
                return "pdflatex"
    except OSError:
        pass
    return "xelatex"


def render_word_reference(word_source: Path, outdir: Path) -> dict:
    result = run_command(
        [
            sys.executable,
            str(SCRIPT_DIR / "render_docx_reference.py"),
            str(word_source),
            "--outdir",
            str(outdir),
        ],
        timeout=300,
    )
    report_path = outdir / "reference_render_report.json"
    report = read_json(report_path) if report_path.exists() else {}
    reference_pdf = Path(report.get("selected_reference_pdf") or "") if report.get("selected_reference_pdf") else None
    return {
        "success": bool(reference_pdf and reference_pdf.exists()),
        "pdf": str(reference_pdf) if reference_pdf and reference_pdf.exists() else None,
        "report_path": str(report_path) if report_path.exists() else None,
        "report": report,
        "command": result,
    }


def render_normalized_word_reference(word_source: Path, outdir: Path) -> dict:
    normalized_docx = outdir / "normalized_word_reference.docx"
    normalization_report_path = outdir / "word_normalization_report.json"
    normalization_command = run_command(
        [
            sys.executable,
            str(SCRIPT_DIR / "normalize_word_stress.py"),
            str(word_source),
            "--output",
            str(normalized_docx),
            "--report",
            str(normalization_report_path),
        ],
        timeout=240,
    )
    normalization_report = read_json(normalization_report_path) if normalization_report_path.exists() else {}
    result = {
        "success": False,
        "normalization_mode": "same_manuscript_preserve_word_template_styles",
        "normalized_word_source": str(normalized_docx) if normalized_docx.exists() else None,
        "normalization_report_path": str(normalization_report_path) if normalization_report_path.exists() else None,
        "normalization_report": normalization_report,
        "normalization_command": normalization_command,
    }
    if not (normalization_report.get("success") and normalized_docx.exists()):
        result["error"] = "official Word template could not be normalized with the fixed stress manuscript"
        return result
    render = render_word_reference(normalized_docx, outdir / "render")
    result.update(
        {
            "success": render.get("success", False),
            "pdf": render.get("pdf"),
            "report_path": render.get("report_path"),
            "report": render.get("report"),
            "render_command": render.get("command"),
        }
    )
    return result


def compare_pdfs(reference_pdf: Path, generated_pdf: Path, outdir: Path, max_pages: int = 30) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    result = run_command(
        [
            sys.executable,
            str(SCRIPT_DIR / "compare_pdfs.py"),
            str(reference_pdf),
            str(generated_pdf),
            "--outdir",
            str(outdir),
            "--max-pages",
            str(max_pages),
        ],
        cwd=outdir.parent,
        timeout=240,
    )
    report_path = outdir / "render_compare_report.json"
    report = {"command": result, "issues": ["comparison report missing"]}
    if report_path.exists():
        try:
            report = read_json(report_path)
            report["command"] = result
        except Exception as exc:
            report["read_error"] = str(exc)
    return report


def score_word_source(path: Path, preferred_patterns: list[str] | None = None) -> int:
    name = path.name.lower()
    score = 0
    for index, pattern in enumerate(preferred_patterns or []):
        if pattern.lower() in name:
            score += 1000 - index
    if any(token in name for token in ["article", "manuscript", "paper", "main", "template"]):
        score += 80
    if any(token in name for token in ["supplement", "supplementary", "title", "statement", "cover", "checklist", "keyword"]):
        score -= 120
    suffix_order = {".docx": 30, ".docm": 28, ".dotx": 25, ".dotm": 20, ".doc": 15, ".dot": 10}
    score += suffix_order.get(path.suffix.lower(), 0)
    score -= len(path.name)
    return score


def choose_word_source(inputs_dir: Path, preferred_patterns: list[str] | None = None) -> Path | None:
    candidates: list[Path] = []
    for ext in ["*.docx", "*.docm", "*.doc", "*.dotx", "*.dotm", "*.dot"]:
        candidates.extend(sorted((inputs_dir / "word").glob(ext)))
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: (-score_word_source(path, preferred_patterns), str(path).lower()))[0]


def build_temp2tex_package(case_root: Path, word_source: Path) -> dict:
    outputs = case_root / "temp2tex"
    outputs.mkdir(parents=True, exist_ok=True)
    inventory = outputs / "source_inventory.json"
    spec = outputs / "template_spec.json"
    notes = outputs / "official_notes.txt"
    source_text_parts = []
    for text_file in sorted((case_root / "source_pages").glob("*.txt")):
        source_text_parts.append(text_file.read_text(encoding="utf-8", errors="replace")[:20000])
    notes.write_text("\n\n".join(source_text_parts), encoding="utf-8")
    commands = []
    commands.append(run_command([sys.executable, str(SCRIPT_DIR / "inspect_sources.py"), str(word_source), "--output", str(inventory)], timeout=180))
    if inventory.exists():
        commands.append(run_command([sys.executable, str(SCRIPT_DIR / "draft_spec_from_inventory.py"), str(inventory), "--notes", str(notes), "--output", str(spec)], timeout=180))
    package_dir = outputs / "latex-package"
    assets_skipped_for_legacy_source = False
    if spec.exists():
        generate_command = [
            sys.executable,
            str(SCRIPT_DIR / "generate_latex_package.py"),
            str(spec),
            "--outdir",
            str(package_dir),
        ]
        # Asset extraction is optional evidence in a regression. A legacy
        # binary can make LibreOffice spend minutes converting media and hide
        # a useful class/compile result, so keep the original source for
        # structure and Word rendering but do not block generation on assets.
        if word_source.suffix.lower() not in {".doc", ".dot", ".rtf"}:
            generate_command.extend(["--word-source", str(word_source)])
        else:
            assets_skipped_for_legacy_source = True
        commands.append(run_command(generate_command, timeout=180))
    return {
        "ok": package_dir.exists() and (package_dir / "main.tex").exists(),
        "source_inventory": str(inventory) if inventory.exists() else None,
        "template_spec": str(spec) if spec.exists() else None,
        "package_dir": str(package_dir) if package_dir.exists() else None,
        "commands": commands,
        "assets_skipped_for_legacy_source": assets_skipped_for_legacy_source,
    }


def set_nested(data: dict, path: str, value) -> None:
    cur = data
    parts = path.split(".")
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def generate_variant_package(spec: dict, spec_path: Path, package_dir: Path, word_source: Path | None = None) -> dict:
    package_dir.mkdir(parents=True, exist_ok=True)
    variant_spec = package_dir / "template_spec.json"
    write_json(variant_spec, spec)
    command_args = [sys.executable, str(SCRIPT_DIR / "generate_latex_package.py"), str(variant_spec), "--outdir", str(package_dir)]
    if any(
        str((((spec.get(owner) or {}).get("render_calibration") or {}).get("status", ""))).lower() == "render_probe"
        for owner in ("page", "document")
    ) or any(
        str((((spec.get(owner) or {}).get("layout_evidence") or {}).get("placement_calibration") or {}).get("status", "")).lower() == "render_probe"
        for owner in ("figures", "tables")
    ) or str(((spec.get("page") or {}).get("float_spacing_calibration") or {}).get("status", "")).lower() == "render_probe" or str(
        ((((spec.get("appendices") or {}).get("layout_evidence") or {}).get("boundary_calibration") or {}).get("status", ""))
    ).lower() == "render_probe" or str(
        ((((spec.get("statements") or {}).get("layout_evidence") or {}).get("boundary_calibration") or {}).get("status", ""))
    ).lower() == "render_probe":
        command_args.append("--apply-render-probe")
    if word_source and word_source.suffix.lower() not in {".doc", ".dot", ".rtf"}:
        command_args.extend(["--word-source", str(word_source)])
    command = run_command(command_args, timeout=180)
    return {
        "package_dir": str(package_dir),
        "template_spec": str(variant_spec),
        "ok": (package_dir / "main.tex").exists(),
        "commands": [command],
        "source_spec": str(spec_path),
    }


def build_temp2tex_variants(
    case_root: Path,
    temp2tex_report: dict,
    enabled: bool,
    figure_placement_probe: bool = False,
    table_placement_probe: bool = False,
    float_spacing_probe: bool = False,
    table_geometry_probe: bool = False,
    body_style_probe: bool = False,
    furniture_geometry_probe: bool = False,
    first_page_furniture_probe: bool = False,
    source_font_probe: bool = False,
    heading_color_probe: bool = False,
    reference_layout_probe: bool = False,
    text_box_placement_probe: bool = False,
    appendix_boundary_probe: bool = False,
    backmatter_boundary_probe: bool = False,
) -> list[dict]:
    package_dir = Path(temp2tex_report.get("package_dir") or "")
    variants = []
    if package_dir.exists() and (package_dir / "main.tex").exists():
        variants.append({
            "label": "base",
            "package_dir": str(package_dir),
            "main_tex": str(package_dir / "main.tex"),
            "ok": True,
            "commands": [],
        })
    spec_path = Path(temp2tex_report.get("template_spec") or "")
    if not spec_path.exists() or (not enabled and not figure_placement_probe and not table_placement_probe and not float_spacing_probe and not table_geometry_probe and not body_style_probe and not furniture_geometry_probe and not first_page_furniture_probe and not source_font_probe and not heading_color_probe and not reference_layout_probe and not text_box_placement_probe and not appendix_boundary_probe and not backmatter_boundary_probe):
        return variants
    try:
        base_spec = read_json(spec_path)
    except Exception:
        return variants

    variant_root = case_root / "temp2tex" / "latex-variants"
    word_inputs = case_root / "inputs" / "word"
    word_source = next((item for item in word_inputs.glob("*") if item.suffix.lower() in {".docx", ".docm", ".dotx", ".dotm"}), None) if word_inputs.exists() else None
    seen = {json.dumps(base_spec, sort_keys=True, ensure_ascii=False)}

    def add_variant(label: str, updates: dict[str, object]) -> None:
        spec = json.loads(json.dumps(base_spec, ensure_ascii=False))
        for key, value in updates.items():
            set_nested(spec, key, value)
        signature = json.dumps(spec, sort_keys=True, ensure_ascii=False)
        if signature in seen:
            return
        seen.add(signature)
        report = generate_variant_package(spec, spec_path, variant_root / safe_name(label), word_source)
        report["label"] = label
        if report.get("ok"):
            report["main_tex"] = str(Path(report["package_dir"]) / "main.tex")
        variants.append(report)

    document = base_spec.get("document", {})
    page = base_spec.get("page", {})
    figure_layout = base_spec.get("figures", {}).get("layout_evidence", {})
    table_layout = base_spec.get("tables", {}).get("layout_evidence", {})
    paper = str(document.get("paper", "a4paper")).lower()
    columns = str(document.get("columns", "single")).lower()
    try:
        font_size = float(document.get("font_size_pt") or (10 if columns == "double" else 12))
    except (TypeError, ValueError):
        font_size = float(10 if columns == "double" else 12)
    margins = page.get("margins_mm") or {}

    # Keep the explicit font probe to exactly two candidates: the normal
    # package and the source-font package. Do this before broad layout
    # variants are constructed.
    if source_font_probe and not enabled:
        source_font = str(document.get("font_family") or "").strip()
        source_font_mode = str(document.get("font_family_mode") or "default").lower()
        if source_font and source_font_mode not in {"verified", "render_verified"}:
            add_variant("source-font-metrics", {
                "document.font_family_mode": "render_verified",
            })
        return variants

    # Heading RGB values can be template-instruction decoration rather than a
    # rule that survives a normalized manuscript body. Probe all concrete
    # heading colours together and retain them only when PDF comparison wins.
    if heading_color_probe and not enabled:
        updates = {}
        headings = ((base_spec.get("body") or {}).get("heading_styles") or {})
        for level in range(5):
            entry = headings.get(f"level{level}") if isinstance(headings, dict) else None
            effective = (entry.get("effective_format") or entry.get("direct_format") or {}) if isinstance(entry, dict) else {}
            color = str((effective.get("font") or {}).get("color") or "").strip()
            if re.fullmatch(r"[0-9A-Fa-f]{6}", color) and color.upper() not in {"000000", "FFFFFF"}:
                updates[f"body.heading_styles.level{level}.color_mode"] = "render_verified"
        if updates:
            add_variant("source-heading-colors", updates)
        return variants

    # Reference list insets are sensitive to bibliography label widths and
    # can shift late pages. Keep Word geometry as evidence in ordinary output,
    # then test it as a bounded same-content candidate.
    if reference_layout_probe and not enabled:
        entry = ((base_spec.get("references") or {}).get("entry_style") or {})
        effective = (entry.get("effective_format") or entry.get("direct_format") or {}) if isinstance(entry, dict) else {}
        paragraph = effective.get("paragraph") or {}
        if any(paragraph.get(key) is not None for key in ("left_indent_twips", "hanging_twips", "space_after_twips")):
            add_variant("source-reference-layout", {
                "references.entry_style.layout_mode": "render_verified",
            })
        return variants

    # Word's inline/anchored XML state is not enough to set the ordinary
    # package's float policy. During explicit regression, however, it is a
    # useful bounded probe: compare the conservative float base package with a
    # non-floating figure variant and retain the winner only as render evidence.
    float_spacing = page.get("float_spacing_evidence") if isinstance(page, dict) else None
    if (enabled or float_spacing_probe) and isinstance(float_spacing, dict) and float_spacing.get("status") == "source":
        try:
            resolved_float_spacing = float(float_spacing.get("resolved_pt"))
        except (TypeError, ValueError):
            resolved_float_spacing = -1
        if 0 <= resolved_float_spacing <= 72:
            add_variant("source-float-text-spacing-probe", {
                "page.float_spacing_calibration": {
                    "status": "render_probe",
                    "textfloatsep_pt": resolved_float_spacing,
                    "intextsep_pt": resolved_float_spacing,
                    "dbltextfloatsep_pt": resolved_float_spacing,
                    "source": "Word object-block/body-text boundary candidate; requires strict same-content PDF promotion",
                },
            })
    if (enabled or figure_placement_probe) and isinstance(figure_layout, dict) and str(figure_layout.get("drawing_type") or "").lower() == "inline":
        add_variant("inline-figure-placement-probe", {
            "figures.layout_evidence.placement_calibration": {
                "status": "render_probe",
                "mode": "nonfloating",
                "source": "Word inline drawing candidate; requires strict same-content PDF promotion",
            },
        })
    if (enabled or table_placement_probe) and isinstance(table_layout, dict) and table_layout:
        add_variant("inline-table-placement-probe", {
            "tables.layout_evidence.placement_calibration": {
                "status": "render_probe",
                "mode": "nonfloating",
                "source": "Word table flow candidate; requires strict same-content PDF promotion",
            },
        })
    text_boxes = (base_spec.get("assets") or {}).get("text_boxes", [])
    if text_box_placement_probe and isinstance(text_boxes, list) and any(
        isinstance(item, dict) and isinstance(item.get("geometry"), dict)
        and item.get("geometry", {}).get("width_emu")
        for item in text_boxes
    ):
        add_variant("text-box-placement-probe", {
            "assets.text_boxes_auto_apply": True,
        })
    if appendix_boundary_probe:
        add_variant("appendix-new-page-boundary-probe", {
            "appendices.layout_evidence.boundary_calibration": {
                "status": "render_probe",
                "mode": "new_page",
                "source": "Isolated same-content PDF diagnostic candidate; promote only when every pre-appendix anchor page is stable and only the appendix is shifted",
            },
        })
    if backmatter_boundary_probe:
        add_variant("backmatter-new-page-boundary-probe", {
            "statements.layout_evidence.boundary_calibration": {
                "status": "render_probe",
                "mode": "new_page",
                "source": "Isolated same-content PDF diagnostic candidate; promote only when ordinary output is shorter and only acknowledgements/data/references/appendix anchors shift together",
            },
        })
    if table_geometry_probe and isinstance(table_layout, dict) and table_layout.get("grid_column_widths_twips"):
        add_variant("table-grid-precise-width", {
            "tables.layout_evidence.geometry_mode": "precise",
        })
        add_variant("table-grid-full-width", {
            "tables.layout_evidence.geometry_mode": "full",
        })
    if body_style_probe and isinstance(base_spec.get("page", {}).get("source_body_style"), dict):
        body_role = base_spec["page"]["source_body_style"]
        candidate = body_role.get("visible_flow_override_candidate")
        if isinstance(candidate, dict) and candidate:
            add_variant("visible-body-exemplar-probe", {
                "document.render_calibration": {
                    "status": "render_probe",
                    "proposal_mode": "visible_body_style",
                    "body_style_mode": "visible_flow_exemplar",
                    "source": "Dominant visible Word flow-body formatting conflicts with the named generic body style; requires strict same-content PDF promotion",
                },
            })
        if body_role.get("evidence_status") != "table_cell_body_exemplar":
            paragraph_sources = []
            if isinstance(candidate, dict) and candidate:
                paragraph_sources.extend([
                    (candidate.get("direct_format") or {}).get("paragraph"),
                    (candidate.get("effective_format") or {}).get("paragraph"),
                ])
            paragraph_sources.extend([
                (body_role.get("direct_format") or {}).get("paragraph"),
                (body_role.get("effective_format") or {}).get("paragraph"),
            ])
            spacing_points = []
            for paragraph in paragraph_sources:
                if not isinstance(paragraph, dict):
                    continue
                for key in ("space_before_twips", "space_after_twips"):
                    try:
                        value = float(paragraph.get(key)) / 20
                    except (TypeError, ValueError):
                        continue
                    if 0 <= value <= 72:
                        spacing_points.append(value)
            resolved_parskip = max(spacing_points, default=0)
            if resolved_parskip >= 6:
                for scale in (0.5, 0.75, 1.0):
                    calibrated_parskip = round(resolved_parskip * scale, 3)
                    label_value = f"{calibrated_parskip:g}".replace(".", "p")
                    add_variant(f"body-paragraph-spacing-{label_value}pt-probe", {
                        "page.render_calibration": {
                            "status": "render_probe",
                            "body_parskip_pt": calibrated_parskip,
                            "word_boundary_pt": resolved_parskip,
                            "calibration_scale": scale,
                            "source": "Bounded TeX calibration of the Word body paragraph boundary max(space-before, space-after); requires strict same-content PDF promotion",
                        },
                    })
    header_distance = page.get("header_distance_mm")
    header_parts = ((page.get("header_footer_evidence") or {}).get("parts") or [])
    if furniture_geometry_probe and isinstance(header_distance, (int, float)) and any(
        isinstance(part, dict) and part.get("kind") == "header" and part.get("paragraphs")
        for part in header_parts
    ):
        add_variant("word-header-distance-probe", {
            "page.header_footer_geometry.status": "render_verified",
            "page.header_footer_geometry.header_distance_mm": header_distance,
            "page.header_footer_geometry.source": "diagnostic Word header distance candidate; select only when same-content comparison improves",
        })
    active_variants = ((page.get("header_footer_evidence") or {}).get("active_variants") or [])
    if first_page_furniture_probe and any(
        isinstance(item, dict) and item.get("variant") == "first" for item in active_variants
    ):
        add_variant("word-first-page-furniture-probe", {
            "page.first_page_furniture_auto_apply": True,
        })
    if figure_placement_probe or table_placement_probe or float_spacing_probe or table_geometry_probe or body_style_probe or furniture_geometry_probe or first_page_furniture_probe or text_box_placement_probe or appendix_boundary_probe or backmatter_boundary_probe:
        return variants

    add_variant("paper-a4" if paper != "a4paper" else "paper-letter", {
        "document.paper": "a4paper" if paper != "a4paper" else "letterpaper",
    })
    if columns == "double":
        add_variant("single-column-density-guard", {
            "document.columns": "single",
            "document.font_size_pt": max(font_size, 11),
            "page.line_spacing": 1.15,
            "page.column_sep_mm": None,
        })
    else:
        add_variant("double-column-compact", {
            "document.columns": "double",
            "document.font_size_pt": min(font_size, 10),
            "page.line_spacing": 1.0,
            "page.column_sep_mm": 6,
        })
        add_variant("single-column-compact", {
            "document.font_size_pt": min(font_size, 10),
            "page.line_spacing": 1.0,
        })
        add_variant("single-column-compact-11pt", {
            "document.font_size_pt": min(max(font_size, 11), 11),
            "page.line_spacing": 1.0,
        })
        add_variant("plain-page-style", {
            "page.header_footer_profile": "plain",
        })
        add_variant("single-column-compact-plain", {
            "document.font_size_pt": min(font_size, 10),
            "page.line_spacing": 1.0,
            "page.header_footer_profile": "plain",
        })
        add_variant("dotted-section-labels", {
            "body.section_label_suffix": ".",
        })
        add_variant("dotted-compact-headings", {
            "body.section_label_suffix": ".",
            "body.heading_profile": "journal-compact",
            "document.font_size_pt": min(font_size, 10),
            "page.line_spacing": 1.0,
        })
        add_variant("dotted-compact-plain", {
            "body.section_label_suffix": ".",
            "body.heading_profile": "journal-compact",
            "document.font_size_pt": min(font_size, 10),
            "page.line_spacing": 1.0,
            "page.header_footer_profile": "plain",
        })
        add_variant("dotted-compact-plain-11pt", {
            "body.section_label_suffix": ".",
            "body.heading_profile": "journal-compact",
            "document.font_size_pt": min(max(font_size, 11), 11),
            "page.line_spacing": 1.0,
            "page.header_footer_profile": "plain",
        })
        add_variant("dotted-compact-empty", {
            "body.section_label_suffix": ".",
            "body.heading_profile": "journal-compact",
            "document.font_size_pt": min(font_size, 10),
            "page.line_spacing": 1.0,
            "page.header_footer_profile": "empty",
        })

    body_paragraph = ((page.get("source_body_style") or {}).get("effective_format") or {}).get("paragraph") or {}

    # Word text-only page furniture has a deterministic mapping to fancyhdr:
    # paragraph alignment and tabs define the slots, and PAGE fields become
    # \thepage. Probe it during regression only when there are no drawings,
    # embedded assets, or first-page variants that would need a separate
    # LaTeX page style. Ordinary package generation keeps this evidence
    # editable and pending until a rendered comparison selects it.
    furniture = page.get("header_footer_evidence") or {}
    parts = furniture.get("parts") if isinstance(furniture, dict) else []
    active = furniture.get("active_variants") if isinstance(furniture, dict) else []
    if isinstance(parts, list) and isinstance(active, list) and parts and active:
        referenced_parts = {item.get("part") for item in active if isinstance(item, dict)}
        active_parts = [item for item in parts if isinstance(item, dict) and item.get("part") in referenced_parts]
        has_visible_tokens = any(
            paragraph.get("tokens")
            for part in active_parts
            for paragraph in (part.get("paragraphs") or [])
            if isinstance(paragraph, dict)
        )
        simple_text_furniture = (
            has_visible_tokens
            and not any(part.get("drawings") or part.get("embedded_relationship_ids") for part in active_parts)
            and not any(item.get("variant") == "first" for item in active if isinstance(item, dict))
        )
        if simple_text_furniture:
            add_variant("source-text-header-footer", {
                "page.header_footer_auto_apply": True,
            })

    # Word font names are retained as evidence but remain disabled for normal
    # delivery until a same-content render verifies their metrics. Regression
    # can safely probe the installed-font path: the generated class falls back
    # to the conservative font stack when the source font is unavailable.
    source_font = str(document.get("font_family") or "").strip()
    source_font_mode = str(document.get("font_family_mode") or "default").lower()
    if source_font and source_font_mode not in {"verified", "render_verified"}:
        add_variant("source-font-metrics", {
            "document.font_family_mode": "render_verified",
        })

    if str(body_paragraph.get("line_spacing_rule") or "").lower() == "exact":
        # Word fixed line spacing is a physical baseline rather than a direct
        # LaTeX linespread ratio. Probe a narrow calibration set only during
        # benchmark work; ordinary package generation retains source evidence
        # and a pending calibration gap instead of picking one automatically.
        calibration_pairs = [
            (max(8.0, font_size - 1.5), 1.0),
            (max(8.0, font_size - 1.0), 1.0),
            (max(8.0, font_size - 0.5), 1.0),
            (font_size, 1.0),
            (font_size, 1.15),
        ]
        for candidate_size, candidate_spacing in calibration_pairs:
            label_size = f"{candidate_size:g}".replace(".", "p")
            label_spacing = f"{candidate_spacing:g}".replace(".", "p")
            add_variant(f"exact-spacing-calibration-{label_size}pt-{label_spacing}", {
                "document.font_size_pt": candidate_size,
                "page.line_spacing": candidate_spacing,
            })
    elif str(body_paragraph.get("line_spacing_rule") or "").lower() == "atleast":
        try:
            baseline = int(body_paragraph.get("line_spacing")) / 20
        except (TypeError, ValueError):
            baseline = None
        if baseline is not None and font_size <= baseline <= 30:
            add_variant(f"atleast-baseline-{baseline:g}pt", {
                "page.line_spacing": 1.0,
                "document.render_calibration": {
                    "status": "render_verified",
                    "body_baseline_pt": baseline,
                    "source": "diagnostic Word atLeast baseline candidate; select only when same-content comparison improves",
                },
            })

    if not (page.get("source_body_style") or {}).get("effective_format"):
        # Empty Word templates often expose page geometry but no representative
        # manuscript paragraph. Probe a narrow density pair in benchmark work
        # rather than treating one publisher's compact fallback as a default.
        add_variant("styleless-dense-9p5", {
            "document.font_size_pt": 9.5,
            "page.line_spacing": 1.0,
            "body.section_label_suffix": ".",
            "body.heading_profile": "journal-compact",
        })
        add_variant("styleless-dense-9p5-tight", {
            "document.font_size_pt": 9.5,
            "page.line_spacing": 0.95,
            "body.section_label_suffix": ".",
            "body.heading_profile": "journal-compact",
        })
        add_variant("styleless-dense-9", {
            "document.font_size_pt": 9.0,
            "page.line_spacing": 1.0,
            "body.section_label_suffix": ".",
            "body.heading_profile": "journal-compact",
        })
        add_variant("styleless-dense-8p5", {
            "document.font_size_pt": 8.5,
            "page.line_spacing": 1.0,
            "body.section_label_suffix": ".",
            "body.heading_profile": "journal-compact",
        })

    try:
        horizontal = float(margins.get("left", 25)) + float(margins.get("right", 25))
        vertical = float(margins.get("top", 25)) + float(margins.get("bottom", 25))
    except Exception:
        horizontal = vertical = 0
    if horizontal > 80 or vertical > 85:
        add_variant("conservative-default-margins", {
            "page.margins_mm": {"top": 25, "right": 25, "bottom": 25, "left": 25},
        })
    if horizontal > 70:
        add_variant("wider-horizontal-margins", {
            "page.margins_mm": {
                "top": margins.get("top", 25),
                "right": 25,
                "bottom": margins.get("bottom", 25),
                "left": 25,
            },
        })

    return variants


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if text.strip():
            return text
    except Exception:
        pass
    candidates = tool_candidates("pdftotext")
    if candidates:
        try:
            proc = subprocess.run(
                [candidates[0], str(path), "-"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=45,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout
        except Exception:
            pass
    return ""


def normalize_search_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def required_zone_aliases(required: str) -> list[str]:
    aliases = {
        "temp2tex regression benchmark": [
            "Temp2TeX Regression Benchmark",
            "Template Fidelity Across Journal Formats",
        ],
        "keywords": ["Keywords", "Key words", "Index Terms"],
        "references": ["References", "Bibliography"],
        "appendix": ["Appendix", "Appendices"],
    }
    return aliases.get(required.lower(), [required])


def has_required_zone(text: str, required: str) -> bool:
    lowered = text.lower()
    normalized = normalize_search_text(text)
    for alias in required_zone_aliases(required):
        if alias.lower() in lowered:
            return True
        if normalize_search_text(alias) in normalized:
            return True
    return False


def validate_fixture_pdf(pdf: Path | None, required_zones: list[str]) -> dict:
    if not pdf or not pdf.exists():
        return {"valid": False, "pdf": str(pdf) if pdf else None, "missing_zones": list(required_zones), "text_chars": 0}
    text = extract_pdf_text(pdf)
    missing = [zone for zone in required_zones if not has_required_zone(text, zone)]
    return {
        "valid": bool(text.strip()) and not missing,
        "pdf": str(pdf),
        "missing_zones": missing,
        "text_chars": len(text),
    }


def first_page_size(pdf: Path | None) -> tuple[float, float] | None:
    if not pdf or not pdf.exists():
        return None
    try:
        import fitz  # type: ignore

        with fitz.open(str(pdf)) as document:
            if not document:
                return None
            return float(document[0].rect.width), float(document[0].rect.height)
    except Exception:
        return None


def pdf_page_count(pdf: Path | None) -> int | None:
    if not pdf or not pdf.exists():
        return None
    try:
        import fitz  # type: ignore

        with fitz.open(str(pdf)) as document:
            return len(document)
    except Exception:
        return None


def validate_reference_geometry(official_pdf: Path | None, word_pdf: Path | None, tolerance_pt: float) -> dict:
    official_size = first_page_size(official_pdf)
    word_size = first_page_size(word_pdf)
    official_pages = pdf_page_count(official_pdf)
    word_pages = pdf_page_count(word_pdf)
    if not official_size or not word_size or official_pages is None or word_pages is None:
        return {
            "available": False,
            "compatible": None,
            "official_first_page_pt": list(official_size) if official_size else None,
            "word_first_page_pt": list(word_size) if word_size else None,
            "official_page_count": official_pages,
            "word_page_count": word_pages,
            "tolerance_pt": tolerance_pt,
        }
    width_delta = official_size[0] - word_size[0]
    height_delta = official_size[1] - word_size[1]
    return {
        "available": True,
        "compatible": (
            abs(width_delta) <= tolerance_pt
            and abs(height_delta) <= tolerance_pt
            and official_pages == word_pages
        ),
        "official_first_page_pt": [round(value, 3) for value in official_size],
        "word_first_page_pt": [round(value, 3) for value in word_size],
        "width_delta_pt": round(width_delta, 3),
        "height_delta_pt": round(height_delta, 3),
        "official_page_count": official_pages,
        "word_page_count": word_pages,
        "same_page_count": official_pages == word_pages,
        "tolerance_pt": tolerance_pt,
    }


def evaluate_outputs(
    case: dict,
    manifest: dict,
    official_compile: dict,
    temp_compile: dict,
    compare_report: dict,
    comparison_mode: str = "official_latex",
) -> dict:
    required = manifest.get("acceptance", {}).get("required_text_zones", [])
    thresholds = manifest.get("acceptance", {})
    avg_limit = float(thresholds.get("visual_diff_average_max", 0.03))
    page_limit = float(thresholds.get("visual_diff_page_max", 0.08))
    size_tol = float(thresholds.get("page_size_tolerance_pt", 1.0))

    official_pdf = Path(official_compile.get("pdf") or "") if official_compile.get("success") is True and official_compile.get("pdf") else None
    temp_pdf = Path(temp_compile.get("pdf") or "") if temp_compile.get("success") is True and temp_compile.get("pdf") else None
    official_text = extract_pdf_text(official_pdf) if official_pdf and official_pdf.exists() else ""
    temp_text = extract_pdf_text(temp_pdf) if temp_pdf and temp_pdf.exists() else ""
    missing_official = [item for item in required if not has_required_zone(official_text, item)]
    missing_temp = [item for item in required if not has_required_zone(temp_text, item)]

    ref_pages = compare_report.get("reference_pages") or []
    gen_pages = compare_report.get("generated_pages") or []
    same_page_count = bool(ref_pages and gen_pages and len(ref_pages) == len(gen_pages))
    same_page_size = True
    if ref_pages and gen_pages:
        for ref, gen in zip(ref_pages, gen_pages):
            if abs(float(ref.get("width_pt") or 0) - float(gen.get("width_pt") or 0)) > size_tol:
                same_page_size = False
            if abs(float(ref.get("height_pt") or 0) - float(gen.get("height_pt") or 0)) > size_tol:
                same_page_size = False

    diff_scores = []
    for comparison in compare_report.get("comparisons", []):
        diff = comparison.get("diff", {})
        if diff.get("available"):
            diff_scores.append(float(diff.get("normalized_diff") or 0.0))
    average_diff = statistics.mean(diff_scores) if diff_scores else None
    max_diff = max(diff_scores) if diff_scores else None
    pixel_exact = bool(diff_scores) and all(score == 0 for score in diff_scores)
    visual_pass = bool(diff_scores) and average_diff is not None and max_diff is not None and average_diff <= avg_limit and max_diff <= page_limit
    layout_summary = (compare_report.get("layout_diagnostics") or {}).get("summary") or {}
    layout_penalty = layout_summary.get("layout_penalty")
    layout_causes = layout_summary.get("top_causes") or []
    hard_gate = all([
        bool(official_compile.get("success")),
        bool(temp_compile.get("success")),
        same_page_count,
        same_page_size,
        not missing_official,
        not missing_temp,
        bool(diff_scores),
    ])
    passed = hard_gate and visual_pass
    return {
        "case_id": case["case_id"],
        "comparison_mode": comparison_mode,
        "status": "passed" if passed else "failed",
        "hard_gate_passed": hard_gate,
        "visual_passed": visual_pass,
        "pixel_exact": pixel_exact,
        "same_page_count": same_page_count,
        "same_page_size": same_page_size,
        "missing_text_zones_official": missing_official,
        "missing_text_zones_temp2tex": missing_temp,
        "average_normalized_diff": average_diff,
        "max_normalized_diff": max_diff,
        "layout_penalty": layout_penalty,
        "layout_visual_causes": layout_causes,
        "layout_summary": layout_summary,
        "diff_page_count": len(diff_scores),
        "compare_issues": compare_report.get("issues", []),
    }


def grade_case(case: dict, comparable: bool, evaluation: dict, reports: dict) -> dict:
    source_page_ok = any(item.get("ok") for item in reports.get("source_page_reports") or [])
    direct_word_url = case.get("doc_template_url")
    direct_word_ok = any(
        item.get("ok")
        and item.get("classification") == "word"
        and item.get("url") == direct_word_url
        for item in reports.get("download_reports") or []
    )
    local_word_provenance = bool(
        reports.get("word_source")
        and direct_word_url
        and case.get("source_page_urls")
    )
    source_provenance_ok = source_page_ok or direct_word_ok or local_word_provenance
    comparison_mode = reports.get("comparison_mode") or evaluation.get("comparison_mode") or "official_latex"
    if comparison_mode == "word_render_fallback":
        expectations = [
            ("Official source provenance is captured", source_provenance_ok),
            ("Official DOC/DOCX source is present", bool(reports.get("word_source"))),
            ("Official LaTeX is unavailable for comparison; Word-render fallback selected", True),
            ("Normalized official Word reference renders to PDF", bool(reports.get("word_reference_render", {}).get("success"))),
            ("Temp2TeX-generated template PDF compiles", bool(reports.get("temp_compile", {}).get("success"))),
            ("PDF comparison report and diff previews are produced", bool(evaluation.get("diff_page_count"))),
            ("Hard gates pass: compile, page count, page size, required zones", bool(evaluation.get("hard_gate_passed"))),
            ("Layered visual diff thresholds pass", bool(evaluation.get("visual_passed"))),
            ("Case is comparable and does not require replacement", comparable and evaluation.get("status") != "not_comparable"),
        ]
    else:
        expectations = [
            ("Official source provenance is captured", source_provenance_ok),
            ("Official DOC/DOCX source is present", bool(reports.get("word_source"))),
            ("Official LaTeX source is present", bool(reports.get("official_main_tex"))),
            ("Official LaTeX normalized PDF compiles", bool(reports.get("official_compile", {}).get("success"))),
            ("Temp2TeX-generated normalized PDF compiles", bool(reports.get("temp_compile", {}).get("success"))),
            ("PDF comparison report and diff previews are produced", bool(evaluation.get("diff_page_count"))),
            ("Hard gates pass: compile, page count, page size, required zones", bool(evaluation.get("hard_gate_passed"))),
            ("Layered visual diff thresholds pass", bool(evaluation.get("visual_passed"))),
            ("Case is comparable and does not require replacement", comparable and evaluation.get("status") != "not_comparable"),
        ]
    graded = []
    for text, passed in expectations:
        graded.append({
            "text": text,
            "passed": bool(passed),
            "evidence": evidence_for(text, passed, evaluation, reports),
        })
    passed_count = sum(1 for item in graded if item["passed"])
    return {
        "expectations": graded,
        "summary": {
            "passed": passed_count,
            "failed": len(graded) - passed_count,
            "total": len(graded),
            "pass_rate": round(passed_count / len(graded), 4) if graded else 0,
        },
        "claims": [
            {
                "claim": "The regression comparison mode is explicit.",
                "type": "process",
                "verified": comparison_mode in {"official_latex", "word_render_fallback"},
                "evidence": comparison_mode,
            }
        ],
        "user_notes_summary": {
            "uncertainties": reports.get("uncertainties", []),
            "needs_review": reports.get("needs_review", []),
            "workarounds": reports.get("workarounds", []),
        },
    }


def evidence_for(text: str, passed: bool, evaluation: dict, reports: dict) -> str:
    if "source provenance" in text:
        reports_list = reports.get("source_page_reports") or []
        ok_count = sum(1 for item in reports_list if item.get("ok"))
        case = reports.get("case") or {}
        direct_url = case.get("doc_template_url")
        direct_ok = any(
            item.get("ok")
            and item.get("classification") == "word"
            and item.get("url") == direct_url
            for item in reports.get("download_reports") or []
        )
        local_ok = bool(
            reports.get("word_source")
            and direct_url
            and case.get("source_page_urls")
        )
        return (
            f"{ok_count}/{len(reports_list)} source page fetch report(s) succeeded; "
            f"direct official Word artifact verified: {direct_ok}; "
            f"offline local official Word provenance recorded: {local_ok}."
        )
    if "source page" in text:
        reports_list = reports.get("source_page_reports") or []
        ok_count = sum(1 for item in reports_list if item.get("ok"))
        return f"{ok_count}/{len(reports_list)} source page fetch report(s) succeeded."
    if "DOC/DOCX" in text:
        return str(reports.get("word_source") or "No Word source selected.")
    if "LaTeX source" in text:
        return str(reports.get("official_main_tex") or "No official main .tex file selected.")
    if "LaTeX is unavailable for comparison" in text:
        source = reports.get("official_main_tex")
        if source:
            return f"Official source found at {source}, but its normalized compile did not produce a PDF."
        return "No official main .tex file was found."
    if "Official LaTeX normalized" in text:
        return json.dumps({"success": reports.get("official_compile", {}).get("success"), "pdf": reports.get("official_compile", {}).get("pdf")}, ensure_ascii=False)
    if "Normalized official Word reference renders" in text:
        return json.dumps({"success": reports.get("word_reference_render", {}).get("success"), "pdf": reports.get("word_reference_render", {}).get("pdf")}, ensure_ascii=False)
    if "Temp2TeX-generated" in text:
        return json.dumps({"success": reports.get("temp_compile", {}).get("success"), "pdf": reports.get("temp_compile", {}).get("pdf")}, ensure_ascii=False)
    if "diff previews" in text:
        return f"{evaluation.get('diff_page_count', 0)} page diff(s) generated."
    if "Hard gates" in text:
        return json.dumps({
            "same_page_count": evaluation.get("same_page_count"),
            "same_page_size": evaluation.get("same_page_size"),
            "missing_official": evaluation.get("missing_text_zones_official"),
            "missing_temp2tex": evaluation.get("missing_text_zones_temp2tex"),
        }, ensure_ascii=False)
    if "visual diff" in text:
        return json.dumps({
            "average": evaluation.get("average_normalized_diff"),
            "max": evaluation.get("max_normalized_diff"),
            "pixel_exact": evaluation.get("pixel_exact"),
        }, ensure_ascii=False)
    if "comparable" in text:
        return evaluation.get("status", "unknown")
    return "Passed." if passed else "Failed."


def write_metrics(outputs_dir: Path, reports: dict, start_time: float) -> None:
    files = [str(path.relative_to(outputs_dir)) for path in outputs_dir.rglob("*") if path.is_file()]
    write_json(outputs_dir / "metrics.json", {
        "tool_calls": {"script": len(reports.get("commands", []))},
        "total_tool_calls": len(reports.get("commands", [])),
        "total_steps": 7,
        "files_created": files,
        "errors_encountered": len(reports.get("needs_review", [])),
        "output_chars": sum(path.stat().st_size for path in outputs_dir.rglob("*") if path.is_file()),
        "transcript_chars": 0,
        "duration_seconds": round(time.time() - start_time, 3),
    })


def copy_outputs_for_review(case_root: Path, outputs_dir: Path) -> None:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    for src in [
        case_root / "case_report.json",
        case_root / "source_manifest.json",
        case_root / "evaluation.json",
        case_root / "discovered_links.json",
        case_root / "temp2tex" / "source_inventory.json",
        case_root / "temp2tex" / "template_spec.json",
    ]:
        if src.exists():
            shutil.copy2(src, outputs_dir / src.name)
    for pdf_name, src in [
        ("official_normalized.pdf", case_root / "official_normalized" / "temp2tex_regression_main.pdf"),
        ("temp2tex_normalized.pdf", case_root / "temp2tex_normalized" / "temp2tex_regression_main.pdf"),
    ]:
        if src.exists():
            shutil.copy2(src, outputs_dir / pdf_name)
    case_report_path = case_root / "case_report.json"
    if case_report_path.exists():
        try:
            word_pdf = Path(read_json(case_report_path).get("word_reference_render", {}).get("pdf") or "")
            if word_pdf.exists():
                shutil.copy2(word_pdf, outputs_dir / "word_normalized.pdf")
        except Exception:
            pass
    for comparison_name in ["official-vs-temp2tex", "word-vs-temp2tex"]:
        comparison_root = case_root / comparison_name
        for artifact_name in ["diff_previews", "layout_profile"]:
            source = comparison_root / artifact_name
            if not source.exists():
                continue
            target = outputs_dir / artifact_name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)


def page_count_delta(compare_report: dict) -> int:
    ref_pages = compare_report.get("reference_pages") or []
    gen_pages = compare_report.get("generated_pages") or []
    if not ref_pages or not gen_pages:
        return 999
    return abs(len(ref_pages) - len(gen_pages))


def variant_score(result: dict) -> tuple:
    evaluation = result.get("evaluation") or {}
    compare_report = result.get("comparison") or {}
    missing_count = len(evaluation.get("missing_text_zones_official") or []) + len(evaluation.get("missing_text_zones_temp2tex") or [])
    avg = evaluation.get("average_normalized_diff")
    max_diff = evaluation.get("max_normalized_diff")
    layout_penalty = evaluation.get("layout_penalty")
    return (
        1 if evaluation.get("status") == "passed" else 0,
        1 if evaluation.get("hard_gate_passed") else 0,
        1 if evaluation.get("same_page_count") else 0,
        1 if evaluation.get("same_page_size") else 0,
        -missing_count,
        -page_count_delta(compare_report),
        -(float(layout_penalty) if layout_penalty is not None else 999.0),
        -(float(avg) if avg is not None else 999.0),
        -(float(max_diff) if max_diff is not None else 999.0),
        1 if result.get("label") == "base" else 0,
    )


def copy_selected_tree(src: Path, dest: Path) -> None:
    if not src.exists() or src.resolve() == dest.resolve():
        return
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


def evaluate_temp2tex_variants(
    case: dict,
    manifest: dict,
    case_root: Path,
    official_compile: dict,
    variants: list[dict],
    generated_compile_engine: str | None,
    comparison_mode: str = "official_latex",
    comparison_dir_name: str = "official-vs-temp2tex",
) -> dict:
    official_pdf = Path(official_compile.get("pdf") or "") if official_compile.get("success") is True and official_compile.get("pdf") else None
    results = []
    if not official_pdf or not official_pdf.exists():
        return {"results": results, "selected": None}

    for variant in variants:
        label = safe_name(str(variant.get("label") or "variant"))
        package_dir = Path(variant.get("package_dir") or "")
        if not package_dir.exists() or not (package_dir / "main.tex").exists():
            results.append({"label": label, "ok": False, "error": "variant package missing"})
            continue
        norm_dir = case_root / "temp2tex_normalized_variants" / label
        compare_dir = case_root / f"{comparison_dir_name}-variants" / label
        temp_norm_main, temp_norm = make_normalized_project(package_dir, package_dir / "main.tex", norm_dir)
        temp_compile = {"success": False}
        compare_report = {"issues": ["comparison was not attempted"], "comparisons": []}
        evaluation = {"case_id": case["case_id"], "status": "not_comparable", "hard_gate_passed": False, "visual_passed": False, "diff_page_count": 0}
        if temp_norm_main:
            temp_compile = compile_latex(
                temp_norm_main,
                temp_norm_main.parent / "compile_report.json",
                engine=generated_compile_engine,
            )
        temp_pdf = Path(temp_compile.get("pdf") or "") if temp_compile.get("success") is True and temp_compile.get("pdf") else None
        if temp_pdf and temp_pdf.exists():
            compare_report = compare_pdfs(official_pdf, temp_pdf, compare_dir)
            evaluation = evaluate_outputs(
                case,
                manifest,
                official_compile,
                temp_compile,
                compare_report,
                comparison_mode=comparison_mode,
            )
        results.append({
            "label": label,
            "ok": bool(temp_compile.get("success")),
            "package_dir": str(package_dir),
            "normalization": temp_norm,
            "normalized_dir": str(norm_dir),
            "compile": temp_compile,
            "comparison": compare_report,
            "evaluation": evaluation,
            "score": list(variant_score({"label": label, "comparison": compare_report, "evaluation": evaluation})),
        })

    selected = None
    if results:
        selected = sorted(results, key=lambda item: tuple(item.get("score") or [-999]), reverse=True)[0]
        norm_dir = Path(selected.get("normalized_dir") or "")
        compare_dir = case_root / f"{comparison_dir_name}-variants" / safe_name(str(selected.get("label") or "variant"))
        copy_selected_tree(norm_dir, case_root / "temp2tex_normalized")
        copy_selected_tree(compare_dir, case_root / comparison_dir_name)
    return {"results": results, "selected": selected}


def run_case(
    case: dict,
    manifest: dict,
    outdir: Path,
    skip_network: bool,
    variant_search: bool = False,
    figure_placement_probe: bool = False,
    table_placement_probe: bool = False,
    float_spacing_probe: bool = False,
    table_geometry_probe: bool = False,
    body_style_probe: bool = False,
    furniture_geometry_probe: bool = False,
    first_page_furniture_probe: bool = False,
    source_font_probe: bool = False,
    heading_color_probe: bool = False,
    reference_layout_probe: bool = False,
    text_box_placement_probe: bool = False,
    appendix_boundary_probe: bool = False,
    backmatter_boundary_probe: bool = False,
) -> dict:
    start = time.time()
    case_root = outdir / case["case_id"]
    run_dir = case_root / "with_skill"
    outputs_dir = run_dir / "outputs"
    source_pages = case_root / "source_pages"
    downloads = case_root / "downloads"
    inputs = case_root / "inputs"
    official_latex_root = case_root / "official_latex_source"
    source_pages.mkdir(parents=True, exist_ok=True)
    downloads.mkdir(parents=True, exist_ok=True)
    inputs.mkdir(parents=True, exist_ok=True)

    eval_prompt = (
        f"Use $temp2tex to convert the official Word/DOCX template for {case['journal_or_template_system']} "
        "into LaTeX, normalize it with the fixed regression manuscript, compile it, and compare it against "
        "the official LaTeX template compiled with the same regression manuscript."
    )
    write_json(case_root / "eval_metadata.json", {
        "eval_id": case["case_id"],
        "eval_name": case["case_id"],
        "prompt": eval_prompt,
        "assertions": manifest.get("acceptance", {}).get("required_text_zones", []),
    })

    source_page_reports, discovered = capture_source_pages(case, source_pages, skip_network)
    discovered = add_explicit_links(case, discovered)
    write_json(case_root / "discovered_links.json", discovered)
    download_reports = download_artifacts(discovered, downloads, skip_network)
    cached_latex_reports = (
        restore_cached_latex_artifacts(case, outdir, downloads)
        if skip_network else cache_latex_artifacts(case, outdir, downloads)
    )
    local_word_reports = copy_local_word_inputs(case, inputs)
    for report in download_reports:
        if report.get("ok") and report.get("classification") == "word" and report.get("local_path"):
            src = Path(report["local_path"])
            target = inputs / "word" / src.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
    downloaded_word_reports = collect_downloaded_word_sources(downloads, inputs)

    extraction_reports, official_main_tex = prepare_official_latex_sources(
        downloads,
        official_latex_root,
        preferred_patterns=case.get("preferred_latex_main_patterns"),
    )
    word_source = choose_word_source(inputs, preferred_patterns=case.get("preferred_word_patterns"))
    temp2tex_report = build_temp2tex_package(case_root, word_source) if word_source else {"ok": False, "error": "missing Word source"}

    reports: dict = {
        "case": case,
        "generated_at": utc_now(),
        "source_page_reports": source_page_reports,
        "download_reports": download_reports,
        "cached_latex_reports": cached_latex_reports,
        "local_word_reports": local_word_reports,
        "downloaded_word_reports": downloaded_word_reports,
        "extraction_reports": extraction_reports,
        "word_source": str(word_source) if word_source else None,
        "official_main_tex": str(official_main_tex) if official_main_tex else None,
        "temp2tex": temp2tex_report,
        "commands": [],
        "uncertainties": [],
        "needs_review": [],
        "workarounds": [],
    }

    official_compile: dict = {"success": False}
    temp_compile: dict = {"success": False}
    word_reference_render: dict | None = None
    word_reference_pdf: Path | None = None
    word_fixture_validation: dict | None = None
    compare_report: dict = {"issues": ["comparison was not attempted"], "comparisons": []}
    evaluation: dict = {"case_id": case["case_id"], "status": "not_comparable", "hard_gate_passed": False, "visual_passed": False, "diff_page_count": 0}
    if official_main_tex:
        comparison_mode = "official_latex"
    elif word_source:
        comparison_mode = "word_render_fallback"
    else:
        comparison_mode = "missing_reference_source"
    reports["comparison_mode"] = comparison_mode
    comparable = bool(word_source and temp2tex_report.get("ok") and comparison_mode in {"official_latex", "word_render_fallback"})

    if not word_source:
        reports["needs_review"].append("No official Word/DOCX source was downloaded or configured.")
    if not official_main_tex:
        reports["needs_review"].append("No official LaTeX main .tex source was found; using Word-rendered PDF comparison fallback when possible.")
    if not temp2tex_report.get("ok"):
        reports["needs_review"].append("Temp2TeX package generation did not produce a main.tex.")

    if comparable and official_main_tex:
        official_norm_main, official_norm = make_normalized_project(
            official_latex_root,
            official_main_tex,
            case_root / "official_normalized",
            adapter=case.get("official_latex_adapter"),
        )
        reports["official_normalization"] = official_norm
        if official_norm_main:
            configured_engine = case.get("compile_engine")
            inferred_engine = infer_official_compile_engine(official_norm_main)
            official_compile = compile_latex(
                official_norm_main,
                official_norm_main.parent / "compile_report.json",
                engine=configured_engine or inferred_engine,
            )
            # Preserve an explicit manifest choice first, but retry a clearly
            # PDFTeX-only official package when that choice fails. Old corpus
            # manifests can carry an engine selected before the publisher
            # updated its class/style implementation.
            if (
                not official_compile.get("success")
                and configured_engine
                and configured_engine != inferred_engine
            ):
                retry = compile_latex(
                    official_norm_main,
                    official_norm_main.parent / "compile_report_engine_retry.json",
                    engine=inferred_engine,
                )
                reports["official_compile_engine_retry"] = {
                    "configured_engine": configured_engine,
                    "inferred_engine": inferred_engine,
                    "report": retry,
                }
                if retry.get("success"):
                    official_compile = retry
        reports["official_compile"] = official_compile
        official_pdf = Path(official_compile.get("pdf") or "") if official_compile.get("success") is True and official_compile.get("pdf") else None
        required_zones = list(manifest.get("acceptance", {}).get("required_text_zones", []))
        official_fixture_validation = validate_fixture_pdf(official_pdf, required_zones)
        reports["official_fixture_validation"] = official_fixture_validation
        if official_pdf and not official_fixture_validation["valid"]:
            reports["needs_review"].append(
                "Official LaTeX PDF does not contain the complete normalized regression fixture; "
                "using the normalized Word-render fallback instead of comparing different manuscripts."
            )
            official_pdf = None
        if official_pdf and word_source:
            word_reference_render = render_normalized_word_reference(word_source, case_root / "word_reference_render")
            reports["word_reference_render"] = word_reference_render
            word_reference_pdf = Path(word_reference_render.get("pdf") or "") if word_reference_render.get("pdf") else None
            word_fixture_validation = validate_fixture_pdf(word_reference_pdf, required_zones)
            reports["word_fixture_validation"] = word_fixture_validation
            if word_fixture_validation["valid"]:
                geometry_validation = validate_reference_geometry(
                    official_pdf,
                    word_reference_pdf,
                    float(manifest.get("acceptance", {}).get("page_size_tolerance_pt", 1.0)),
                )
                reports["official_word_compatibility_validation"] = geometry_validation
                if geometry_validation.get("compatible") is False:
                    reports["needs_review"].append(
                        "Official LaTeX and normalized Word references use different page geometry or pagination; "
                        "using the Word render because Temp2TeX reconstructs the Word template."
                    )
                    official_pdf = None

        if official_pdf and official_pdf.exists():
            variants = build_temp2tex_variants(
                case_root, temp2tex_report, enabled=variant_search,
                figure_placement_probe=figure_placement_probe,
                table_placement_probe=table_placement_probe,
                float_spacing_probe=float_spacing_probe,
                table_geometry_probe=table_geometry_probe,
                body_style_probe=body_style_probe,
                furniture_geometry_probe=furniture_geometry_probe,
                first_page_furniture_probe=first_page_furniture_probe,
                source_font_probe=source_font_probe,
                heading_color_probe=heading_color_probe,
                reference_layout_probe=reference_layout_probe,
                text_box_placement_probe=text_box_placement_probe,
                appendix_boundary_probe=appendix_boundary_probe,
                backmatter_boundary_probe=backmatter_boundary_probe,
            )
            reports["temp_variants"] = variants
            variant_eval = evaluate_temp2tex_variants(
                case,
                manifest,
                case_root,
                official_compile,
                variants,
                generated_compile_engine=case.get("generated_compile_engine"),
            )
            reports["temp_variant_evaluation"] = variant_eval
            selected_variant = variant_eval.get("selected")
            if selected_variant:
                temp_compile = selected_variant.get("compile", {"success": False})
                compare_report = selected_variant.get("comparison", compare_report)
                evaluation = selected_variant.get("evaluation", evaluation)
                reports["temp_normalization"] = selected_variant.get("normalization")
                reports["selected_temp_variant"] = {
                    "label": selected_variant.get("label"),
                    "package_dir": selected_variant.get("package_dir"),
                    "score": selected_variant.get("score"),
                }
            reports["temp_compile"] = temp_compile
        else:
            temp_package_dir = Path(temp2tex_report["package_dir"])
            temp_norm_main, temp_norm = make_normalized_project(
                temp_package_dir,
                temp_package_dir / "main.tex",
                case_root / "temp2tex_normalized",
            )
            reports["temp_normalization"] = temp_norm
            if temp_norm_main:
                temp_compile = compile_latex(
                    temp_norm_main,
                    temp_norm_main.parent / "compile_report.json",
                    engine=case.get("generated_compile_engine"),
                )
            reports["temp_compile"] = temp_compile

        temp_pdf = Path(temp_compile.get("pdf") or "") if temp_compile.get("success") is True and temp_compile.get("pdf") else None
        if not (official_pdf and temp_pdf and official_pdf.exists() and temp_pdf.exists()):
            reports["needs_review"].append(
                "Official-LaTeX comparison could not produce both PDFs; attempting the normalized Word-render fallback."
            )
            comparable = False
            evaluation["status"] = "not_comparable"
    # A normalized Word render is the reference for Word-only cases and for an
    # official LaTeX package that cannot produce both comparison PDFs. Do not
    # use it to mask a completed official-LaTeX comparison that failed its gates.
    if word_source and temp2tex_report.get("ok") and (
        comparison_mode == "word_render_fallback" or not comparable
    ):
        comparison_mode = "word_render_fallback"
        reports["comparison_mode"] = comparison_mode
        if official_main_tex:
            reports["workarounds"].append(
                "Official LaTeX source was found but could not produce a comparable PDF; "
                "used normalized official Word render as the reference instead."
            )
        if word_reference_render is None:
            word_reference_render = render_normalized_word_reference(word_source, case_root / "word_reference_render")
        reports["word_reference_render"] = word_reference_render
        if word_reference_pdf is None:
            word_reference_pdf = Path(word_reference_render.get("pdf") or "") if word_reference_render.get("pdf") else None
        required_zones = list(manifest.get("acceptance", {}).get("required_text_zones", []))
        if word_fixture_validation is None:
            word_fixture_validation = validate_fixture_pdf(word_reference_pdf, required_zones)
        reports["word_fixture_validation"] = word_fixture_validation
        if word_reference_pdf and not word_fixture_validation["valid"]:
            reports["needs_review"].append(
                "Normalized Word reference does not contain the complete regression fixture; case remains not_comparable."
            )
            word_reference_pdf = None

        if word_reference_pdf and word_reference_pdf.exists():
            reference_compile = {
                "success": True,
                "pdf": str(word_reference_pdf),
                "renderer": "word_reference_render",
                "comparison_mode": comparison_mode,
            }
            variants = build_temp2tex_variants(
                case_root, temp2tex_report, enabled=variant_search,
                figure_placement_probe=figure_placement_probe,
                table_placement_probe=table_placement_probe,
                float_spacing_probe=float_spacing_probe,
                table_geometry_probe=table_geometry_probe,
                body_style_probe=body_style_probe,
                furniture_geometry_probe=furniture_geometry_probe,
                first_page_furniture_probe=first_page_furniture_probe,
                source_font_probe=source_font_probe,
                heading_color_probe=heading_color_probe,
                reference_layout_probe=reference_layout_probe,
                text_box_placement_probe=text_box_placement_probe,
                appendix_boundary_probe=appendix_boundary_probe,
                backmatter_boundary_probe=backmatter_boundary_probe,
            )
            reports["temp_variants"] = variants
            variant_eval = evaluate_temp2tex_variants(
                case,
                manifest,
                case_root,
                reference_compile,
                variants,
                generated_compile_engine=case.get("generated_compile_engine"),
                comparison_mode=comparison_mode,
                comparison_dir_name="word-vs-temp2tex",
            )
            reports["temp_variant_evaluation"] = variant_eval
            selected_variant = variant_eval.get("selected")
            if selected_variant:
                temp_compile = selected_variant.get("compile", {"success": False})
                compare_report = selected_variant.get("comparison", compare_report)
                evaluation = selected_variant.get("evaluation", evaluation)
                reports["temp_normalization"] = selected_variant.get("normalization")
                reports["selected_temp_variant"] = {
                    "label": selected_variant.get("label"),
                    "package_dir": selected_variant.get("package_dir"),
                    "score": selected_variant.get("score"),
                }
            reports["temp_compile"] = temp_compile
            reports["word_reference_compile"] = reference_compile
            comparable = evaluation.get("status") != "not_comparable"
        else:
            reports["needs_review"].append("Word-render fallback could not produce both PDFs.")
            comparable = False
            evaluation["comparison_mode"] = comparison_mode
            evaluation["status"] = "not_comparable"
    reports.setdefault("official_compile", official_compile)
    reports.setdefault("temp_compile", temp_compile)
    reports["comparison"] = compare_report
    reports["evaluation"] = evaluation

    source_manifest = {
        "case_id": case["case_id"],
        "publisher": case.get("publisher"),
        "journal_or_template_system": case.get("journal_or_template_system"),
        "downloaded_at": utc_now(),
        "source_page_urls": case.get("source_page_urls", []),
        "doc_template_url": case.get("doc_template_url"),
        "latex_template_url": case.get("latex_template_url"),
        "word_source": reports.get("word_source"),
        "official_main_tex": reports.get("official_main_tex"),
        "files": [
            {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in sorted(case_root.rglob("*"))
            if path.is_file() and path.stat().st_size < 100 * 1024 * 1024
        ],
    }
    write_json(case_root / "source_manifest.json", source_manifest)
    write_json(case_root / "case_report.json", reports)
    write_json(case_root / "evaluation.json", evaluation)

    grading = grade_case(case, comparable, evaluation, reports)
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "grading.json", grading)
    copy_outputs_for_review(case_root, outputs_dir)
    write_metrics(outputs_dir, reports, start)
    write_json(run_dir / "timing.json", {
        "executor_duration_seconds": round(time.time() - start, 3),
        "total_duration_seconds": round(time.time() - start, 3),
    })
    return {
        "case_id": case["case_id"],
        "eval_name": case["case_id"],
        "status": evaluation.get("status"),
        "comparison_mode": evaluation.get("comparison_mode") or reports.get("comparison_mode"),
        "grading": grading,
        "evaluation": evaluation,
        "time_seconds": round(time.time() - start, 3),
        "errors": 0 if evaluation.get("status") == "passed" else 1,
    }


def build_benchmark(outdir: Path, results: list[dict]) -> dict:
    runs = []
    for idx, result in enumerate(results, 1):
        summary = result["grading"]["summary"]
        runs.append({
            "eval_id": idx,
            "eval_name": result["eval_name"],
            "configuration": "with_skill",
            "run_number": 1,
            "result": {
                "pass_rate": summary["pass_rate"],
                "passed": summary["passed"],
                "failed": summary["failed"],
                "total": summary["total"],
                "time_seconds": result["time_seconds"],
                "tokens": 0,
                "tool_calls": 0,
                "errors": result["errors"],
            },
            "expectations": result["grading"]["expectations"],
            "notes": [
                f"case status: {result['status']}",
                f"comparison mode: {result.get('comparison_mode')}",
                f"average visual diff: {result['evaluation'].get('average_normalized_diff')}",
                f"max visual diff: {result['evaluation'].get('max_normalized_diff')}",
                f"layout penalty: {result['evaluation'].get('layout_penalty')}",
                f"layout causes: {', '.join(result['evaluation'].get('layout_visual_causes') or [])}",
            ],
        })
    pass_rates = [run["result"]["pass_rate"] for run in runs]
    times = [run["result"]["time_seconds"] for run in runs]
    errors = sum(run["result"]["errors"] for run in runs)
    benchmark = {
        "metadata": {
            "skill_name": "temp2tex",
            "skill_path": str(SKILL_ROOT),
            "executor_model": "local-regression-runner",
            "analyzer_model": "programmatic",
            "timestamp": utc_now(),
            "evals_run": [r["eval_name"] for r in results],
            "runs_per_configuration": 1,
        },
        "runs": runs,
        "run_summary": {
            "with_skill": {
                "pass_rate": stat_summary(pass_rates),
                "time_seconds": stat_summary(times),
                "tokens": stat_summary([0 for _ in runs]),
            }
        },
        "notes": [
            f"{len(results)} case(s) run.",
            f"{errors} case(s) have failing expectations or require replacement.",
            "When official LaTeX exists, the benchmark compares normalized official LaTeX PDFs against normalized Temp2TeX PDFs.",
            "When official LaTeX is unavailable for comparison but Word exists, the benchmark compares a Word-rendered PDF against the generated Temp2TeX PDF.",
        ],
    }
    write_json(outdir / "benchmark.json", benchmark)
    lines = [
        "# Temp2TeX Regression Benchmark",
        "",
        f"- Cases run: {len(results)}",
        f"- Cases needing attention: {errors}",
        "",
        "| Case | Mode | Status | Pass rate | Avg diff | Max diff | Layout penalty | Layout causes |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in results:
        ev = result["evaluation"]
        lines.append(
            f"| {result['case_id']} | {result.get('comparison_mode')} | {result['status']} | {result['grading']['summary']['pass_rate']:.2f} | "
            f"{ev.get('average_normalized_diff')} | {ev.get('max_normalized_diff')} | "
            f"{ev.get('layout_penalty')} | {', '.join(ev.get('layout_visual_causes') or [])} |"
        )
    write_text(outdir / "benchmark.md", "\n".join(lines) + "\n")
    return benchmark


def completed_case_results(outdir: Path, manifest: dict, current_results: list[dict]) -> list[dict]:
    """Merge this command's results with prior reports in a split iteration.

    Full corpus runs can exceed a shell timeout. Each case writes durable
    reports before the outer process exits, so rebuilding the benchmark from
    those reports preserves one complete iteration across tail reruns.
    """
    merged = {str(result["case_id"]): result for result in current_results}
    for case in manifest.get("cases", []):
        case_id = str(case.get("case_id") or "")
        if not case_id or case_id in merged:
            continue
        case_root = outdir / case_id
        report_path = case_root / "case_report.json"
        evaluation_path = case_root / "evaluation.json"
        grading_path = case_root / "with_skill" / "grading.json"
        timing_path = case_root / "with_skill" / "timing.json"
        if not (report_path.exists() and evaluation_path.exists() and grading_path.exists()):
            continue
        try:
            report = read_json(report_path)
            evaluation = read_json(evaluation_path)
            grading = read_json(grading_path)
            timing = read_json(timing_path) if timing_path.exists() else {}
        except Exception:
            continue
        merged[case_id] = {
            "case_id": case_id,
            "eval_name": case_id,
            "status": evaluation.get("status"),
            "comparison_mode": evaluation.get("comparison_mode") or report.get("comparison_mode"),
            "grading": grading,
            "evaluation": evaluation,
            "time_seconds": float(timing.get("total_duration_seconds") or 0),
            "errors": 0 if evaluation.get("status") == "passed" else 1,
        }
    return [merged[case_id] for case_id in [str(case.get("case_id")) for case in manifest.get("cases", [])] if case_id in merged]


def stat_summary(values: list[float]) -> dict:
    if not values:
        return {"mean": 0, "stddev": 0, "min": 0, "max": 0}
    return {
        "mean": round(statistics.mean(values), 4),
        "stddev": round(statistics.pstdev(values), 4) if len(values) > 1 else 0,
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def generate_review(outdir: Path) -> dict:
    static_path = outdir / "review.html"
    benchmark_path = outdir / "benchmark.json"
    if not benchmark_path.exists():
        return {"ok": False, "error": f"benchmark not found: {benchmark_path}"}
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    if isinstance(benchmark, dict):
        rows = benchmark.get("runs") or benchmark.get("cases") or benchmark
    else:
        rows = benchmark
    if not isinstance(rows, list):
        rows = []
    cards = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or row.get("eval_name") or "unknown")
        case_dir = Path(case_id)
        result = row.get("result") or {}
        status = "passed" if result.get("failed", 0) == 0 else "needs review"
        evaluation = f"{result.get('passed', 0)}/{result.get('total', 0)} expectations"
        cards.append(
            "<article><h2>{}</h2><p>Status: <strong>{}</strong>; evaluation: {}</p>"
            "<p><a href=\"{}/evaluation.json\">evaluation.json</a> · "
            "<a href=\"{}/grading.json\">grading.json</a> · "
            "<a href=\"{}/official-vs-temp2tex/diff_previews/\">diff previews</a></p></article>".format(
                html.escape(case_id), html.escape(status), html.escape(evaluation),
                case_dir.as_posix(), case_dir.as_posix(), case_dir.as_posix()
            )
        )
    document = """<!doctype html>
<meta charset="utf-8">
<title>Temp2TeX regression review</title>
<style>body{{font:15px system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem}}article{{border:1px solid #ccc;padding:1rem;margin:1rem 0}}h1{{margin-bottom:.25rem}}a{{color:#0645ad}}</style>
<h1>Temp2TeX regression review</h1>
<p>Static case index generated by the bundled skill tooling.</p>
{}
""".format("\n".join(cards))
    static_path.write_text(document, encoding="utf-8")
    return {"ok": True, "static_path": str(static_path), "case_count": len(cards)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Path to regression manifest.json")
    parser.add_argument("--outdir", required=True, help="Output directory for this iteration")
    parser.add_argument("--cases", nargs="*", default=None, help="Case ids to run. Defaults to all cases.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of selected cases.")
    parser.add_argument("--skip-network", action="store_true", help="Use configured local inputs and existing downloads only.")
    parser.add_argument("--review", action="store_true", help="Generate a self-contained static regression review page.")
    parser.add_argument("--variant-search", action="store_true", help="Compile a small set of source-derived generated-layout variants and select the closest one against the reference PDF.")
    parser.add_argument("--figure-placement-probe", action="store_true", help="Compare only the base package and a source-derived non-floating figure candidate when Word contains inline body drawings.")
    parser.add_argument("--table-placement-probe", action="store_true", help="Compare only the base package and a source-derived non-floating table candidate when Word table evidence exists.")
    parser.add_argument("--float-spacing-probe", action="store_true", help="Compare only the base package and a source-derived float/text spacing candidate when Word body-text boundaries exist.")
    parser.add_argument("--table-geometry-probe", action="store_true", help="Compare only the base package with precise/full-width candidates for source-derived table column grids.")
    parser.add_argument("--body-style-probe", action="store_true", help="Compare the base package with bounded body paragraph-boundary and visible-flow style candidates derived from Word evidence.")
    parser.add_argument("--furniture-geometry-probe", action="store_true", help="Compare only the base package and a Word header-distance candidate when source-backed header text is available.")
    parser.add_argument("--first-page-furniture-probe", action="store_true", help="Compare only the base package and a Word first-page header/footer candidate when an active first-page variant exists.")
    parser.add_argument("--source-font-probe", action="store_true", help="Compare only the base package and an installed Word source-font candidate.")
    parser.add_argument("--heading-color-probe", action="store_true", help="Compare only the base package and source-backed heading RGB candidates.")
    parser.add_argument("--reference-layout-probe", action="store_true", help="Compare only the base package and a Word reference-list layout candidate.")
    parser.add_argument("--text-box-placement-probe", action="store_true", help="Compare only the base package with page/margin-relative Word text-box placement candidates.")
    parser.add_argument("--appendix-boundary-probe", action="store_true", help="Compare the base package with an isolated appendix-new-page candidate; strict promotion requires only the appendix anchor to be shifted in ordinary output.")
    parser.add_argument("--backmatter-boundary-probe", action="store_true", help="Compare the base package with an isolated new-page boundary before acknowledgements/statements; strict promotion requires only backmatter anchors to shift together.")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    outdir = Path(args.outdir).expanduser().resolve()
    manifest = read_json(manifest_path)
    outdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest_path, outdir / "manifest.json")

    selected_cases = manifest.get("cases", [])
    if args.cases:
        wanted = set(args.cases)
        selected_cases = [case for case in selected_cases if case.get("case_id") in wanted]
    if args.limit:
        selected_cases = selected_cases[: args.limit]
    if not selected_cases:
        raise SystemExit("No regression cases selected.")

    results = []
    for case in selected_cases:
        print(f"[temp2tex-regression] running {case['case_id']}")
        results.append(run_case(
            case, manifest, outdir, skip_network=args.skip_network,
            variant_search=args.variant_search,
            figure_placement_probe=args.figure_placement_probe,
            table_placement_probe=args.table_placement_probe,
            float_spacing_probe=args.float_spacing_probe,
            table_geometry_probe=args.table_geometry_probe,
            body_style_probe=args.body_style_probe,
            furniture_geometry_probe=args.furniture_geometry_probe,
            first_page_furniture_probe=args.first_page_furniture_probe,
            source_font_probe=args.source_font_probe,
            heading_color_probe=args.heading_color_probe,
            reference_layout_probe=args.reference_layout_probe,
            text_box_placement_probe=args.text_box_placement_probe,
            appendix_boundary_probe=args.appendix_boundary_probe,
            backmatter_boundary_probe=args.backmatter_boundary_probe,
        ))
    all_results = completed_case_results(outdir, manifest, results)
    benchmark = build_benchmark(outdir, all_results)
    summary = {
        "generated_at": utc_now(),
        "manifest": str(manifest_path),
        "outdir": str(outdir),
        "case_count": len(all_results),
        "passed_cases": [r["case_id"] for r in all_results if r["status"] == "passed"],
        "failed_or_not_comparable": [r["case_id"] for r in all_results if r["status"] != "passed"],
        "benchmark": str(outdir / "benchmark.json"),
    }
    if args.review:
        summary["review"] = generate_review(outdir)
    write_json(outdir / "regression_summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if not summary["failed_or_not_comparable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
