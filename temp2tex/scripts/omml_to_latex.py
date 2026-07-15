#!/usr/bin/env python3
"""Conservative OMML-to-LaTeX conversion for visible Word equation samples."""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET


M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

SYMBOLS = {
    "\u00d7": r"\times ",
    "\u00f7": r"\div ",
    "\u00b1": r"\pm ",
    "\u2212": "-",
    "\u2212": "-",
    "\u2260": r"\ne ",
    "\u2264": r"\le ",
    "\u2265": r"\ge ",
    "\u221e": r"\infty ",
    "\u2211": r"\sum ",
    "\u220f": r"\prod ",
    "\u222b": r"\int ",
    "\u222e": r"\oint ",
    "\u2202": r"\partial ",
    "\u2207": r"\nabla ",
    "\u2208": r"\in ",
    "\u2209": r"\notin ",
    "\u2282": r"\subset ",
    "\u2286": r"\subseteq ",
    "\u222a": r"\cup ",
    "\u2229": r"\cap ",
    "\u2192": r"\to ",
    "\u2190": r"\leftarrow ",
    "\u2194": r"\leftrightarrow ",
    "\u0393": r"\Gamma ",
    "\u0394": r"\Delta ",
    "\u0398": r"\Theta ",
    "\u039b": r"\Lambda ",
    "\u039e": r"\Xi ",
    "\u03a0": r"\Pi ",
    "\u03a3": r"\Sigma ",
    "\u03a6": r"\Phi ",
    "\u03a8": r"\Psi ",
    "\u03a9": r"\Omega ",
    "\u03b1": r"\alpha ",
    "\u03b2": r"\beta ",
    "\u03b3": r"\gamma ",
    "\u03b4": r"\delta ",
    "\u03b5": r"\epsilon ",
    "\u03b8": r"\theta ",
    "\u03bb": r"\lambda ",
    "\u03bc": r"\mu ",
    "\u03c0": r"\pi ",
    "\u03c1": r"\rho ",
    "\u03c3": r"\sigma ",
    "\u03c4": r"\tau ",
    "\u03c6": r"\phi ",
    "\u03c7": r"\chi ",
    "\u03c8": r"\psi ",
    "\u03c9": r"\omega ",
}

NARY_SYMBOLS = {
    "\u2211": r"\sum",
    "\u220f": r"\prod",
    "\u222b": r"\int",
    "\u222e": r"\oint",
    "\u22c2": r"\bigcap",
    "\u22c3": r"\bigcup",
}

DELIMITERS = {
    "(": ("(", ")"),
    "[": ("[", "]"),
    "{": (r"\{", r"\}"),
    "|": ("|", "|"),
    "\u2016": (r"\lVert", r"\rVert"),
    "\u230a": (r"\lfloor", r"\rfloor"),
    "\u2308": (r"\lceil", r"\rceil"),
}

FUNCTIONS = {
    "arccos", "arcsin", "arctan", "arg", "cos", "cosh", "cot", "coth",
    "csc", "deg", "det", "dim", "exp", "gcd", "hom", "inf", "ker",
    "lg", "lim", "liminf", "limsup", "ln", "log", "max", "min", "Pr",
    "sec", "sin", "sinh", "sup", "tan", "tanh",
}

PROPERTY_NODES = {
    "accPr", "barPr", "borderBoxPr", "boxPr", "ctrlPr", "dPr", "fPr",
    "eqArrPr", "funcPr", "groupChrPr", "limLowPr", "limUppPr", "mPr", "naryPr",
    "radPr", "sPrePr", "sSubPr", "sSubSupPr", "sSupPr",
}

CONTAINER_NODES = {
    "argPr", "base", "deg", "den", "e", "fName", "lim", "num", "sub",
    "sup",
}


def local_name(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]


def math_child(node: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in node if local_name(child) == name), None)


def math_attr(node: ET.Element | None, name: str) -> str | None:
    if node is None:
        return None
    return node.attrib.get(f"{{{M_NS}}}{name}") or node.attrib.get(name)


def tex_text(value: str) -> str:
    pieces: list[str] = []
    for char in value:
        if char in SYMBOLS:
            pieces.append(SYMBOLS[char])
        elif char == "\\":
            pieces.append(r"\backslash ")
        elif char in {"#", "%", "&", "_", "{", "}"}:
            pieces.append("\\" + char)
        elif char == "~":
            pieces.append(r"\sim ")
        elif char == "^":
            pieces.append(r"\mathbin{\hat{}}")
        else:
            pieces.append(char)
    return "".join(pieces)


class Converter:
    def __init__(self) -> None:
        self.unsupported: set[str] = set()
        self.notes: set[str] = set()

    def render_children(self, node: ET.Element) -> str:
        return "".join(self.render(child) for child in node if local_name(child) not in PROPERTY_NODES)

    def render(self, node: ET.Element | None) -> str:
        if node is None:
            return ""
        name = local_name(node)
        if name in {"oMath", "oMathPara", *CONTAINER_NODES}:
            return self.render_children(node)
        if name == "r":
            return tex_text("".join(child.text or "" for child in node if local_name(child) == "t"))
        if name in {"t", "delText"}:
            return tex_text(node.text or "")
        if name == "f":
            return rf"\frac{{{self.render(math_child(node, 'num'))}}}{{{self.render(math_child(node, 'den'))}}}"
        if name == "eqArr":
            rows = [self.render(child) for child in node if local_name(child) == "e"]
            if not rows:
                self.unsupported.add("eqArr_empty")
                return ""
            return r"\begin{aligned}" + r" \\ ".join(rows) + r"\end{aligned}"
        if name == "m":
            rows = []
            for row in node:
                if local_name(row) != "mr":
                    continue
                cells = [self.render(cell) for cell in row if local_name(cell) == "e"]
                if not cells:
                    self.unsupported.add("matrix_empty_row")
                    continue
                rows.append(" & ".join(cells))
            if not rows:
                self.unsupported.add("matrix_empty")
                return ""
            column_counts = [
                sum(1 for cell in row if local_name(cell) == "e")
                for row in node if local_name(row) == "mr"
            ]
            if len(set(column_counts)) > 1:
                self.unsupported.add("matrix_irregular_rows")
                return ""
            return r"\begin{matrix}" + r" \\ ".join(rows) + r"\end{matrix}"
        if name == "sSub":
            return rf"{{{self.render(math_child(node, 'e'))}}}_{{{self.render(math_child(node, 'sub'))}}}"
        if name == "sSup":
            return rf"{{{self.render(math_child(node, 'e'))}}}^{{{self.render(math_child(node, 'sup'))}}}"
        if name == "sSubSup":
            return (
                rf"{{{self.render(math_child(node, 'e'))}}}"
                rf"_{{{self.render(math_child(node, 'sub'))}}}"
                rf"^{{{self.render(math_child(node, 'sup'))}}}"
            )
        if name == "rad":
            degree = self.render(math_child(node, "deg"))
            expression = self.render(math_child(node, "e"))
            hidden = math_attr(math_child(node, "radPr"), "degHide")
            if degree and str(hidden or "").lower() not in {"1", "true", "on"}:
                return rf"\sqrt[{degree}]{{{expression}}}"
            return rf"\sqrt{{{expression}}}"
        if name == "d":
            props = math_child(node, "dPr")
            begin = math_attr(math_child(props, "begChr") if props is not None else None, "val") or "("
            end = math_attr(math_child(props, "endChr") if props is not None else None, "val") or ")"
            if begin not in DELIMITERS or end != DELIMITERS[begin][1]:
                self.unsupported.add("delimiter")
                return self.render(math_child(node, "e"))
            left, right = DELIMITERS[begin]
            return rf"\left{left}{self.render(math_child(node, 'e'))}\right{right}"
        if name == "func":
            function = self.render(math_child(node, "fName")).strip()
            argument = self.render(math_child(node, "e"))
            function_name = re.sub(r"\\[A-Za-z]+", "", function).strip() or function
            limit_match = re.fullmatch(r"\{?(lim(?:inf|sup)?)\}?_\{(.+)\}", function)
            if limit_match:
                return rf"\{limit_match.group(1)}_{{{limit_match.group(2)}}} {argument}"
            if function_name in FUNCTIONS:
                return rf"\{function_name} {argument}"
            if re.fullmatch(r"[A-Za-z]+", function_name):
                return rf"\operatorname{{{function_name}}} {argument}"
            self.unsupported.add("function_name")
            return argument
        if name == "nary":
            props = math_child(node, "naryPr")
            char = math_attr(math_child(props, "chr") if props is not None else None, "val")
            command = NARY_SYMBOLS.get(char or "")
            if not command:
                self.unsupported.add("nary_character")
                return self.render(math_child(node, "e"))
            sub = self.render(math_child(node, "sub"))
            sup = self.render(math_child(node, "sup"))
            suffix = (rf"_{{{sub}}}" if sub else "") + (rf"^{{{sup}}}" if sup else "")
            return command + suffix + " " + self.render(math_child(node, "e"))
        if name == "limLow":
            return rf"{{{self.render(math_child(node, 'e'))}}}_{{{self.render(math_child(node, 'lim'))}}}"
        if name == "limUpp":
            return rf"{{{self.render(math_child(node, 'e'))}}}^{{{self.render(math_child(node, 'lim'))}}}"
        if name == "acc":
            props = math_child(node, "accPr")
            accent = math_attr(math_child(props, "chr") if props is not None else None, "val")
            accents = {"\u0302": r"\hat", "\u0305": r"\bar", "\u0307": r"\dot", "\u20d7": r"\vec"}
            if not accent:
                # ECMA-376 specifies U+0302 when m:accPr/m:chr is omitted.
                accent = "\u0302"
                self.notes.add("default_accent_u0302")
            command = accents.get(accent or "")
            if not command:
                self.unsupported.add("accent")
                return self.render(math_child(node, "e"))
            return rf"{command}{{{self.render(math_child(node, 'e'))}}}"
        if name in PROPERTY_NODES:
            return ""
        self.unsupported.add(name)
        return self.render_children(node)


def convert_omml(math: ET.Element) -> dict:
    """Return a source-transparent conversion result for one m:oMath node."""
    converter = Converter()
    latex = converter.render(math).strip()
    structure = sorted({local_name(node) for node in math.iter() if local_name(node) not in PROPERTY_NODES})
    status = "converted" if latex and not converter.unsupported else ("partial" if latex else "not_convertible")
    return {
        "latex": latex,
        "translation_status": status,
        "unsupported_nodes": sorted(converter.unsupported),
        "structure": structure,
        "notes": sorted(converter.notes),
    }
