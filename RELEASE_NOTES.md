# Release Notes

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
