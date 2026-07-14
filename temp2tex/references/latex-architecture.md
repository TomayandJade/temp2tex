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
- Paper size, margins, columns, column gap, text block, header/footer, page numbering.
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
`\affiliation{...}` calls and `\correspondingauthor{...}` alongside `\title`,
`\author`, and `\date`. A journal that needs author-to-affiliation markers,
ORCID, received dates, or editorial metadata should extend this interface in
the class, with all visible layout rules kept out of `main.tex`.

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
- Example paragraph, list, equation, table, figure, footnote, references, and appendix.
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

Use XeLaTeX when Chinese text may appear. Put CJK package/font decisions in the class and keep source files UTF-8. Do not add CJK machinery to English-only templates unless official evidence or user content requires it.

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
slots.

## Official Class Preservation

If an official LaTeX class already exists and the task is comparison or adaptation, preserve the official class for the official-golden side. For the generated Temp2TeX package, still use `journal-template.cls` unless the user's requested output is explicitly a patch layer for the official class.
