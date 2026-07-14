# Word Input Triage

Use this decision layer before extracting styles or writing LaTeX. “Any journal
Word template” means the skill must degrade honestly across Word containers and
evidence quality. It does not mean an unreadable file contains recoverable
evidence.

## 1. Establish Provenance

- Prefer the current journal or publisher author page and its directly linked
  template. Record the page URL, download URL, access date, local path, and
  file hash.
- When several official Word files exist, identify article type, language,
  edition date, and current/legacy status before choosing the primary source.
  Preserve the other files as variants; never merge incompatible editions into
  one invented layout.
- Treat a local file with no official provenance as user-supplied evidence. It
  may still be converted, but do not label its rules official without support.

## 2. Detect the Container

Inspect the payload before trusting the suffix.

| Source condition | Primary handling | Required record |
| --- | --- | --- |
| Valid DOCX/DOTX/DOCM/DOTM OpenXML package | Read ZIP parts, relationships, styles, sections, headers/footers, notes, drawings, and media directly. Never execute macros. | Actual package type and retained original hash. |
| Legacy binary DOC/DOT or RTF | Retain the original; convert a copy through an available Word-compatible renderer for structural inspection and rendering. | Conversion engine, converted-copy path, and original hash. |
| Extension disagrees with payload | Follow the payload type and record the mismatch. | Claimed suffix, detected type, and inspection method. |
| Protected or encrypted Word file | Do not claim XML/style inspection. Use an accessible official PDF, author page, or user-provided unlocked copy if available. | Protection failure and every replacement evidence source. |
| Truncated, HTML-disguised, or corrupt download | Reject it as a Word artifact, retry from the official page, or use another official source. | Validation failure; never hash the bad payload as a valid template. |

## 3. Classify Template Content

- **Populated manuscript example:** prioritize visible role paragraphs and the
  rendered page, then reconcile them with effective style chains and direct
  formatting.
- **Sparse or blank style template:** inspect named styles, document defaults,
  section geometry, headers/footers, numbering, and media. Mark unused styles
  as template candidates, not rendered proof. Populate only a working copy
  with representative content for comparison.
- **Layout-table manuscript:** distinguish page-layout cells from semantic
  article tables. A body exemplar inside a layout table can supply qualified
  body evidence, but the LaTeX output should remain normal editable flow.
- **Text-box or drawing-heavy template:** separate flow content, page furniture,
  and decorative assets. Preserve coordinates and wrapping as candidates until
  rendering confirms their semantic role.
- **Mixed sections or article types:** choose the repeated manuscript-body frame
  as the default and preserve other section frames as explicit candidates.

## 4. Resolve Language and Defaults

- Detect English, Chinese, or mixed content from visible text, styles, and
  official instructions. Do not infer language from filename alone.
- Use official rules where available. For every missing rule, apply the matching
  documented language default and add a `default` entry to
  `template_spec.json` and `format_gap_log.md`.
- Never turn a publisher convention remembered by the model into an official
  rule without source evidence.

## 5. Choose the Deliverable Path

- If the Word structure is readable, build the evidence packet and class from
  it, then render when tools are available.
- If structure is unreadable but an official rendered PDF or detailed author
  page exists, reconstruct from those sources and label Word-only properties
  unverified.
- If only partial evidence is usable, still deliver the editable
  `journal-template.cls + main.tex` package with conservative defaults and an
  exact gap log. Do not claim visual equivalence.
- If no source is readable and no official layout evidence exists, deliver only
  a clearly default-based starter package when the user asked for an immediate
  artifact; otherwise request an accessible source. In both cases, state that
  journal-specific reconstruction is unverified.

## 6. Verification Boundary

Missing Word, LibreOffice, TeX, or PDF tooling is a pending verification stage,
not automatic conversion failure. Missing or inaccessible source evidence is
different: it caps the fidelity claim. Record which condition applies so a
later model can resume without repeating or fabricating the evidence search.
