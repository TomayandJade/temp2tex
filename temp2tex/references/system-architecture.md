# System Architecture

Temp2TeX has one purpose: turn an official journal non-LaTeX template into an editable LaTeX template package that can be opened in Overleaf. Render comparison and regression tooling are verification aids when the environment and task scope support them; they are not required to start or finish an ordinary package reconstruction.

## Source Priority

Use sources in this order:

1. Official journal or publisher DOC/DOCX template.
2. Official journal guide for authors or author instructions page.
3. Official PDF sample article or filled template.
4. Official publisher-wide artwork, table, reference, and submission rules.
5. Recent articles only as weak supporting evidence.
6. General defaults from `format-defaults.md`.

Avoid third-party template sites unless official sources are unavailable and the user explicitly accepts weaker evidence.

## Project Stages

Use these stages as separate work packages:

1. **Evidence capture**: download or identify source files, record URLs, access date, file hashes, renderer versions, and local paths.
2. **Reference rendering, optional for ordinary tasks**: convert the original DOC/DOCX to PDF using the best available renderer when tools are available. Keep all successful renders, but designate one reference.
3. **Structure extraction**: inspect DOCX styles and PDF pages for sections, title blocks, headings, tables, figures, footnotes, references, appendices, and language.
4. **Specification**: write `template_spec.json` as the single source of truth for generation.
5. **LaTeX generation**: produce an editable package, not a final manuscript. Use source-derived sections and front matter guidance so the generated PDF is long enough for meaningful comparison with the rendered source template.
6. **Compilation, when TeX is available**: build the generated LaTeX PDF from a clean directory and record the result.
7. **PDF comparison, when possible**: compare the generated PDF against the reference render using page images and measurable differences.
8. **Iteration**: fix missing structural zones first, then page frame, then typography, then local spacing.

## Evidence Rules

- Do not label inferred defaults as official requirements.
- Record unsupported gaps in `format_gap_log.md`.
- Prefer source-backed behavior over generic LaTeX conventions.
- Keep enough example content to exercise the template: title, authors, abstract, keywords, headings, table, figure, equation, footnote, references, and appendix.
- Preserve enough source template guidance text in `body.sections`, `front_matter.highlights_guidance`, and `abstracts.source_text` to make PDF comparison useful. A four-page scaffold against a ten-page Word reference is usually not enough.
- Make generated code readable and editable; avoid opaque conversions that users cannot maintain.

## Renderer Choice

DOCX render fidelity depends on the local environment. The best reference PDF is the one that most faithfully represents the official source. In practice:

- Microsoft Word usually gives the best DOC/DOCX fidelity when available.
- LibreOffice is a good portable fallback and is often sufficient for plain academic templates.
- If both are available, keep both renders and choose the successful render with the clearest page count and least conversion warnings. Prefer Word for complex Word-native layouts unless the visual result is clearly worse.

## Failure Handling

When the source template is too sparse, still generate a working template, but mark missing details as defaults. When rendering or comparison tools are missing, state exactly which verification stage could not run and leave the project ready for rerun once tools are available.
