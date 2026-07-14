# temp2tex

`temp2tex` is a Codex skill for reconstructing editable, Overleaf-ready LaTeX
template packages from official journal Word templates and related author
evidence.

## Version 0.1.0

The skill turns official `.doc`, `.docx`, `.docm`, `.dot`, `.dotx`, and
`.dotm` templates into a class-based package: `journal-template.cls`,
`main.tex`, a BibTeX starter, assets, an evidence-backed specification, and a
format-gap log. It covers English and Chinese layouts, title/front matter,
headings, figures, tables, captions, notes, references, appendices, page
furniture, and body formatting.

The bundled scripts support deterministic source inspection, Word
normalization, LaTeX generation, compilation, and PDF comparison. They are
optional aids: an agent must still provide a usable editable template package
when local rendering tools are unavailable.

## Install

Copy the `temp2tex/` directory into your Codex skills directory, typically
`~/.codex/skills/temp2tex/`, then start a new Codex session. The release asset
`temp2tex-v0.1.0.skill` contains the same directory as an installable archive.

## Validation

The v0.1.0 package passes the structural skill validator. Its latest canonical
30-case source-faithful regression compiled all generated packages and passed
the hard layout gates for 22 cases. The regression corpus itself and downloaded
publisher templates are intentionally not included in this repository.

## Scope

This is an evidence-driven template reconstruction skill, not a claim that
every publisher template is pixel-identical by default. It records source
evidence, conservative language-specific defaults, and unresolved formatting
gaps so that generated LaTeX remains editable and reviewable.
