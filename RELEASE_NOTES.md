# Release Notes

## v0.2.0

This release strengthens Temp2TeX as a guided reconstruction skill. It adds
auditable checkpoints that keep an agent working from Word evidence, prevent
premature completion claims, and preserve a clear path from individual source
features to editable LaTeX ownership.

### Added

- A bounded atomic-mapping workflow with review packets, merge helpers, and
  strict audit records for paragraph, run, table, drawing, note, and
  page-furniture evidence.
- System-format triage for OOXML settings, themes, and named styles, including
  child-level dispositions and links back to the visible source role they
  affect.
- A readiness assessment and handoff-status contract that report the next safe
  action, package fingerprint, and verification boundary.
- Ledger-bound semantic confirmation for title, author, and affiliation style
  candidates before they become final class mappings.
- An explicit instruction-versus-style guard. Author-facing text such as
  `List`, `Include`, `Please`, `Present`, and `Authors are` remains guidance
  even when it uses an author or affiliation Word style.
- A documented protocol for measuring loaded-skill agent behavior separately
  from deterministic corpus regression.

### Changed

- `journal-template.cls` and `main.tex` remain the default package
  architecture, with validation requiring the delivered class to be actively
  loaded by the fixture.
- Ordinary conversions now follow a focused evidence, mapping, build, audit,
  and handoff loop. Full corpus regression remains a skill-development or
  explicitly requested comparison activity.
- Tool availability is recorded as part of verification status. A missing
  local renderer produces an explicit pending check rather than a fabricated
  visual result.

### Distribution

Publisher-owned templates, downloaded corpora, and generated regression
workspaces remain excluded from this release.

## v0.1.1

This release refines temp2tex as an agent-guidance skill for reconstructing
editable LaTeX journal templates from official Word and related publisher
evidence.

### Added

- An atomic reconstruction protocol for paragraph/run, table-cell, drawing,
  note, and page-furniture evidence.
- Explicit phase gates from source evidence through role mapping, build, audit,
  and handoff.
- A source-feature coverage audit that requires editable LaTeX ownership or an
  explicit gap for each observable source feature.
- Same-content, role-level PDF comparison guidance for optional layout
  verification.

### Changed

- An initial converter output is now explicitly treated as a draft to audit,
  not proof of template fidelity.
- Table structure remains a full audit target; image-content differences may be
  excluded only from the dedicated format metric while image geometry and flow
  remain checked.
- Chinese author detection guidance now separates author names from affiliations
  and trailing formatting instructions.

### Distribution

Publisher-owned template sources, local training corpora, and generated
regression workspaces remain excluded from the public repository.

## v0.1.0

Initial public release of the temp2tex Codex skill.
