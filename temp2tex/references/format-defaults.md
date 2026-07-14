# Format Defaults

Use these defaults only when official sources are incomplete. Add every default used to `format_gap_log.md`.

## English Journal Defaults

- Engine: XeLaTeX.
- Generated class: `journal-template.cls`, loading `article` internally unless source evidence requires another base.
- Paper: A4.
- Margins: 25 mm on all sides.
- Font size: 12 pt.
- Font: Times-compatible when available.
- Line spacing: 1.15.
- Paragraph indent: 1.5 em.
- Paragraph spacing: 0 pt.
- Headings: numbered, left aligned, bold.
- Abstract: unnumbered `Abstract` block before keywords.
- Keywords: `Keywords:` label, comma or semicolon separated according to visible source pattern.
- Tables: captions above, `booktabs` rules, notes below using `threeparttable`.
- Figures: captions below, files stored in `figures/`.
- References: numeric placeholder unless official source specifies author-year or a publisher style.

## Chinese Journal Defaults

- Engine: XeLaTeX.
- Generated class: `journal-template.cls`, loading `ctexart` or equivalent CJK-safe base internally unless source evidence requires another base.
- Paper: A4.
- Margins: 25 mm on all sides.
- Body size: source-derived Word point size when available; otherwise small
  four (approximately 12 pt) is the default.
- Paragraph indent: 2 em.
- Line spacing: 1.3.
- Chinese headings: numbered, left aligned, bold.
- English title or abstract blocks: Times-compatible font if available.
- Tables: captions above unless official source shows otherwise.
- Figures: captions below.
- References: numeric placeholder unless official source specifies GB/T 7714 or another style.

## Mixed-Language Defaults

For mixed Chinese/English templates, prefer `journal-template.cls` with a CJK-safe base such as `ctexart` and explicit English font settings. Keep bilingual abstract order and labels source-backed. If the source does not define order, use Chinese abstract first for Chinese-first journals and English abstract first for English-first journals.

Record Latin and East Asian font evidence separately. Do not silently apply a
Word CJK font name merely because it appeared in OOXML: set
`cjk_font_mode: "verified"` only after the local font exists and PDF comparison
supports it. Until then, retain the CTeX fallback chain and record the source
font as evidence. For Chinese-first `zh` or `mixed` templates, use Chinese
abstract and keyword labels by default unless official evidence says otherwise.

## LaTeX Package Defaults

Use a conservative core:

```latex
\usepackage{geometry}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{multirow}
\usepackage{caption}
\usepackage{subcaption}
\usepackage{threeparttable}
\usepackage{tablefootnote}
\usepackage{amsmath}
\usepackage{titlesec}
\usepackage{fancyhdr}
\usepackage[hidelinks]{hyperref}
```

Add packages only when the source requires them or the template examples need them. Add `amssymb` only after checking it does not conflict with the chosen math font package.

## Reference Defaults

If official bibliography files exist, use them. If the source gives only prose instructions, create a compiling placeholder and mark the exact punctuation as review-needed. Do not invent detailed reference punctuation and call it official.
