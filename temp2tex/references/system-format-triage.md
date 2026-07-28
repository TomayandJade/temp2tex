# System-Format Triage

## Purpose

Word templates contain two different kinds of format evidence:

1. **Role evidence**: a visible title, table cell, caption, note, or run that
   must be reconstructed in the editable package.
2. **System evidence**: an OOXML setting, theme alias, named style, or document
   policy that may affect a role, may be explicitly disabled, or may not affect
   rendered manuscript content at all.

Do not turn every system setting into a global LaTeX option. Do not leave an
entire system unresolved merely because one sample is difficult. Create the
complete system queue before the ordinary atomic mapping loop, then connect
every active visible effect to its actual role and span as the linked ordinary
paragraph/run decisions become final. Queue creation is a prerequisite;
closing every system child is not an all-upfront replacement for ordinary role
mapping.

The required result is a `system_format_triage.json` record, whether it is
written manually or prepared with `scripts/prepare_system_format_triage.py`.
Version 2 of that queue creates one child for every captured visible system
sample. It is an evidence and decision artifact, not a claim that a source
layout has already matched.

Before strict audit, run `scripts/reconcile_system_format_triage.py` after the
relevant ordinary paragraph/run decisions are final. It may transfer a final
disposition into a child that already links to the exact ordinary evidence ID.
It must leave unlinked samples pending. Treat that transfer as traceability,
not as a visual approval. Complete the child-local owner, token, and reason
before final audit; reconciliation itself never closes the full system queue.

## Required Record

Create one record per detected system and one child record for each property or
visible span that has a different disposition.

```json
{
  "system": "word.unmodeled_format",
  "source_evidence_id": "word.unmodeled-format-properties.noProof",
  "child_id": "run.noProof",
  "source_scope": "word/document.xml",
  "observed_value": {"val": "0"},
  "rendering_class": "non_rendering",
  "disposition": "default",
  "role": "word.unmodeled_format",
  "latex_owner": "journal-template.cls",
  "latex_file": "journal-template.cls",
  "latex_token": "\\journalwordnonrenderingdefaults",
  "reason": "w:noProof controls Word proofing, not PDF glyph geometry.",
  "verification": "No PDF geometry check required; retain the source record."
}
```

For `word.unmodeled_format`, the ledger-level
`word.unmodeled-format-properties.system` item is only an aggregate signal.
The strict audit requires one triage record for each captured node, such as
`word.unmodeled-format-properties.noProof` or
`word.unmodeled-format-properties.adjustRightInd`. Do not create a synthetic
`.system` triage record, and do not close different OOXML nodes with one
aggregate disposition.

`disposition` must be one of the atomic-audit statuses: `mapped`, `default`,
`guidance`, `not_observable`, or `unresolved`. A `mapped` or `default` record
must name a real package-local owner and an executable token. A no-op class
macro is acceptable only for an explicit source-disabled or non-rendering
policy; it must document that policy and must not masquerade as a visual
implementation. A bare class macro that is merely declared is not executable
evidence: it must have a non-declaration use somewhere in the package, or the
child remains unresolved.

`source_unit_evidence_id` is traceability to the ordinary paragraph/run audit,
not a substitute for the child mapping. A linked `mapped` or `default` child
still needs its own concise reason plus `latex_owner`, `latex_file`, and active
`latex_token`; its source property must not disappear behind a generic body or
run rule.

## Child Review Batches

Do not ask a model to decide a large system aggregate from its summary alone.
Create the queue once, then expose a bounded, ledger-matched child batch with
local source text, locator, and observed value:

```powershell
python scripts/prepare_system_format_triage.py word_format_ledger.json `
  --existing system_format_triage.json `
  --output system_format_triage.json `
  --markdown-output system_triage_batch_001.md `
  --systems page.text_grid,run.script_language,paragraph.break_policy `
  --pending-only --batch-size 20 --batch-index 1 --review-order priority
```

The initial invocation omits `--existing` and creates the full queue. Later
invocations must use the same ledger fingerprint and may write back to the
same JSON file. This preserves final child decisions while presenting the next
stable subset for review.

When reopening an existing queue, the helper refreshes only `pending` children'
producer-owned source fields from the current ledger. This corrects derived
links such as table-local Word coordinates without changing a model decision.
If a `mapped`, `default`, `unresolved`, `not_observable`, or `guidance` child
would need a different source link, the helper stops: rebuild and review that
child explicitly rather than silently rewriting a finalized audit trail.

## Workflow Order

1. Create the full ledger-matched queue before requesting an ordinary mapping
   batch. This prevents aggregate Word evidence from being lost or converted
   into a global default.
2. Run `assess_conversion_readiness.py`; follow its next ordinary
   `recommended_mapping_slice` and merge one bounded paragraph/run batch.
3. Reopen the queue with `--existing --pending-only --review-order priority`.
   Review children whose linked ordinary unit now has enough role context; use
   `reconcile_system_format_triage.py` only as a traceability aid.
4. Alternate bounded ordinary and system review packets until both queues have
   final evidence-bound dispositions. Only then run the strict atomic audit.

Do not wait to finalize every theme alias, Word-only default, or instruction
sample before starting the ordinary title/front-matter/body mapping that gives
those children their role context. Conversely, do not claim an atomic audit or
PDF fidelity pass until every required system child is final.

- `--systems` limits the batch to exact system names; never infer a system from
  a similarly named Word property.
- `--pending-only` hides final children from the review sheet, but does not
  delete or reopen them in the JSON queue.
- `--batch-size` and `--batch-index` select a stable order. The default
  `--review-order priority` shows source-backed page geometry and semantic
  roles before likely instruction/example text and explicitly non-rendering
  defaults. Every card remains pending and the card explains its rank; this is
  a work-order aid, not a decision artifact.
- `--review-order source-order` provides a deterministic producer-order pass
  for forensic rechecks. It does not alter source values, final dispositions,
  or strict-audit requirements.
- Edit only the matching child in `system_format_triage.json`. Preserve its
  `child_id`, `source_locator`, `source_text`, and observed source value.
- Rerun the strict atomic audit after changes. A final system aggregate is
  valid only when every child has an evidence-bound disposition.
- The audit records a fingerprint of the exact triage queue it reviewed. Any
  child edit, including a reason-only correction, makes the old audit stale;
  rerun it before coverage refresh, package validation, visual calibration, or
  a fidelity claim.

## Decision Order

For each system, answer these questions in order:

1. Is there a visible manuscript use, or only a named style/XML setting?
2. Does the observed value change rendered glyphs, spacing, line breaking,
   direction, colour, or geometry?
3. Is the value explicitly disabled or a known non-rendering Word-only policy?
4. Is the visible use an instruction/example rather than manuscript content?
5. If it is an active visible effect, which exact source role and span owns it?
6. Can the effect be recreated locally and checked on a same-content render?

Use the following routes:

| Evidence condition | Required disposition |
| --- | --- |
| Explicitly disabled or non-rendering setting | `default`, with a source-labelled executable class policy and reason. |
| Named style with no visible use | `not_observable` or `guidance` with `template_scaffold`; do not invent body formatting. |
| Instruction or placeholder example | `guidance`, split from adjacent manuscript text. |
| Active visible effect with a source-backed local role | `mapped` only after adding a role-local class/main interface. |
| Active visible effect whose LaTeX behavior is unknown or has not been render-checked | `unresolved`, with a targeted next check. |

Never use a generic `\\journalcharacterstyle`, `\\journalscriptlanguage`, or
`\\journalthemeformat` token to close unrelated source spans. The token must
implement the exact local policy or state the explicit disabled/non-rendering
default.

## System Rules

### Text Grid

Inspect section `w:docGrid` separately from local `w:snapToGrid`, East Asian
auto-spacing, punctuation, and vertical-text settings.

- A bare Word grid is not automatically a LaTeX baseline grid.
- If all relevant visible roles explicitly have `snapToGrid=false` and there is
  no active Chinese/mixed grid override, record the source opt-out as a
  `default`; do not enable a global grid.
- If a visible role actively snaps to a grid, preserve section scope, pitch, and
  local opt-outs. Map only that role after a same-content line and page-flow
  check.
- For Chinese/mixed templates, do not substitute an arbitrary CTeX baseline
  grid from OOXML numbers alone.

### Paragraph Break Policy

Inspect `w:suppressAutoHyphens` and `w:wordWrap` by child, including inherited
named styles and visible paragraph/table/furniture examples.

- A Word no-hyphenation or no-wrap value is not evidence for a document-wide
  TeX hyphenation setting. Retain its exact local role and scope.
- Split visible paragraph policy from an unexercised named-style rule. The
  latter may be `not_observable` or `guidance`; it must not create a class-wide
  line-breaking rule.
- Map an active local policy only after a same-content check of line breaks,
  page flow, and the surrounding paragraph. A source-disabled policy may be a
  documented `default` only when its owner token is executable and its scope
  is explicit.

### Character Effects

Split visible spans before deciding. A single system record may contain an
instructional theorem example, a highlighted manuscript placeholder, and an
unused named style; those cannot share one disposition.

- Instructional/example spans are `guidance`.
- A named character style with no visible use is a `template_scaffold` or
  `not_observable` record.
- Map actual local small caps, highlight, shading, borders, scale, position,
  spacing, or fit-text only through a role-local wrapper. `fitText` and glyph
  scaling require a same-content role render; do not replace them with a font
  size guess.

### Character Styles

For every visible `w:rStyle`, preserve the style ID, resolved effective format,
and exact span. A hyperlink-style span must remain local to its source text.

- If the target is an external URL/mailto, map URL, colour, and underline as a
  local editable link policy and check it on the matching role.
- If the named style is not visibly exercised, do not make it a document-wide
  font rule.
- Do not merge a character style into its paragraph style merely because their
  font family happens to match.

### Language, Complex Script, And RTL

Read actual Unicode content as well as `w:lang`, `w:cs`, `w:bCs`, `w:iCs`, and
`w:rtl`.

- Repeated inherited language slots on Latin-only text do not justify global
  Babel, Polyglossia, CJK, or RTL activation. Record an explicit `default`
  policy instead.
- Visible CJK, Arabic, Hebrew, or another non-Latin role needs a local engine,
  font, and direction decision backed by source text. Map it locally first;
  render-check line breaks and direction before promoting it to a document
  policy.
- A language alias in a footer/table cell never makes the whole paper RTL.

### Theme Fonts And Colours

The theme part is a palette definition, not proof that every palette entry is
used.

- Resolve only aliases used by a visible span or an actively used named style.
- Preserve tint/shade and the actual role. Do not use the generic Office palette
  as a substitute for a journal colour.
- An unexercised theme alias remains source evidence; record it as
  `not_observable` or `template_scaffold` rather than changing the global body
  font.

### Unmodeled OOXML Properties

Classify each property node separately. Do not leave one aggregate
`unmodeled_format` decision when its nodes have different effects.

- `w:noProof` affects Word spelling/grammar proofing, not PDF layout: record a
  non-rendering `default`.
- `w:adjustRightInd=0` and `w:mirrorIndents=0` explicitly disable their Word
  behaviors: record a source-disabled `default`; do not add a geometry change.
- An active or value-less `w:suppressOverlap` has no safe generic LaTeX
  equivalent. Preserve its part, attributes, and linked role; determine whether
  it is exercised by visible overlapping/floating content from the Word page
  or a confirmed publisher rule. Until then keep it `unresolved` rather than
  changing text-box, float, or paragraph geometry.
- Any enabled value, unknown node, or property that may affect visible flow,
  glyph geometry, or pagination remains local to its role and is `unresolved`
  until its behavior is understood and checked.

## Audit Gate

Before generating the final package-validation record, check that:

1. No aggregate system record hides child records with mixed dispositions.
   `audit_atomic_mapping.py --system-triage system_format_triage.json` must be
   used whenever the ledger contains a text-grid, tab-stop, paragraph-break,
   character-effect, character-style, script/language, theme, or unmodeled
   OOXML aggregate. The audit rejects a missing, stale, or childless v2 queue.
2. Every `default` is either source-disabled or non-rendering, with an
   executable owner token and a reason.
3. Every `mapped` system effect names a real source role, local interface, and
   role-matched verification status.
4. Every `guidance` record names one allowed guidance kind.
5. Every remaining `unresolved` record appears in `format_gap_log.md` with the
   next evidence or render action.

An unresolved active visible effect blocks a full-fidelity claim. A documented
non-rendering or source-disabled setting does not.
