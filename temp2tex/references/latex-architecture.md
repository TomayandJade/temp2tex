# LaTeX Architecture

Temp2TeX defaults to a class-based package:

- `journal-template.cls`
- `main.tex`
- `references.bib`
- `figures/`
- `assets/`
- `template_spec.json`
- `format_gap_log.md`
- `README.md`

Use `.sty` only as a legacy compatibility shim or when the official evidence says an existing class must be preserved and additional behavior should be layered on top.

## What Belongs in `journal-template.cls`

Put reusable template behavior in the class:

- `\LoadClass` choice and class options.
- Paper size, margins, columns, column gap, text block, header/footer, page numbering, and line-numbering policy.
- Named body, abstract, keyword, or reference content-box environments when the
  Word evidence gives those roles different left/right indents. Keep the
  physical page frame separate from these role-level boxes.
- Font family, base size, line spacing, paragraph indentation, paragraph spacing.
- Metadata commands: title, subtitle, short title, authors, affiliations, corresponding author, dates, funding, conflict statements when the template requires them.
- `\maketitle` and front-matter layout.
- Abstract and keyword environments, including bilingual variants when required.
- Heading levels, numbering, punctuation, spacing, run-in behavior, and appendix heading changes.
- Caption style, table rule defaults, float placement defaults, figure/table note helpers.
- Footnote marker and footnote text style.
- Bibliography/citation package defaults and reference heading hook.
- Appendix numbering for sections, equations, tables, and figures.

Class code should be readable and conservative. Avoid burying journal logic in generated one-off macros that are impossible for the user to edit.

When a role-specific content box is evidence-backed, expose it as a readable
class interface, for example a `journalbody` environment or an abstract
environment that owns its own margins. Do not put repeated `\hspace`, `minipage`,
or manual width arithmetic in `main.tex`; those obscure the template rule and
make later PDF calibration brittle.

The bundled generator exposes the same principle through
`\tempTwoTexAbstractBegin` / `\tempTwoTexAbstractEnd`,
`\tempTwoTexKeywords{...}`, and `\tempTwoTexBodyBegin` /
`\tempTwoTexBodyEnd`. Use equivalent readable class interfaces in a manually
written package. Keep title-page material outside the body interface unless
its Word role has the same content-box evidence.

For basic editable front matter, the bundled class exposes repeatable
`\affiliation{...}` calls, `\correspondingauthor{...}`, and repeatable
`\journalmetadata[kind]{...}` calls alongside `\title`, `\author`, and
`\date`. The supported typed values are `publication_id`, `doi`, `dates`,
`funding`, `contributor_note`, and `editorial_note`; write source labels with
`\journalmetadatalabel[kind]{...}`. Each detected kind has its own line,
value, and label-format hook in the class. Do not merge a DOI, received date,
funding statement, classification code, or author biography merely because
they appear next to one another in Word. The untyped
`\journalmetadata{...}` form is a documented generic default, not evidence
for any source-specific kind, and the generic fixture intentionally leaves all
metadata empty. Keep visible layout rules in the class rather than `main.tex`.

When one or more typed metadata fields are observed, ship a commented
`metadata.tex` skeleton and a commented `\input{metadata.tex}` in `main.tex`.
Each skeleton line should retain the source label and typed command but replace
the article-specific value with an editable placeholder. Do not copy a sample
DOI, funding number, author biography, or received date into the default
manuscript.

The class must redefine the abstract environment for every supported
`abstracts.label_mode`: inline, separate, none, and default. Do not fall back to
the base `article`/`ctexart` abstract implementation, because it silently owns a
heading, quotation width, font, and vertical skips that may contradict Word.
Keep label typography, content typography, and keyword typography separate.
Consume `front_matter.spacing_boundaries` so each title/author/affiliation/
abstract/keyword transition is emitted once; role-local code must not add a
second skip at the same boundary.

## What Belongs in `main.tex`

Put user-facing usage and example manuscript content in `main.tex`:

- `\documentclass{journal-template}`.
- Metadata values that demonstrate the class commands.
- Abstract and keyword body text.
- Representative sections and heading levels.
- Example paragraph, every observed list family/level, equation, table, figure, footnote, references, and appendix. A list family belongs in editable class-owned `journalitemize`/`journalenumerate` configuration; its visible `\item` examples remain in `main.tex`. Do not flatten distinct Word numbering definitions into one generic list setting.
- Put reusable equation display, counter, tag, and spacing behavior in `journal-template.cls` through `journalequation`; keep each source OMML conversion candidate or explicit manual-translation record in `equations.tex`, then move only rendered-checked examples into `main.tex`.
- Keep the editable manuscript sequence as body, declarations/statements, references, then appendix. Call `\journalbackmatter` before the first declaration and `\journalappendix` only after the bibliography.
- Editable bibliography fixture plus an optional `references.bib` backend
  migration point; use the journal's official `.bst` or BibLaTeX commands when
  source evidence provides them.
- Comments that explain where the author should edit content, not how Temp2TeX works internally.

Keep `main.tex` as a clean template the user can start from. It should not contain large conversion debris from Word.

## Evidence Ledger

`template_spec.json` records why each visible rule exists. Use it to separate:

- `official`: directly supported by the journal template or official instructions.
- `inferred`: derived from visible layout or rendered samples.
- `default`: filled from Temp2TeX defaults because official evidence was missing.
- `unsupported`: known requirement that was not implemented.

`format_gap_log.md` is the human-readable version of the same risk record. It should name missing evidence, assumptions, and verification that remains pending.

## Chinese and Mixed-Language Templates

Use XeLaTeX when Chinese text may appear. Put CJK package/font decisions in the class and keep source files UTF-8. Do not add CJK machinery to English-only templates unless official evidence or user content requires it. For English-only packages, prefer an engine-portable font branch: XeLaTeX/LuaLaTeX may use a source-backed system font, while PDFLaTeX must use a named TeX fallback and disclose that fallback in the generated README and gap log. Never load `fontspec` unconditionally in an English-only class.

For bilingual templates, provide separate commands or fields only when the source requires them, such as English and Chinese titles, abstracts, keywords, author names, or affiliations.

For `zh` or `mixed` packages, make the starter manuscript exercise the CJK
path with real Chinese title, author, affiliation, abstract, and keyword text;
do not leave an English-only fixture that merely happens to compile under
XeLaTeX. Keep the English companion metadata in its separate editable fields
when the source calls for bilingual front matter.

When Word only proves a first-page candidate (`titlePg` or a first-page
header/footer variant), generate an optional `cover.tex` using the editable
`journalcover` interface but do not input it from `main.tex`. Enable it only
after the rendered source proves a standalone cover instead of an article
title-page variation.

For Word text boxes whose coordinates cannot be reconstructed from XML alone,
keep an optional `textboxes.tex` file with source-labeled commented
`journaltextbox` candidates. When page/margin-relative geometry is available,
also expose a commented `journalpositionedtextbox` candidate backed by
`textpos`; keep column- or paragraph-relative shapes evidence-only until the
semantic anchor is known. Do not input it from `main.tex` by default. The
class environments are editable candidates, not a claim that LaTeX has
reproduced the original floating coordinates.

Keep first-page furniture separate from later-page furniture. The generated
class exposes `\journalfirstpageheaderleft`, `\journalfirstpageheadercenter`,
`\journalfirstpageheaderright`, and matching footer commands, plus the
`tempTwoFirstPage` style. Populate and activate that style only after a
same-content PDF comparison verifies the first-page logo, rule, text, and
page-number behavior; do not reuse first-page assets in normal `fancyhdr`
slots. A logo and masthead text that share one Word slot must remain separate
composable fields in the class: activating the logo must not replace the
ordered masthead paragraphs. Preserve all observed first-page header/footer
paragraphs as an ordered block, then calibrate its height and baseline from
the rendered first page. For a logo beside masthead text, use top-aligned
parallel boxes and reserve the taller component's height, not their combined
height; baseline alignment that places the text below the logo is a failed
candidate. A multi-line first-page footer may not behave like a conventional
bottom footer. Keep a `fancyfoot` candidate editable, but promote a vertical
offset only from a local rendered-zone check; use a separately positioned
first-page block when the source footer is tied to article flow rather than
the physical page bottom.

Within a header or footer paragraph, preserve a right-aligned Word tab as one
line-level layout rather than concatenating its left and right text. Some
legacy DOC conversions lose the tab node but retain two text runs separated by
a very long blank run. Treat that only as a candidate for `\hfill`-style
layout, record the degraded evidence, and verify both endpoint boxes against
the rendered source before promotion.

When Word has distinct `default` and `even` variants, expose
`\journaloddheader...` / `\journaloddfooter...` and
`\journalevenheader...` / `\journalevenfooter...` separately. The generated
`tempTwoMirroredRunning` style is an editable candidate that binds those
interfaces to odd/even selectors; it is not enabled by default. Do not map an
even-page author head into an odd-page title head, or reduce the two variants
to a generic `\pagestyle{fancy}` merely because that compiles.
When an even Word variant exists, load the LaTeX base class with `twoside`
even if Word does not use mirrored margins. `fancyhdr` otherwise ignores the
even-page selectors and gives a misleading successful compilation.

## Official Class Preservation

If an official LaTeX class already exists and the task is comparison or adaptation, preserve the official class for the official-golden side. For the generated Temp2TeX package, still use `journal-template.cls` unless the user's requested output is explicitly a patch layer for the official class.
