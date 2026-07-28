# LLM Evaluation Records

## 2026-07-22 RSC Word-only paired smoke test

- Evaluation ID: `rsc-word-only-smoke-20260722`
- Input: official RSC Word template `art-template-2-2.docx`
- Loaded-skill output: `F:\document\doc2tex\tmp\llm-skill-eval\with-skill\rsc-article`
- Baseline output: `F:\document\doc2tex\tmp\llm-skill-eval\baseline\rsc-article`
- Status: `invalid_for_comparison`

Both agents produced the requested class-based package and reported successful
PDFLaTeX compilation. This establishes only a local smoke-test result.

The comparison is invalid for two independent reasons:

1. The shared prompt disclosed Temp2TeX-specific deliverables and evaluation
   behavior, including the full file contract, granular evidence extraction,
   and the instruction not to run corpus regression.
2. The agents ran in a shared host filesystem where the baseline could inspect
   the installed Temp2TeX skill, repository scripts, and generated artifacts.

Do not use this record to claim a behavior improvement, pass-rate change, or
regression result. Re-run this task only under the isolation and prompt-control
requirements in `references/llm-skill-evaluation.md`.

## 2026-07-22 LDZK Chinese-English loaded-skill smoke test

- Evaluation ID: `ldzk-cjk-loaded-skill-smoke-20260722`
- Input: official Chinese-English LDZK Word template
  `F:\document\doc2tex\temp2tex-chinese-corpus\ldzk-radar\official-word-template.docx`
- Loaded-skill output:
  `F:\document\doc2tex\tmp\llm-skill-smoke-cjk\ldzk-radar`
- Status: `smoke_test_not_comparative`

The agent was given a natural single-template conversion request with the
installed Temp2TeX skill loaded. It produced the required editable package and
evidence records, selected XeLaTeX for the mixed Chinese-English source, and
compiled `main.tex` successfully. The package validator wrote the current
schema and fingerprint but returned `valid: false`; the readiness report kept
the work in `atomic_mapping`, and `HANDOFF_STATUS.md` explicitly blocked an
ordinary handoff while naming the next bounded front-matter batch.

This is a behavior smoke test for scope control and honest handoff only. It
has no baseline, no isolated paired comparison, and no source-fidelity score.
Do not use it to claim an LLM quality improvement, a pass-rate change, or a
corpus-regression result.
