# Feature Specification: Public Text Hygiene — No Internal Requirement IDs in End-User-Readable Text

**Spec ID**: PUBTXT
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     PUBTXT removes every citation of 3Powers' own internal requirement IDs (3PWR-FR-###, HARDN-FR-###,
     and friends), epic letters, and plan/spec numbers from all end-user-readable text — CLI help and
     echoed messages, engine source docstrings and comments, docs/ prose, and the scaffold assets that
     3pwr init ships into end-user repositories — and makes the rule durable via a written convention
     (AGENTS.md/CLAUDE.md) plus a permanent enforcement test in engine/tests/test_oss_readiness.py.
     Source plan: plan/031 Tracks A–C. -->

**Risk Tier**: Standard
<!-- Text-only rewrite plus one permanent test. No trust-spine module changes, no gate weakened
     (3PWR-FR-032). Standard, not Cosmetic, because the enforcement test becomes part of the
     repository's permanent quality bar and scaffold/seeded assets (sealed surfaces) are edited. -->

**Status**: Draft

**Input**: Plan 031, Tracks A–C: internal requirement IDs leak into end-user text — CLI help
strings, echoed messages, engine docstrings/comments (~1,500 occurrences), docs/ prose, and the
scaffold assets shipped by `3pwr init` — and no rule or test prevents regression.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

- Does **not** touch `engine/tests/**` — `Covers:` declarations are parsed by the
  `spec_conformance` gate; anti-gaming binding depends on them.
- Does **not** touch `specs/`, `plan/`, `.3powers/ledger.jsonl`, `.3powers/verdicts/`,
  `.3powers/runs/`, `docs/STATUS.md`, `AGENTS.md` (beyond adding the convention), `CLAUDE.md`
  (beyond the mirror note), or memory files — the sanctioned exemption list.
- Does **not** ban bare `FR-###`/`NFR-###` — that is how scaffold templates legitimately teach end
  users to number their own requirements.
- Does **not** change any behavior: text-only edits, with exact-string test expectations updated
  in the same commit.

## Requirements *(mandatory)*

### Functional Requirements

- **PUBTXT-FR-001**: A disposable, stdlib-only scanner (`plan/scratch/scan_public_ids.py`) MUST
  walk the public surfaces — `engine/src/threepowers/**` (including `scaffold/**` assets),
  `docs/**` minus `STATUS.md`, `README.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `CHANGELOG.md`,
  `.3powers/**` seeded copies, and `.github/**` non-agent files — match namespaced requirement IDs
  plus the sibling forms `(epic X#)` and `(plan NNN)`/`(spec NNN)`, classify each hit
  (`help-string`, `echoed-message`, `docstring`, `comment`, `doc-prose`, `scaffold-asset`,
  `format-example`), and emit a per-file inventory with per-kind and per-namespace summary counts.
- **PUBTXT-FR-002**: Every must-go inventory entry MUST be resolved: where the citation carried
  meaning it is rewritten as plain-English rationale; where it carried none it is deleted. This
  applies equally to requirement IDs and the sibling `(plan NNN)`/`(spec NNN)`/`(epic X#)` forms.
- **PUBTXT-FR-003**: All of `engine/src/threepowers/` MUST be cleaned — docstrings and inline
  comments included. Rewrites convert the citation into the rationale it stood for; every public
  module, class, and function keeps (or gains) a docstring — rewrite, never delete.
- **PUBTXT-FR-004**: Format-teaching text MUST stay legal: bare `FR-###`/`NFR-###` remains allowed
  everywhere, and examples showing the full namespaced format use the reserved `DEMO-` example
  namespace (e.g. `DEMO-FR-001`) or explicit placeholder forms (`<SPECID>-FR-###`).
- **PUBTXT-FR-005**: Scaffold assets under `engine/src/threepowers/scaffold/**` and the repo's own
  `.3powers/` seeded twins MUST be edited in lockstep (same commit per file pair); a fresh
  `3pwr init` in a scratch directory MUST ship zero namespaced internal IDs.
- **PUBTXT-FR-006**: The convention MUST be written down in `AGENTS.md`'s Conventions section
  (with a mirror note in `CLAUDE.md`): internal requirement IDs, epic letters, and plan/spec
  numbers live only in `specs/`, `plan/`, engine tests' `Covers:` lines, commit messages,
  `docs/STATUS.md`, and `AGENTS.md`/`CLAUDE.md` — never in end-user-readable text.
- **PUBTXT-FR-007**: `engine/tests/test_oss_readiness.py` MUST gain a permanent enforcement
  section: surfaces are `docs/**` minus `STATUS.md`, `README.md`, `CONTRIBUTING.md`,
  `GOVERNANCE.md`, `CHANGELOG.md`, and `engine/src/threepowers/**`; the forbidden pattern is the
  namespaced form only — `\b[A-Z0-9][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b` — plus `\(epic [A-Z][0-9]\)`;
  a short frozen allowlist admits the `DEMO-` namespace and explicit placeholder forms; the failure
  message names file, line, matched token, and the one-line rule; the scan is file-based and
  hermetic (no process spawning).
- **PUBTXT-FR-008**: The disposable scanner and its inventory MUST be deleted once the enforcement
  test is green — their regex and surface list live on inside the permanent test.

### Non-Functional Requirements

- **PUBTXT-NFR-001**: Every commit in the rewrite stays green — tests asserting exact help or
  message strings are updated in the same commit as each text change.
- **PUBTXT-NFR-002**: Trust-spine coverage stays ≥ 95% and the mutation-testing scope is neither
  widened nor narrowed.

## Success Criteria *(mandatory)*

1. `3pwr --help` (and every subcommand help) contains no namespaced internal requirement ID.
2. A fresh `3pwr init` in a scratch directory ships a `.3powers/` tree with zero namespaced
   internal IDs.
3. The permanent enforcement test fails on a seeded violation and passes on the cleaned tree.
4. The full engine check suite (pytest, ruff, mypy) and the self-application gate run stay green.
