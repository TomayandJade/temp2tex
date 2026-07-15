# Atomic Reconstruction Protocol

## Purpose

This protocol keeps a model focused on reconstructing a journal template,
rather than transcribing a Word sample, trusting an initial converter, or
optimizing a PDF score. The template is rebuilt from small, traceable source
decisions.

## The Evidence Unit

Use the smallest visible source unit that has formatting meaning:

- an ordinary paragraph and each contiguous run-format span;
- a table-cell paragraph together with its cell grid, border, fill, merge, and
  alignment context;
- a drawing plus its anchor, dimensions, wrap state, and caption relation;
- a footnote/endnote paragraph and its marker;
- a header/footer paragraph, field, or page-furniture object.

Do not use whole-document defaults as a substitute for these units. A named
Word style is supporting evidence, not a mapping, until a role-matched visible
unit or an explicit sparse-template style rule supports it.

## Required Loop

For every unit considered for template behavior, record the following before
editing the class:

| Question | Required record |
| --- | --- |
| What is it? | Source ID, text/object identity, and role candidate. |
| What is visible? | Paragraph geometry plus every local run, cell, or object format. |
| Why does it represent that role? | Role-matched exemplar, explicit named style, or official instruction; otherwise reject it as guidance/example/noise. |
| Who owns it in LaTeX? | Exact macro, environment, class setting, or fixture location. |
| What remains uncertain? | `default`, `unresolved`, `not_observable`, or render-confirmation action. |

Use one owner per requirement. Split mixed paragraphs at formatting or
semantic boundaries. For example, a bold `Abstract` label and regular abstract
text are two units; an author line followed by red typesetting guidance is an
author-format unit plus a guidance unit, not a red author rule.

## Classification Guards

- **Authors:** require a plausible name sequence and first-page context.
  Exclude affiliations, addresses, dates, correspondence, funding, abstracts,
  keywords, and typography instructions. For Chinese names, a sequence of
  two-to-four CJK-character names with author separators and optional
  affiliation marks is strong evidence; commas alone are not.
- **Headings:** require semantic style, outline structure, role-matched wording,
  or repeated rendered evidence. Lists and instructions do not become headings.
- **Captions:** require an adjacent/nearby labelled figure or table relation.
  A sentence explaining caption rules is guidance, not a caption exemplar.
- **Tables:** inspect cells as text and geometry. Preserve row/column,
  border/fill, merge, alignment, and cell-local runs. Never pass a table by
  masking or rasterising it.
- **Images:** image pixels may differ in a render comparison, but frame size,
  position, caption, wrapping, whitespace, and later page flow remain required
  audit targets.

## Mapping Rules

Put reusable journal behavior in `journal-template.cls`; put editable example
content in `main.tex`. Keep source-specific art under `assets/` or `figures/`.
Do not encode role formatting in a flattened converted manuscript.

For each change, identify the ledger IDs it implements. If no ID or explicit
default/gap justifies the change, do not make it. If one evidence unit conflicts
with a global rule, preserve it as a local override or leave a gap; do not
silently erase it.

## Audit Gate

Before visual comparison, verify that each applicable role has:

1. at least one classified evidence unit or an explicit absence record;
2. a source/default/gap status;
3. one editable LaTeX owner;
4. a compiled fixture that exercises the owner; and
5. a named audit action.

Only then use same-content PDF comparison to refine already mapped geometry.
PDF results can reject or promote a candidate mapping; they cannot manufacture
missing role evidence. A failed comparison returns the agent to the specific
ledger item, not to generic margin or pixel-threshold tuning.
