# temp2tex v0.1.0

Initial public release of the `temp2tex` Codex skill.

## Included

- Evidence-led conversion from official journal Word templates to editable
  LaTeX packages.
- Default `journal-template.cls + main.tex` architecture.
- English and Chinese fallback defaults when official requirements are absent.
- Optional Word inspection, normalization, asset extraction, compilation, and
  PDF layout comparison tools.
- Regression methodology for official Word and LaTeX sources, including a
  Word-render reference fallback when official LaTeX is unavailable.

## Verification

- Skill structural validation: passed.
- Installable archive SHA-256:
  `f9214d820f5f588d6f7029fc81ecbfeb36d105a4e8efbd760e465118b79edd46`.
- Latest canonical 30-case run: all generated packages compiled; 22 cases
  passed the hard layout gate.

The official template corpus and generated regression outputs are excluded from
the repository because they contain third-party publisher materials and large
intermediate artifacts.
