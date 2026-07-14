#!/usr/bin/env python3
"""Compile a generated LaTeX package and write a compile report."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import re


def tool_candidates(name: str) -> list[str]:
    candidates = []
    preferred = [
        Path(r"D:\texlive\2025\bin\windows") / f"{name}.exe",
        Path(r"C:\texlive\2025\bin\windows") / f"{name}.exe",
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
    unique.sort(key=lambda p: (0 if "texlive" in p.lower() else 1 if "miktex" in p.lower() else 2, p.lower()))
    return unique


def run(cmd: list[str], cwd: Path, timeout: int = 90) -> dict:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-5000:],
            "stderr_tail": (proc.stderr or "")[-5000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "returncode": 124,
            "stdout_tail": (exc.stdout or "")[-5000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": f"Timed out after {timeout} seconds. This often means TeX is waiting for interactive package installation.",
        }


def compile_diagnostics(commands: list[dict], engine: str) -> dict:
    """Report final-pass warnings without treating ordinary warnings as fatal."""
    engine_names = {engine.lower(), "latex" if engine == "latex-dvips" else engine.lower()}
    tex_runs = [
        item for item in commands
        if any(name in " ".join(str(part).lower() for part in item.get("cmd", [])) for name in engine_names)
    ]
    final = tex_runs[-1] if tex_runs else (commands[-1] if commands else {})
    output = "\n".join([str(final.get("stdout_tail", "")), str(final.get("stderr_tail", ""))])
    undefined_references = sorted(set(re.findall(r"Reference `([^']+)' undefined", output)))
    undefined_citations = sorted(set(re.findall(r"Citation `([^']+)' undefined", output)))
    overfull_boxes = len(re.findall(r"Overfull \\hbox", output))
    package_warnings = len(re.findall(r"Package [^\n]+ Warning:", output))
    fatal_errors = [item.strip() for item in re.findall(r"^!\s+(.+)$", output, re.MULTILINE)]
    return {
        "final_pass_command": final.get("cmd", []),
        "final_returncode": final.get("returncode"),
        "fatal_errors": fatal_errors,
        "undefined_references": undefined_references,
        "undefined_citations": undefined_citations,
        "overfull_box_count": overfull_boxes,
        "package_warning_count": package_warnings,
        "warnings_present": bool(undefined_references or undefined_citations or overfull_boxes or package_warnings),
    }
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", help="Path to main.tex")
    parser.add_argument("--output", default="compile_report.json")
    parser.add_argument("--engine", choices=["xelatex", "pdflatex", "lualatex", "latex-dvips"], default="xelatex")
    args = parser.parse_args()

    main_tex = Path(args.main_tex).expanduser().resolve()
    if not main_tex.exists():
        raise SystemExit(f"main tex not found: {main_tex}")

    cwd = main_tex.parent
    # TeX can leave a partial PDF even when -halt-on-error returns nonzero.
    # Remove prior products so a failed rerun cannot publish stale output.
    for suffix in (".pdf", ".dvi", ".ps"):
        artifact = main_tex.with_suffix(suffix)
        if artifact.exists():
            artifact.unlink()
    latexmk_candidates = tool_candidates("latexmk")
    commands = []
    if args.engine == "latex-dvips":
        latex_candidates = tool_candidates("latex")
        dvips_candidates = tool_candidates("dvips")
        ps2pdf_candidates = tool_candidates("ps2pdf")
        if latex_candidates and dvips_candidates and ps2pdf_candidates:
            latex = latex_candidates[0]
            for _ in range(2):
                commands.append(run([latex, "-interaction=nonstopmode", "-halt-on-error", main_tex.name], cwd))
                if commands[-1]["returncode"] != 0:
                    break
            dvi = main_tex.with_suffix(".dvi")
            ps = main_tex.with_suffix(".ps")
            if dvi.exists() and all(item.get("returncode") == 0 for item in commands):
                commands.append(run([dvips_candidates[0], "-o", ps.name, dvi.name], cwd))
            if ps.exists() and all(item.get("returncode") == 0 for item in commands):
                commands.append(run([ps2pdf_candidates[0], ps.name, main_tex.with_suffix(".pdf").name], cwd))
        elif latexmk_candidates:
            latexmk = latexmk_candidates[0]
            commands.append(run([latexmk, "-pdfps", "-interaction=nonstopmode", "-halt-on-error", main_tex.name], cwd))
        else:
            commands.append({"cmd": ["latex/dvips/ps2pdf"], "returncode": 127, "stdout_tail": "", "stderr_tail": "latex, dvips, ps2pdf, or latexmk not found"})
    else:
        engine_candidates = tool_candidates(args.engine)
        # Prefer the direct engine so a TeX Live latexmk wrapper cannot accidentally call a different TeX binary earlier on PATH.
        if engine_candidates:
            engine = engine_candidates[0]
            for _ in range(2):
                commands.append(run([engine, "-interaction=nonstopmode", "-halt-on-error", main_tex.name], cwd))
                if commands[-1]["returncode"] != 0:
                    break
        elif latexmk_candidates:
            latexmk = latexmk_candidates[0]
            commands.append(run([latexmk, f"-{args.engine}", "-interaction=nonstopmode", "-halt-on-error", main_tex.name], cwd))
        else:
            commands.append({"cmd": [f"latexmk/{args.engine}"], "returncode": 127, "stdout_tail": "", "stderr_tail": f"latexmk or {args.engine} not found"})

    pdf = main_tex.with_suffix(".pdf")
    commands_succeeded = bool(commands) and all(item.get("returncode") == 0 for item in commands)
    success = pdf.exists() and commands_succeeded
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "main_tex": str(main_tex),
        "engine": args.engine,
        "pdf": str(pdf) if success else None,
        "partial_pdf": str(pdf) if pdf.exists() and not success else None,
        "success": success,
        "commands": commands,
        "diagnostics": compile_diagnostics(commands, args.engine),
    }
    output = Path(args.output)
    if not output.is_absolute():
        output = cwd / output
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(output)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
