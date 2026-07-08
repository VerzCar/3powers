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

**Input**: Plan 031, Tracks A–C: internal requirement IDs leaked into end-user text — CLI help
strings, echoed messages, engine docstrings/comments (~1,500 occurrences), docs/ prose, and the
scaffold assets shipped by `3pwr init` — and no rule or test prevented regression.

*Process narrative (how the cleanup was executed, not an enduring requirement):* a disposable,
stdlib-only scanner (`plan/scratch/scan_public_ids.py`) walked the public surfaces, matched
namespaced requirement IDs plus the sibling `(epic X#)` and `(plan NNN)`/`(spec NNN)` forms,
classified each hit (`help-string`, `echoed-message`, `docstring`, `comment`, `doc-prose`,
`scaffold-asset`, `format-example`), and emitted a per-file inventory. Every must-go entry was
resolved — citations carrying meaning rewritten as plain-English rationale, the rest deleted —
with scaffold assets and the repo's own `.3powers/` seeded twins edited in lockstep and
exact-string test expectations updated in the same commit as each text change. The scanner and
its inventory were then deleted; their regex and surface list live on inside the permanent
enforcement test. The requirements below capture only the enduring, testable properties that
cleanup established.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

- Does **not** rewrite existing citations in `engine/tests/**` — `Covers:` declarations are
  parsed by the `spec_conformance` gate; anti-gaming binding depends on them. (The permanent
  enforcement test is an *addition* to `engine/tests/`, not a rewrite.)
- Does **not** touch `specs/`, `plan/`, `.3powers/ledger.jsonl`, `.3powers/verdicts/`,
  `.3powers/runs/`, `docs/STATUS.md`, `AGENTS.md` (beyond adding the convention), `CLAUDE.md`
  (beyond the mirror note), or memory files — the sanctioned exemption list.
- Does **not** ban bare `FR-###`/`NFR-###` — that is how scaffold templates legitimately teach end
  users to number their own requirements.
- Does **not** change any behavior: text-only edits, with exact-string test expectations updated
  in the same commit.

## Requirements *(mandatory)*

### Functional Requirements

- **PUBTXT-FR-001**: Every end-user-readable surface — `docs/**` minus `STATUS.md`;
  `README.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `CHANGELOG.md`; and the whole engine source
  tree `engine/src/threepowers/**` (scaffold assets included) — MUST carry zero namespaced
  internal requirement IDs (the `<SPECID>-FR-###`/`<SPECID>-NFR-###` form) and zero
  `(epic X#)` references.
- **PUBTXT-FR-002**: Engine source docstrings and inline comments MUST be citation-free, and
  every module under `engine/src/threepowers/` MUST keep a module docstring — citations are
  rewritten into the rationale they stood for, never resolved by deleting the docstring.
- **PUBTXT-FR-003**: The scaffold assets shipped by `3pwr init` (everything under
  `engine/src/threepowers/scaffold/**`) MUST carry no namespaced internal requirement IDs — a
  fresh `3pwr init` ships a `.3powers/` tree with zero such IDs.
- **PUBTXT-FR-004**: Format-teaching text MUST stay legal: bare `FR-###`/`NFR-###` remains allowed
  everywhere, and examples showing the full namespaced format use the reserved `DEMO-` example
  namespace (e.g. `DEMO-FR-001`) or explicit placeholder forms (`<SPECID>-FR-###`).
- **PUBTXT-FR-005**: The convention MUST be written down in `AGENTS.md` (the "Open-source
  readiness" section, with a mirror note in `CLAUDE.md`): internal requirement IDs, epic letters,
  and plan/spec numbers live only in `specs/`, `plan/`, engine tests' `Covers:` lines, commit
  messages, `docs/STATUS.md`, and `AGENTS.md`/`CLAUDE.md` — never in end-user-readable text —
  and format teaching uses the reserved `DEMO-` namespace.
- **PUBTXT-FR-006**: A permanent enforcement test in `engine/tests/test_oss_readiness.py` MUST
  guard the rule: surfaces are `docs/**` minus `STATUS.md`, `README.md`, `CONTRIBUTING.md`,
  `GOVERNANCE.md`, `CHANGELOG.md`, and `engine/src/threepowers/**`; the forbidden pattern is the
  namespaced form only — `\b[A-Z0-9][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b` — plus `\(epic [A-Z][0-9]\)`;
  a short **frozen** allowlist admits the `DEMO-` namespace and explicit placeholder forms; the
  failure message names file, line, matched token, and the one-line rule; the scan is file-based
  and hermetic (no process spawning).
- **PUBTXT-FR-007**: No disposable scan tooling ships in the repository — the temporary inventory
  scanner was deleted once the permanent test landed; its regex and surface list live only inside
  the enforcement test (`plan/` carries no `scan_public_ids.py`).

### Non-Functional Requirements

- **PUBTXT-NFR-001**: The hygiene checks run as part of the ordinary engine test suite —
  file-based and offline (plain-file reads, no network, no subprocess).
- **PUBTXT-NFR-002**: The trust-spine mutation-testing scope in `engine/pyproject.toml`
  (`[tool.mutmut]`) is unchanged: `only_mutate` names exactly `anchor`, `canonical`, `keys`,
  `ledger`, `speclock`, and `verify`, and trust-spine coverage stays ≥ 95%.

## Success Criteria *(mandatory)*

1. `3pwr --help` (and every subcommand help) contains no namespaced internal requirement ID.
2. A fresh `3pwr init` in a scratch directory ships a `.3powers/` tree with zero namespaced
   internal IDs.
3. The permanent enforcement test fails on a seeded violation and passes on the cleaned tree.
4. The full engine check suite (pytest, ruff, mypy) and the self-application gate run stay green.
