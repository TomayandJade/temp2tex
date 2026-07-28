---
name: temp2tex
description: Convert official journal website non-LaTeX templates, especially Word .doc/.docx/.docm/.dot/.dotx/.dotm/.rtf author templates, into editable Overleaf-ready LaTeX template packages. Use this skill whenever the user asks to rebuild a journal template from official Word/PDF/web author instructions, including sparse or blank Word templates that define formatting through named styles; reproduce cover/title/abstract/table/figure/heading/footnote/reference/appendix/body formatting in LaTeX; create a class-based `.cls + main.tex` package; handle Chinese or English journal defaults when official rules are incomplete; or optionally verify the result with PDF rendering or official Word-vs-LaTeX regression.
---

# Temp2TeX

## Purpose

Reconstruct an editable LaTeX journal template from official non-LaTeX source
materials. This is an evidence-backed reconstruction task for an LLM agent,
not a one-shot Word converter, a flattened PDF imitation, or a benchmark
runner.

The usual source is an official Word author template plus author instructions,
sample PDFs, reference rules, artwork rules, and website guidance. Word is the
primary template evidence; supporting official sources resolve ambiguity.

The default result is an editable, Overleaf-ready package centered on
`journal-template.cls + main.tex`. Use a `.sty` file only as a compatibility
layer or when preserving an official class is the source-backed choice.

## Mission Lock

Keep this invariant visible in working notes:

> Every observable source formatting decision is mapped to an editable LaTeX
> owner, recorded as a justified default, retained as an unresolved gap,
> marked not observable, or classified as non-format guidance with a reason.

Do not claim fidelity because a converter ran, a class compiled, or a PDF looks
plausible. A source rule, an inference, a language default, and a pending gap
are different states and must remain distinguishable.

For an ordinary user conversion, produce the package and its evidence record.
Do not start the 30-case corpus. Run official Word-vs-LaTeX regression only
when the user explicitly requests comparison or the task is skill development.

## Start Here

Read these files in order before beginning a conversion:

1. `references/agent-control-loop.md`: task invariant, phase gates, live
   ledger, anti-drift checks, and ordinary versus training scope.
2. `references/input-triage.md`: authoritative-source selection, source
   payload detection, legacy DOC/DOT/RTF handling, sparse templates, and
   unavailable-input behavior.
3. `references/atomic-reconstruction.md`: indivisible Word evidence units,
   map-or-gap rule, bounded review batches, direct/object bindings, and audit.

At every phase boundary, state: current phase, source evidence used,
unresolved roles, and next audit action. If work drifts into tool setup,
benchmark automation, sample-manuscript transcription, or cosmetic tuning
without resolving an evidence or mapping item, return to the current phase.

## Workflow

### 1. Classify The Task And Sources

Classify the work as ordinary conversion, explicit official Word-vs-LaTeX
comparison, or skill training. Inspect actual file contents rather than trusting
the extension. An OpenXML-looking `.dot` may be parsed directly; true legacy
DOC, DOT, and RTF retain the original as authority and may use a temporary
LibreOffice DOCX only for inspection.

For a legacy conversion, retain that derived DOCX inside the package workspace
with `build_word_format_ledger.py --retain-derived-docx ...`; its path and
hash must remain bound to the original-file hash in the ledger. It is never a
replacement authority. Before a source-fidelity claim, compare the legacy
original render or an official PDF with the derived inspection path.

An unreadable, protected, or damaged Word file limits Word-specific claims but
does not justify fabricated rules or withholding a default-backed editable
package when official PDF/web evidence is usable. Record the limitation and
the next verification action.

### 2. Capture Evidence Before Writing LaTeX

Build a source inventory and, for readable Word input, a Word format ledger.
When those helpers or structured Word inspection are unavailable, create
`manual_evidence_ledger.md` before writing the class. It must use the
tool-independent record in `references/atomic-reconstruction.md`: one
source-located unit at a time, with its observed format, role decision,
LaTeX owner, status, and next verification. Tool absence never permits a
memory-only or prose-only reconstruction.
Resolve evidence separately for page frame, furniture, title/article type,
author/affiliation/metadata, abstract/keywords, each heading level, body,
lists, equations, tables, figures/captions, notes, references, appendix, and
cover or text boxes when present.

For metadata, separate publication identifiers, DOI, received/revised/accepted
dates, funding, contributor notes, and editorial notices. Preserve each visible
line plus its label and value runs. Do not collapse adjacent metadata into one
front-matter style: every detected kind needs its own source/default/gap
decision and class-level editable owner.

Preserve visible paragraph and contiguous run boundaries. Treat table grids and
cell text, drawing geometry and captions, list systems and list items, formula
systems and formula instances, and header/footer variants as separate evidence
units. A generic Word style, placeholder, instruction, first nonempty line, or
initial converter output never proves a manuscript role.

Also retain layout-only runs. A tab, line break, non-breaking space, or
directly formatted whitespace can define an inline separator, table/header
layout, or field boundary even without visible letters. It needs an explicit
mapping/default/gap disposition; ordinary inherited spaces remain part of the
parent paragraph rather than becoming artificial formatting rules.

Treat an otherwise empty paragraph with explicit paragraph layout, break/tab,
or anchored-object evidence the same way. It is a local `paragraph.layout`
unit that must be reconstructed or logged, particularly around title pages,
abstracts, figures, tables, and page furniture. Do not replace it with a
document-wide line-spacing or margin adjustment.

Before mapping a large or unfamiliar Word source, audit capture completeness.
The ledger must report every observable document-flow/table-cell paragraph,
contiguous visible run, ancillary text unit, and observable object/system
unit. `capture_complete` authorizes atomic map-or-gap review only;
`captured_sparse_or_empty` requires external official evidence or explicit
defaults; `capture_incomplete` blocks strict mapping completion and visual
calibration.

For every table or body drawing, classify its caption relation before choosing
caption order, float behavior, spacing, or a PDF anchor. Only an adjacent or
nearby external caption with a source-confirmed above/below relation may drive
those decisions. A distant candidate, unmatched label, tie, or missing caption
is a diagnostic or evidence gap, not permission to guess. Such an object may
still supply local geometry, but its caption/float rules remain default-backed
or pending until stronger source or same-content render evidence exists.

Read the following when extracting or interpreting evidence:

- `references/model-playbook.md` for evidence priority, front matter, Word
  styles, headers/footers, layout order, defaults, and Chinese/mixed sources.
- `references/word-evidence-to-latex.md` for run, paragraph, table, figure,
  caption, note, TOC, list, and equation details.
- `references/system-format-triage.md` before acting on Word grids, character
  effects/styles, language/RTL, themes, or unmodeled OOXML properties.
- `references/reconstruction-protocol.md` for evidence packet structure and
  sparse-template comparison procedure.

### 3. Make One Auditable Mapping Decision At A Time

Use the atomic reconstruction loop: observe, classify, map or gap, exercise,
and audit. Give each source unit a semantic role and one narrow editable LaTeX
owner, or make its default/guidance/unresolved/not-observable status explicit.
Keep run-local effects local. Never turn a single paragraph, a generic `Normal`
style, or a visual score into a document-wide rule.

When `word_format_ledger.json.front_matter_sequence_review` requires semantic
confirmation, create or complete the ledger-fingerprint-bound
`front_matter_semantic_confirmation.json` before the first atomic mapping
batch. Confirm each ordered candidate from visible Word context and retain its
candidate role. A disagreement is an evidence gap requiring further official
material or a conservative unresolved record. Regenerate the ledger only after
source interpretation or extraction actually changes.

For a large ledger, work in one dependency-ordered role slice at a time. Use
`--pending-only` with the atomic review helper for active continuation batches;
it shows only unresolved work. If that slice has no pending groups, audit its
existing final decisions only for a concrete source/owner/binding conflict, or
move to the next readiness-recommended pending slice. Do not manufacture an
empty task for a later model.

Mapped/default decisions with direct Word formatting need property-level
bindings from each exact source value to an active package-local LaTeX token.
Table, drawing, text-box, page-frame, and furniture decisions also need
property-level object-layout bindings. A declared but unused class macro is not
an active owner. See `references/atomic-reconstruction.md` for the required
records and `references/latex-architecture.md` for where each behavior belongs.

### 4. Build An Editable Package

Put reusable journal behavior in `journal-template.cls`: page frame, fonts,
title/front matter interfaces, headings, captions, floats, notes, bibliography,
appendix, and running furniture. Put neutral editable fixture content and user
metadata in `main.tex`. Keep assets in `assets/` or `figures/`; do not turn a
filled manuscript or source artwork content into the default template body.

Declare the compilation engine in the package README. Chinese or mixed-language
packages require XeLaTeX. English-only packages may offer PDFLaTeX as a
portable fallback only when the class selects a documented TeX font fallback;
do not load `fontspec` unconditionally and leave the engine implicit.

When source-backed metadata types are present, ship a commented `metadata.tex`
field skeleton and a commented `\input{metadata.tex}` entry in `main.tex`.
The skeleton must expose each observed typed field with its source label but no
copied article value. It is not acceptable to hide all source-backed metadata
behind one empty generic command.

Read `references/latex-architecture.md` before writing the class, and
`references/spec-schema.md` before creating `template_spec.json`. When official
requirements are incomplete, use the appropriate English, Chinese, or mixed
default from `references/format-defaults.md`; log the missing source evidence,
chosen value, language profile, LaTeX owner, and verification need.

### 5. Audit And Verify In Order

Audit source capture and atomic decisions first, then active ownership,
compilation, required structure, and finally visual layout. A pending Word
mapping blocks full-fidelity claims and calibration, but a missing local TeX or
PDF tool does not block delivery of an editable package with explicit rerun
instructions.

When a comparable same-content PDF pair exists, repair in this order: fixture
validity, structural page flow, local furniture, front matter, object/caption
flow, page frame, body density, then running furniture. Change one
source-backed variable at a time. Do not use a generic margin, font, or
line-spacing search to conceal an unfinished role.

For images, raster content may differ. Mask only raster image interiors in an
image-insensitive metric; continue checking image frame geometry, caption,
wrapping, whitespace, and surrounding flow. Never mask table text, table rules,
captions, vector geometry, or ordinary text.

Before comparing a populated fixture, save a language- and profile-specific
same-content anchor map. It must cover every populated role, including Chinese
or bilingual front matter when present. Align the image representation and
declared frame geometry on both sides first: a Word raster placeholder versus a
LaTeX empty frame is a fixture mismatch, not evidence for changing the journal
class. Preserve that mismatch for repair; do not hide it by masking the whole
figure or by tuning unrelated margins and fonts.

A full-document comparison contract also requires source-observable or
independently verified shared structure for every populated table and figure.
When a sparse Word source contains no table or body-artwork evidence, an
injected default table or image may exercise package interfaces and provide
local diagnostics, but it must use a `partial_zone` contract and cannot
calibrate global page, body, float, or caption rules. For a controlled
same-content render test, optional tooling may use the same neutral raster
placeholder on both paths; mask only its interior after its declared width,
height, frame, caption, and surrounding flow agree.

Read `references/verification-checklist.md` before handoff and
`references/render-compare.md` whenever rendering is possible. Read
`references/regression-testing.md` only for explicit comparison or skill
training work.

### 6. Hand Off Without Overclaiming

Separate official rules, inferences, defaults, completed checks, and pending
checks in the package README and gap log. An ordinary handoff is not complete
when it silently omits an observable role. A continuation checkpoint may retain
pending mapping work for the next model, but it is never a fidelity claim.

When the local validator is available, run
`validate_latex_package.py <package-directory>` immediately before handoff.
Its report now belongs in `<package-directory>/package_validation.json` unless
an explicit `--output` is supplied. `valid: false` is a handoff blocker for an
ordinary conversion: fix the reported contract issue, or label the result a
continuation checkpoint and state exactly which audit/coverage/specification
gate remains open. A successful TeX compile, a nonempty `.cls`, or a rendered
PDF never substitutes for this gate. Accept a `valid: true` report only when
its `schema_version` is current and its `package_contract_fingerprint` matches
the package after the latest editable-source change; rerun validation after any
class, fixture, evidence, asset, specification, or gap-log edit. When the
validator is unavailable, retain the corresponding manual checklist and make
the missing check explicit.

The generated `HANDOFF_STATUS.md` intentionally starts as `blocked`, with
pending validation and fingerprint fields. To finalize an ordinary handoff,
first validate the finished non-status package, then set `Ordinary handoff` to
`ready`, `Package validation` to `valid`, and `Package fingerprint` to that
report's fingerprint. Run validation once more. The status file itself is
excluded from the fingerprint so this final status update does not stale the
report; any later template, fixture, evidence, asset, specification, README,
or gap-log edit does.

When the Word mapping and package structure are complete but a required local
validator, TeX engine, or PDF renderer is unavailable, use the narrower state
`Ordinary handoff: ready_with_pending_local_verification`. It is permitted only
with `Package validation: pending`, `Package fingerprint: pending`,
`Verification environment: unavailable`, and a `Required Next Action` that
gives the exact missing command. This permits an editable ordinary delivery
with an explicit local-verification boundary; it never permits unfinished
source capture, mapping, ownership, or gap work to be called ready.

## Required Deliverable

For an ordinary conversion, deliver:

- `main.tex`
- `journal-template.cls`
- `references.bib`
- `figures/` and `assets/`
- `template_spec.json`
- `format_gap_log.md`
- `HANDOFF_STATUS.md`
- `README.md`

When explicit front-matter metadata types were observed, also deliver
`metadata.tex` with commented typed field skeletons and a commented input
entry in `main.tex`.

When the Word source was legacy DOC, DOT, or RTF and a converted DOCX supplied
structured inspection evidence, also retain the hash-bound derived DOCX at the
package-relative path recorded in `word_format_ledger.json`.

When the source was inspectable, also retain `source_inventory.json`,
`word_format_ledger.json`, atomic decisions/audit, and the relevant mapping or
system-triage records. When rendering ran, also provide the compile report,
comparison report, layout profile, and diff previews as applicable. When a
tool is unavailable, the README must give exact rerun commands and pending
checks rather than treating tool absence as a conversion failure.

`HANDOFF_STATUS.md` must state the current phase, whether ordinary handoff is
ready, ready with pending local verification, or blocked, package-validation
state, package fingerprint, verification environment, completed checks, and
the exact next action. A generated or partially audited package is a
continuation checkpoint, not a source-faithful completion.

When structured inspection or audit helpers were unavailable, retain
`manual_evidence_ledger.md` and `manual_mapping_audit.md` instead. They must
cover every applicable required zone and preserve the same source/default/gap
distinction; a manual record is not optional merely because the package cannot
be compiled locally.

## Optional Tooling

Scripts accelerate deterministic work but never replace model judgement. Use
them when available; otherwise make the same evidence/mapping decisions
manually and record the unavailable verification stage.

| Need | Preferred helper |
| --- | --- |
| Inspect source payloads | `inspect_sources.py` |
| Build Word paragraph/run/object ledger | `build_word_format_ledger.py` |
| Audit paragraph/run/cell/furniture capture completeness | `audit_word_capture_coverage.py` |
| Audit object/caption relations and machine-readable decision limits | `audit_caption_relations.py` |
| Prepare or merge a bounded mapping batch | `prepare_atomic_mapping_review.py`, `apply_atomic_mapping_batch.py` |
| Prepare a front-matter semantic confirmation | `prepare_front_matter_confirmation.py` |
| Reconcile a regenerated ledger | `reconcile_atomic_mapping_decisions.py` |
| Audit mappings and system evidence | `prepare_system_format_triage.py` to initialize or reopen a ledger-matched child queue; use `--existing --systems --pending-only --batch-size --review-order priority` for an explainable stable review batch, then `audit_atomic_mapping.py` |
| Draft spec and generate package | `draft_spec_from_inventory.py`, `generate_latex_package.py` |
| Extract Word assets | `extract_word_assets.py` |
| Compile and validate package | `compile_latex_package.py`, `validate_latex_package.py` |
| Assess next safe action | `assess_conversion_readiness.py` |
| Render and compare PDFs | `render_docx_reference.py`, `compare_pdfs.py`, `profile_pdf_layout.py` |
| Train or compare deterministic corpus tooling | `run_regression.py`; read `references/llm-skill-evaluation.md` for actual loaded-skill model evaluation |

Use `--help` for the current command contract. `assess_conversion_readiness.py`
is the source of truth for whether the next step is mapping, compilation,
visual repair, verification, or a safe continuation checkpoint. A missing or
fingerprint-mismatched system-format triage blocks its mapping-slice output;
create the triage queue first instead of sending a model contradictory work.

Treat every explicit `--output` path as a fresh per-journal workspace. Helpers
must create its parent directory rather than requiring an agent to pre-create
it. For legacy DOC, DOT, or RTF inspection, retain the original file as the
authority and mark any temporary LibreOffice DOCX as a derived inspection
artifact, not a replacement source.

## Completion States

An ordinary conversion may be handed off when the editable package contract is
present, source/default/gap records are honest, all applicable source units are
mapped or explicitly retained, and completed versus pending checks are clear.

Call the result source-faithful only when the applicable Word mapping audit is
complete, the package compiles, required zones exist, and any available
same-content visual check has been assessed without unresolved critical gaps.

For skill changes, do not use one journal as proof. Run affected cases first,
then the representative set and required corpus manifests. A corpus metric is
training evidence; it does not replace the per-journal ledger.

## Guardrails

- Do not fabricate publisher requirements or hide uncertainty behind a generic
  default.
- Do not use an official LaTeX package as the primary rule when the task is to
  reconstruct an official Word template; it is supporting comparison evidence.
- Do not compare unrelated Word and LaTeX samples. Use the same representative
  fixture or mark the pair not comparable.
- Do not let local tool failure, an attractive PDF score, or a compiling file
  bypass evidence capture, atomic mapping, or the gap log.
- Do not commit, push, tag, or release this skill unless the user explicitly
  confirms that publication action.
