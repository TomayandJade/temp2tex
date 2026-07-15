#!/usr/bin/env python3
"""Generate an Overleaf-ready LaTeX template package from template_spec.json."""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
from pathlib import Path

from audit_source_feature_coverage import build_coverage
from extract_word_assets import extract_assets


CLASS_TEMPLATE = r"""\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{journal-template}[__DATE__ Template class reconstructed by Temp2TeX]

\LoadClass[__BASE_OPTIONS__]{__BASE_CLASS__}

__FONT_SETUP__

\RequirePackage{geometry}
\RequirePackage{graphicx}
\RequirePackage{booktabs}
\RequirePackage{longtable}
\RequirePackage{array}
\RequirePackage{multirow}
\RequirePackage{caption}
\RequirePackage{subcaption}
\RequirePackage{threeparttable}
\RequirePackage{tablefootnote}
\RequirePackage{chngcntr}
\RequirePackage{amsmath}
\RequirePackage{enumitem}
\RequirePackage{titlesec}
\RequirePackage{fancyhdr}
\RequirePackage{etoolbox}
__HEADING_PAGINATION_PACKAGE__
\RequirePackage{lastpage}
\RequirePackage[absolute,overlay]{textpos}
__UNEQUAL_COLUMNS_PACKAGE__
\RequirePackage[table]{xcolor}
\RequirePackage[normalem]{ulem}
\RequirePackage[hidelinks]{hyperref}
__CITATION_SETUP__
__FOOTNOTE_SETUP__
__ENDNOTE_SETUP__
__LINE_NUMBER_PACKAGE__
__INDENT_FIRST_PACKAGE__

\geometry{__GEOMETRY__}
\setlength{\parindent}{__PARAGRAPH_INDENT__}
\setlength{\parskip}{0pt}
\linespread{__LINE_SPACING__}
\setlength{\headheight}{14.5pt}
__PAGE_FURNITURE_GEOMETRY__
\setlength{\columnsep}{__COLUMN_SEP__}
__FLOAT_SPACING_SETUP__
\raggedbottom

\newlength{\tempTwoBodyLeftIndent}
\newlength{\tempTwoBodyRightIndent}
\newlength{\tempTwoAbstractLeftIndent}
\newlength{\tempTwoAbstractRightIndent}
\newlength{\tempTwoKeywordLeftIndent}
\newlength{\tempTwoKeywordRightIndent}
\setlength{\tempTwoBodyLeftIndent}{__BODY_LEFT_INDENT__}
\setlength{\tempTwoBodyRightIndent}{__BODY_RIGHT_INDENT__}
\setlength{\tempTwoAbstractLeftIndent}{__ABSTRACT_LEFT_INDENT__}
\setlength{\tempTwoAbstractRightIndent}{__ABSTRACT_RIGHT_INDENT__}
\setlength{\tempTwoKeywordLeftIndent}{__KEYWORD_LEFT_INDENT__}
\setlength{\tempTwoKeywordRightIndent}{__KEYWORD_RIGHT_INDENT__}
\newcommand{\tempTwoKeywordsLabel}{__KEYWORDS_LABEL__}
\newcommand{\tempTwoTexAbstractBegin}{\begingroup\leftskip=\tempTwoAbstractLeftIndent\rightskip=\tempTwoAbstractRightIndent}
\newcommand{\tempTwoTexAbstractEnd}{\par\endgroup}
\newcommand{\tempTwoTexBodyBegin}{\begingroup\leftskip=\tempTwoBodyLeftIndent\rightskip=\tempTwoBodyRightIndent\setlength{\parskip}{__BODY_PARAGRAPH_SKIP__}}
\newcommand{\tempTwoTexBodyEnd}{\par\endgroup}
\newcommand{\tempTwoKeywordsFormat}{__KEYWORDS_FORMAT__}
\newcommand{\tempTwoKeywordsLabelFormat}{__KEYWORDS_LABEL_FORMAT__}
\newcommand{\tempTwoKeywordsAlignment}{__KEYWORDS_ALIGNMENT__}
\newcommand{\tempTwoTexKeywords}[1]{%
  \par\vspace*{__KEYWORDS_BEFORE_SKIP__}%
  \begingroup\leftskip=\tempTwoKeywordLeftIndent\rightskip=\tempTwoKeywordRightIndent
  \tempTwoKeywordsAlignment\noindent
  {\tempTwoKeywordsFormat\tempTwoKeywordsLabelFormat\tempTwoKeywordsLabel}\enspace #1\par
  \endgroup\vspace{__KEYWORDS_AFTER_SKIP__}%
}
\newcommand{\journalfigurewidth}{\linewidth}
\newcommand{\journalfigurerepresentativewidth}{__JOURNAL_FIGURE_WIDTH__}
\newcommand{\journalfigurerepresentativeheight}{__JOURNAL_FIGURE_HEIGHT__}
\newcommand{\journaltablewidthspec}{__JOURNAL_TABLE_WIDTH__}
\newlength{\journaltablewidth}
\setlength{\journaltablewidth}{\linewidth}
\newcommand{\journalsettablewidth}{\setlength{\journaltablewidth}{\journaltablewidthspec}}
\newcommand{\journaltablerepresentativecolspec}{__JOURNAL_TABLE_COLSPEC__}
\newcommand{\journaltableheaderrow}{__TABLE_HEADER_ROW_SETUP__}
\newcommand{\journaltableheadercell}[1]{{__TABLE_HEADER_CELL_FORMAT__{\journaltableheaderstrut #1}}}
\newcommand{\journaltableheaderstrut}{__TABLE_HEADER_STRUT__}
\newcommand{\tempTwoListLeftMargin}{__LIST_LEFT_MARGIN__}
\newcommand{\tempTwoListLabel}{__LIST_LABEL__}
__FIGURE_ENVIRONMENT__
__TABLE_ENVIRONMENT__
__WIDE_FIGURE_ENVIRONMENT__
__WIDE_TABLE_ENVIRONMENT__
\newenvironment{journalequation}{\begin{__EQUATION_ENVIRONMENT__}}{\end{__EQUATION_ENVIRONMENT__}}
\newenvironment{journalitemize}{\begin{itemize}[leftmargin=\tempTwoListLeftMargin]}{\end{itemize}}
\newenvironment{journalenumerate}{\begin{enumerate}[leftmargin=\tempTwoListLeftMargin,label=\tempTwoListLabel]}{\end{enumerate}}
\newenvironment{journaltextbox}[1][0.92\linewidth]{\par\noindent\begin{minipage}{#1}}{\end{minipage}\par}
\newenvironment{journalpositionedtextbox}[3]{%
  \begin{textblock*}{#1}(#2,#3)\begin{minipage}{#1}}{%
  \end{minipage}\end{textblock*}}
\newenvironment{journalcover}{\clearpage\thispagestyle{empty}\begin{titlepage}}{\end{titlepage}\clearpage}
\newcommand{\journalbackmatter}{__BACKMATTER_PAGE_BREAK__}
\newcommand{\journalappendix}{%
  __APPENDIX_PAGE_BREAK__%
  \appendix
  \counterwithin{equation}{section}%
  \counterwithin{table}{section}%
  \counterwithin{figure}{section}%
  \renewcommand{\theequation}{\thesection.\arabic{equation}}%
  \renewcommand{\thetable}{\thesection.\arabic{table}}%
  \renewcommand{\thefigure}{\thesection.\arabic{figure}}%
  \setcounter{equation}{0}\setcounter{table}{0}\setcounter{figure}{0}%
}
\newcommand{\tempTwoHeaderLeft}{__DEFAULT_HEADER_LEFT__}
\newcommand{\tempTwoHeaderCenter}{__DEFAULT_HEADER_CENTER__}
\newcommand{\tempTwoHeaderRight}{__DEFAULT_HEADER_RIGHT__}
\newcommand{\tempTwoFooterLeft}{__DEFAULT_FOOTER_LEFT__}
\newcommand{\tempTwoFooterCenter}{__DEFAULT_FOOTER_CENTER__}
\newcommand{\tempTwoFooterRight}{__DEFAULT_FOOTER_RIGHT__}
\newcommand{\journalheaderleft}[1]{\gdef\tempTwoHeaderLeft{#1}}
\newcommand{\journalheadercenter}[1]{\gdef\tempTwoHeaderCenter{#1}}
\newcommand{\journalheaderright}[1]{\gdef\tempTwoHeaderRight{#1}}
\newcommand{\journalfooterleft}[1]{\gdef\tempTwoFooterLeft{#1}}
\newcommand{\journalfootercenter}[1]{\gdef\tempTwoFooterCenter{#1}}
\newcommand{\journalfooterright}[1]{\gdef\tempTwoFooterRight{#1}}
\newcommand{\tempTwoFirstPageHeaderLeft}{__DEFAULT_FIRST_PAGE_HEADER_LEFT__}
\newcommand{\tempTwoFirstPageHeaderCenter}{__DEFAULT_FIRST_PAGE_HEADER_CENTER__}
\newcommand{\tempTwoFirstPageHeaderRight}{__DEFAULT_FIRST_PAGE_HEADER_RIGHT__}
\newcommand{\tempTwoFirstPageFooterLeft}{__DEFAULT_FIRST_PAGE_FOOTER_LEFT__}
\newcommand{\tempTwoFirstPageFooterCenter}{__DEFAULT_FIRST_PAGE_FOOTER_CENTER__}
\newcommand{\tempTwoFirstPageFooterRight}{__DEFAULT_FIRST_PAGE_FOOTER_RIGHT__}
\newcommand{\journalfirstpageheaderleft}[1]{\gdef\tempTwoFirstPageHeaderLeft{#1}}
\newcommand{\journalfirstpageheadercenter}[1]{\gdef\tempTwoFirstPageHeaderCenter{#1}}
\newcommand{\journalfirstpageheaderright}[1]{\gdef\tempTwoFirstPageHeaderRight{#1}}
\newcommand{\journalfirstpagefooterleft}[1]{\gdef\tempTwoFirstPageFooterLeft{#1}}
\newcommand{\journalfirstpagefootercenter}[1]{\gdef\tempTwoFirstPageFooterCenter{#1}}
\newcommand{\journalfirstpagefooterright}[1]{\gdef\tempTwoFirstPageFooterRight{#1}}
\fancypagestyle{tempTwoFirstPage}{%
  \fancyhf{}%
  \fancyhead[L]{\tempTwoFirstPageHeaderLeft}%
  \fancyhead[C]{\tempTwoFirstPageHeaderCenter}%
  \fancyhead[R]{\tempTwoFirstPageHeaderRight}%
  \fancyfoot[L]{\tempTwoFirstPageFooterLeft}%
  \fancyfoot[C]{\tempTwoFirstPageFooterCenter}%
  \fancyfoot[R]{\tempTwoFirstPageFooterRight}%
  \renewcommand{\headrulewidth}{0pt}%
  \renewcommand{\footrulewidth}{0pt}%
}
\newcommand{\journalusefirstpagefurniture}{\thispagestyle{tempTwoFirstPage}}
\newcommand{\journalstartbodycolumns}{__BODY_COLUMN_TRANSITION__}
% Editable helpers for additional Word section boundaries. Use only when the
% section-flow evidence and rendered reference establish the corresponding
% page break or continuous transition.
\newcommand{\journalstartsinglecolumn}{\onecolumn}
\newcommand{\journalstartdoublecolumn}{\twocolumn}
\newcommand{\journalsectionpagebreak}{\clearpage}
\newcommand{\journalcolumnwidths}{__JOURNAL_COLUMN_WIDTHS__}
\newcommand{\journalcolumnratioleft}{__JOURNAL_COLUMN_RATIO_LEFT__}
\newcommand{\journalcolumnratioright}{__JOURNAL_COLUMN_RATIO_RIGHT__}
\newcommand{\journalcolumnratio}{\journalcolumnratioleft[\journalcolumnratioright]}
\makeatletter
\newcommand{\journalstartunequalcolumns}{%
  \if@twocolumn\onecolumn\fi
  \columnratio{\journalcolumnratioleft}[\journalcolumnratioright]%
  \begin{paracol}{2}%
}
\newcommand{\journalendunequalcolumns}{\end{paracol}}
\makeatother
__ABSTRACT_ENVIRONMENT__

__PAGE_STYLE_BLOCK__
__SECTION_NUMBERING_SETUP__

\titleformat{\section}{__SECTION_FORMAT__}{\thesection__SECTION_LABEL_SUFFIX__}{0.75em}{}
\titleformat{\subsection}{__SUBSECTION_FORMAT__}{\thesubsection__SECTION_LABEL_SUFFIX__}{0.75em}{}
\titleformat{\subsubsection}{__SUBSUBSECTION_FORMAT__}{\thesubsubsection__SECTION_LABEL_SUFFIX__}{0.75em}{}
\titleformat{\paragraph}[runin]{__PARAGRAPH_FORMAT__}{\theparagraph__SECTION_LABEL_SUFFIX__}{0.75em}{}
\titleformat{\subparagraph}[runin]{__SUBPARAGRAPH_FORMAT__}{\thesubparagraph__SECTION_LABEL_SUFFIX__}{0.75em}{}
\titlespacing*{\section}{__SECTION_LEFT_INDENT__}{__SECTION_BEFORE_SKIP__}{__SECTION_AFTER_SKIP__}
\titlespacing*{\subsection}{__SUBSECTION_LEFT_INDENT__}{__SUBSECTION_BEFORE_SKIP__}{__SUBSECTION_AFTER_SKIP__}
\titlespacing*{\subsubsection}{__SUBSUBSECTION_LEFT_INDENT__}{__SUBSUBSECTION_BEFORE_SKIP__}{__SUBSUBSECTION_AFTER_SKIP__}
\titlespacing*{\paragraph}{__PARAGRAPH_LEFT_INDENT__}{__PARAGRAPH_BEFORE_SKIP__}{__PARAGRAPH_AFTER_SKIP__}
\titlespacing*{\subparagraph}{__SUBPARAGRAPH_LEFT_INDENT__}{__SUBPARAGRAPH_BEFORE_SKIP__}{__SUBPARAGRAPH_AFTER_SKIP__}
\setcounter{secnumdepth}{__SECNUMDEPTH__}
__HEADING_KEEP_WITH_NEXT_SETUP__

\captionsetup{font=small,labelfont=bf,skip=__CAPTION_SKIP__}
__TABLE_CAPTION_SETUP__
__FIGURE_CAPTION_SETUP__
__BIBLIOGRAPHY_SETUP__

\makeatletter
\gdef\@tempTwoAffiliation{}
\newcommand{\affiliation}[1]{%
  \ifx\@tempTwoAffiliation\@empty
    \gdef\@tempTwoAffiliation{#1}%
  \else
    \gappto\@tempTwoAffiliation{\par #1}%
  \fi
}
\newcommand{\correspondingauthor}[1]{\thanks{Corresponding author: #1}}
\gdef\@tempTwoEnglishTitle{}
\gdef\@tempTwoEnglishAuthor{}
\gdef\@tempTwoEnglishAffiliation{}
\gdef\@tempTwoEnglishAbstract{}
\gdef\@tempTwoEnglishKeywords{}
\newcommand{\englishtitle}[1]{\gdef\@tempTwoEnglishTitle{#1}}
\newcommand{\englishauthor}[1]{\gdef\@tempTwoEnglishAuthor{#1}}
\newcommand{\englishaffiliation}[1]{\gdef\@tempTwoEnglishAffiliation{#1}}
\newcommand{\englishabstract}[1]{\gdef\@tempTwoEnglishAbstract{#1}}
\newcommand{\englishkeywords}[1]{\gdef\@tempTwoEnglishKeywords{#1}}
\newcommand{\printenglishabstract}{%
  \ifx\@tempTwoEnglishAbstract\@empty\else
    \par{__ENGLISH_ABSTRACT_ALIGNMENT__ __ENGLISH_ABSTRACT_FORMAT__ \noindent\textbf{Abstract:}\enspace\@tempTwoEnglishAbstract\par}%
    \ifx\@tempTwoEnglishKeywords\@empty\else
      {__ENGLISH_KEYWORDS_ALIGNMENT__ __ENGLISH_KEYWORDS_FORMAT__ \noindent\textbf{Keywords:}\enspace\@tempTwoEnglishKeywords\par}%
    \fi
  \fi
}
\newcommand{\printenglishfrontmatter}{%
  \ifx\@tempTwoEnglishTitle\@empty\else
    \par\vskip __BILINGUAL_FRONTMATTER_SKIP__%
    {__ENGLISH_TITLE_ALIGNMENT__ __ENGLISH_TITLE_FORMAT__ \@tempTwoEnglishTitle\par}%
    \ifx\@tempTwoEnglishAuthor\@empty\else
      \vskip __TITLE_AFTER_SKIP__%
      {__ENGLISH_AUTHOR_ALIGNMENT__ __ENGLISH_AUTHOR_FORMAT__ \@tempTwoEnglishAuthor\par}%
    \fi
    \ifx\@tempTwoEnglishAffiliation\@empty\else
      \vskip __AUTHOR_AFTER_SKIP__%
      {__ENGLISH_AFFILIATION_ALIGNMENT__ __ENGLISH_AFFILIATION_FORMAT__ \@tempTwoEnglishAffiliation\par}%
    \fi
  \fi
}
\renewcommand{\maketitle}{%
  \begingroup
  \renewcommand\thefootnote{\fnsymbol{footnote}}%
  \thispagestyle{__FIRST_PAGE_STYLE__}%
  \vspace*{__TITLE_TOP_SKIP__}%
    {__TITLE_ALIGNMENT__ __TITLE_FORMAT__ \@title\par}%
    \vskip __TITLE_AFTER_SKIP__%
    {__AUTHOR_ALIGNMENT__ __AUTHOR_FORMAT__ __AUTHOR_RENDER__\par}%
    \vskip __AUTHOR_AFTER_SKIP__%
    \ifx\@tempTwoAffiliation\@empty\else
      {__AFFILIATION_ALIGNMENT__ __AFFILIATION_FORMAT__ \@tempTwoAffiliation\par}%
      \vskip __AFFILIATION_AFTER_SKIP__%
    \fi
    \ifx\@date\@empty\else {__AFFILIATION_ALIGNMENT__ \@date\par}\fi
  \par\vskip __MAKETITLE_AFTER_SKIP__%
  \@thanks
  \endgroup
  \setcounter{footnote}{0}%
}
\makeatother

\newcommand{\tempTWOEnableLineNumbers}{__LINE_NUMBER_SETUP__}
"""


MAIN_TEMPLATE = r"""\documentclass{{journal-template}}

{header_asset_setup}

\title{{{title}}}
\author{{{author_metadata}}}
\affiliation{{{primary_affiliation}}}
\affiliation{{{secondary_affiliation}}}
\date{{}}
{bilingual_metadata}

\begin{{document}}
\tempTWOEnableLineNumbers

{unequal_columns_begin}
{front_matter_column_begin}
\maketitle
{text_box_layout_block}

{highlights}
{graphical_abstract}
\tempTwoTexAbstractBegin
\begin{{abstract}}
{abstract_text}
\end{{abstract}}
\tempTwoTexAbstractEnd

\tempTwoTexKeywords{{{keywords_text}}}
{english_frontmatter_block}
{english_abstract_block}

{toc_block}
{front_matter_column_end}

\journalstartbodycolumns
\tempTwoTexBodyBegin
{body_block}

\journalbackmatter
{statements_block}

% The default fixture uses an editable thebibliography block so two LaTeX
% passes compile without requiring a publisher-specific BibTeX backend.
% To use references.bib, replace that block with the official commands, for
% example: \bibliographystyle{{<official-bst>}} and \bibliography{{references}},
% then run the backend required by the journal.
\begin{{thebibliography}}{{9}}
\bibitem{bibitem_label}
Author A. Sample reference placeholder. \emph{{Journal Name}}. 2026;1(1):1--10.
\end{{thebibliography}}

{appendix_block}
\tempTwoTexBodyEnd
{unequal_columns_end}

\end{{document}}
"""


def get_nested(data: dict, path: str, default):
    cur = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def mm_geometry(spec: dict) -> str:
    margins = effective_page_margins(spec)
    paper = get_nested(spec, "document.paper", "a4paper")
    dimensions = get_nested(spec, "document.paper_dimensions_mm", {})
    if paper == "custom" and isinstance(dimensions, dict):
        width = dimensions.get("width_mm")
        height = dimensions.get("height_mm")
        if isinstance(width, (int, float)) and isinstance(height, (int, float)):
            paper = f"paperwidth={width}mm, paperheight={height}mm"
        else:
            paper = "a4paper"
    mirror_margins = bool(get_nested(spec, "page.mirror_margins", False))
    if mirror_margins:
        geometry = (
            f"{paper}, twoside, top={margins.get('top', 25)}mm, inner={margins.get('left', 25)}mm, "
            f"bottom={margins.get('bottom', 25)}mm, outer={margins.get('right', 25)}mm"
        )
    else:
        geometry = (
            f"{paper}, top={margins.get('top', 25)}mm, right={margins.get('right', 25)}mm, "
            f"bottom={margins.get('bottom', 25)}mm, left={margins.get('left', 25)}mm"
        )
    gutter = get_nested(spec, "page.gutter_mm", None)
    if isinstance(gutter, (int, float)) and gutter > 0:
        geometry += f", bindingoffset={gutter}mm"
    return geometry


def verified_page_calibration(spec: dict) -> dict:
    calibration = get_nested(spec, "page.render_calibration", {})
    if not isinstance(calibration, dict):
        return {}
    if str(calibration.get("status", "")).lower() not in {"render_verified", "verified"}:
        return {}
    return calibration


def effective_page_margins(spec: dict) -> dict:
    source = get_nested(spec, "page.margins_mm", {})
    margins = dict(source) if isinstance(source, dict) else {}
    calibration = verified_page_calibration(spec)
    calibrated = calibration.get("margins_mm", {})
    if isinstance(calibrated, dict):
        for side in ("top", "right", "bottom", "left"):
            value = calibrated.get(side)
            if isinstance(value, (int, float)) and 5 <= value <= 80:
                margins[side] = value
    return {side: margins.get(side, 25) for side in ("top", "right", "bottom", "left")}


def effective_column_sep_mm(spec: dict) -> float:
    value = get_nested(spec, "page.column_sep_mm", 6)
    calibration = verified_page_calibration(spec)
    candidate = calibration.get("column_sep_mm") if calibration else None
    if isinstance(candidate, (int, float)) and 2 <= candidate <= 30:
        value = candidate
    try:
        return float(value)
    except (TypeError, ValueError):
        return 6.0


def float_spacing_setup(spec: dict) -> str:
    calibration = get_nested(spec, "page.float_spacing_calibration", {})
    if not isinstance(calibration, dict) or str(calibration.get("status", "")).lower() not in {"verified", "render_verified"}:
        return ""
    lines = []
    for field, latex_length in (
        ("textfloatsep_pt", r"\textfloatsep"),
        ("intextsep_pt", r"\intextsep"),
        ("dbltextfloatsep_pt", r"\dbltextfloatsep"),
    ):
        try:
            value = float(calibration.get(field))
        except (TypeError, ValueError):
            continue
        if 0 <= value <= 72:
            lines.append(rf"\setlength{{{latex_length}}}{{{value:g}pt}}")
    if not lines:
        return ""
    return "\n".join([r"\AtBeginDocument{%", *[f"  {line}%" for line in lines], "}"])


def page_furniture_geometry_setup(spec: dict) -> str:
    """Apply a rendered header-distance calibration when explicitly verified.

    Word's header distance is measured from the page edge, whereas LaTeX uses
    a header box plus a separation above the text block. The conversion is
    useful only after same-content PDF comparison selects it, so the ordinary
    package keeps the conservative LaTeX defaults.
    """
    calibration = get_nested(spec, "page.header_footer_geometry", {})
    if not isinstance(calibration, dict) or str(calibration.get("status", "")).lower() not in {"verified", "render_verified"}:
        return ""
    margins = effective_page_margins(spec)
    try:
        header_distance = float(calibration.get("header_distance_mm", get_nested(spec, "page.header_distance_mm", 0)))
        top_margin = float(margins.get("top", 0))
        headheight = float(calibration.get("headheight_pt", 14.5))
    except (TypeError, ValueError):
        return ""
    if not (0 <= header_distance <= 80 and 5 <= top_margin <= 80 and 6 <= headheight <= 36):
        return ""
    # Convert source edge distances to the gap between LaTeX's header box and
    # its text block. Negative values indicate incompatible or incomplete
    # source evidence and intentionally leave the default untouched.
    headsep = top_margin * 72.27 / 25.4 - header_distance * 72.27 / 25.4 - headheight
    if headsep < 0:
        return ""
    return "\n".join([
        rf"\setlength{{\headheight}}{{{headheight:g}pt}}",
        rf"\setlength{{\headsep}}{{{headsep:g}pt}}",
    ])


def representative_word_section_from_spec(spec: dict) -> dict:
    sections = get_nested(spec, "page.header_footer_evidence.sections", [])
    if not isinstance(sections, list) or not sections:
        return {}
    target_index = get_nested(spec, "page.representative_section_index", None)
    for section in sections:
        if isinstance(section, dict) and section.get("index") == target_index:
            return section
    return sections[0] if isinstance(sections[0], dict) else {}


def journal_table_width(spec: dict) -> str:
    """Map Word width to the selected local single- or double-column container."""
    layout = get_nested(spec, "tables.layout_evidence", {})
    if not isinstance(layout, dict):
        return r"\linewidth"
    span = layout.get("span_evidence", {})
    if not isinstance(span, dict) or span.get("status") != "source":
        return r"\linewidth"
    try:
        object_width = float(span.get("object_width_pt"))
        container_width = (
            float(span.get("usable_width_pt"))
            if span.get("mode") == "double_column"
            else float(span.get("local_column_width_pt"))
        )
        ratio = object_width / container_width
    except (TypeError, ValueError, ZeroDivisionError):
        return r"\linewidth"
    if 0.92 <= ratio <= 1.08:
        return r"\linewidth"
    if 0.10 <= ratio < 0.92:
        return f"{ratio:.3f}\\linewidth"
    return r"\linewidth"


def table_border_mode(spec: dict) -> str:
    """Classify printable Word borders separately from table gridlines."""
    layout = get_nested(spec, "tables.layout_evidence", {})
    if not isinstance(layout, dict):
        return "unknown"
    active = layout.get("active_borders")
    if isinstance(active, list):
        edges = {str(item).lower() for item in active}
        if not edges:
            style_id = str(layout.get("style_id") or "").lower()
            if style_id in {"tablegrid", "gridtable"}:
                return "grid"
            return "none"
        vertical = bool(edges & {"left", "right", "insidev"})
        horizontal = bool(edges & {"top", "bottom", "insideh"})
        if vertical and horizontal:
            return "grid"
        if vertical:
            return "vertical"
        if horizontal:
            return "horizontal"
        return "none"
    profile = str(layout.get("border_profile") or "").lower()
    return "grid" if profile == "grid" else "unknown"


def representative_table_colspec(spec: dict) -> str:
    """Expose source grid proportions without forcing them on every table."""
    layout = get_nested(spec, "tables.layout_evidence", {})
    if not isinstance(layout, dict):
        return "lll"
    try:
        widths = [float(value) for value in layout.get("grid_column_widths_twips", [])]
    except (TypeError, ValueError):
        return "lll"
    if not 2 <= len(widths) <= 8 or any(value <= 0 for value in widths):
        return "lll"
    total = sum(widths)
    if total <= 0:
        return "lll"
    border_mode = table_border_mode(spec)
    geometry_mode = str(layout.get("geometry_mode") or "").lower()
    if border_mode in {"grid", "vertical"}:
        width_budget = {"precise": 0.995, "full": 1.0}.get(geometry_mode, 0.98)
    else:
        width_budget = 1.0
    column_parts = [
        rf">{{\raggedright\arraybackslash}}p{{{width / total * width_budget:.3f}\journaltablewidth}}"
        for width in widths
    ]
    if border_mode in {"grid", "vertical"}:
        # Suppress tabcolsep on both sides of every vertical rule.  Word's
        # grid width already accounts for the rule; leaving LaTeX's default
        # glue around the rules makes a full-width representative table
        # overrun the text block.
        return "@{}|@{}" + "@{}|@{}".join(column_parts) + "@{}|@{}"
    # Word's fixed grid width already includes the inter-column space. Remove
    # LaTeX's default tabcolsep for the representative fixture so proportional
    # p-columns do not overflow the source-backed table width.
    return "@{}" + "@{}".join(column_parts) + "@{}"


def table_header_style_from_spec(spec: dict) -> tuple[str, str, str]:
    """Map direct Word header-row evidence into an editable fixture style."""
    layout = get_nested(spec, "tables.layout_evidence", {})
    if not isinstance(layout, dict):
        return "", r"\textbf", r"\rule{0pt}{0pt}"
    fill = str(layout.get("header_fill") or "").strip()
    row_setup = rf"\rowcolor[HTML]{{{fill}}}" if re.fullmatch(r"[0-9A-Fa-f]{6}", fill) else ""
    font_consensus = layout.get("header_font_consensus")
    font = layout.get("header_effective_font", {}) if font_consensus is not False else {}
    font = font if isinstance(font, dict) else {}
    commands = [r"\normalfont"]
    try:
        size = int(font.get("size_half_points")) / 2
    except (TypeError, ValueError):
        size = None
    if size and 6 <= size <= 24:
        baseline = round(max(size * 1.2, size + 1), 1)
        commands.append(rf"\fontsize{{{size:g}pt}}{{{baseline:g}pt}}\selectfont")
    bold_consensus = layout.get("header_bold_consensus")
    if font.get("bold") is True or bold_consensus is True or (bold_consensus is None and layout.get("header_bold")):
        commands.append(r"\bfseries")
    if font.get("italic") is True:
        commands.append(r"\itshape")
    color = str(font.get("color") or "").strip().lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{6}", color) and color.upper() not in {"000000", "FFFFFF"}:
        commands.append(rf"\color[HTML]{{{color.upper()}}}")
    cell_format = "".join(commands) if len(commands) > 1 else ""
    try:
        height = float(layout.get("header_row_height_twips")) / 20
    except (TypeError, ValueError):
        height = 0
    strut = rf"\rule{{0pt}}{{{height:g}pt}}" if 8 <= height <= 72 else r"\rule{0pt}{0pt}"
    return row_setup, cell_format, strut


def equation_environment_from_spec(spec: dict) -> str:
    """Use an unnumbered environment only when the source establishes it."""
    numbering = str(get_nested(spec, "equations.numbering", "")).lower()
    return "equation*" if numbering == "unnumbered" else "equation"


def equation_candidate_file(spec: dict) -> str:
    """Emit source-derived OMML candidates without replacing the editable fixture."""
    candidates = get_nested(spec, "equations.latex_candidates", [])
    if not isinstance(candidates, list) or not candidates:
        return ""
    lines = [
        "% temp2tex-source-equation-candidates: reconstructed from Word OMML",
        "% This file is not input by main.tex. Move only render-checked samples into a manuscript.",
        "",
    ]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        index = candidate.get("index", "?")
        status = str(candidate.get("translation_status") or "not_convertible")
        latex = str(candidate.get("latex") or "").strip()
        unsupported = candidate.get("unsupported_nodes", [])
        lines.append(f"% Word OMML sample {index}; status={status}")
        if status != "converted" or not latex:
            details = ", ".join(str(item) for item in unsupported) or "no safe LaTeX candidate"
            lines.append(f"% Manual translation required: {details}.")
            if latex:
                lines.append(f"% Partial candidate: {latex}")
            lines.append("")
            continue
        if candidate.get("display_like"):
            lines.extend([
                r"\begin{journalequation}",
                latex,
                r"\end{journalequation}",
            ])
        else:
            lines.append(rf"\({latex}\)")
        lines.append("")
    return "\n".join(lines)


def list_style_from_spec(spec: dict) -> tuple[str, str]:
    evidence = get_nested(spec, "body.lists", {})
    if not isinstance(evidence, dict):
        return "18pt", r"\arabic*."
    try:
        left_margin = float(evidence.get("left_indent_twips")) / 20
    except (TypeError, ValueError):
        left_margin = 18
    left = f"{left_margin:g}pt" if 9 <= left_margin <= 144 else "18pt"
    number_format = str(evidence.get("number_format") or "decimal").lower()
    level_text = str(evidence.get("level_text") or "")
    if number_format in {"lowerletter", "loweralpha"}:
        label = r"\alph*)" if ")" in level_text else r"\alph*."
    elif number_format in {"upperletter", "upperalpha"}:
        label = r"\Alph*)" if ")" in level_text else r"\Alph*."
    elif number_format in {"lowerroman"}:
        label = r"\roman*)" if ")" in level_text else r"\roman*."
    elif number_format in {"upperroman"}:
        label = r"\Roman*)" if ")" in level_text else r"\Roman*."
    else:
        label = r"\arabic*)" if ")" in level_text else r"\arabic*."
    return left, label


def representative_figure_dimensions(spec: dict) -> tuple[str, str]:
    """Expose a Word drawing size as editable representative figure evidence."""
    layout = get_nested(spec, "figures.layout_evidence", {})
    if not isinstance(layout, dict):
        return r"\journalfigurewidth", "35mm"
    try:
        width_emu = float(layout.get("width_emu"))
        height_emu = float(layout.get("height_emu"))
        width_pt = width_emu / 12700
        height_pt = height_emu / 12700
        span = layout.get("span_evidence", {})
        if not isinstance(span, dict) or span.get("status") != "source":
            raise ValueError("unverified local container")
        container_pt = (
            float(span.get("usable_width_pt"))
            if span.get("mode") == "double_column"
            else float(span.get("local_column_width_pt"))
        )
        ratio = width_pt / container_pt
    except (TypeError, ValueError, IndexError, KeyError, ZeroDivisionError):
        return r"\journalfigurewidth", "35mm"
    width = r"\linewidth" if 0.92 <= ratio <= 1.08 else f"{ratio:.3f}\\linewidth" if 0.10 <= ratio < 0.92 else r"\journalfigurewidth"
    height = f"{height_pt:.2f}pt" if 10 <= height_pt <= 720 else "35mm"
    return width, height


def figure_environment_from_spec(spec: dict) -> str:
    layout = get_nested(spec, "figures.layout_evidence", {})
    drawing_type = str(layout.get("drawing_type") or "").lower() if isinstance(layout, dict) else ""
    # A Word inline drawing describes how that exemplar is anchored in Word,
    # not a journal-wide prohibition on LaTeX floats. Keeping figures as
    # floats is the conservative, editable default unless the evidence ledger
    # explicitly records a rendered, non-floating placement rule.
    calibration = layout.get("placement_calibration", {}) if isinstance(layout, dict) else {}
    placement_mode = str(calibration.get("mode") or "").lower() if isinstance(calibration, dict) else ""
    placement_status = str(calibration.get("status") or "").lower() if isinstance(calibration, dict) else ""
    if drawing_type == "inline" and placement_mode == "nonfloating" and placement_status in {"verified", "render_verified"}:
        return (
            r"\newenvironment{journalfigure}[1][]{%" "\n"
            r"  \par\begin{center}\captionsetup{type=figure}%" "\n"
            r"}{%" "\n"
            r"  \end{center}\par%" "\n"
            r"}"
        )
    return r"\newenvironment{journalfigure}[1][htbp]{\begin{figure}[#1]\centering}{\end{figure}}"


def table_environment_from_spec(spec: dict) -> str:
    """Keep non-floating tables as an explicit render-confirmed candidate."""
    layout = get_nested(spec, "tables.layout_evidence", {})
    calibration = layout.get("placement_calibration", {}) if isinstance(layout, dict) else {}
    placement_mode = str(calibration.get("mode") or "").lower() if isinstance(calibration, dict) else ""
    placement_status = str(calibration.get("status") or "").lower() if isinstance(calibration, dict) else ""
    if placement_mode == "nonfloating" and placement_status in {"verified", "render_verified"}:
        return (
            r"\newenvironment{journaltable}[1][]{%" "\n"
            r"  \par\begingroup\captionsetup{type=table}\centering\journalsettablewidth%" "\n"
            r"}{%" "\n"
            r"  \par\endgroup%" "\n"
            r"}"
        )
    return r"\newenvironment{journaltable}[1][htbp]{\begin{table}[#1]\centering\journalsettablewidth}{\end{table}}"


def wide_figure_environment_from_spec(spec: dict) -> str:
    if str(get_nested(spec, "document.columns", "single")).lower() == "double":
        return r"\newenvironment{journalfigurewide}[1][t]{\begin{figure*}[#1]\centering}{\end{figure*}}"
    return r"\newenvironment{journalfigurewide}[1][htbp]{\begin{figure}[#1]\centering}{\end{figure}}"


def wide_table_environment_from_spec(spec: dict) -> str:
    if str(get_nested(spec, "document.columns", "single")).lower() == "double":
        return r"\newenvironment{journaltablewide}[1][t]{\begin{table*}[#1]\centering\journalsettablewidth}{\end{table*}}"
    return r"\newenvironment{journaltablewide}[1][htbp]{\begin{table}[#1]\centering\journalsettablewidth}{\end{table}}"


def class_base_from_spec(spec: dict, language: str) -> dict[str, str]:
    columns = str(get_nested(spec, "document.columns", "single")).lower()
    font_size = effective_body_font_size(spec, 10 if columns == "double" else 12)
    font_size = min(max(font_size, 8), 12)
    # article and ctexart only accept 10/11/12pt class options. Non-standard
    # Word body sizes are applied explicitly in font_setup_from_spec.
    class_size = int(font_size) if font_size in {10, 11, 12} else 10
    if language in {"zh", "mixed"}:
        options = ["UTF8", f"{class_size}pt"]
        if bool(get_nested(spec, "page.mirror_margins", False)):
            options.append("twoside")
        if columns == "double" and not bool(get_nested(spec, "front_matter.body_column_transition_after_front_matter", False)):
            options.append("twocolumn")
        return {"base_class": "ctexart", "base_options": ",".join(options)}
    options = [f"{class_size}pt"]
    if bool(get_nested(spec, "page.mirror_margins", False)):
        options.append("twoside")
    if columns == "double" and not bool(get_nested(spec, "front_matter.body_column_transition_after_front_matter", False)):
        options.append("twocolumn")
    return {"base_class": "article", "base_options": ",".join(options)}


def unequal_column_layout(spec: dict) -> bool:
    """Detect source-backed Word columns whose widths are not equal."""
    if str(get_nested(spec, "document.columns", "single")).lower() != "double":
        return False
    widths = get_nested(spec, "page.column_widths_twips", [])
    if not isinstance(widths, list) or len(widths) < 2:
        return False
    try:
        values = [float(item) for item in widths if float(item) > 0]
    except (TypeError, ValueError):
        return False
    return len(values) >= 2 and max(values) - min(values) > 1


def unequal_column_setup(spec: dict) -> tuple[str, str, str, str]:
    """Return package line, editable source widths, and paracol ratio."""
    widths = get_nested(spec, "page.column_widths_twips", [])
    if not unequal_column_layout(spec):
        return "", "not detected", "0.5", "0.5"
    values = [float(item) for item in widths]
    total = sum(values)
    ratios = [f"{value / total:.5f}" for value in values]
    left = ratios[0]
    right = ratios[1] if len(ratios) > 1 else "0.5"
    source = ", ".join(f"{int(value) if value.is_integer() else value:g} twips" for value in values)
    return r"\RequirePackage{paracol}", source, left, right


def effective_body_style_mode(spec: dict) -> str:
    """Select a visible-flow body candidate only through verified calibration."""
    calibration = get_nested(spec, "document.render_calibration", {})
    if isinstance(calibration, dict) and str(calibration.get("status", "")).lower() in {"render_verified", "verified"}:
        mode = str(calibration.get("body_style_mode") or "").lower()
        if mode == "visible_flow_exemplar":
            return mode
    # Retain compatibility with older explicit candidate specs. Ordinary source
    # specs do not set this field; new probes use document.render_calibration.
    return str(get_nested(spec, "page.source_body_style.render_mode", "")).lower()


def effective_body_font_size(spec: dict, default: int | float) -> float:
    """Use a render-calibrated body size only when the evidence says it is verified."""
    source_size = get_nested(spec, "document.font_size_pt", default)
    body_override = get_nested(spec, "page.source_body_style.visible_flow_override_candidate", {})
    body_mode = effective_body_style_mode(spec)
    if body_mode == "visible_flow_exemplar" and isinstance(body_override, dict):
        candidate_size = get_nested(body_override, "effective_format.font.size_half_points", None)
        try:
            if candidate_size is not None:
                source_size = float(candidate_size) / 2
        except (TypeError, ValueError):
            pass
    calibration = get_nested(spec, "document.render_calibration", {})
    if isinstance(calibration, dict) and str(calibration.get("status", "")).lower() in {"render_verified", "verified"}:
        source_size = calibration.get("calibrated_font_size_pt", source_size)
    try:
        return round(float(source_size), 2)
    except (TypeError, ValueError):
        return default


def latex_font_name(value: object) -> str | None:
    """Accept a Word font name only when it is safe to embed in a TeX command."""
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name or any(char in name for char in "{}\\%#"):
        return None
    return name


def source_body_baseline_pt(spec: dict) -> float | None:
    """Map unambiguous Word body line metrics to a physical LaTeX baseline.

    Word exact spacing is stored in twips. It is stronger evidence than a
    class-wide ``\\linespread`` multiplier once Temp2TeX selects an explicit
    body font size. Word automatic spacing remains relative: Word and TeX
    apply font metrics differently, so it must stay on the relative path
    unless a render calibration verifies a physical baseline. ``atLeast`` is
    also unresolved because the rendered baseline depends on line contents.
    """
    role = get_nested(spec, "page.source_body_style", {})
    if not isinstance(role, dict):
        return None
    paragraph = role.get("direct_format", {}).get("paragraph", {})
    if effective_body_style_mode(spec) == "visible_flow_exemplar":
        candidate = role.get("visible_flow_override_candidate", {})
        if isinstance(candidate, dict):
            paragraph = candidate.get("direct_format", {}).get("paragraph", paragraph)
    rule = str(paragraph.get("line_spacing_rule") or "").lower()
    try:
        line = float(paragraph.get("line_spacing"))
        size = effective_body_font_size(spec, 10)
    except (TypeError, ValueError):
        return None
    if rule == "exact" and 120 <= line <= 960:
        return round(line / 20, 2)
    return None


def source_body_parskip(spec: dict) -> str:
    """Map verified body-boundary calibration or explicit non-table body after spacing."""
    calibration = verified_page_calibration(spec)
    try:
        calibrated_points = float(calibration.get("body_parskip_pt"))
    except (TypeError, ValueError):
        calibrated_points = -1
    if 0 <= calibrated_points <= 72:
        return f"{calibrated_points:g}pt"
    spacing_evidence = get_nested(spec, "page.body_paragraph_spacing_evidence", {})
    if isinstance(spacing_evidence, dict) and spacing_evidence.get("status") == "source":
        try:
            source_points = float(spacing_evidence.get("paragraph_skip_pt"))
        except (TypeError, ValueError):
            source_points = -1
        if 0 <= source_points <= 72:
            return f"{source_points:g}pt"
    role = get_nested(spec, "page.source_body_style", {})
    if not isinstance(role, dict) or role.get("evidence_status") in {
        "template_style_candidate", "table_cell_body_exemplar"
    }:
        return "0pt"
    paragraph = role.get("direct_format", {}).get("paragraph", {})
    if effective_body_style_mode(spec) == "visible_flow_exemplar":
        candidate = role.get("visible_flow_override_candidate", {})
        if isinstance(candidate, dict):
            paragraph = candidate.get("direct_format", {}).get("paragraph", paragraph)
    if not isinstance(paragraph, dict):
        return "0pt"
    try:
        points = int(paragraph.get("space_after_twips")) / 20
    except (TypeError, ValueError):
        return "0pt"
    # Very small Word gaps are especially sensitive to TeX font metrics and
    # float reflow; require a visible 6pt-or-larger role gap before making it
    # a class-wide paragraph skip.
    return f"{points:g}pt" if 6 <= points <= 72 else "0pt"


def effective_body_font_family(spec: dict) -> str | None:
    """Use a visible-body candidate only when its render mode is explicit."""
    body_mode = effective_body_style_mode(spec)
    candidate = get_nested(spec, "page.source_body_style.visible_flow_override_candidate", {})
    if body_mode == "visible_flow_exemplar" and isinstance(candidate, dict):
        value = get_nested(candidate, "effective_format.font.family", None)
        if value:
            return str(value)
    value = get_nested(spec, "document.font_family", None)
    return str(value) if value else None


def font_setup_from_spec(spec: dict, language: str) -> str:
    source_size = effective_body_font_size(spec, 10)
    size_setup = []
    calibration = get_nested(spec, "document.render_calibration", {})
    baseline = source_body_baseline_pt(spec)
    if isinstance(calibration, dict) and str(calibration.get("status", "")).lower() in {"render_verified", "verified"}:
        try:
            candidate = float(calibration.get("body_baseline_pt"))
            if source_size <= candidate <= 30:
                baseline = candidate
        except (TypeError, ValueError):
            pass
    if baseline is not None:
        # Word exact metrics are mapped to physical baseline distances.
        # Reset the class stretch so that a source-backed baseline is not
        # multiplied a second time by the article class default.
        size_setup.append(
            rf"\AtBeginDocument{{\renewcommand{{\baselinestretch}}{{1}}\fontsize{{{source_size:g}pt}}{{{baseline:g}pt}}\selectfont}}"
        )
    elif source_size not in {10, 11, 12} and 8 <= source_size <= 12:
        baseline = round(max(source_size * 1.2, source_size + 1.5), 1)
        size_setup.append(rf"\AtBeginDocument{{\fontsize{{{source_size}pt}}{{{baseline}pt}}\selectfont}}")
    if language in {"zh", "mixed"}:
        lines = ["% XeLaTeX CJK support is provided by the ctexart base class.", *size_setup]
        cjk_family = latex_font_name(get_nested(spec, "document.cjk_font_family", None))
        cjk_mode = str(get_nested(spec, "document.cjk_font_mode", "default")).lower()
        if cjk_family and cjk_mode in {"evidence_only", "verified", "render_verified"}:
            lines.append(rf"\IfFontExistsTF{{{cjk_family}}}{{\setCJKmainfont{{{cjk_family}}}}}{{}}")
        latin_family = latex_font_name(effective_body_font_family(spec))
        latin_mode = str(get_nested(spec, "document.font_family_mode", "default")).lower()
        if language == "mixed" and latin_family and latin_mode in {"evidence_only", "verified", "render_verified"}:
            lines.append(rf"\IfFontExistsTF{{{latin_family}}}{{\setmainfont{{{latin_family}}}}}{{}}")
        return "\n".join(lines)
    family = latex_font_name(effective_body_font_family(spec))
    mode = str(get_nested(spec, "document.font_family_mode", "default")).lower()
    if not family or mode not in {"evidence_only", "verified", "render_verified"}:
        return "\n".join([r"\RequirePackage{newtxtext,newtxmath}", *size_setup])
    return "\n".join([
        r"\RequirePackage{fontspec}",
        rf"\IfFontExistsTF{{{family}}}{{\setmainfont{{{family}}}}}{{\RequirePackage{{newtxtext,newtxmath}}}}",
        *size_setup,
    ])


def heading_style(spec: dict) -> dict[str, str]:
    profile = str(get_nested(spec, "body.heading_profile", "article-bold")).lower()
    suffix = str(get_nested(spec, "body.section_label_suffix", "") or "")
    if suffix.lower() in {"dot", "period"}:
        suffix = "."
    if profile in {"compact", "legacy-compact", "journal-compact"}:
        styles = {
            "section": r"\normalfont\normalsize",
            "subsection": r"\normalfont\normalsize",
            "subsubsection": r"\normalfont\normalsize",
            "paragraph": r"\normalfont\normalsize",
            "subparagraph": r"\normalfont\normalsize",
            "suffix": suffix,
        }
    else:
        styles = {
            "section": r"\normalfont\bfseries\Large",
            "subsection": r"\normalfont\bfseries\large",
            "subsubsection": r"\normalfont\bfseries\normalsize",
            "paragraph": r"\normalfont\bfseries\normalsize",
            "subparagraph": r"\normalfont\bfseries\normalsize",
            "suffix": suffix,
        }
    for number, key in enumerate(["section", "subsection", "subsubsection", "paragraph", "subparagraph"]):
        path = f"body.heading_styles.level{number}"
        role_format = role_effective_format(spec, path)
        direct = role_format.get("font", {})
        try:
            size = int(direct.get("size_half_points")) / 2
        except (TypeError, ValueError, AttributeError):
            continue
        if not 6 <= size <= 24:
            continue
        baseline = round(max(size * 1.2, size + 2), 1)
        commands = [r"\normalfont", rf"\fontsize{{{size:g}pt}}{{{baseline:g}pt}}\selectfont"]
        if direct.get("bold") is True:
            commands.append(r"\bfseries")
        if direct.get("italic") is True:
            commands.append(r"\itshape")
        color = str(direct.get("color") or "").strip()
        color_mode = str(get_nested(spec, f"{path}.color_mode", "evidence_only") or "evidence_only").lower()
        if color_mode in {"verified", "render_verified"} and re.fullmatch(r"[0-9A-Fa-f]{6}", color) and color.upper() not in {"000000", "FFFFFF"}:
            commands.append(rf"\color[HTML]{{{color.upper()}}}")
        alignment = str(role_format.get("paragraph", {}).get("alignment") or "").lower()
        if alignment in {"center", "centre"}:
            commands.append(r"\centering")
        elif alignment in {"right", "end"}:
            commands.append(r"\raggedleft")
        styles[key] = "".join(commands)
    return styles


def section_numbering_setup(spec: dict) -> str:
    evidence = get_nested(spec, "body.section_numbering_evidence", {})
    profile = str(evidence.get("profile") if isinstance(evidence, dict) else "arabic").lower()
    if profile == "roman":
        return "\n".join([
            r"\renewcommand{\thesection}{\Roman{section}}",
            r"\renewcommand{\thesubsection}{\thesection.\arabic{subsection}}",
            r"\renewcommand{\thesubsubsection}{\thesubsection.\arabic{subsubsection}}",
        ])
    if profile == "alpha":
        return "\n".join([
            r"\renewcommand{\thesection}{\Alph{section}}",
            r"\renewcommand{\thesubsection}{\thesection.\arabic{subsection}}",
            r"\renewcommand{\thesubsubsection}{\thesubsection.\arabic{subsubsection}}",
        ])
    return ""


def heading_keep_with_next_levels(spec: dict) -> list[tuple[int, str]]:
    """Return only heading commands explicitly kept with following Word text."""
    levels = [
        (0, "section"),
        (1, "subsection"),
        (2, "subsubsection"),
        (3, "paragraph"),
        (4, "subparagraph"),
    ]
    selected = []
    for level, command in levels:
        paragraph = role_effective_format(spec, f"body.heading_styles.level{level}").get("paragraph", {})
        if isinstance(paragraph, dict) and paragraph.get("keep_with_next") is True:
            selected.append((level, command))
    return selected


def heading_keep_with_next_setup(spec: dict) -> str:
    """Map Word keepNext to a bounded heading-plus-one-line page constraint."""
    return "\n".join(
        rf"\pretocmd{{\{command}}}{{\Needspace{{2\baselineskip}}}}{{}}{{}}"
        for _, command in heading_keep_with_next_levels(spec)
    )


def header_rule_width(spec: dict) -> str:
    parts = get_nested(spec, "page.header_footer_evidence.parts", [])
    for part in parts if isinstance(parts, list) else []:
        if part.get("kind") != "header":
            continue
        for rule in part.get("rules", []):
            try:
                size = int(rule.get("size_eighth_points")) / 8
            except (TypeError, ValueError):
                continue
            if size > 0:
                return f"{size:g}pt"
    return "0pt"


def source_text_furniture_part_names(spec: dict, include_first: bool = False) -> set[str]:
    """Return active header/footer parts that are safe text-only evidence.

    A Word template can mix a render-sensitive first-page logo or text box
    with a deterministic later-page running header. Treat safety per part so
    one unsafe variant does not suppress unrelated editable page-field text.
    """
    furniture = get_nested(spec, "page.header_footer_evidence", {})
    if not isinstance(furniture, dict):
        return set()
    parts = furniture.get("parts")
    active = furniture.get("active_variants")
    if not isinstance(parts, list) or not isinstance(active, list) or not active:
        return set()
    later = [
        item for item in active
        if isinstance(item, dict) and (include_first or item.get("variant") != "first")
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
    return safe_parts


def source_text_furniture_is_safe(spec: dict) -> bool:
    """Allow direct text/page-field furniture without enabling asset placement."""
    return bool(source_text_furniture_part_names(spec))


def source_text_furniture_enabled(spec: dict) -> bool:
    return bool(
        get_nested(spec, "page.header_footer_auto_apply", False)
        or get_nested(spec, "page.header_footer_text_auto_apply", False)
        or source_text_furniture_is_safe(spec)
    )


def page_style_block(spec: dict) -> str:
    profile = str(get_nested(spec, "page.header_footer_profile", "fancy-running-head")).lower()
    if profile in {"plain", "plain-page", "no-running-head"}:
        return r"\pagestyle{plain}"
    if profile in {"empty", "none"}:
        return r"\pagestyle{empty}"
    if profile in {"source-backed-custom", "custom", "word-header-footer"}:
        # OOXML proves that page furniture exists, but not its rendered
        # baseline, first-page selection, or asset visibility. Preserve source
        # text in editable fancyhdr slots, but do not activate any custom
        # furniture until a rendered candidate has been selected.
        if not source_text_furniture_enabled(spec):
            return r"\pagestyle{empty}"
        return "\n".join([
            r"\pagestyle{fancy}",
            r"\fancyhf{}",
            r"\fancyhead[L]{\tempTwoHeaderLeft}",
            r"\fancyhead[C]{\tempTwoHeaderCenter}",
            r"\fancyhead[R]{\tempTwoHeaderRight}",
            r"\fancyfoot[L]{\tempTwoFooterLeft}",
            r"\fancyfoot[C]{\tempTwoFooterCenter}",
            r"\fancyfoot[R]{\tempTwoFooterRight}",
            rf"\renewcommand{{\headrulewidth}}{{{header_rule_width(spec)}}}",
            r"\renewcommand{\footrulewidth}{0pt}",
        ])
    running_head = str(get_nested(spec, "journal.short_title", get_nested(spec, "journal.name", "Journal short title")))
    return "\n".join([
        r"\pagestyle{fancy}",
        r"\fancyhf{}",
        rf"\fancyhead[L]{{{running_head}}}",
        r"\fancyhead[R]{\thepage}",
        r"\renewcommand{\headrulewidth}{0.4pt}",
    ])


def class_length(spec: dict, path: str, default: str) -> str:
    value = get_nested(spec, path, default)
    if isinstance(value, (int, float)):
        return f"{value}pt"
    text = str(value or default).strip()
    if not text:
        return default
    if any(text.endswith(unit) for unit in ["pt", "mm", "cm", "em", "ex", "in"]):
        return text
    return f"{text}pt"


def content_box_length(spec: dict, path: str, side: str) -> str:
    value = get_nested(spec, f"{path}.{side}_indent", None)
    return class_length({"value": value}, "value", "0pt")


def requires_first_paragraph_indent(spec: dict) -> bool:
    value = get_nested(spec, "page.source_body_style.direct_format.paragraph.first_line_twips", None)
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def heading_length(spec: dict, level: int, key: str, default: str) -> str:
    paragraph = role_effective_format(spec, f"body.heading_styles.level{level}").get("paragraph", {})
    twips_key = {
        "left": "left_indent_twips",
        "before": "space_before_twips",
        "after": "space_after_twips",
    }[key]
    try:
        value = int(paragraph.get(twips_key)) / 20
    except (TypeError, ValueError, AttributeError):
        return default
    return f"{value:g}pt" if value >= 0 else default


def title_format(spec: dict) -> str:
    profile = str(get_nested(spec, "front_matter.title_profile", "article-bold")).lower()
    if profile in {"compact", "journal-compact"}:
        return r"\normalfont\bfseries\large"
    if profile in {"plain", "regular"}:
        return r"\normalfont\Large"
    return r"\normalfont\bfseries\Large"


def author_format(spec: dict) -> str:
    profile = str(get_nested(spec, "front_matter.author_profile", "article-normal")).lower()
    if profile in {"compact", "journal-compact"}:
        return r"\normalfont\normalsize"
    if profile in {"small"}:
        return r"\normalfont\small"
    return r"\normalfont\normalsize"


def source_role_baseline_pt(spec: dict, path: str, size: float) -> float:
    """Map an explicit Word role line metric to a physical TeX baseline."""
    paragraph = role_effective_format(spec, path).get("paragraph", {})
    rule = str(paragraph.get("line_spacing_rule") or "").lower()
    try:
        candidate = float(paragraph.get("line_spacing")) / 20
    except (TypeError, ValueError):
        candidate = 0.0
    # Word stores automatic spacing in twips too, but its rendered result is
    # font-dependent. Only exact and minimum-baseline evidence is stable
    # enough to map before a PDF comparison confirms an automatic value.
    if rule in {"exact", "atleast"} and size <= candidate <= 72:
        return round(candidate, 2)
    return round(max(size * 1.2, size + 2), 1)


def source_role_format(spec: dict, path: str, fallback: str) -> str:
    effective = role_effective_format(spec, path).get("font", {})
    source_role = get_nested(spec, path, {})
    source_direct = source_role.get("direct_format", {}) if isinstance(source_role, dict) else {}
    direct_font = source_direct.get("font", {}) if isinstance(source_direct, dict) else {}
    direct = {**direct_font, **effective} if isinstance(effective, dict) else direct_font
    try:
        size = int(direct.get("size_half_points")) / 2
    except (TypeError, ValueError, AttributeError):
        size = None
    if size is not None and 6 <= size <= 24:
        baseline = source_role_baseline_pt(spec, path, size)
        commands = [r"\normalfont", rf"\fontsize{{{size:g}pt}}{{{baseline:g}pt}}\selectfont"]
    else:
        commands = [fallback]
    if direct.get("bold") is True:
        commands.append(r"\bfseries")
    if direct.get("italic") is True:
        commands.append(r"\itshape")
    color = str(direct.get("color") or "").strip()
    if re.fullmatch(r"[0-9A-Fa-f]{6}", color) and color.upper() not in {"000000", "FFFFFF"}:
        commands.append(rf"\color[HTML]{{{color.upper()}}}")
    return "".join(commands)


def source_role_skip(spec: dict, path: str, default: str) -> str:
    points = source_role_spacing_points(spec, path, "space_after_twips")
    return f"{points:g}pt" if points is not None else default


def source_role_spacing_points(spec: dict, path: str, key: str) -> float | None:
    """Return the effective nonnegative Word paragraph spacing for one role."""
    for paragraph in (
        get_nested(spec, f"{path}.direct_format.paragraph", {}),
        role_effective_format(spec, path).get("paragraph", {}),
    ):
        if not isinstance(paragraph, dict) or key not in paragraph:
            continue
        try:
            points = int(paragraph.get(key)) / 20
        except (TypeError, ValueError):
            continue
        if points >= 0:
            return points
    return None


def source_role_direct_after_skip(spec: dict, path: str, default: str) -> str:
    """Read only an explicit role after-gap, avoiding inherited Normal spacing."""
    direct = get_nested(spec, f"{path}.direct_format.paragraph", {})
    if not isinstance(direct, dict) or "space_after_twips" not in direct:
        return default
    try:
        points = int(direct.get("space_after_twips")) / 20
    except (TypeError, ValueError):
        return default
    return f"{points:g}pt" if points >= 0 else default


def source_role_before_skip(spec: dict, path: str, default: str) -> str:
    """Use an explicit Word paragraph-before value without double counting.

    Word front matter commonly expresses the title-to-author gap on the
    author paragraph rather than after the title. Prefer direct formatting so
    generic Normal-style inheritance does not accidentally become a journal
    front-matter rule.
    """
    points = source_role_spacing_points(spec, path, "space_before_twips")
    return f"{points:g}pt" if points is not None else default


def source_role_transition_skip(spec: dict, previous_path: str, next_path: str, default: str) -> str:
    """Map one Word paragraph boundary to one LaTeX vertical skip.

    A Word paragraph gap can be stored either after the preceding role or
    before the next role.  Selecting both would duplicate the gap in LaTeX.
    """
    previous_after = source_role_spacing_points(spec, previous_path, "space_after_twips")
    next_before = source_role_spacing_points(spec, next_path, "space_before_twips")
    values = [value for value in (previous_after, next_before) if value is not None]
    return f"{max(values):g}pt" if values else default


def abstract_entry_role_path(spec: dict) -> str:
    return "abstracts.label_style" if str(get_nested(spec, "abstracts.label_mode", "default")).lower() in {"separate", "default"} else "abstracts.style"


def front_matter_boundary_skip(spec: dict, name: str, fallback: str) -> str:
    boundary = get_nested(spec, f"front_matter.spacing_boundaries.{name}", {})
    if isinstance(boundary, dict):
        try:
            value = float(boundary.get("resolved_pt"))
        except (TypeError, ValueError):
            value = -1
        if value >= 0:
            return f"{value:g}pt"
    return fallback


def author_rendering(spec: dict) -> str:
    layout = str(get_nested(spec, "front_matter.author_layout", "tabular")).lower()
    if layout == "inline":
        return r"\def\and{, }\@author"
    return r"\lineskip .5em \begin{tabular}[t]{c}\@author\end{tabular}"


def role_effective_format(spec: dict, path: str) -> dict:
    if path == "page.source_body_style" and effective_body_style_mode(spec) == "visible_flow_exemplar":
        candidate = get_nested(spec, "page.source_body_style.visible_flow_override_candidate", {})
        if isinstance(candidate, dict):
            candidate_effective = candidate.get("effective_format") or candidate.get("direct_format") or {}
            if isinstance(candidate_effective, dict) and candidate_effective:
                return candidate_effective
    effective = get_nested(spec, f"{path}.effective_format", {})
    if isinstance(effective, dict) and effective:
        return effective
    direct = get_nested(spec, f"{path}.direct_format", {})
    return direct if isinstance(direct, dict) else {}


def source_role_alignment(spec: dict, path: str, fallback: str = r"\centering") -> str:
    alignment = str(role_effective_format(spec, path).get("paragraph", {}).get("alignment") or "").lower()
    role_evidence = get_nested(spec, path, {})
    has_word_role = isinstance(role_evidence, dict) and bool(
        role_evidence.get("style_id") or role_evidence.get("source") or role_evidence.get("sample_text")
    )
    if not alignment and has_word_role:
        # Word's paragraph default is left aligned. Keep centering only for a
        # generated fallback that has no source role evidence at all.
        return r"\raggedright"
    return {
        "left": r"\raggedright",
        "start": r"\raggedright",
        "right": r"\raggedleft",
        "end": r"\raggedleft",
        "center": r"\centering",
        # Word `both` is justified, not left-ragged. `\relax` leaves the
        # surrounding LaTeX paragraph's normal justification in place without
        # requiring an extra justification package inside title/front matter.
        "both": r"\relax",
    }.get(alignment, fallback)


def role_font_command(spec: dict, path: str, fallback: str = r"\normalfont") -> str:
    direct = role_effective_format(spec, path)
    source_role = get_nested(spec, path, {})
    source_direct = source_role.get("direct_format", {}) if isinstance(source_role, dict) else {}
    source_font = source_direct.get("font", {}) if isinstance(source_direct, dict) else {}
    effective_font = direct.get("font", {}) if isinstance(direct.get("font", {}), dict) else {}
    font = {**source_font, **effective_font}
    paragraph = direct.get("paragraph", {})
    try:
        size = int(font.get("size_half_points")) / 2
    except (TypeError, ValueError):
        return fallback
    if not 6 <= size <= 24:
        return fallback
    try:
        line = int(paragraph.get("line_spacing")) / 20
    except (TypeError, ValueError):
        line = max(size * 1.2, size + 2)
    commands = [r"\normalfont", rf"\fontsize{{{size:g}pt}}{{{line:g}pt}}\selectfont"]
    if font.get("bold") is True:
        commands.append(r"\bfseries")
    if font.get("italic") is True:
        commands.append(r"\itshape")
    color = str(font.get("color") or "").strip()
    if re.fullmatch(r"[0-9A-Fa-f]{6}", color) and color.upper() not in {"000000", "FFFFFF"}:
        commands.append(rf"\color[HTML]{{{color.upper()}}}")
    return "".join(commands)


def caption_setup(spec: dict, kind: str, path: str, default_position: str) -> str:
    direct = role_effective_format(spec, path)
    if not direct:
        return ""
    declaration = rf"\DeclareCaptionFont{{tempTwo{kind.title()}Caption}}{{{role_font_command(spec, path)}}}"
    font = direct.get("font", {})
    paragraph = direct.get("paragraph", {})
    alignment = str(paragraph.get("alignment") or "").lower()
    justification = {"both": "justified", "center": "centering", "left": "raggedright", "right": "raggedleft"}.get(alignment)
    options = [f"position={get_nested(spec, f'{kind}s.caption_position', default_position)}", f"font=tempTwo{kind.title()}Caption", "singlelinecheck=false"]
    options.append("labelfont=bf" if font.get("bold") is True else "labelfont=normalfont")
    if justification:
        options.append(f"justification={justification}")
    spacing = get_nested(spec, f"{kind}s.caption_spacing_evidence", {})
    try:
        skip = float(spacing.get("resolved_pt")) if isinstance(spacing, dict) else None
    except (TypeError, ValueError):
        skip = None
    try:
        outer_skip = float(spacing.get("outer_pt")) if isinstance(spacing, dict) else None
    except (TypeError, ValueError):
        outer_skip = None
    # Compatibility for hand-authored legacy specs. Newly drafted specs own
    # this decision in caption_spacing_evidence and never use the wrong side
    # of a below-caption paragraph merely because space-after is populated.
    if skip is None and not spacing:
        try:
            skip = int(paragraph.get("space_after_twips")) / 20
        except (TypeError, ValueError):
            skip = None
    if skip is not None and skip >= 0:
        options.append(f"aboveskip={skip:g}pt")
    if outer_skip is not None and outer_skip >= 0:
        options.append(f"belowskip={outer_skip:g}pt")
    return declaration + "\n" + rf"\captionsetup[{kind}]{{{','.join(options)}}}"


def bibliography_setup(spec: dict) -> str:
    direct = role_effective_format(spec, "references.entry_style")
    if not direct:
        return ""
    font = role_font_command(spec, "references.entry_style")
    lines = [
        rf"\newcommand{{\tempTwoReferenceFont}}{{{font}}}",
        r"\AtBeginEnvironment{thebibliography}{\tempTwoReferenceFont}",
    ]
    paragraph = direct.get("paragraph", {})
    try:
        left_indent = int(paragraph.get("left_indent_twips")) / 20
    except (TypeError, ValueError):
        left_indent = 0
    try:
        hanging = int(paragraph.get("hanging_twips")) / 20
    except (TypeError, ValueError):
        hanging = 0
    try:
        item_spacing = int(paragraph.get("space_after_twips")) / 20
    except (TypeError, ValueError):
        item_spacing = None
    layout_mode = str(get_nested(spec, "references.entry_style.layout_mode", "evidence_only") or "evidence_only").lower()
    list_settings = []
    if layout_mode in {"verified", "render_verified"} and left_indent > 0:
        list_settings.append(rf"\setlength{{\leftmargin}}{{{left_indent:g}pt}}")
    if layout_mode in {"verified", "render_verified"} and hanging > 0:
        # Word hanging indentation means the entry's first line projects back
        # from the continuation block. This is backend-safe for the standard
        # thebibliography list, while label-width fine tuning remains a PDF
        # verification concern.
        list_settings.append(rf"\setlength{{\itemindent}}{{-{hanging:g}pt}}")
    if layout_mode in {"verified", "render_verified"} and item_spacing is not None and item_spacing >= 0:
        list_settings.append(rf"\setlength{{\itemsep}}{{{item_spacing:g}pt}}")
        list_settings.append(r"\setlength{\parsep}{0pt}")
    if list_settings:
        lines.extend([
            r"\makeatletter",
            rf"\apptocmd{{\thebibliography}}{{{''.join(list_settings)}}}{{}}{{}}",
            r"\makeatother",
        ])
    return "\n".join(lines)


def appendix_page_break(spec: dict) -> str:
    """Apply only a render-verified appendix new-page boundary."""
    calibration = get_nested(spec, "appendices.layout_evidence.boundary_calibration", {})
    if not isinstance(calibration, dict):
        return ""
    status = str(calibration.get("status") or "").lower()
    mode = str(calibration.get("mode") or "").lower()
    return r"\clearpage" if status in {"verified", "render_verified"} and mode == "new_page" else ""


def backmatter_page_break(spec: dict) -> str:
    """Apply only a render-verified boundary before statements/references."""
    calibration = get_nested(spec, "statements.layout_evidence.boundary_calibration", {})
    if not isinstance(calibration, dict):
        return ""
    status = str(calibration.get("status") or "").lower()
    mode = str(calibration.get("mode") or "").lower()
    return r"\clearpage" if status in {"verified", "render_verified"} and mode == "new_page" else ""


def footnote_setup(spec: dict) -> str:
    if not get_nested(spec, "footnotes.enabled", False):
        return ""
    direct = role_effective_format(spec, "footnotes.style")
    marker_style = str(get_nested(spec, "footnotes.marker_style", "") or "")
    marker_commands = {
        "alph": r"\alph{footnote}",
        "Alph": r"\Alph{footnote}",
        "roman": r"\roman{footnote}",
        "Roman": r"\Roman{footnote}",
        "fnsymbol": r"\fnsymbol{footnote}",
    }
    marker_setup = marker_commands.get(marker_style)
    if not direct:
        return rf"\renewcommand{{\thefootnote}}{{{marker_setup}}}" if marker_setup else ""
    font = role_font_command(spec, "footnotes.style")
    paragraph = direct.get("paragraph", {})
    try:
        left_indent = int(paragraph.get("left_indent_twips")) / 20
    except (TypeError, ValueError):
        left_indent = 0
    try:
        first_line = int(paragraph.get("first_line_twips")) / 20
    except (TypeError, ValueError):
        first_line = 0
    try:
        hanging = int(paragraph.get("hanging_twips")) / 20
    except (TypeError, ValueError):
        hanging = 0
    indent_setup = ""
    if any(value for value in (left_indent, first_line, hanging)):
        # Apply paragraph geometry inside the footnote text, preserving a Word
        # hanging indent by moving only the first line back from the body inset.
        first_indent = first_line - hanging
        indent_setup = (
            rf"\setlength{{\leftskip}}{{{left_indent:g}pt}}"
            rf"\setlength{{\parindent}}{{{first_indent:g}pt}}"
        )
    lines = [
        *([rf"\renewcommand{{\thefootnote}}{{{marker_setup}}}"] if marker_setup else []),
        rf"\newcommand{{\tempTwoFootnoteFormat}}{{{font}}}",
        r"\makeatletter",
        r"\patchcmd{\@makefntext}{\footnotesize}{\footnotesize\tempTwoFootnoteFormat}{}{}",
    ]
    if indent_setup:
        lines.append(rf"\patchcmd{{\@makefntext}}{{\ignorespaces}}{{{indent_setup}\ignorespaces}}{{}}{{}}")
    lines.append(r"\makeatother")
    return "\n".join(lines)


def endnote_setup(spec: dict) -> str:
    if not get_nested(spec, "endnotes.enabled", False):
        return (
            r"\newcommand{\journalendnote}[1]{\footnote{#1}}" "\n"
            r"\newcommand{\printjournalendnotes}{}"
        )
    font = role_font_command(spec, "endnotes.style")
    return "\n".join([
        r"\RequirePackage{endnotes}",
        rf"\newcommand{{\tempTwoEndnoteFormat}}{{{font}}}",
        r"\renewcommand{\enoteformat}{\tempTwoEndnoteFormat}",
        r"\newcommand{\journalendnote}[1]{\endnote{#1}}",
        r"\newcommand{\printjournalendnotes}{\theendnotes}",
    ])


def abstract_environment(spec: dict) -> str:
    mode = str(get_nested(spec, "abstracts.layout_mode", "block")).lower()
    label_mode = str(get_nested(spec, "abstracts.label_mode", "default")).lower()
    label = latex_escape(str(get_nested(spec, "abstracts.label", "Abstract:") or ""))
    content_format = source_role_format(spec, "abstracts.style", r"\small")
    content_alignment = source_role_alignment(spec, "abstracts.style", r"\raggedright")
    label_format = source_role_format(spec, "abstracts.label_style", r"\bfseries")
    label_alignment = source_role_alignment(spec, "abstracts.label_style", r"\centering")
    if mode in {"inline", "inline_label", "run_in"} or label_mode == "inline":
        return (
            rf"\renewenvironment{{abstract}}{{\par\noindent\begingroup{content_alignment}{content_format}"
            rf"{{{label_format} {label}}}\enspace\ignorespaces}}"
            rf"{{\par\endgroup}}"
        )
    label_block = ""
    if label_mode in {"separate", "default"} and label:
        label_to_content = front_matter_boundary_skip(
            spec,
            "abstract_label_to_content",
            source_role_transition_skip(spec, "abstracts.label_style", "abstracts.style", "4pt"),
        )
        label_block = (
            rf"{{{label_alignment}{label_format} {label}\par}}"
            rf"\vskip {label_to_content}"
        )
    return (
        rf"\renewenvironment{{abstract}}{{\par\noindent\begingroup{label_block}"
        rf"{content_alignment}{content_format}\noindent\ignorespaces}}"
        rf"{{\par\endgroup}}"
    )


def keyword_setup(spec: dict) -> tuple[str, str, str, str, str]:
    """Keep keyword typography and spacing local to the keyword paragraph."""
    path = "abstracts.keyword_style"
    role = get_nested(spec, path, {})
    paragraph = role_effective_format(spec, path).get("paragraph", {})
    font = role_effective_format(spec, path).get("font", {})
    table_only_sample = isinstance(role, dict) and role.get("sample_in_table_cells") is True
    before = "0pt" if table_only_sample else front_matter_boundary_skip(
        spec,
        "abstract_to_keywords",
        source_role_transition_skip(spec, "abstracts.style", path, "6pt"),
    )
    after = "0pt"
    label_format = r"\bfseries"
    if isinstance(font, dict) and font.get("bold") is False:
        label_format = r"\normalfont"
    alignment = source_role_alignment(spec, path, r"\raggedright")
    return (
        role_font_command(spec, path, r"\normalfont"),
        label_format,
        alignment,
        before,
        after,
    )


def emu_to_pt(value: object) -> float | None:
    try:
        return round(int(str(value)) / 12700, 2)
    except (TypeError, ValueError):
        return None


def header_asset_setup(
    spec: dict,
    asset_manifest: Path | None,
    enabled: bool,
    variant: str = "default",
    command_prefix: str = "",
) -> str:
    if not enabled or asset_manifest is None or not asset_manifest.exists():
        return ""
    try:
        manifest = json.loads(asset_manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    drawing_index = {}
    active_variants = get_nested(spec, "page.header_footer_evidence.active_variants", [])
    active_parts = {
        item.get("part") for item in active_variants if isinstance(item, dict)
        and item.get("kind") in {"header", "footer"} and item.get("section_index") == 1 and item.get("variant") == variant
    }
    parts = get_nested(spec, "page.header_footer_evidence.parts", [])
    for part in parts if isinstance(parts, list) else []:
        for drawing in part.get("drawings", []):
            drawing_index[(part.get("part"), drawing.get("relationship_id"))] = drawing
    slots: dict[str, list[str]] = {}
    max_header_height = 0.0
    for asset in manifest.get("assets", []):
        for reference in asset.get("referenced_by", []):
            if reference.get("part") not in active_parts:
                continue
            drawing = drawing_index.get((reference.get("part"), reference.get("relationship_id")))
            if not drawing or drawing.get("drawing_type") != "inline":
                continue
            kind = "header" if str(reference.get("part", "")).split("/")[-1].startswith("header") else "footer"
            alignment = str(drawing.get("horizontal_alignment") or drawing.get("alignment") or "left").lower()
            side = "right" if alignment == "right" else "center" if alignment in {"center", "centre"} else "left"
            width = emu_to_pt(drawing.get("width_emu"))
            height = emu_to_pt(drawing.get("height_emu"))
            if width is None:
                continue
            latex_output = asset.get("latex_output") or asset.get("output")
            if not latex_output or asset.get("latex_compatible") is False:
                continue
            command = rf"\includegraphics[width={width:g}pt]{{assets/{latex_output}}}"
            slots.setdefault(f"{kind}{side}", []).append(command)
            if kind == "header" and height is not None:
                max_header_height = max(max_header_height, height)
    lines = []
    if max_header_height:
        # fancyhdr needs room for the graphic's natural baseline as well as
        # its measured OOXML height. Keep a small conservative allowance so a
        # render-confirmed header candidate does not compile with a clipped
        # or undersized headheight warning.
        lines.append(rf"\setlength{{\headheight}}{{{max_header_height + 6:g}pt}}")
    for slot in sorted(slots):
        content = r"\hspace{4pt}".join(slots[slot])
        lines.append(rf"\journal{command_prefix}{slot}{{{content}}}")
    return "\n".join(lines)


def first_page_style(spec: dict) -> str:
    if bool(get_nested(spec, "page.first_page_furniture_auto_apply", False)):
        return "tempTwoFirstPage"
    if (
        str(get_nested(spec, "page.header_footer_profile", "")).lower()
        in {"source-backed-custom", "custom", "word-header-footer"}
        and not source_text_furniture_enabled(spec)
    ):
        return "empty"
    if (
        str(get_nested(spec, "page.header_footer_profile", "")).lower()
        in {"source-backed-custom", "custom", "word-header-footer"}
        and source_text_furniture_enabled(spec)
        and not bool(get_nested(spec, "page.first_page_furniture_auto_apply", False))
        and any(
            isinstance(item, dict) and item.get("variant") == "first"
            for item in get_nested(spec, "page.header_footer_evidence.active_variants", [])
            if isinstance(get_nested(spec, "page.header_footer_evidence.active_variants", []), list)
        )
    ):
        # A different-first-page section must not inherit later-page furniture
        # unless the first-page candidate was independently verified.
        return "empty"
    value = str(get_nested(spec, "page.first_page_style", "") or "").lower()
    if value in {"empty", "plain", "fancy", "tempTwoFirstPage"}:
        return value
    profile = str(get_nested(spec, "page.header_footer_profile", "fancy-running-head")).lower()
    return "empty" if profile in {"empty", "none"} else "plain"


def latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in value)


def furniture_span_commands(font: dict) -> str:
    """Return local TeX commands for one visible Word header/footer span."""
    if not isinstance(font, dict):
        return ""
    commands = [r"\normalfont"]
    try:
        size = int(font.get("size_half_points")) / 2
    except (TypeError, ValueError):
        size = None
    if size and 5 <= size <= 24:
        baseline = round(max(size * 1.2, size + 1), 1)
        commands.append(rf"\fontsize{{{size:g}pt}}{{{baseline:g}pt}}\selectfont")
    if font.get("bold") is True:
        commands.append(r"\bfseries")
    if font.get("italic") is True:
        commands.append(r"\itshape")
    color = str(font.get("color") or "").strip().lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{6}", color):
        commands.append(rf"\color[HTML]{{{color.upper()}}}")
    return "".join(commands) if len(commands) > 1 else ""


def decorated_span_text(font: dict, text: str) -> str:
    """Map visible Word run decorations without flattening surrounding text."""
    if not isinstance(font, dict) or not text:
        return text
    value = text
    vertical = str(font.get("vertical_align") or "").lower()
    if vertical == "superscript":
        value = rf"\textsuperscript{{{value}}}"
    elif vertical == "subscript":
        value = rf"\textsubscript{{{value}}}"
    underline = str(font.get("underline") or "").lower()
    if underline and underline not in {"none", "0", "false", "off"}:
        # LaTeX core has one robust editable underline. Preserve the original
        # OOXML variant in the span ledger even when it was double or words-only.
        value = rf"\underline{{{value}}}"
    if font.get("strike") is True or font.get("double_strike") is True:
        value = rf"\sout{{{value}}}"
    return value


def linked_span_text(text: str, target: object) -> str:
    """Map a safe external Word hyperlink without treating arbitrary text as a URL."""
    value = str(target or "").strip()
    if not re.fullmatch(r"(?:https?://|mailto:)[^\s{}<>]+", value, flags=re.I):
        return text
    return rf"\href{{\detokenize{{{value}}}}}{{{text}}}"


def furniture_span_at(spans: list[dict], cursor: int) -> dict:
    for span in spans:
        try:
            if int(span.get("start", -1)) <= cursor < int(span.get("end", -1)):
                return span
        except (TypeError, ValueError):
            continue
    return {}


def render_furniture_text(
    value: str,
    spans: list[dict],
    span_text: str,
    cursor: int,
) -> tuple[str, int]:
    """Escape and locally format one Word furniture token from run evidence."""
    if not value:
        return "", cursor
    start = span_text.find(value, cursor)
    if start < 0:
        return latex_escape(value), cursor
    end = start + len(value)
    pieces = []
    position = start
    while position < end:
        span = furniture_span_at(spans, position)
        boundary = end
        if span:
            try:
                boundary = min(end, int(span.get("end", end)))
            except (TypeError, ValueError):
                boundary = end
            font = (span.get("effective_format") or {}).get("font", {})
        else:
            font = {}
            future = [
                int(item.get("start"))
                for item in spans
                if str(item.get("start", "")).isdigit() and int(item["start"]) > position
            ]
            if future:
                boundary = min(end, min(future))
        text = latex_escape(value[position - start:boundary - start])
        commands = furniture_span_commands(font)
        text = decorated_span_text(font, text)
        text = linked_span_text(text, span.get("hyperlink_target") if span else None)
        pieces.append(rf"{{{commands} {text}}}" if commands else text)
        position = boundary
    return "".join(pieces), end


def render_furniture_field(
    value: str,
    spans: list[dict],
    span_text: str,
    cursor: int,
) -> tuple[str, int]:
    """Format a dynamic page field with the source run active at its position."""
    span = furniture_span_at(spans, cursor)
    font = (span.get("effective_format") or {}).get("font", {}) if span else {}
    commands = furniture_span_commands(font)
    if cursor < len(span_text) and span_text[cursor].isdigit():
        cursor += 1
    value = decorated_span_text(font, value)
    return (rf"{{{commands} {value}}}" if commands else value), cursor


def render_source_text_spans(value: str, spans: list[dict], span_text: str | None = None) -> str:
    """Render visible Word text with its local run formats for an editable fixture."""
    if not value:
        return ""
    rendered, _ = render_furniture_text(value, spans, span_text or value, 0)
    return rendered


def text_box_latex_paragraphs(box: dict) -> list[str]:
    """Render Word text-box paragraph spans without asserting placement."""
    records = box.get("paragraphs", []) if isinstance(box, dict) else []
    rendered = []
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, dict):
                continue
            text = str(record.get("format_span_text") or record.get("text") or "").strip()
            spans = record.get("format_spans", [])
            if text:
                rendered.append(render_source_text_spans(text, spans if isinstance(spans, list) else [], text))
    if rendered:
        return rendered
    text = str(box.get("text") or "") if isinstance(box, dict) else ""
    return [latex_escape(paragraph.strip()) for paragraph in text.splitlines() if paragraph.strip()] or [""]


def table_header_fixture_cells(spec: dict, count: int) -> list[str]:
    """Use source header labels when their per-cell span evidence is safe to replay."""
    layout = get_nested(spec, "tables.layout_evidence", {})
    samples = layout.get("header_cell_samples", []) if isinstance(layout, dict) else []
    if not isinstance(samples, list) or len(samples) < count:
        return [f"Column {chr(65 + index)}" for index in range(count)]
    cells = []
    for sample in samples[:count]:
        if not isinstance(sample, dict):
            return [f"Column {chr(65 + index)}" for index in range(count)]
        text = str(sample.get("format_span_text") or "").strip()
        spans = sample.get("format_spans", [])
        if not text or len(text) > 160 or "\n" in text or not isinstance(spans, list):
            return [f"Column {chr(65 + index)}" for index in range(count)]
        cells.append(render_source_text_spans(text, spans, text))
    return cells


def source_table_fixture(spec: dict, count: int, colspec: str) -> str | None:
    """Replay a bounded Word table sample when its cell evidence is unambiguous."""
    layout = get_nested(spec, "tables.layout_evidence", {})
    samples = layout.get("cell_format_samples", []) if isinstance(layout, dict) else []
    if (
        not isinstance(samples, list)
        or not samples
        or layout.get("cell_format_samples_truncated")
    ):
        return None
    rows: dict[int, list[dict]] = {}
    for sample in samples:
        if not isinstance(sample, dict):
            return None
        try:
            row_index = int(sample.get("row_index"))
            column_index = int(sample.get("column_index"))
            grid_span = int(sample.get("grid_span") or 1)
        except (TypeError, ValueError):
            return None
        paragraphs = sample.get("paragraphs", [])
        if (
            row_index < 1
            or column_index < 1
            or not 1 <= grid_span <= count
            or not isinstance(paragraphs, list)
            or not 1 <= len(paragraphs) <= 4
            or sample.get("paragraphs_truncated")
        ):
            return None
        vertical_merge = str(sample.get("vertical_merge") or "").lower() or None
        if vertical_merge == "continue":
            if any(str(paragraph.get("format_span_text") or "").strip() for paragraph in paragraphs if isinstance(paragraph, dict)):
                return None
            rows.setdefault(row_index, []).append({
                "column_index": column_index,
                "grid_span": grid_span,
                "text": "",
                "alignment": "left",
                "vertical_merge": vertical_merge,
            })
            continue
        rendered_paragraphs = []
        alignments = []
        for paragraph in paragraphs:
            if not isinstance(paragraph, dict):
                return None
            text = str(paragraph.get("format_span_text") or "").strip()
            spans = paragraph.get("format_spans", [])
            if len(text) > 160 or "\n" in text or not isinstance(spans, list):
                return None
            rendered_paragraphs.append(render_source_text_spans(text, spans, text))
            alignments.append(get_nested(paragraph, "effective_format.paragraph.alignment", "left"))
        rendered_text = rendered_paragraphs[0] if len(rendered_paragraphs) == 1 else r"\shortstack[l]{" + r" \\ ".join(rendered_paragraphs) + "}"
        rows.setdefault(row_index, []).append({
            "column_index": column_index,
            "grid_span": grid_span,
            "text": rendered_text,
            "alignment": alignments[0] if alignments else "left",
            "vertical_merge": vertical_merge,
        })
    ordered = [rows[index] for index in sorted(rows)]
    if not 2 <= len(ordered) <= 20:
        return None
    for row in ordered:
        row.sort(key=lambda item: item["column_index"])
        if sum(item["grid_span"] for item in row) != count:
            return None
        logical_column = 1
        for item in row:
            item["logical_column"] = logical_column
            logical_column += item["grid_span"]
    by_position = {
        (row_index + 1, item["logical_column"]): item
        for row_index, row in enumerate(ordered)
        for item in row
    }
    for row_index, row in enumerate(ordered, 1):
        for item in row:
            merge = item["vertical_merge"]
            if merge == "continue":
                if item["text"]:
                    return None
                continue
            if merge not in {None, "restart"}:
                return None
            if merge == "restart":
                span = 1
                next_row = row_index + 1
                while True:
                    continuation = by_position.get((next_row, item["logical_column"]))
                    if (
                        continuation is None
                        or continuation["vertical_merge"] != "continue"
                        or continuation["grid_span"] != item["grid_span"]
                    ):
                        break
                    span += 1
                    next_row += 1
                if span < 2:
                    return None
                item["vertical_span"] = span
            else:
                item["vertical_span"] = 1
    border_mode = table_border_mode(spec)

    def merged_alignment(item: dict) -> str:
        alignment = {"center": "c", "right": "r"}.get(str(item.get("alignment") or "").lower(), "l")
        return f"|{alignment}|" if border_mode in {"grid", "vertical"} else alignment

    def render_row(row: list[dict], is_header: bool) -> str:
        cells = []
        for item in row:
            if item["vertical_merge"] == "continue":
                cells.append("")
                continue
            text = rf"\journaltableheadercell{{{item['text']}}}" if is_header else item["text"]
            if item.get("vertical_span", 1) > 1:
                text = rf"\multirow{{{item['vertical_span']}}}{{*}}{{{text}}}"
            if item["grid_span"] > 1:
                text = rf"\multicolumn{{{item['grid_span']}}}{{{merged_alignment(item)}}}{{{text}}}"
            cells.append(text)
        return " & ".join(cells) + r" \\"

    def rule_after(row_index: int) -> str:
        """Avoid drawing an inner grid rule through a Word vertical merge."""
        if row_index >= len(ordered) - 1:
            return r"\hline"
        continued_columns = set()
        for item in ordered[row_index + 1]:
            if item["vertical_merge"] == "continue":
                continued_columns.update(range(item["logical_column"], item["logical_column"] + item["grid_span"]))
        if not continued_columns:
            return r"\hline"
        ranges = []
        start = None
        for column in range(1, count + 1):
            if column not in continued_columns and start is None:
                start = column
            if start is not None and (column in continued_columns or column == count):
                end = column - 1 if column in continued_columns else column
                ranges.append((start, end))
                start = None
        return "".join(rf"\cline{{{start}-{end}}}" for start, end in ranges)

    lines = [rf"\begin{{tabular}}{{{colspec}}}", "% temp2tex-source-table-spans: replayed from Word cell evidence"]
    if border_mode in {"grid", "horizontal"}:
        lines.append(r"\hline")
    elif border_mode == "unknown":
        lines.append(r"\toprule")
    for row_index, row in enumerate(ordered):
        if row_index == 0:
            lines.append(r"\journaltableheaderrow")
        lines.append(render_row(row, row_index == 0))
        if border_mode == "grid":
            lines.append(rule_after(row_index))
        elif border_mode == "horizontal" and row_index == 0:
            lines.append(r"\hline")
        elif border_mode == "unknown" and row_index == 0:
            lines.append(r"\midrule")
    if border_mode == "horizontal":
        lines.append(r"\hline")
    elif border_mode == "unknown":
        lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines)


def header_footer_slots(
    spec: dict,
    preferred_variant: str = "default",
    section_index: int | None = None,
) -> dict[str, str]:
    """Map source-backed running text into editable fancyhdr slots.

    Word templates often encode later-page furniture in later sections, while
    the first section contains only a logo or a first-page variant. Prefer the
    first active textual variant for each kind, and infer a dynamic page number
    only when equivalent active variants demonstrate changing numeric slots.
    """
    slots = {
        "header_left": "", "header_center": "", "header_right": "",
        "footer_left": "", "footer_center": "", "footer_right": "",
    }
    variants = get_nested(spec, "page.header_footer_evidence.active_variants", [])
    if not isinstance(variants, list):
        return slots
    safe_parts = source_text_furniture_part_names(
        spec,
        include_first=preferred_variant == "first",
    )
    for kind in ("header", "footer"):
        candidates = [
            item for item in variants
            if isinstance(item, dict)
            and item.get("kind") == kind
            and item.get("variant") == preferred_variant
            and item.get("part") in safe_parts
            and (section_index is None or item.get("section_index") == section_index)
        ]
        if not candidates and section_index is None:
            candidates = [
                item for item in variants
                if isinstance(item, dict)
                and item.get("kind") == kind
                and item.get("part") in safe_parts
            ]
        parsed_candidates = []
        for candidate in candidates:
            paragraphs = candidate.get("paragraphs", [])
            if not isinstance(paragraphs, list):
                continue
            # A Word footer frequently stores its running text and page field
            # in separate paragraphs.  The first paragraph can also be an
            # empty compatibility artifact, so consider every tokenized
            # paragraph rather than treating its position as evidence.
            for paragraph in paragraphs:
                if not isinstance(paragraph, dict):
                    continue
                segments: list[str] = [""]
                rendered_tokens: list[str] = []
                first_page_token_index: int | None = None
                has_tab = False
                spans = [item for item in paragraph.get("format_spans", []) if isinstance(item, dict)]
                span_text = str(paragraph.get("format_span_text") or "")
                span_cursor = 0
                for token in paragraph.get("tokens", []):
                    if token.get("kind") == "tab":
                        has_tab = True
                        segments.append("")
                        tab_at = span_text.find("\t", span_cursor)
                        if tab_at >= 0:
                            span_cursor = tab_at + 1
                    elif token.get("kind") == "page_field":
                        value, span_cursor = render_furniture_field(
                            r"\thepage", spans, span_text, span_cursor,
                        )
                        if first_page_token_index is None:
                            first_page_token_index = len(rendered_tokens)
                        rendered_tokens.append(value)
                        segments[-1] += value
                    elif token.get("kind") == "page_count_field":
                        value, span_cursor = render_furniture_field(
                            r"\pageref{LastPage}", spans, span_text, span_cursor,
                        )
                        if first_page_token_index is None:
                            first_page_token_index = len(rendered_tokens)
                        rendered_tokens.append(value)
                        segments[-1] += value
                    elif token.get("kind") == "text":
                        value, span_cursor = render_furniture_text(
                            str(token.get("value", "")), spans, span_text, span_cursor,
                        )
                        rendered_tokens.append(value)
                        segments[-1] += value
                # Some Word producers encode the visual right tab stop only in
                # paragraph properties. When a page field exists without an
                # explicit tab token, split the running label from the page
                # number sequence so fancyhdr can preserve the two slots.
                if not has_tab and first_page_token_index is not None and len(segments) == 1:
                    before = "".join(rendered_tokens[:first_page_token_index]).strip()
                    after = "".join(rendered_tokens[first_page_token_index:]).strip()
                    if before and after:
                        segments = [before, after]
                if any(segments):
                    parsed_candidates.append((candidate, paragraph, segments))
        if not parsed_candidates:
            continue
        numeric_samples = {
            value
            for _, _, peer_segments in parsed_candidates
            for value in peer_segments
            if re.fullmatch(r"\d+", value)
        }
        for _, paragraph, raw_segments in parsed_candidates:
            segments = list(raw_segments)
            for index, value in enumerate(segments):
                if not re.fullmatch(r"\d+", value):
                    continue
                peer_values = [peer_segments[index] for _, _, peer_segments in parsed_candidates if len(peer_segments) == len(segments)]
                if (
                    len(set(peer_values)) >= 2 and all(re.fullmatch(r"\d+", peer) for peer in peer_values)
                ) or len(numeric_samples) >= 2:
                    segments[index] = r"\thepage"
            # Run spans preserve mixed bold, italic, colour, and size inside
            # one header/footer paragraph. Only use the legacy whole-paragraph
            # formatter when no span ledger is available.
            if paragraph.get("format_spans"):
                direct = {}
            else:
                direct = paragraph.get("direct_format", {}) if isinstance(paragraph.get("direct_format"), dict) else {}
            font = direct.get("font", {}) if isinstance(direct.get("font"), dict) else {}
            try:
                size = int(font.get("size_half_points")) / 2
            except (TypeError, ValueError):
                size = None
            format_commands = [r"\normalfont"]
            if size and 5 <= size <= 24:
                baseline = round(max(size * 1.2, size + 1), 1)
                format_commands.append(rf"\fontsize{{{size:g}pt}}{{{baseline:g}pt}}\selectfont")
            if font.get("bold") is True:
                format_commands.append(r"\bfseries")
            if font.get("italic") is True:
                format_commands.append(r"\itshape")
            color = str(font.get("color") or "").strip().lstrip("#")
            if re.fullmatch(r"[0-9A-Fa-f]{6}", color):
                format_commands.append(rf"\color[HTML]{{{color.upper()}}}")
            if len(format_commands) > 1:
                formatting = "".join(format_commands)
                segments = [rf"{{{formatting} {value}}}" if value else "" for value in segments]
            if len(segments) == 1:
                alignment = str(paragraph.get("alignment", "left")).lower()
                target = "center" if alignment in {"center", "centre"} else "right" if alignment == "right" else "left"
                key = f"{kind}_{target}"
                if not slots[key]:
                    slots[key] = segments[0]
            elif len(segments) == 2:
                if not slots[f"{kind}_left"]:
                    slots[f"{kind}_left"] = segments[0]
                if not slots[f"{kind}_right"]:
                    slots[f"{kind}_right"] = segments[1]
            else:
                if not slots[f"{kind}_left"]:
                    slots[f"{kind}_left"] = segments[0]
                if not slots[f"{kind}_center"]:
                    slots[f"{kind}_center"] = segments[1]
                if not slots[f"{kind}_right"]:
                    slots[f"{kind}_right"] = segments[-1]
    return slots


def page_furniture_candidate_file(spec: dict) -> str:
    """Write section-specific Word furniture as commented editable candidates."""
    furniture = get_nested(spec, "page.header_footer_evidence", {})
    sections = furniture.get("sections", []) if isinstance(furniture, dict) else []
    variants = furniture.get("active_variants", []) if isinstance(furniture, dict) else []
    lines = [
        "% Optional section-specific page-furniture candidates reconstructed from Word XML.",
        "% Do not input this file automatically: place a style at the corresponding",
        "% semantic section boundary only after a same-content PDF comparison confirms it.",
        "% A global fancyhdr mapping cannot represent every Word section variant.",
        "",
    ]
    if not isinstance(variants, list) or not variants:
        lines.append("% No active Word header/footer variants were recorded.")
        return "\n".join(lines) + "\n"
    section_indices = []
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, dict) and section.get("index") is not None:
                section_indices.append(section.get("index"))
    if not section_indices:
        section_indices = sorted({item.get("section_index") for item in variants if isinstance(item, dict) and item.get("section_index") is not None})
    for section_index in section_indices:
        try:
            numeric_index = int(section_index)
        except (TypeError, ValueError):
            continue
        active = [
            item for item in variants
            if isinstance(item, dict) and item.get("section_index") == numeric_index
        ]
        if not active:
            continue
        slots = header_footer_slots(spec, section_index=numeric_index)
        parts = sorted({str(item.get("part")) for item in active if item.get("part")})
        lines.append(f"% Section {numeric_index}; active parts: {', '.join(parts) or 'unknown'}")
        lines.append(f"% \\fancypagestyle{{journalsection{numeric_index}}}{{%")
        lines.append("%   \\fancyhf{}%")
        for kind in ("header", "footer"):
            for side in ("left", "center", "right"):
                value = slots.get(f"{kind}_{side}", "")
                if value:
                    command = "head" if kind == "header" else "foot"
                    lines.append(f"%   \\fancy{command}[{side[0].upper()}]{{{value}}}%")
        lines.extend([
            "%   \\renewcommand{\\headrulewidth}{0pt}%",
            "%   \\renewcommand{\\footrulewidth}{0pt}%",
            "% }",
            f"% \\pagestyle{{journalsection{numeric_index}}}",
            "",
        ])
    if len(lines) == 5:
        lines.append("% Active variants exist, but no section-specific text/page-field candidate was executable.")
    return "\n".join(lines).rstrip() + "\n"


def paragraph_block(items: list[str], limit: int | None = None) -> str:
    selected = items[:limit] if limit else items
    blocks = []
    for item in selected:
        text = latex_escape(str(item).strip())
        if text:
            blocks.append(text)
            blocks.append("")
    return "\n".join(blocks).strip()


def text_box_position_candidate(spec: dict, geometry: dict) -> tuple[str, str, str] | None:
    """Return a safe page/margin-relative textpos candidate.

    Column- and paragraph-relative offsets depend on the surrounding Word
    flow, so they remain evidence comments instead of being misread as page
    coordinates. Page and margin origins can be exposed as an editable
    candidate while still keeping it commented until visual confirmation.
    """
    try:
        width = float(geometry.get("width_emu")) / 36000
        x = float(geometry.get("horizontal_offset_emu", 0)) / 36000
        y = float(geometry.get("vertical_offset_emu", 0)) / 36000
    except (TypeError, ValueError):
        return None
    if width <= 0 or x < -500 or y < -500:
        return None
    h_relative = str(geometry.get("horizontal_relative_to") or "").lower()
    v_relative = str(geometry.get("vertical_relative_to") or "").lower()
    if h_relative not in {"page", "margin"} or v_relative not in {"page", "margin"}:
        return None
    margins = get_nested(spec, "page.margins_mm", {})
    if h_relative == "margin":
        x += float(margins.get("left", 0) or 0)
    if v_relative == "margin":
        y += float(margins.get("top", 0) or 0)
    return f"{width:.2f}mm", f"{x:.2f}mm", f"{y:.2f}mm"


def text_box_candidate_file(spec: dict) -> str:
    """Write non-flow Word text boxes as an explicit, non-auto-input candidate."""
    boxes = get_nested(spec, "assets.text_boxes", [])
    lines = [
        "% Optional text-box candidates reconstructed from Word non-flow XML.",
        "% Do not input this file into main.tex until the source PDF confirms",
        "% that the text boxes are manuscript content rather than instructions.",
        "% The journaltextbox environment is a flow-safe editable fallback;",
        "% exact floating coordinates require a same-content render comparison.",
        "",
    ]
    if not isinstance(boxes, list) or not boxes:
        lines.append("% No Word text-box evidence was recorded.")
        return "\n".join(lines) + "\n"
    for index, box in enumerate(boxes, 1):
        if not isinstance(box, dict):
            continue
        part = str(box.get("part") or box.get("source") or "unknown source")
        text = str(box.get("text") or "").strip()
        lines.append(f"% Text box {index}; source: {part}")
        geometry = box.get("geometry") if isinstance(box.get("geometry"), dict) else {}
        if geometry:
            fields = (
                "anchor_type", "width_emu", "height_emu",
                "horizontal_relative_to", "horizontal_offset_emu",
                "vertical_relative_to", "vertical_offset_emu", "wrap_type",
                "docpr_name", "relative_width_from", "relative_height_from",
            )
            summary = "; ".join(
                f"{field}={geometry[field]}"
                for field in fields
                if geometry.get(field) not in (None, "")
            )
            if summary:
                lines.append(f"% Geometry: {summary}")
            positioned = text_box_position_candidate(spec, geometry)
            if positioned:
                width, x, y = positioned
                lines.append("% Page/margin-relative executable candidate (keep commented until PDF confirmation):")
                lines.append(f"% \\begin{{journalpositionedtextbox}}{{{width}}}{{{x}}}{{{y}}}")
                for paragraph in text_box_latex_paragraphs(box):
                    lines.append((f"% {paragraph}" + r"\par") if paragraph else "%")
                lines.append("% \\end{journalpositionedtextbox}")
            else:
                lines.append("% No executable coordinate candidate: the source origin is flow-relative or incomplete.")
        if box.get("requires_visual_review"):
            lines.append("% Placement remains pending visual confirmation.")
        lines.append("% \\begin{journaltextbox}")
        for paragraph in text_box_latex_paragraphs(box):
            lines.append((f"% {paragraph}" + r"\par") if paragraph else "%")
        lines.append("% \\end{journaltextbox}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def text_box_active_file(spec: dict) -> str:
    """Write only page/margin-relative text boxes for an explicit probe."""
    boxes = get_nested(spec, "assets.text_boxes", [])
    lines = [
        "% Explicit text-box placement probe generated from Word geometry.",
        "% This file is included only when assets.text_boxes_auto_apply is true.",
        "",
    ]
    if not isinstance(boxes, list):
        return "\n".join(lines)
    for index, box in enumerate(boxes, 1):
        if not isinstance(box, dict):
            continue
        geometry = box.get("geometry") if isinstance(box.get("geometry"), dict) else {}
        positioned = text_box_position_candidate(spec, geometry)
        if not positioned:
            lines.append(f"% Text box {index} omitted: flow-relative or incomplete coordinate origin.")
            continue
        width, x, y = positioned
        lines.append(f"% Text box {index}; source: {box.get('part') or 'unknown source'}")
        lines.append(f"\\begin{{journalpositionedtextbox}}{{{width}}}{{{x}}}{{{y}}}")
        for paragraph in text_box_latex_paragraphs(box):
            lines.append(paragraph + r"\par")
        lines.append("\\end{journalpositionedtextbox}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def section_flow_candidate_file(spec: dict) -> str:
    """Write Word section transitions as commented, boundary-aware helpers."""
    sections = get_nested(spec, "page.section_flow.sections", [])
    lines = [
        "% Optional section-flow candidates reconstructed from Word section XML.",
        "% Do not input this file automatically: place each helper at the",
        "% corresponding semantic manuscript boundary after PDF comparison.",
        "% A continuous Word section does not imply a LaTeX page break.",
        "",
    ]
    if not isinstance(sections, list) or len(sections) <= 1:
        lines.append("% No multi-section Word flow was recorded.")
        return "\n".join(lines) + "\n"
    for index, section in enumerate(sections, 1):
        if not isinstance(section, dict):
            continue
        columns = str(section.get("columns") or "1")
        try:
            column_count = int(columns)
        except (TypeError, ValueError):
            column_count = 1
        break_type = str(section.get("section_break_type") or "unspecified")
        widths = section.get("column_widths_twips") or []
        lines.append(
            f"% Section {index}: {column_count} column(s); break={break_type}; "
            f"page={section.get('page_width_twips') or '?'}x{section.get('page_height_twips') or '?'} twips"
        )
        if widths:
            lines.append(f"% Source unequal column widths (twips): {', '.join(str(item) for item in widths)}")
        if index > 1 and break_type.lower() not in {"continuous", "unspecified"}:
            lines.append("% \\journalsectionpagebreak")
        if column_count >= 2:
            lines.append("% \\journalstartdoublecolumn")
        else:
            lines.append("% \\journalstartsinglecolumn")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def page_frame_candidate_file(spec: dict) -> str:
    """Write per-section Word page-frame candidates without auto-applying them."""
    sections = get_nested(spec, "page.section_flow.sections", [])
    lines = [
        "% Optional page-frame candidates reconstructed from Word section XML.",
        "% Do not input this file automatically: each frame may belong to a",
        "% cover, front-matter block, body transition, or local section only.",
        "% A continuous section must not be turned into a page break without PDF proof.",
        "",
    ]
    if not isinstance(sections, list) or not sections:
        lines.append("% No Word section frame evidence was recorded.")
        return "\n".join(lines) + "\n"

    def mm(value: object) -> str:
        try:
            return f"{float(value) * 25.4 / 1440:.2f}mm"
        except (TypeError, ValueError):
            return "unknown"

    for index, section in enumerate(sections, 1):
        if not isinstance(section, dict):
            continue
        margins = section.get("margins_twips") if isinstance(section.get("margins_twips"), dict) else {}
        break_type = str(section.get("section_break_type") or "unspecified")
        lines.append(
            f"% Section {index}: break={break_type}; page="
            f"{mm(section.get('page_width_twips'))} x {mm(section.get('page_height_twips'))}; "
            f"columns={section.get('columns') or 1}"
        )
        source_margins = ", ".join(
            f"{key}={mm(margins.get(key))}"
            for key in ("top", "right", "bottom", "left", "header", "footer", "gutter")
        )
        lines.append(f"% Source margins: {source_margins}")
        if index > 1 and break_type.lower() not in {"continuous", "unspecified"}:
            lines.append("% \\clearpage")
        lines.append(
            f"% \\newgeometry{{paperwidth={mm(section.get('page_width_twips'))},"
            f"paperheight={mm(section.get('page_height_twips'))},"
            f"top={mm(margins.get('top'))},right={mm(margins.get('right'))},"
            f"bottom={mm(margins.get('bottom'))},left={mm(margins.get('left'))}}}"
        )
        lines.append("% Header/footer edge distances remain separate evidence; calibrate headsep/footskip from a rendered page.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def representative_table_fixture(spec: dict) -> str:
    """Exercise the extracted Word table geometry in the editable fixture."""
    layout = get_nested(spec, "tables.layout_evidence", {})
    widths = layout.get("grid_column_widths_twips", []) if isinstance(layout, dict) else []
    count = len(widths) if isinstance(widths, list) and 2 <= len(widths) <= 8 else 3
    colspec = representative_table_colspec(spec)
    replayed_source = source_table_fixture(spec, count, colspec)
    if replayed_source:
        return replayed_source
    header_cells = table_header_fixture_cells(spec, count)
    headers = " & ".join(rf"\journaltableheadercell{{{value}}}" for value in header_cells) + r" \\"
    values = " & ".join(f"Item {index + 1}" for index in range(count)) + r" \\"
    tail = " & ".join("Value" for _ in range(max(0, count - 2)))
    merged = rf"\multicolumn{{2}}{{l}}{{Merged cells}}" + (f" & {tail}" if tail else "") + r" \\"
    border_mode = table_border_mode(spec)
    if border_mode == "grid":
        merged = rf"\multicolumn{{2}}{{|c|}}{{Merged cells}}" + (f" & {tail}" if tail else "") + r" \\"
        return rf"""\begin{{tabular}}{{{colspec}}}
\hline
\journaltableheaderrow
{headers}
\hline
{merged}
\hline
{values}
\hline
\end{{tabular}}"""
    if border_mode == "vertical":
        merged = rf"\multicolumn{{2}}{{|c|}}{{Merged cells}}" + (f" & {tail}" if tail else "") + r" \\"
        return rf"""\begin{{tabular}}{{{colspec}}}
\journaltableheaderrow
{headers}
{merged}
{values}
\end{{tabular}}"""
    if border_mode == "horizontal":
        return rf"""\begin{{tabular}}{{{colspec}}}
\hline
\journaltableheaderrow
{headers}
\hline
{merged}
{values}
\hline
\end{{tabular}}"""
    if border_mode == "none":
        return rf"""\begin{{tabular}}{{{colspec}}}
\journaltableheaderrow
{headers}
{merged}
{values}
\end{{tabular}}"""
    return rf"""\begin{{tabular}}{{{colspec}}}
\toprule
\journaltableheaderrow
{headers}
\midrule
{merged}
{values}
\bottomrule
\end{{tabular}}"""


def body_asset_paths(asset_manifest: Path | None) -> list[str]:
    """Return editable body-image paths extracted from the Word source."""
    if asset_manifest is None or not asset_manifest.exists():
        return []
    try:
        manifest = json.loads(asset_manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    candidates = []
    for asset in manifest.get("assets", []):
        if not isinstance(asset, dict) or "body" not in (asset.get("roles") or []):
            continue
        if asset.get("latex_compatible") is False:
            continue
        output = asset.get("latex_output") or asset.get("output")
        if output:
            candidates.append((int(asset.get("bytes") or 0), str(output).replace("\\", "/")))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [path for _, path in candidates]


def captioned_float_fixture(
    spec: dict,
    kind: str,
    content: str,
    caption: str,
    label: str,
    *,
    use_representative_span: bool = True,
) -> str:
    """Exercise the source-backed caption order in the editable starter body."""
    environment = "journaltable" if kind == "table" else "journalfigure"
    span = get_nested(spec, f"{kind}s.layout_evidence.span_evidence", {})
    if (
        use_representative_span
        and isinstance(span, dict)
        and span.get("status") == "source"
        and span.get("mode") == "double_column"
    ):
        environment += "wide"
    default = "above" if kind == "table" else "below"
    position = str(get_nested(spec, f"{kind}s.caption_position", default) or default).lower()
    caption_block = f"\\caption{{{caption}}}\n\\label{{{label}}}"
    body = f"{caption_block}\n{content}" if position == "above" else f"{content}\n{caption_block}"
    return f"\\begin{{{environment}}}\n{body}\n\\end{{{environment}}}"


def default_body_block(
    sample_citation: str,
    spec: dict,
    asset_manifest: Path | None = None,
    *,
    include_source_body_assets: bool = False,
) -> str:
    """Return a compileable fixture that exercises every core class interface.

    Word body artwork normally belongs to the sample manuscript, not the
    reusable journal template. Keep extracted files in ``assets/`` as evidence,
    but use a neutral placeholder in ``main.tex`` unless a caller explicitly
    requests content conversion rather than template reconstruction.
    """
    language = str(get_nested(spec, "journal.language", "en") or "en").lower()
    is_cjk = language in {"zh", "mixed"}
    labels = {
        "table_note": "\u793a\u4f8b\u8868\u6ce8\u3002",
        "table_caption": "\u5e26\u8868\u6ce8\u7684\u793a\u4f8b\u8868",
        "figure_caption": "\u793a\u4f8b\u56fe\u7247\u5360\u4f4d\u7b26",
        "list_section": "\u5217\u8868\u9a8c\u8bc1",
        "list_item": "\u8bf7\u66ff\u6362\u4e3a\u53ef\u7f16\u8f91\u7684\u5217\u8868\u9879\u3002",
        "nested_item": "\u5d4c\u5957\u5217\u8868\u9879\u3002",
        "list_check": "\u8bf7\u4e0e\u539f\u6a21\u677f\u5bf9\u7167\u5217\u8868\u7f29\u8fdb\u3002",
        "endnote": "\u793a\u4f8b\u5c3e\u6ce8\u3002",
        "section": "\u6a21\u677f\u9a8c\u8bc1\u6837\u7a3f",
        "intro": "\u6b64\u53ef\u7f16\u8f91\u6837\u7a3f\u7528\u4e8e\u68c0\u67e5\u6b63\u6587\u3001\u7f29\u8fdb\u3001\u5f15\u6587\u548c\u4ea4\u53c9\u5f15\u7528\u3002\u5176\u4e2d\u5305\u542b\u4e00\u4e2a\u811a\u6ce8",
        "footnote": "\u793a\u4f8b\u811a\u6ce8\u3002",
        "second": "\u4e8c\u7ea7\u6807\u9898",
        "second_check": "\u68c0\u67e5\u4e8c\u7ea7\u6807\u9898\u7684\u95f4\u8ddd\u3002",
        "third": "\u4e09\u7ea7\u6807\u9898",
        "third_check": "\u68c0\u67e5\u4e09\u7ea7\u6807\u9898\u7684\u683c\u5f0f\u3002",
        "fourth": "\u56db\u7ea7\u6807\u9898",
        "fifth": "\u4e94\u7ea7\u6807\u9898",
        "run_in": "\u884c\u5185\u6587\u5b57\u3002",
        "math_section": "\u516c\u5f0f\u3001\u8868\u683c\u4e0e\u56fe\u7247",
        "results": "\u7ed3\u679c",
        "results_text": None,
    } if is_cjk else {
        "table_note": "Example table note.",
        "table_caption": "Example table with notes",
        "figure_caption": "Example figure placeholder",
        "list_section": "List Verification",
        "list_item": "Replace with an editable list item.",
        "nested_item": "Nested list item.",
        "list_check": "Verify list indentation against the source.",
        "endnote": "Example endnote.",
        "section": "Template Verification Fixture",
        "intro": "This editable fixture checks body text, indentation, citations, and cross-references. It includes a footnote",
        "footnote": "Example footnote.",
        "second": "Second-Level Heading",
        "second_check": "Check the second-level heading spacing.",
        "third": "Third-Level Heading",
        "third_check": "Check the third-level heading.",
        "fourth": "Fourth",
        "fifth": "Fifth",
        "run_in": "Run-in.",
        "math_section": "Equation, Table, and Figure",
        "results": "Results",
        "results_text": None,
    }
    if is_cjk:
        labels["results_text"] = (
            f"\u53c2\u89c1\u8868~\\ref{{tab:example}}\u3001\u56fe~\\ref{{fig:example}}"
            f"\u4e0e\u516c\u5f0f~\\ref{{eq:sample}}\uff1b\u5f15\u7528 {sample_citation}\u3002"
        )
    else:
        labels["results_text"] = (
            f"See Table~\\ref{{tab:example}}, Figure~\\ref{{fig:example}}, "
            f"and Equation~\\ref{{eq:sample}}; cite {sample_citation}."
        )
    table_fixture = representative_table_fixture(spec)
    body_assets = body_asset_paths(asset_manifest) if include_source_body_assets else []
    if body_assets:
        figure_source = rf"\includegraphics[width=\journalfigurerepresentativewidth,height=\journalfigurerepresentativeheight,keepaspectratio]{{assets/{latex_escape(body_assets[0])}}}"
    else:
        figure_source = r"\fbox{\rule{0pt}{\journalfigurerepresentativeheight}\rule{\dimexpr\journalfigurerepresentativewidth-2\fboxsep-2\fboxrule\relax}{0pt}}"
    table_content = rf"""\begin{{threeparttable}}
{table_fixture}
\begin{{tablenotes}}
\small
\item {labels["table_note"]}
\end{{tablenotes}}
\end{{threeparttable}}"""
    table_float = captioned_float_fixture(
        spec, "table", table_content, labels["table_caption"], "tab:example"
    )
    figure_float = captioned_float_fixture(
        spec, "figure", figure_source, labels["figure_caption"], "fig:example"
    )
    list_evidence = get_nested(spec, "body.lists", {})
    list_fixture = ""
    if isinstance(list_evidence, dict) and list_evidence.get("present"):
        environment = "journalitemize" if list_evidence.get("kind") == "itemize" else "journalenumerate"
        nested = ""
        levels = list_evidence.get("levels_seen", [])
        if isinstance(levels, list) and len(levels) > 1:
            nested = f"\n\\begin{{journalitemize}}\n\\item {labels['nested_item']}\n\\end{{journalitemize}}"
        list_fixture = rf"""
\section{{{labels["list_section"]}}}
\begin{{{environment}}}
\item {labels["list_item"]}{nested}
\item {labels["list_check"]}
\end{{{environment}}}
"""
    endnote_fixture = ""
    if get_nested(spec, "endnotes.enabled", False):
        endnote_fixture = (
            f"\n\\journalendnote{{{labels['endnote']}}}\n"
            "\\printjournalendnotes\n"
        )
    return rf"""\section{{{labels["section"]}}}
{labels["intro"]}\footnote{{{labels["footnote"]}}}.

\subsection{{{labels["second"]}}}
{labels["second_check"]}

\subsubsection{{{labels["third"]}}}
{labels["third_check"]}

\paragraph{{{labels["fourth"]}}}
{labels["run_in"]}

\subparagraph{{{labels["fifth"]}}}
{labels["run_in"]}

\section{{{labels["math_section"]}}}

\begin{{journalequation}}
E = mc^2
\label{{eq:sample}}
\end{{journalequation}}

{table_float}

{figure_float}

\section{{{labels["results"]}}}
{labels["results_text"]}
{list_fixture}
{endnote_fixture}
"""


def body_block_from_spec(spec: dict, sample_citation: str, asset_manifest: Path | None = None) -> str:
    sections = get_nested(spec, "body.sections", [])
    if not sections:
        return default_body_block(sample_citation, spec, asset_manifest)
    blocks = []
    for section in sections:
        source_title = str(section.get("title", "Section")).strip() or "Section"
        normalized_source = source_title.lower().strip("* ")
        # Front-matter samples and bibliographic examples are evidence for the
        # class, not manuscript body content to copy into a clean template.
        is_long_instruction = len(normalized_source) > 100
        is_labeled_example = normalized_source.startswith(("keywords:", "keyword:", "figure ", "table "))
        is_template_instruction = any(
            marker in normalized_source
            for marker in (
                "how to use this template",
                "may have a footer",
                "instruction",
                "instructions for authors",
                "author instructions",
                "submission guidelines",
                "formatting guidelines",
                "manuscript guidelines",
                "please insert",
                "please replace",
                "do not use",
                "delete this",
                "replace this",
            )
        )
        is_appendix_heading = normalized_source in {"appendix", "appendices"} or normalized_source.startswith(("appendix ", "appendices ")) or source_title.startswith(("\u9644\u5f55", "\u9644\u9304"))
        is_chinese_abstract = source_title.startswith(("\u6458\u8981", "\u4e2d\u6587\u6458\u8981", "\u82f1\u6587\u6458\u8981"))
        is_chinese_references = "\u53c2\u8003\u6587\u732e" in source_title
        if (
            normalized_source in {"template front matter", "abstract", "highlights", "references", "acknowledgements", "acknowledgments"}
            or is_chinese_abstract
            or is_chinese_references
            or is_appendix_heading
            or is_long_instruction
            or is_labeled_example
            or is_template_instruction
        ):
            continue
        source_level = section.get("level")
        try:
            level = max(0, min(4, int(source_level)))
        except (TypeError, ValueError):
            match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?[.)]?\s+", source_title)
            level = 0 if not match else sum(1 for group in match.groups()[1:] if group)
        raw_title = re.sub(r"^(?:\d+|[A-Za-z])(?:\.\d+)*[.)]?\s+", "", source_title)
        title = latex_escape(raw_title or "Section")
        command = [r"\section", r"\subsection", r"\subsubsection", r"\paragraph", r"\subparagraph"][level]
        blocks.append(f"{command}{{{title}}}")
        blocks.append("Replace with editable manuscript content.")
        blocks.append("")
    fixture = default_body_block(sample_citation, spec, asset_manifest)
    if not blocks:
        return fixture
    # Source-derived headings prove the mapping. The fixture below proves that
    # the delivered class actually compiles the table, figure, equation,
    # footnote, citation, and cross-reference paths as well.
    return "\n".join(blocks).strip() + "\n\n" + fixture


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", help="template_spec.json")
    parser.add_argument("--outdir", default="latex-package")
    parser.add_argument("--word-source", help="Optional DOC/DOCX/DOCM/DOT/DOTX/DOTM/RTF source from which to copy embedded assets")
    parser.add_argument("--source-inventory", help="Optional source_inventory.json to copy into the generated package; a sibling file is auto-discovered")
    parser.add_argument("--format-ledger", help="Optional word_format_ledger.json to copy into the generated package")
    parser.add_argument("--promotion-report", help="Accepted promotion_report.json for a render_verified page/body/placement/float-spacing/backmatter/appendix boundary calibration")
    parser.add_argument("--apply-source-header-assets", action="store_true", help="Apply Word XML header/footer asset candidates after render confirmation")
    parser.add_argument("--apply-first-page-furniture", action="store_true", help="Apply a render-confirmed Word first-page header/footer candidate")
    parser.add_argument("--apply-render-probe", action="store_true", help="Temporarily apply regression-only page/body/placement/float-spacing/backmatter/appendix boundary probes from a separate candidate spec")
    args = parser.parse_args()

    spec_path = Path(args.spec).expanduser().resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec.setdefault("document", {})["class_strategy"] = "cls"
    for fallback in spec.get("fallbacks", []):
        if isinstance(fallback, dict) and fallback.get("latex_location") == "journal-template.sty":
            fallback["latex_location"] = "journal-template.cls"
    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "figures").mkdir(exist_ok=True)
    (outdir / "assets").mkdir(exist_ok=True)
    inventory_candidate = Path(args.source_inventory).expanduser().resolve() if args.source_inventory else spec_path.parent / "source_inventory.json"
    format_ledger_path = None
    format_ledger_data = None
    if args.source_inventory and not inventory_candidate.is_file():
        raise SystemExit(f"--source-inventory does not exist: {inventory_candidate}")
    if inventory_candidate.is_file():
        inventory_path = inventory_candidate
        (outdir / "source_inventory.json").write_bytes(inventory_path.read_bytes())
    if args.format_ledger:
        ledger_path = Path(args.format_ledger).expanduser().resolve()
        if not ledger_path.is_file():
            raise SystemExit(f"--format-ledger does not exist: {ledger_path}")
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--format-ledger is not valid JSON: {exc}") from exc
        if ledger.get("schema_version") != "temp2tex.word-format-ledger.v1":
            raise SystemExit("--format-ledger has an unsupported schema_version")
        (outdir / "word_format_ledger.json").write_bytes(ledger_path.read_bytes())
        format_ledger_path = ledger_path
        format_ledger_data = ledger

    language = get_nested(spec, "journal.language", "en")
    title = get_nested(spec, "journal.name", "Journal Template")
    asset_manifest = None
    asset_extraction_error = None
    if args.word_source:
        try:
            asset_manifest = extract_assets(Path(args.word_source), outdir / "assets")
            spec.setdefault("assets", {})["extracted_manifest"] = str(asset_manifest.relative_to(outdir))
        except ValueError as exc:
            asset_extraction_error = str(exc)
            spec.setdefault("assets", {})["extraction_error"] = asset_extraction_error
    if args.apply_source_header_assets:
        spec.setdefault("page", {})["header_footer_auto_apply"] = True
        spec["page"]["first_page_style"] = "fancy"
    if args.apply_first_page_furniture:
        spec.setdefault("page", {})["first_page_furniture_auto_apply"] = True
    if args.apply_render_probe:
        probes = []
        for owner in ("page", "document"):
            calibration = spec.setdefault(owner, {}).get("render_calibration")
            if isinstance(calibration, dict) and calibration.get("status") == "render_probe":
                probes.append(calibration)
        for owner in ("figures", "tables"):
            calibration = get_nested(spec, f"{owner}.layout_evidence.placement_calibration", {})
            if isinstance(calibration, dict) and calibration.get("status") == "render_probe":
                probes.append(calibration)
        calibration = get_nested(spec, "page.float_spacing_calibration", {})
        if isinstance(calibration, dict) and calibration.get("status") == "render_probe":
            probes.append(calibration)
        calibration = get_nested(spec, "appendices.layout_evidence.boundary_calibration", {})
        if isinstance(calibration, dict) and calibration.get("status") == "render_probe":
            probes.append(calibration)
        calibration = get_nested(spec, "statements.layout_evidence.boundary_calibration", {})
        if isinstance(calibration, dict) and calibration.get("status") == "render_probe":
            probes.append(calibration)
        if not probes:
            raise SystemExit("--apply-render-probe requires a separate spec with an allowed calibration status=render_probe")
        probe_ledger_spec = copy.deepcopy(spec)
        # This mutation applies only to the generated candidate package. The
        # original source spec remains pending until comparison accepts it.
        for calibration in probes:
            calibration["status"] = "render_verified"
    verified_render_calibrations = [
        f"{owner}.render_calibration"
        for owner in ("page", "document")
        if isinstance(get_nested(spec, f"{owner}.render_calibration", {}), dict)
        and str(get_nested(spec, f"{owner}.render_calibration.status", "")).lower() in {"verified", "render_verified"}
    ]
    verified_render_calibrations.extend(
        f"{owner}.layout_evidence.placement_calibration"
        for owner in ("figures", "tables")
        if str(get_nested(spec, f"{owner}.layout_evidence.placement_calibration.status", "")).lower() in {"verified", "render_verified"}
    )
    if str(get_nested(spec, "page.float_spacing_calibration.status", "")).lower() in {"verified", "render_verified"}:
        verified_render_calibrations.append("page.float_spacing_calibration")
    if str(get_nested(spec, "appendices.layout_evidence.boundary_calibration.status", "")).lower() in {"verified", "render_verified"}:
        verified_render_calibrations.append("appendices.layout_evidence.boundary_calibration")
    if str(get_nested(spec, "statements.layout_evidence.boundary_calibration.status", "")).lower() in {"verified", "render_verified"}:
        verified_render_calibrations.append("statements.layout_evidence.boundary_calibration")
    promotion_report = None
    if args.promotion_report:
        promotion_path = Path(args.promotion_report).expanduser().resolve()
        if not promotion_path.is_file():
            raise SystemExit(f"--promotion-report does not exist: {promotion_path}")
        promotion_report = json.loads(promotion_path.read_text(encoding="utf-8"))
        if promotion_report.get("accepted") is not True or promotion_report.get("status") != "accepted":
            raise SystemExit("--promotion-report must be an accepted strict render-probe report")
        if not verified_render_calibrations:
            raise SystemExit("--promotion-report requires a spec with a render_verified calibration")
        active_report_paths = set(promotion_report.get("active_calibration_paths") or [])
        if active_report_paths and not active_report_paths.intersection(verified_render_calibrations):
            raise SystemExit("--promotion-report does not authorize any render_verified calibration in this spec")
        (outdir / "promotion_report.json").write_bytes(promotion_path.read_bytes())
    class_base = class_base_from_spec(spec, language)
    font_setup = font_setup_from_spec(spec, language)
    if language in {"zh", "mixed"}:
        # Word abstract paragraphs are often instructions or sample filler.
        # Retain them in template_spec.json as evidence, never as manuscript
        # content in the editable template.
        abstract_text = "请在此填写中文摘要；如期刊要求双语摘要，请在中文摘要后添加英文摘要。"
        keywords_label = "关键词："
        title = "中文论文标题"
        author_metadata = r"第一作者\correspondingauthor{email@example.com} \and 第二作者"
        primary_affiliation = "模板工程系，示例大学"
        secondary_affiliation = "可复现排版学院，示例研究院"
        keywords_text = "关键词一；关键词二；关键词三"
    else:
        # Source examples and instructions are evidence, not manuscript
        # content. Use a neutral editable fixture in main.tex.
        abstract_text = "Replace this with the journal abstract. Match the official template word limit, indentation, and heading style."
        keywords_label = "Keywords:"
        author_metadata = r"First Author\correspondingauthor{email@example.com} \and Second Author"
        primary_affiliation = "Department of Template Engineering, Example University"
        secondary_affiliation = "School of Reproducible Typesetting, Example Institute"
        keywords_text = "keyword one; keyword two; keyword three"
    source_keyword_label = get_nested(spec, "abstracts.keyword_label", None)
    if isinstance(source_keyword_label, str) and source_keyword_label.strip():
        keywords_label = source_keyword_label.strip()
    abstract_text = latex_escape(str(abstract_text))
    bilingual_metadata = ""
    if language == "mixed":
        english_abstract_text = "Replace with the English abstract when the official template requires bilingual abstracts."
        bilingual_metadata = (
            "\\englishtitle{English Title of the Manuscript}\n"
            "\\englishauthor{First Author; Second Author}\n"
            "\\englishaffiliation{Department of Template Engineering, Example University}\n"
            f"\\englishabstract{{{latex_escape(str(english_abstract_text))}}}\n"
            "\\englishkeywords{keyword one; keyword two; keyword three}\n"
        )
    english_abstract_block = "\\printenglishabstract" if language == "mixed" else ""
    english_frontmatter_block = "\\printenglishfrontmatter" if language == "mixed" else ""

    reference_style = str(get_nested(spec, "references.style", "numeric")).lower()
    if reference_style in {"author-year", "authoryear", "author_date", "author-date"}:
        citation_setup = r"\RequirePackage[authoryear,round]{natbib}"
        sample_citation = r"\citep{sample-ref}"
        bibitem_label = r"[Author(2026)]{sample-ref}"
    else:
        citation_setup = r"\RequirePackage[numbers,sort&compress]{natbib}"
        sample_citation = r"\citep{sample-ref}"
        bibitem_label = r"{sample-ref}"

    if get_nested(spec, "body.line_numbers", False):
        line_number_package = "\n" + r"\RequirePackage{lineno}"
        line_number_setup = r"\linenumbers"
    else:
        line_number_package = ""
        line_number_setup = ""
    indent_first_package = "\n" + r"\RequirePackage{indentfirst}" if requires_first_paragraph_indent(spec) else ""

    highlights = ""
    if get_nested(spec, "front_matter.highlights", False):
        guidance = get_nested(spec, "front_matter.highlights_guidance", [])
        if guidance:
            highlights = "\\section*{Highlights}\n" + paragraph_block(guidance) + "\n\\clearpage\n"
        else:
            highlights = "\\section*{Highlights}\n\\begin{itemize}\n\\item Replace with short journal-compliant highlight.\n\\end{itemize}\n\\clearpage\n"
    graphical = ""
    if get_nested(spec, "front_matter.graphical_abstract", False):
        graphical = "\\section*{Graphical Abstract}\n\\fbox{\\rule{0pt}{30mm}\\rule{0.8\\linewidth}{0pt}}\n"
    if get_nested(spec, "body.toc", False):
        toc_depth = get_nested(spec, "body.toc_depth", None)
        try:
            toc_depth = max(0, min(5, int(toc_depth)))
        except (TypeError, ValueError):
            toc_depth = None
        toc = (f"\\setcounter{{tocdepth}}{{{toc_depth}}}\n" if toc_depth is not None else "") + "\\tableofcontents\n\\newpage"
    else:
        toc = "% Add \\tableofcontents only if the journal requires it."
    is_cjk_default = language in {"zh", "mixed"}
    if is_cjk_default:
        appendix_title = "\u9644\u5f55\u6807\u9898" if get_nested(spec, "appendices.enabled", True) else "\u9644\u5f55\u9a8c\u8bc1\u6837\u7a3f"
        appendix_intro = (
            "\u9644\u5f55\u56fe\u3001\u8868\u4e0e\u516c\u5f0f\u5e94\u9075\u5faa\u671f\u520a\u7684\u7f16\u53f7\u89c4\u5219\u3002"
            if get_nested(spec, "appendices.enabled", True)
            else "\u5b98\u65b9\u6e90\u6587\u4ef6\u672a\u63d0\u4f9b\u9644\u5f55\u8bc1\u636e\uff0c\u6b64\u53ef\u7f16\u8f91\u6837\u7a3f\u7528\u4e8e\u9a8c\u8bc1\u9644\u5f55\u8ba1\u6570\u5668\u3002"
        )
        appendix_headers = ("\u9879\u76ee", "\u503c")
        appendix_row = ("\u9644\u5f55\u8bc1\u636e", "\u53ef\u7f16\u8f91")
        appendix_table_caption = "\u9644\u5f55\u8868\u683c\u9a8c\u8bc1"
        appendix_figure_caption = "\u9644\u5f55\u56fe\u7247\u9a8c\u8bc1"
    else:
        appendix_title = "Appendix Title" if get_nested(spec, "appendices.enabled", True) else "Optional Appendix Verification"
        appendix_intro = (
            "Appendix figures, tables, and equations should follow the journal numbering policy."
            if get_nested(spec, "appendices.enabled", True)
            else "This editable default exercises appendix counters because the official source did not provide appendix evidence."
        )
        appendix_headers = ("Item", "Value")
        appendix_row = ("Appendix evidence", "Editable")
        appendix_table_caption = "Appendix table verification"
        appendix_figure_caption = "Appendix figure verification"
    appendix_table_content = (
        r"\begin{tabular}{ll}" "\n"
        r"\toprule" "\n"
        f"{appendix_headers[0]} & {appendix_headers[1]} \\\\" "\n"
        r"\midrule" "\n"
        f"{appendix_row[0]} & {appendix_row[1]} \\\\" "\n"
        r"\bottomrule" "\n"
        r"\end{tabular}"
    )
    appendix_table = captioned_float_fixture(
        spec,
        "table",
        appendix_table_content,
        appendix_table_caption,
        "tab:appendix-sample",
        use_representative_span=False,
    )
    appendix_figure = captioned_float_fixture(
        spec,
        "figure",
        r"\fbox{\rule{0pt}{12mm}\rule{0.45\linewidth}{0pt}}",
        appendix_figure_caption,
        "fig:appendix-sample",
        use_representative_span=False,
    )
    appendix = rf"""\journalappendix
\section{{{appendix_title}}}
{appendix_intro}

\begin{{equation}}
a + b = c
\label{{eq:appendix-sample}}
\end{{equation}}

{appendix_table}

{appendix_figure}
"""
    statements = []
    if get_nested(spec, "statements.acknowledgements_before_references", True):
        statements.append("\\section*{Acknowledgements}\nAcknowledge non-author contributions here.")
    if get_nested(spec, "statements.credit_author_statement", False):
        statements.append("\\section*{CRediT Author Statement}\nFirst Author: Conceptualization, Methodology, Writing - original draft. Second Author: Validation, Writing - review and editing.")
    if get_nested(spec, "statements.declaration_of_competing_interest", False):
        statements.append("\\section*{Declaration of Competing Interest}\nThe authors declare no competing interests.")
    if get_nested(spec, "statements.data_availability", False):
        statements.append("\\section*{Data Availability}\nData availability statement placeholder.")
    statements_block = "\n\n".join(statements)

    headings = heading_style(spec)
    source_title_format = source_role_format(spec, "front_matter.title_style", title_format(spec))
    source_author_format = source_role_format(spec, "front_matter.author_style", author_format(spec))
    source_affiliation_format = source_role_format(spec, "front_matter.affiliation_style", r"\normalfont\small")
    source_title_alignment = source_role_alignment(spec, "front_matter.title_style")
    source_author_alignment = source_role_alignment(spec, "front_matter.author_style")
    source_affiliation_alignment = source_role_alignment(spec, "front_matter.affiliation_style")
    source_english_title_format = source_role_format(spec, "front_matter.english_title_style", source_title_format)
    source_english_author_format = source_role_format(spec, "front_matter.english_author_style", source_author_format)
    source_english_affiliation_format = source_role_format(spec, "front_matter.english_affiliation_style", source_affiliation_format)
    source_english_abstract_format = source_role_format(spec, "front_matter.english_abstract_style", r"\normalfont")
    source_english_keywords_format = source_role_format(spec, "front_matter.english_keywords_style", r"\normalfont")
    source_english_title_alignment = source_role_alignment(spec, "front_matter.english_title_style", source_title_alignment)
    source_english_author_alignment = source_role_alignment(spec, "front_matter.english_author_style", source_author_alignment)
    source_english_affiliation_alignment = source_role_alignment(spec, "front_matter.english_affiliation_style", source_affiliation_alignment)
    source_english_abstract_alignment = source_role_alignment(spec, "front_matter.english_abstract_style", r"\raggedright")
    source_english_keywords_alignment = source_role_alignment(spec, "front_matter.english_keywords_style", r"\raggedright")
    abstract_environment_block = abstract_environment(spec)
    (
        keywords_format,
        keywords_label_format,
        keywords_alignment,
        keywords_before_skip,
        keywords_after_skip,
    ) = keyword_setup(spec)
    table_caption_setup = caption_setup(spec, "table", "tables.caption_style", "top")
    figure_caption_setup = caption_setup(spec, "figure", "figures.caption_style", "bottom")
    reference_setup = bibliography_setup(spec)
    source_footnote_setup = footnote_setup(spec)
    source_endnote_setup = endnote_setup(spec)
    # Inline Word header assets are extractable, but renderer behavior can
    # suppress or reposition them. Apply them only after PDF confirmation.
    header_assets = header_asset_setup(
        spec,
        asset_manifest,
        bool(get_nested(spec, "page.header_footer_auto_apply", False)),
    )
    first_page_assets = header_asset_setup(
        spec,
        asset_manifest,
        bool(get_nested(spec, "page.first_page_furniture_auto_apply", False)),
        variant="first",
        command_prefix="firstpage",
    )
    header_footer_defaults = header_footer_slots(spec)
    first_page_footer_defaults = header_footer_slots(spec, preferred_variant="first")
    representative_figure_width, representative_figure_height = representative_figure_dimensions(spec)
    list_left_margin, list_label = list_style_from_spec(spec)
    table_header_row_setup, table_header_cell_format, table_header_strut = table_header_style_from_spec(spec)
    (
        unequal_columns_package,
        journal_column_widths,
        journal_column_ratio_left,
        journal_column_ratio_right,
    ) = unequal_column_setup(spec)
    heading_keep_levels = heading_keep_with_next_levels(spec)
    heading_keep_setup = heading_keep_with_next_setup(spec)
    cls = (
        CLASS_TEMPLATE
        .replace("__DATE__", "2026/07/08")
        .replace("__BASE_OPTIONS__", class_base["base_options"])
        .replace("__BASE_CLASS__", class_base["base_class"])
        .replace("__FONT_SETUP__", font_setup)
        .replace("__HEADING_PAGINATION_PACKAGE__", "\n" + r"\RequirePackage{needspace}" if heading_keep_setup else "")
        .replace("__CITATION_SETUP__", "\n" + citation_setup)
        .replace("__FOOTNOTE_SETUP__", "\n" + source_footnote_setup)
        .replace("__ENDNOTE_SETUP__", "\n" + source_endnote_setup)
        .replace("__LINE_NUMBER_PACKAGE__", line_number_package)
        .replace("__INDENT_FIRST_PACKAGE__", indent_first_package)
        .replace("__UNEQUAL_COLUMNS_PACKAGE__", unequal_columns_package)
        .replace("__GEOMETRY__", mm_geometry(spec))
        .replace("__PARAGRAPH_INDENT__", str(get_nested(spec, "page.paragraph_indent", "1.5em")))
        .replace("__BODY_PARAGRAPH_SKIP__", source_body_parskip(spec))
        .replace("__LINE_SPACING__", "1" if source_body_baseline_pt(spec) is not None else str(get_nested(spec, "page.line_spacing", 1.15)))
        .replace("__PAGE_FURNITURE_GEOMETRY__", page_furniture_geometry_setup(spec))
        .replace("__COLUMN_SEP__", f"{effective_column_sep_mm(spec):g}mm")
        .replace("__FLOAT_SPACING_SETUP__", float_spacing_setup(spec))
        .replace("__APPENDIX_PAGE_BREAK__", appendix_page_break(spec))
        .replace("__BACKMATTER_PAGE_BREAK__", backmatter_page_break(spec))
        .replace("__JOURNAL_COLUMN_WIDTHS__", journal_column_widths)
        .replace("__JOURNAL_COLUMN_RATIO_LEFT__", journal_column_ratio_left)
        .replace("__JOURNAL_COLUMN_RATIO_RIGHT__", journal_column_ratio_right)
        .replace("__BODY_LEFT_INDENT__", content_box_length(spec, "body.content_box", "left"))
        .replace("__BODY_RIGHT_INDENT__", content_box_length(spec, "body.content_box", "right"))
        .replace("__ABSTRACT_LEFT_INDENT__", content_box_length(spec, "abstracts.content_box", "left"))
        .replace("__ABSTRACT_RIGHT_INDENT__", content_box_length(spec, "abstracts.content_box", "right"))
        .replace("__KEYWORD_LEFT_INDENT__", content_box_length(spec, "body.keyword_content_box", "left"))
        .replace("__KEYWORD_RIGHT_INDENT__", content_box_length(spec, "body.keyword_content_box", "right"))
        .replace("__KEYWORDS_LABEL__", latex_escape(keywords_label))
        .replace("__KEYWORDS_FORMAT__", keywords_format)
        .replace("__KEYWORDS_LABEL_FORMAT__", keywords_label_format)
        .replace("__KEYWORDS_ALIGNMENT__", keywords_alignment)
        .replace("__KEYWORDS_BEFORE_SKIP__", keywords_before_skip)
        .replace("__KEYWORDS_AFTER_SKIP__", keywords_after_skip)
        .replace("__JOURNAL_TABLE_WIDTH__", journal_table_width(spec))
        .replace("__JOURNAL_TABLE_COLSPEC__", representative_table_colspec(spec))
        .replace("__TABLE_HEADER_ROW_SETUP__", table_header_row_setup)
        .replace("__TABLE_HEADER_CELL_FORMAT__", table_header_cell_format)
        .replace("__TABLE_HEADER_STRUT__", table_header_strut)
        .replace("__JOURNAL_FIGURE_WIDTH__", representative_figure_width)
        .replace("__JOURNAL_FIGURE_HEIGHT__", representative_figure_height)
        .replace("__FIGURE_ENVIRONMENT__", figure_environment_from_spec(spec))
        .replace("__TABLE_ENVIRONMENT__", table_environment_from_spec(spec))
        .replace("__WIDE_FIGURE_ENVIRONMENT__", wide_figure_environment_from_spec(spec))
        .replace("__WIDE_TABLE_ENVIRONMENT__", wide_table_environment_from_spec(spec))
        .replace("__EQUATION_ENVIRONMENT__", equation_environment_from_spec(spec))
        .replace("__LIST_LEFT_MARGIN__", list_left_margin)
        .replace("__LIST_LABEL__", list_label)
        .replace("__DEFAULT_HEADER_LEFT__", header_footer_defaults["header_left"])
        .replace("__DEFAULT_HEADER_CENTER__", header_footer_defaults["header_center"])
        .replace("__DEFAULT_HEADER_RIGHT__", header_footer_defaults["header_right"])
        .replace("__DEFAULT_FOOTER_LEFT__", header_footer_defaults["footer_left"])
        .replace("__DEFAULT_FOOTER_CENTER__", header_footer_defaults["footer_center"])
        .replace("__DEFAULT_FOOTER_RIGHT__", header_footer_defaults["footer_right"])
        .replace("__DEFAULT_FIRST_PAGE_HEADER_LEFT__", first_page_footer_defaults["header_left"])
        .replace("__DEFAULT_FIRST_PAGE_HEADER_CENTER__", first_page_footer_defaults["header_center"])
        .replace("__DEFAULT_FIRST_PAGE_HEADER_RIGHT__", first_page_footer_defaults["header_right"])
        .replace("__DEFAULT_FIRST_PAGE_FOOTER_LEFT__", first_page_footer_defaults["footer_left"])
        .replace("__DEFAULT_FIRST_PAGE_FOOTER_CENTER__", first_page_footer_defaults["footer_center"])
        .replace("__DEFAULT_FIRST_PAGE_FOOTER_RIGHT__", first_page_footer_defaults["footer_right"])
        .replace(
            "__BODY_COLUMN_TRANSITION__",
            r"\relax",
        )
        .replace("__ABSTRACT_ENVIRONMENT__", abstract_environment_block)
        .replace("__TABLE_CAPTION_SETUP__", table_caption_setup)
        .replace("__FIGURE_CAPTION_SETUP__", figure_caption_setup)
        .replace("__BIBLIOGRAPHY_SETUP__", reference_setup)
        .replace("__PAGE_STYLE_BLOCK__", page_style_block(spec))
        .replace("__SECTION_NUMBERING_SETUP__", section_numbering_setup(spec))
        .replace("__HEADING_KEEP_WITH_NEXT_SETUP__", heading_keep_setup)
        .replace("__SECTION_FORMAT__", headings["section"])
        .replace("__SUBSECTION_FORMAT__", headings["subsection"])
        .replace("__SUBSUBSECTION_FORMAT__", headings["subsubsection"])
        .replace("__PARAGRAPH_FORMAT__", headings["paragraph"])
        .replace("__SUBPARAGRAPH_FORMAT__", headings["subparagraph"])
        .replace("__SECTION_LABEL_SUFFIX__", headings["suffix"])
        .replace("__SECTION_LEFT_INDENT__", heading_length(spec, 0, "left", "0pt"))
        .replace("__SECTION_BEFORE_SKIP__", heading_length(spec, 0, "before", "3.5ex plus 1ex minus .2ex"))
        .replace("__SECTION_AFTER_SKIP__", heading_length(spec, 0, "after", "2.3ex plus .2ex"))
        .replace("__SUBSECTION_LEFT_INDENT__", heading_length(spec, 1, "left", "0pt"))
        .replace("__SUBSECTION_BEFORE_SKIP__", heading_length(spec, 1, "before", "3.25ex plus 1ex minus .2ex"))
        .replace("__SUBSECTION_AFTER_SKIP__", heading_length(spec, 1, "after", "1.5ex plus .2ex"))
        .replace("__SUBSUBSECTION_LEFT_INDENT__", heading_length(spec, 2, "left", "0pt"))
        .replace("__SUBSUBSECTION_BEFORE_SKIP__", heading_length(spec, 2, "before", "3.25ex plus 1ex minus .2ex"))
        .replace("__SUBSUBSECTION_AFTER_SKIP__", heading_length(spec, 2, "after", "1.5ex plus .2ex"))
        .replace("__PARAGRAPH_LEFT_INDENT__", heading_length(spec, 3, "left", "0pt"))
        .replace("__PARAGRAPH_BEFORE_SKIP__", heading_length(spec, 3, "before", "2.5ex plus .5ex minus .2ex"))
        .replace("__PARAGRAPH_AFTER_SKIP__", heading_length(spec, 3, "after", "0.75em"))
        .replace("__SUBPARAGRAPH_LEFT_INDENT__", heading_length(spec, 4, "left", "0pt"))
        .replace("__SUBPARAGRAPH_BEFORE_SKIP__", heading_length(spec, 4, "before", "2.0ex plus .5ex minus .2ex"))
        .replace("__SUBPARAGRAPH_AFTER_SKIP__", heading_length(spec, 4, "after", "0.75em"))
        .replace("__SECNUMDEPTH__", "5" if any(get_nested(spec, f"body.heading_styles.level{level}", {}) for level in (3, 4)) else "3")
        .replace("__CAPTION_SKIP__", class_length(spec, "captions.skip", "4pt"))
        .replace("__FIRST_PAGE_STYLE__", first_page_style(spec))
        .replace("__TITLE_TOP_SKIP__", class_length(spec, "front_matter.title_top_skip", source_role_before_skip(spec, "front_matter.title_style", "0pt")))
        .replace("__TITLE_ALIGNMENT__", source_title_alignment)
        .replace("__TITLE_FORMAT__", source_title_format)
        .replace("__ENGLISH_TITLE_ALIGNMENT__", source_english_title_alignment)
        .replace("__ENGLISH_TITLE_FORMAT__", source_english_title_format)
        .replace("__TITLE_AFTER_SKIP__", class_length(spec, "front_matter.title_after_skip", front_matter_boundary_skip(spec, "title_to_author", source_role_transition_skip(spec, "front_matter.title_style", "front_matter.author_style", "8pt"))))
        .replace("__AUTHOR_FORMAT__", source_author_format)
        .replace("__AUTHOR_ALIGNMENT__", source_author_alignment)
        .replace("__ENGLISH_AUTHOR_FORMAT__", source_english_author_format)
        .replace("__ENGLISH_AUTHOR_ALIGNMENT__", source_english_author_alignment)
        .replace("__AUTHOR_RENDER__", author_rendering(spec))
        .replace("__AUTHOR_AFTER_SKIP__", class_length(spec, "front_matter.author_after_skip", front_matter_boundary_skip(spec, "author_to_affiliation", source_role_transition_skip(spec, "front_matter.author_style", "front_matter.affiliation_style", "6pt"))))
        .replace("__AFFILIATION_FORMAT__", source_affiliation_format)
        .replace("__AFFILIATION_ALIGNMENT__", source_affiliation_alignment)
        .replace("__ENGLISH_AFFILIATION_FORMAT__", source_english_affiliation_format)
        .replace("__ENGLISH_AFFILIATION_ALIGNMENT__", source_english_affiliation_alignment)
        .replace("__ENGLISH_ABSTRACT_FORMAT__", source_english_abstract_format)
        .replace("__ENGLISH_ABSTRACT_ALIGNMENT__", source_english_abstract_alignment)
        .replace("__ENGLISH_KEYWORDS_FORMAT__", source_english_keywords_format)
        .replace("__ENGLISH_KEYWORDS_ALIGNMENT__", source_english_keywords_alignment)
        # The affiliation-to-abstract boundary is emitted once after
        # \maketitle. Keeping an additional affiliation skip would duplicate
        # Word paragraph spacing at the same semantic boundary.
        .replace("__AFFILIATION_AFTER_SKIP__", "0pt")
        .replace("__MAKETITLE_AFTER_SKIP__", class_length(
            spec,
            "front_matter.maketitle_after_skip",
            front_matter_boundary_skip(
                spec,
                "affiliation_to_abstract",
                source_role_transition_skip(
                    spec,
                    "front_matter.affiliation_style",
                    abstract_entry_role_path(spec),
                    "12pt",
                ),
            ),
        ))
        .replace("__BILINGUAL_FRONTMATTER_SKIP__", class_length(spec, "front_matter.bilingual_frontmatter_skip", "12pt"))
        .replace("__LINE_NUMBER_SETUP__", line_number_setup)
    )
    main = MAIN_TEMPLATE.format(
        title=title,
        author_metadata=author_metadata,
        primary_affiliation=primary_affiliation,
        secondary_affiliation=secondary_affiliation,
        bilingual_metadata=bilingual_metadata,
        header_asset_setup="\n".join(item for item in (header_assets, first_page_assets) if item),
        highlights=highlights,
        graphical_abstract=graphical,
        abstract_text=abstract_text,
        english_abstract_block=english_abstract_block,
        english_frontmatter_block=english_frontmatter_block,
        front_matter_column_begin=r"\twocolumn[" if bool(get_nested(spec, "front_matter.body_column_transition_after_front_matter", False)) else "",
        front_matter_column_end="]" if bool(get_nested(spec, "front_matter.body_column_transition_after_front_matter", False)) else "",
        text_box_layout_block=r"\input{textboxes-active.tex}" if bool(get_nested(spec, "assets.text_boxes_auto_apply", False)) else "",
        # Unequal-column flow is a render-confirmed candidate. Keep the
        # ordinary fixture in the source-backed baseline and expose the
        # candidate macros in the class and README instead of enabling an
        # independent-column output routine silently.
        unequal_columns_begin="",
        unequal_columns_end="",
        keywords_label=keywords_label,
        keywords_text=keywords_text,
        toc_block=toc,
        body_block=body_block_from_spec(spec, sample_citation, asset_manifest),
        appendix_block=appendix,
        statements_block=statements_block,
        sample_citation=sample_citation,
        bibitem_label=bibitem_label,
    )

    legacy_sty = outdir / "journal-template.sty"
    if legacy_sty.exists():
        legacy_sty.unlink()
    (outdir / "journal-template.cls").write_text(cls, encoding="utf-8")
    (outdir / "main.tex").write_text(main, encoding="utf-8")
    (outdir / "references.bib").write_text(
        "@article{sample-ref,\n"
        "  author = {Author, A.},\n"
        "  title = {Sample reference placeholder},\n"
        "  journal = {Journal Name},\n"
        "  year = {2026}\n"
        "}\n",
        encoding="utf-8",
    )
    equation_candidates = get_nested(spec, "equations.latex_candidates", [])
    if isinstance(equation_candidates, list) and equation_candidates:
        (outdir / "equations.tex").write_text(equation_candidate_file(spec), encoding="utf-8")
    if str(get_nested(spec, "front_matter.cover_mode", "")).startswith("candidate"):
        cover_title = title
        (outdir / "cover.tex").write_text(
            "% Optional first-page candidate reconstructed from Word title-page evidence.\n"
            "% Do not input this file until PDF comparison confirms a standalone cover.\n"
            "\\begin{journalcover}\n"
            "\\begin{center}\n"
            f"{{\\Large\\bfseries {cover_title}\\par}}\n"
            "\\vspace{12pt}\n"
            "{\\normalsize First Author; Second Author\\par}\n"
            "\\vspace{8pt}\n"
            "{\\small Replace with verified cover metadata or artwork.\\par}\n"
            "\\end{center}\n"
            "\\end{journalcover}\n",
            encoding="utf-8",
        )
    if get_nested(spec, "assets.text_boxes", []):
        (outdir / "textboxes.tex").write_text(text_box_candidate_file(spec), encoding="utf-8")
        if bool(get_nested(spec, "assets.text_boxes_auto_apply", False)):
            (outdir / "textboxes-active.tex").write_text(text_box_active_file(spec), encoding="utf-8")
    section_flow_entries = get_nested(spec, "page.section_flow.sections", [])
    if isinstance(section_flow_entries, list) and len(section_flow_entries) > 1:
        (outdir / "section-flow.tex").write_text(section_flow_candidate_file(spec), encoding="utf-8")
        (outdir / "page-frame.tex").write_text(page_frame_candidate_file(spec), encoding="utf-8")
    header_footer_evidence = get_nested(spec, "page.header_footer_evidence", {})
    if isinstance(header_footer_evidence, dict) and (
        header_footer_evidence.get("parts") or header_footer_evidence.get("active_variants")
    ):
        (outdir / "page-furniture.tex").write_text(page_furniture_candidate_file(spec), encoding="utf-8")
    if get_nested(spec, "front_matter.highlights", False):
        (outdir / "highlights.tex").write_text(
            "\\section*{Highlights}\n"
            "\\begin{itemize}\n"
            "\\item Replace with a complete finding under the journal character limit.\n"
            "\\item Replace with a second complete finding.\n"
            "\\item Replace with a third complete finding.\n"
            "\\end{itemize}\n",
            encoding="utf-8",
        )
    if get_nested(spec, "statements.credit_author_statement", False):
        (outdir / "author_statement.tex").write_text(
            "\\section*{Author Statement}\n"
            "First Author: Conceptualization, Methodology, Writing - original draft.\n\n"
            "Second Author: Validation, Writing - review and editing.\n",
            encoding="utf-8",
        )
    output_spec = probe_ledger_spec if args.apply_render_probe else spec
    (outdir / "template_spec.json").write_text(json.dumps(output_spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    fallbacks = spec.get("fallbacks", [])
    gap_lines = ["# Format Gap Log", ""]
    if fallbacks:
        for fb in fallbacks:
            gap_lines.extend([
                f"## {fb.get('area', 'Unspecified area')}",
                f"- Official evidence checked: {fb.get('source_checked', '')}",
                f"- Missing or ambiguous requirement: {fb.get('missing_requirement', '')}",
                f"- Fallback used: {fb.get('fallback_used', '')}",
                f"- LaTeX location: {fb.get('latex_location', '')}",
                "",
            ])
    section_flow = get_nested(spec, "page.section_flow", {})
    section_entries = section_flow.get("sections", []) if isinstance(section_flow, dict) else []
    if isinstance(section_entries, list) and len(section_entries) > 1:
        summary = "; ".join(
            f"section {item.get('index')}: {item.get('columns') or 1} column(s), "
            f"{item.get('section_break_type') or 'unspecified'}"
            for item in section_entries
            if isinstance(item, dict)
        )
        gap_lines.extend([
            "## page.section_flow",
            "- Official evidence checked: every Word section's page frame, column count, and section-break type.",
            f"- Source flow: {summary or 'section entries were present but incomplete.'}",
            "- Missing or ambiguous requirement: LaTeX cannot reproduce every continuous Word section transition without a manuscript boundary and rendered confirmation.",
            "- Fallback used: exposed `\\journalstartsinglecolumn`, `\\journalstartdoublecolumn`, and `\\journalsectionpagebreak`; use them only at the evidenced boundary.",
            "- LaTeX location: journal-template.cls and main.tex",
            "",
        ])
    if unequal_column_layout(spec):
        widths = get_nested(spec, "page.column_widths_twips", [])
        gap_lines.extend([
            "## page.unequal_columns",
            "- Official evidence checked: Word `w:cols/w:col` widths on the representative section.",
            f"- Source column widths: {', '.join(str(item) for item in widths)} twips.",
            "- Missing or ambiguous requirement: ordinary LaTeX two-column output is equal-width; the source requires an unequal-column flow model.",
            "- Fallback used: exposed `\\journalstartunequalcolumns`, `\\journalendunequalcolumns`, and `\\journalcolumnratio` using the source ratio; activate only after rendered confirmation because independent-column packages do not reproduce every Word float and page-flow rule.",
            "- LaTeX location: journal-template.cls and main.tex",
            "",
        ])
    abstract_layout_mode = str(get_nested(spec, "abstracts.layout_mode", "block")).lower()
    abstract_layout_evidence = str(get_nested(spec, "abstracts.layout_evidence", "") or "")
    abstract_label_mode = str(get_nested(spec, "abstracts.label_mode", "default") or "default").lower()
    if abstract_label_mode == "default":
        gap_lines.extend([
            "## abstracts.layout_mode",
            "- Official evidence checked: visible Word abstract label/content paragraphs and their document-flow adjacency.",
            f"- Missing or ambiguous requirement: {abstract_layout_evidence or 'no defensible visible abstract structure was found.'}",
            "- Fallback used: generated an editable block abstract with a separate default label; confirm it against a rendered Word/PDF reference.",
            "- LaTeX location: journal-template.cls",
            "",
        ])
    boundaries = get_nested(spec, "front_matter.spacing_boundaries", {})
    if isinstance(boundaries, dict):
        for name, boundary in boundaries.items():
            if not isinstance(boundary, dict) or boundary.get("status") != "default":
                continue
            gap_lines.extend([
                f"## front_matter.spacing_boundaries.{name}",
                "- Official evidence checked: the preceding Word paragraph space-after and following paragraph space-before values.",
                "- Missing or ambiguous requirement: neither side supplied usable spacing evidence for this semantic boundary.",
                f"- Fallback used: `{boundary.get('resolved_pt', 0):g}pt`, emitted once rather than duplicated on both roles.",
                "- LaTeX location: journal-template.cls and template_spec.json",
                "",
            ])
    cjk_font = str(get_nested(spec, "document.cjk_font_family", "") or "").strip()
    cjk_font_mode = str(get_nested(spec, "document.cjk_font_mode", "default") or "default").lower()
    if language in {"zh", "mixed"} and cjk_font and cjk_font_mode not in {"verified", "render_verified"}:
        gap_lines.extend([
            "## document.cjk_font_family",
            f"- Official evidence checked: Word East Asian body font `{cjk_font}`.",
            "- Missing or ambiguous requirement: local XeLaTeX font availability and rendered equivalence have not been verified.",
            "- Fallback used: apply the source font only when XeLaTeX can find it; otherwise retain the CTeX CJK fallback chain.",
            "- LaTeX location: journal-template.cls",
            "",
        ])
    body_paragraph_format = role_effective_format(spec, "page.source_body_style").get("paragraph", {})
    body_line_spacing = body_paragraph_format.get("line_spacing")
    body_line_rule = str(body_paragraph_format.get("line_spacing_rule") or "").lower()
    body_baseline = source_body_baseline_pt(spec)
    body_comment_evidence = get_nested(spec, "page.source_body_style.comment_format_evidence", {})
    if body_line_rule == "exact" and body_baseline is not None:
        evidence_label = "anchored official Word formatting comment plus selected body evidence" if isinstance(body_comment_evidence, dict) and body_comment_evidence else "Word body style and paragraph-level direct formatting"
        gap_lines.extend([
            "## page.line_spacing",
            f"- Official evidence checked: {evidence_label}.",
            f"- Implemented: fixed source baseline `{body_baseline:g}pt` using an explicit LaTeX body font baseline.",
            "- Remaining verification: confirm rendered body density and glyph metrics against the source PDF; do not replace this physical baseline with a generic line-spread multiplier.",
            "- LaTeX location: journal-template.cls",
            "",
        ])
    elif body_line_spacing is None:
        gap_lines.extend([
            "## page.line_spacing",
            "- Official evidence checked: Word body style and paragraph-level direct formatting.",
            "- Missing or ambiguous requirement: no direct Word line-spacing metric was available for the selected body role.",
            f"- Fallback used: generated line spacing `{get_nested(spec, 'page.line_spacing', 1.15)}`; verify body density against a rendered reference.",
            "- LaTeX location: journal-template.cls",
            "",
        ])
    if heading_keep_levels:
        role_names = ", ".join(command for _, command in heading_keep_levels)
        gap_lines.extend([
            "## body.heading_keep_with_next",
            "- Official evidence checked: Word heading paragraph/style `keepNext` values.",
            f"- Implemented: `{role_names}` reserve two baseline lines before the heading so it stays with following text.",
            "- Remaining gap: exact Word pagination depends on the manuscript and must be checked with a same-content PDF comparison.",
            "- LaTeX location: journal-template.cls",
            "",
        ])
    footnote_count = get_nested(spec, "footnotes.count_in_template", 0)
    footnote_style = get_nested(spec, "footnotes.style", {})
    if footnote_count and not footnote_style:
        gap_lines.extend([
            "## footnotes.style",
            "- Official evidence checked: Word footnotes.xml contains note nodes but no visible footnote paragraph sample.",
            "- Missing or ambiguous requirement: footnote font, paragraph format, marker sequence, and separator rule.",
            "- Fallback used: retained standard LaTeX footnotes; verify against a rendered manuscript containing real notes.",
            "- LaTeX location: journal-template.cls and main.tex",
            "",
        ])
    cover_mode = str(get_nested(spec, "front_matter.cover_mode", "not_detected"))
    if cover_mode.startswith("candidate"):
        gap_lines.extend([
            "## front_matter.cover_mode",
            "- Official evidence checked: Word first-section first-page header/footer variant.",
            "- Missing or ambiguous requirement: a different first page can be an article title-page rule rather than a standalone cover.",
            "- Fallback used: exposed an editable `journalcover` environment without automatically adding a cover page; verify the first rendered page.",
            "- LaTeX location: journal-template.cls and main.tex",
            "",
        ])
    toc_evidence = get_nested(spec, "body.toc_evidence", {})
    if isinstance(toc_evidence, dict) and toc_evidence.get("heading_only_candidate"):
        gap_lines.extend([
            "## body.toc",
            "- Official evidence checked: a Word paragraph labelled Contents/目录 was found without a TOC field.",
            "- Missing or ambiguous requirement: whether that heading represents a required generated table of contents or static sample text.",
            "- Fallback used: did not generate `\\tableofcontents`; verify against a rendered source or author instructions.",
            "- LaTeX location: main.tex",
            "",
        ])
    header_footer_parts = get_nested(spec, "page.header_footer_evidence.parts", [])
    if header_footer_parts and not source_text_furniture_enabled(spec):
        gap_lines.extend([
            "## page.header_footer_position",
            "- Official evidence checked: Word section header/footer distances and XML parts.",
            "- Missing or ambiguous requirement: exact rendered header/footer baseline, asset placement, and first-page behavior have not been confirmed.",
            "- Fallback used: preserved source-backed text in editable later-page slots but left all custom furniture inactive; graphics, rules, and exact placement remain pending PDF comparison.",
            "- LaTeX location: journal-template.cls",
            "",
        ])
    elif header_footer_parts and not bool(get_nested(spec, "page.header_footer_auto_apply", False)):
        gap_lines.extend([
            "## page.header_footer_assets",
            "- Official evidence checked: active Word header/footer parts contain deterministic text/page-field tokens.",
            "- Implemented: enabled the text-only furniture mapping through fancyhdr.",
            "- Remaining gap: drawings, rules, text boxes, and exact baseline geometry stay inactive until PDF comparison confirms their placement.",
            "- LaTeX location: journal-template.cls",
            "",
        ])
    if header_footer_parts:
        gap_lines.extend([
            "## page.furniture_candidates",
            "- Official evidence checked: active Word header/footer parts and their section references.",
            "- Missing or ambiguous requirement: one global fancyhdr mapping cannot prove section-specific header/footer boundaries or asset baselines.",
            "- Fallback used: generated commented per-section `page-furniture.tex` candidates; apply a style only at a semantically confirmed boundary after same-content PDF comparison.",
            "- LaTeX location: page-furniture.tex and journal-template.cls",
            "",
        ])
    active_variants = get_nested(spec, "page.header_footer_evidence.active_variants", [])
    has_first_page_variant = isinstance(active_variants, list) and any(
        isinstance(item, dict) and item.get("variant") == "first" for item in active_variants
    )
    if has_first_page_variant and not bool(get_nested(spec, "page.first_page_furniture_auto_apply", False)):
        gap_lines.extend([
            "## page.first_page_furniture",
            "- Official evidence checked: active Word first-page header/footer variant and related assets.",
            "- Missing or ambiguous requirement: whether the first-page furniture is visible in the rendered article, including its asset baseline and rules.",
            "- Fallback used: exposed editable `\\journalfirstpageheader...` and `\\journalfirstpagefooter...` commands plus the `tempTwoFirstPage` page style without enabling them.",
            "- LaTeX location: journal-template.cls; generate a separate candidate with `--apply-first-page-furniture` only after same-content PDF comparison is available.",
            "",
        ])
    template_style_candidates = []
    default_role_fallbacks = []
    for label, path in [
        ("body", "page.source_body_style"),
        ("title", "front_matter.title_style"),
        ("author", "front_matter.author_style"),
        ("affiliation", "front_matter.affiliation_style"),
        ("abstract", "abstracts.style"),
        ("keywords", "abstracts.keyword_style"),
        ("heading level 1", "body.heading_styles.level0"),
        ("heading level 2", "body.heading_styles.level1"),
        ("heading level 3", "body.heading_styles.level2"),
        ("table caption", "tables.caption_style"),
        ("figure caption", "figures.caption_style"),
        ("references", "references.entry_style"),
    ]:
        evidence = get_nested(spec, path, {})
        if isinstance(evidence, dict):
            if evidence.get("evidence_status") == "template_style_candidate":
                name = str(evidence.get("style_name") or evidence.get("style_id") or "unnamed style")
                template_style_candidates.append(f"{label}: `{name}`")
            elif evidence.get("evidence_status") == "default":
                default_role_fallbacks.append(label)
    if template_style_candidates:
        gap_lines.extend([
            "## template_style_candidate",
            "- Official evidence checked: named paragraph styles in the official Word template.",
            "- Missing or ambiguous requirement: these semantic style mappings have no visible source paragraph yet.",
            "- Fallback used: applied the styles as editable class rules; verify each listed role with a same-content rendered Word working copy.",
            "- Candidate roles: " + "; ".join(template_style_candidates),
            "- LaTeX location: journal-template.cls and template_spec.json",
            "",
        ])
    if default_role_fallbacks:
        gap_lines.extend([
            "## semantic_role_defaults",
            "- Official evidence checked: role-specific Word paragraphs and named styles.",
            "- Missing or ambiguous requirement: no visible semantic exemplar or matching named style was found for the listed roles.",
            "- Fallback used: retained the documented English/Chinese default and marked the role as `default` in template_spec.json; replace it only after source evidence or a same-content render check.",
            "- Default roles: " + ", ".join(default_role_fallbacks),
            "- LaTeX location: journal-template.cls and main.tex",
            "",
        ])
    body_evidence = get_nested(spec, "page.source_body_style", {})
    if isinstance(body_evidence, dict) and body_evidence.get("visible_flow_override_candidate") and effective_body_style_mode(spec) != "visible_flow_exemplar":
        gap_lines.extend([
            "## page.source_body_style.visible_flow_override_candidate",
            "- Official evidence checked: multiple long ordinary-flow Word paragraphs with stable effective formatting.",
            "- Missing or ambiguous requirement: visible direct formatting conflicts with the named body style and may be local instruction content.",
            "- Fallback used: kept the named body style in ordinary output; compare `--body-style-probe` before promoting the candidate.",
            "- LaTeX location: template_spec.json and journal-template.cls",
            "",
        ])
    for level in range(5):
        path = f"body.heading_styles.level{level}"
        heading_font = role_effective_format(spec, path).get("font", {})
        color = str(heading_font.get("color") or "").strip()
        color_mode = str(get_nested(spec, f"{path}.color_mode", "evidence_only") or "evidence_only").lower()
        if re.fullmatch(r"[0-9A-Fa-f]{6}", color) and color.upper() not in {"000000", "FFFFFF"} and color_mode not in {"verified", "render_verified"}:
            gap_lines.extend([
                f"## {path}.color",
                "- Official evidence checked: concrete RGB formatting on the selected Word heading role.",
                "- Missing or ambiguous requirement: template instructional colour can differ from the normalized manuscript heading colour.",
                "- Fallback used: preserved the RGB value in template_spec.json but kept the ordinary heading black; enable it only after a same-content heading-colour probe improves PDF comparison.",
                "- LaTeX location: journal-template.cls and template_spec.json",
                "",
            ])
    if get_nested(spec, "assets.extraction_required", False):
        gap_lines.extend([
            "## assets.word_media",
            "- Official evidence checked: embedded Word media and header/footer parts recorded in template_spec.json.",
            "- Missing or ambiguous requirement: " + (
                f"asset extraction could not complete: {asset_extraction_error}"
                if asset_extraction_error else "asset placement and dimensions require source-render confirmation."
            ),
            f"- Fallback used: {'official Word media was copied to assets/' if asset_manifest else 'assets/ is prepared but Word media has not been copied yet.'}",
            "- LaTeX location: journal-template.cls and main.tex",
            "",
        ])
    table_layout = get_nested(spec, "tables.layout_evidence", {})
    if isinstance(table_layout, dict) and table_layout:
        gap_lines.extend([
            "## tables.layout_evidence",
            "- Official evidence checked: Word table grid, width, alignment, layout mode, and merged-cell markers.",
            "- Missing or ambiguous requirement: a single sample table does not prove the default width or rule treatment for every manuscript table.",
            "- Fallback used: exposed editable `journaltable` and `journaltablewidth` class interfaces; verify representative table widths against a rendered reference.",
            "- LaTeX location: journal-template.cls and main.tex",
            "",
        ])
    figure_layout = get_nested(spec, "figures.layout_evidence", {})
    if isinstance(figure_layout, dict) and figure_layout:
        gap_lines.extend([
            "## figures.layout_evidence",
            "- Official evidence checked: Word body drawing type, dimensions, and alignment candidates.",
            "- Missing or ambiguous requirement: sample artwork dimensions and Word anchor behavior do not prove a universal figure width or float placement rule.",
            "- Fallback used: exposed editable `journalfigure` and `journalfigurewidth` class interfaces; apply source artwork geometry only after rendered comparison.",
            "- LaTeX location: journal-template.cls and main.tex",
            "",
        ])
    for kind in ("table", "figure"):
        span = get_nested(spec, f"{kind}s.layout_evidence.span_evidence", {})
        if isinstance(span, dict) and span.get("status") != "source":
            gap_lines.extend([
                f"## {kind}s.layout_evidence.span_mode",
                "- Official evidence checked: the selected Word object's paragraph, containing section, usable page width, and local column widths.",
                "- Missing or ambiguous requirement: " + str(span.get("reason") or "the object could not be classified safely as column-local or spanning."),
                f"- Fallback used: kept the representative {kind} in the ordinary local `journal{kind}` environment at `\\linewidth`; use the wide helper only after source or rendered evidence confirms a span.",
                f"- LaTeX location: journal-template.cls (`journal{kind}` and `journal{kind}wide`), main.tex, and template_spec.json",
                "",
            ])
    for kind, default in (("table", "above"), ("figure", "below")):
        evidence = get_nested(spec, f"{kind}s.caption_position_evidence", {})
        if isinstance(evidence, dict) and evidence.get("status") == "default":
            position = str(get_nested(spec, f"{kind}s.caption_position", default) or default)
            gap_lines.extend([
                f"## {kind}s.caption_position",
                "- Official evidence checked: Word caption paragraphs and their document-flow adjacency to the selected object.",
                "- Missing or ambiguous requirement: " + str(evidence.get("reason") or "no unambiguous nearby relation was found."),
                f"- Fallback used: `{position}`; this is a documented default, not an official journal rule.",
                "- LaTeX location: journal-template.cls, main.tex, and template_spec.json",
                "",
            ])
        spacing = get_nested(spec, f"{kind}s.caption_spacing_evidence", {})
        if isinstance(spacing, dict) and spacing.get("status") == "default":
            gap_lines.extend([
                f"## {kind}s.caption_spacing_evidence",
                "- Official evidence checked: the two Word paragraph-spacing sides that face across the selected caption/object boundary.",
                "- Missing or ambiguous requirement: source-backed caption order or facing-side spacing was unavailable.",
                f"- Fallback used: internal `{spacing.get('resolved_pt', 4)}pt`, outer `{spacing.get('outer_pt', 0)}pt`; the opposite outside-caption side was not substituted for the missing object gap.",
                "- LaTeX location: journal-template.cls and template_spec.json",
                "",
            ])
    for label, path in [
        ("tables.caption_style", "tables.caption_style"),
        ("figures.caption_style", "figures.caption_style"),
    ]:
        paragraph = role_effective_format(spec, path).get("paragraph", {})
        try:
            left_indent = int(paragraph.get("left_indent_twips")) / 20
        except (TypeError, ValueError):
            left_indent = 0
        if left_indent > 0:
            gap_lines.extend([
                f"## {label}.content_box",
                "- Official evidence checked: used Word caption style with direct left indentation.",
                f"- Missing or ambiguous requirement: caption has a one-sided {left_indent:g}pt content-box indent that standard caption options do not safely reproduce.",
                "- Fallback used: source font, alignment, label weight, and spacing were applied; confirm caption box geometry against a rendered reference.",
                "- LaTeX location: journal-template.cls",
                "",
            ])
    reference_paragraph = role_effective_format(spec, "references.entry_style").get("paragraph", {})
    reference_style_evidence = get_nested(spec, "references.style_evidence", {})
    if isinstance(reference_style_evidence, dict) and str(reference_style_evidence.get("confidence", "")).lower() in {"default", "inferred", "pending"}:
        gap_lines.extend([
            "## references.style",
            "- Official evidence checked: " + str(reference_style_evidence.get("source") or "Word template and official guidance."),
            "- Missing or ambiguous requirement: no explicit source-backed citation system was found.",
            "- Fallback used: `" + str(get_nested(spec, "references.style", "numeric")) + "` citation mode; verify in author instructions, a visible reference list, or an official bibliography style.",
            "- LaTeX location: journal-template.cls, main.tex, and references.bib",
            "",
        ])
    source_margins = get_nested(spec, "page.margins_mm", {})
    if isinstance(source_margins, dict):
        try:
            horizontal_margins = float(source_margins.get("left", 0)) + float(source_margins.get("right", 0))
            vertical_margins = float(source_margins.get("top", 0)) + float(source_margins.get("bottom", 0))
            largest_margin = max(float(source_margins.get(side, 0)) for side in ("top", "right", "bottom", "left"))
        except (TypeError, ValueError):
            horizontal_margins = vertical_margins = largest_margin = 0
        if horizontal_margins > 70 or vertical_margins > 80 or largest_margin > 40:
            gap_lines.extend([
                "## page.margins_mm",
                "- Official evidence checked: Word representative section margins.",
                "- Missing or ambiguous requirement: unusually large Word page margins can encode a content box, title-page layout, or renderer-specific section behavior rather than the final LaTeX page frame.",
                "- Fallback used: preserved the Word section values; compare a same-content rendered PDF before enabling a page.render_calibration override.",
                "- LaTeX location: journal-template.cls and template_spec.json",
                "",
            ])
    try:
        hanging_indent = int(reference_paragraph.get("hanging_twips")) / 20
    except (TypeError, ValueError):
        hanging_indent = 0
    if hanging_indent > 0:
        gap_lines.extend([
            "## references.entry_style.hanging_indent",
            "- Official evidence checked: used Word reference entry with direct hanging indentation.",
            f"- Missing or ambiguous requirement: {hanging_indent:g}pt hanging indent depends on the final bibliography backend and label width.",
            "- Fallback used: source reference font and line spacing were applied; configure the backend-specific hanging indent after rendered verification.",
            "- LaTeX location: journal-template.cls",
            "",
        ])
    float_spacing_evidence = get_nested(spec, "page.float_spacing_evidence", {})
    float_spacing_status = str(float_spacing_evidence.get("status", "default")) if isinstance(float_spacing_evidence, dict) else "default"
    float_spacing_value = float_spacing_evidence.get("resolved_pt", 12) if isinstance(float_spacing_evidence, dict) else 12
    float_spacing_count = float_spacing_evidence.get("eligible_boundary_count", 0) if isinstance(float_spacing_evidence, dict) else 0
    float_spacing_calibration_status = str(get_nested(spec, "page.float_spacing_calibration.status", "not_run"))
    if float_spacing_status == "source" and float_spacing_calibration_status not in {"verified", "render_verified"}:
        gap_lines.extend([
            "## page.float_spacing_calibration",
            f"- Official evidence checked: {float_spacing_count} body-text/object outer Word boundary value(s), aggregated to {float_spacing_value}pt.",
            "- Missing or ambiguous requirement: Word paragraph flow does not identify the corresponding LaTeX output-routine length or prove a journal-wide float policy.",
            "- Fallback used: retained ordinary LaTeX float spacing; test the source value only as a same-content render probe.",
            "- LaTeX location: template_spec.json and journal-template.cls",
            "",
        ])
    if not fallbacks and abstract_label_mode != "default" and not get_nested(spec, "assets.extraction_required", False):
        gap_lines.extend([
            "No fallbacks recorded yet. Add entries for every inferred non-official rule.",
            "",
        ])
    coverage_report = None
    if inventory_candidate.is_file():
        coverage_report = build_coverage(
            json.loads(inventory_candidate.read_text(encoding="utf-8")),
            output_spec,
            outdir,
            format_ledger_data,
        )
        (outdir / "source_feature_coverage.json").write_text(
            json.dumps(coverage_report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if coverage_report["priority_gaps"]:
            gap_lines.extend([
                "## source_feature_coverage",
                "- Source-visible feature audit: `source_feature_coverage.json`.",
                "- Priority gaps must be mapped from the recorded Word evidence before PDF micro-calibration:",
                *[
                    f"  - `{item.get('feature') or item.get('role') or 'unclassified'}`: {item['reason']}"
                    for item in coverage_report["priority_gaps"]
                ],
                "",
            ])
    (outdir / "format_gap_log.md").write_text("\n".join(gap_lines), encoding="utf-8")
    visual_verification_text = (
        "This package contains a render-verified calibration at "
        + ", ".join(f"`{path}`" for path in verified_render_calibrations)
        + ". The calibration was promoted only after same-target structural and visual checks. "
        + ("See `promotion_report.json` for the acceptance gate and metrics. " if promotion_report else "See the calibration acceptance ledger in `template_spec.json`; retain the external promotion report with the audit artifacts. ")
        + "Recompile after manuscript edits and rerun comparison because verification applies to the normalized fixture and recorded reference PDF, not arbitrary future content."
        if verified_render_calibrations and not args.apply_render_probe
        else "This package was generated without claiming that a PDF comparison has completed. Render the official Word source (or use the official PDF), inspect `reference_render_report.json` and use its `selected_reference_pdf`, then compile `main.tex` and run the bundled PDF comparison tool. The comparison run creates `render_compare_report.json`, `layout_profile/`, and `diff_previews/`; until then, visual verification remains pending in `format_gap_log.md`."
    )
    readme_lines = [
        f"# {title}",
        "",
        "## Compile",
        "",
        "```powershell",
        "xelatex -interaction=nonstopmode main.tex",
        "xelatex -interaction=nonstopmode main.tex",
        "```",
        "",
        "The class owns page geometry, front matter, headings, content boxes, captions, and page style. Edit manuscript content in `main.tex`.",
        "",
        "## Source Feature Coverage",
        "",
        (
            f"`source_feature_coverage.json` records {coverage_report['summary']['mapped']} mapped source-visible features, "
            f"{coverage_report['summary']['needs_mapping']} feature(s) needing mapping, and "
            f"{coverage_report['summary']['observed_run_format_spans']} preserved Word run-format span(s). "
            f"The paragraph/run role audit records {coverage_report['summary'].get('ledger_roles_mapped', 'n/a')} source-backed mappings, "
            f"{coverage_report['summary'].get('ledger_roles_needing_mapping', 'n/a')} missing role mapping(s), and "
            f"{coverage_report['summary'].get('ledger_roles_pending_visual_confirmation', 'n/a')} role(s) pending visual confirmation. "
            "Resolve priority gaps before visual micro-calibration."
            if coverage_report
            else "No source inventory was supplied, so source-feature coverage is pending. Inspect the official Word evidence before visual calibration."
        ),
        "",
        *(
            [
                "## Word Format Ledger",
                "",
                "`word_format_ledger.json` preserves the paragraph-and-run evidence used to map title, front matter, headings, body, tables, figures, notes, references, and appendices. Review unresolved mapping entries before changing class-level formatting.",
                "",
            ]
            if format_ledger_path else []
        ),
        "## References",
        "",
        "`main.tex` uses an editable `thebibliography` fixture by default so the package compiles without a publisher-specific BibTeX backend. `references.bib` is provided as the editable database; when the official journal supplies a `.bst` or BibLaTeX backend, replace the fixture with the official bibliography commands and run the required backend before comparing PDFs.",
        "",
        "## Visual Verification",
        "",
        visual_verification_text,
        "",
        "```powershell",
        "python <temp2tex-skill>/scripts/render_docx_reference.py <official-template.docx> --outdir reference-render",
        "python <temp2tex-skill>/scripts/compare_pdfs.py reference-render/<source-stem>.word.pdf main.pdf --outdir render-compare",
        "python <temp2tex-skill>/scripts/profile_pdf_layout.py reference-render/<source-stem>.word.pdf main.pdf --outdir layout-profile",
        "```",
    ]
    if language == "mixed":
        readme_lines.extend([
            "",
            "## Bilingual Metadata",
            "",
            "For Chinese-English source templates, edit `\\englishtitle`, `\\englishauthor`, `\\englishaffiliation`, `\\englishabstract`, and `\\englishkeywords` in `main.tex`. The class keeps the bilingual layout editable without requiring class-file edits.",
        ])
    readme_lines.extend([
        "",
        "## Abstract Structure",
        "",
        f"Abstract label mode: `{abstract_label_mode}`; layout mode: `{abstract_layout_mode}`. {abstract_layout_evidence}",
        "The class owns the abstract environment and does not inherit the base article class's default quotation width, heading, or vertical spacing. Front-matter boundaries in `template_spec.json` use the larger adjacent Word paragraph spacing and emit it once.",
        "",
        "## Float Spacing",
        "",
        f"Word outer-boundary evidence: `{float_spacing_status}` with {float_spacing_count} eligible body-text boundary value(s), aggregate `{float_spacing_value}pt`. Calibration status: `{float_spacing_calibration_status}`.",
        "Caption/object spacing and outside-caption spacing are separate ledgers. Ordinary LaTeX float lengths remain unchanged unless a strict same-content promotion report verifies `page.float_spacing_calibration`.",
    ])
    if str(get_nested(spec, "front_matter.cover_mode", "")).startswith("candidate"):
        readme_lines.extend([
            "",
            "## First Page",
            "",
            "Word contains a first-page variant. `cover.tex` is an editable candidate; input it only after confirming that the rendered source has a standalone cover rather than an article title-page variation.",
        ])
    if get_nested(spec, "assets.text_boxes", []):
        readme_lines.extend([
            "",
            "## Text Boxes",
            "",
            "The Word source contains non-flow text boxes. `textboxes.tex` preserves their text and available native geometry as commented, editable candidates. Page/margin-relative shapes also include a `journalpositionedtextbox`/`textpos` candidate; column- or paragraph-relative shapes remain evidence-only. The file is intentionally not input by `main.tex` until a rendered comparison confirms manuscript role and placement.",
        ])
    section_flow = get_nested(spec, "page.section_flow.sections", [])
    if isinstance(section_flow, list) and len(section_flow) > 1:
        readme_lines.extend([
            "",
            "## Section Flow",
            "",
            "`section-flow.tex` contains source-labeled, commented candidates for Word section boundaries, and `page-frame.tex` preserves each section's paper size and margins. Place the helpers at semantic manuscript boundaries only after comparing section page frames and pagination; neither file is automatically input by `main.tex`.",
        ])
    if header_footer_parts:
        readme_lines.extend([
            "",
            "## Page Furniture",
            "",
            "`page-furniture.tex` contains commented, per-section fancyhdr candidates derived from active Word header/footer parts. It is not automatically input: select a candidate only at a confirmed manuscript boundary after comparing the same-content rendered reference.",
        ])
    if get_nested(spec, "body.toc", False):
        readme_lines.extend([
            "",
            "## Contents",
            "",
            "A Word TOC field was detected. Compile twice so LaTeX can populate the generated table of contents, then compare depth and page breaks with the source.",
        ])
    section_flow = get_nested(spec, "page.section_flow.sections", [])
    if isinstance(section_flow, list) and len(section_flow) > 1:
        readme_lines.extend([
            "",
            "## Word Section Flow",
            "",
            "The source contains multiple Word sections. The class exposes `\\journalstartsinglecolumn`, `\\journalstartdoublecolumn`, and `\\journalsectionpagebreak`; place them at the corresponding manuscript boundary only after checking the section-flow evidence and rendered reference in `template_spec.json` and `format_gap_log.md`.",
        ])
    if unequal_column_layout(spec):
        readme_lines.extend([
            "",
            "## Unequal Columns",
            "",
            "Word records unequal column widths. `template_spec.json` preserves the source widths and the class exposes `\\journalstartunequalcolumns`, `\\journalendunequalcolumns`, and `\\journalcolumnratio`. Activate this candidate only after a rendered same-content check; it is not silently enabled as ordinary equal-width `twocolumn` output.",
        ])
    if get_nested(spec, "tables.layout_evidence", {}) or get_nested(spec, "figures.layout_evidence", {}):
        table_position = str(get_nested(spec, "tables.caption_position", "above"))
        figure_position = str(get_nested(spec, "figures.caption_position", "below"))
        table_position_status = str(get_nested(spec, "tables.caption_position_evidence.status", "default"))
        figure_position_status = str(get_nested(spec, "figures.caption_position_evidence.status", "default"))
        table_spacing = get_nested(spec, "tables.caption_spacing_evidence", {})
        figure_spacing = get_nested(spec, "figures.caption_spacing_evidence", {})
        table_span = get_nested(spec, "tables.layout_evidence.span_evidence", {})
        figure_span = get_nested(spec, "figures.layout_evidence.span_evidence", {})
        table_span_mode = str(table_span.get("mode", "uncertain")) if isinstance(table_span, dict) else "uncertain"
        table_span_status = str(table_span.get("status", "unknown")) if isinstance(table_span, dict) else "unknown"
        figure_span_mode = str(figure_span.get("mode", "uncertain")) if isinstance(figure_span, dict) else "uncertain"
        figure_span_status = str(figure_span.get("status", "unknown")) if isinstance(figure_span, dict) else "unknown"
        readme_lines.extend([
            "",
            "## Tables And Figures",
            "",
            "Use `journaltable` and `journalfigure` for column-local editable floats. In a two-column class, `journaltablewide` and `journalfigurewide` are the explicit full-width wrappers. The representative fixture uses a wide wrapper only when the selected Word object's containing section and local column geometry provide source-backed span evidence; never infer span from page-wide ratios alone.",
            f"Representative span decisions: table `{table_span_mode}` (`{table_span_status}`), figure `{figure_span_mode}` (`{figure_span_status}`). An uncertain decision stays local at `\\linewidth` and remains listed in `format_gap_log.md`.",
            f"Caption order in the fixture: table `{table_position}` (`{table_position_status}`), figure `{figure_position}` (`{figure_position_status}`). A source status means a nearby Word caption/object relation was found; a default status remains a visual-verification item.",
            f"Caption gaps (internal/outer): table `{table_spacing.get('resolved_pt', 4)}pt`/`{table_spacing.get('outer_pt', 0)}pt` (`{table_spacing.get('status', 'default')}`), figure `{figure_spacing.get('resolved_pt', 4)}pt`/`{figure_spacing.get('outer_pt', 0)}pt` (`{figure_spacing.get('status', 'default')}`). The class uses only the two paragraph-spacing sides that face the object for the internal maximum, emits it once, and preserves the opposite caption side separately.",
        ])
    if get_nested(spec, "assets.extraction_required", False):
        readme_lines.extend([
            "",
            "## Word Assets",
            "",
            "Official Word assets were copied to `assets/`; see `assets/word_asset_manifest.json` for source roles. Apply header/footer candidate positions only after PDF confirmation with `--apply-source-header-assets`." if asset_manifest else "Extract official embedded assets before final visual verification:",
        ])
        if not asset_manifest:
            readme_lines.extend([
                "```powershell",
                "python <temp2tex-skill>/scripts/extract_word_assets.py <official-template.docx> --outdir assets",
                "```",
                "Review `word_asset_manifest.json`, then set the class `\\journalheaderleft`, `\\journalheaderright`, `\\journalfooterleft`, and related commands with the verified asset paths and dimensions.",
            ])
    (outdir / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    print(outdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
