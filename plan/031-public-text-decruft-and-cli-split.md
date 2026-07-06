# Plan 031 — Public-text de-cruft and the cli.py split

**Git branch:** `feat/031-public-text-decruft-and-cli-split` — **not yet created.** This plan was
authored while plan 030 is still implementing on `feat/030-run-identity-gates-ux`; the branch is
cut from `main` (with that name) only after plan 030's branch merges. Until then this file rides
along uncommitted / on the 030 branch for review.

**Covers four tracks** planned together because they share one root cause (a single 5,700-line
`cli.py` accreted every feature's help text, messages, and internal requirement-ID citations, and
the same citation habit spread to docs and scaffold assets) and compound each other: the inventory
(A) feeds the rewrite (B), the rewrite defines the allowlist the enforcement test (C) needs, and
the split (D) is far cheaper on text that has already been cleaned. Each track is independently
deliverable and tested.

## Decisions recorded

Authored non-interactively as recommendations; **confirmed by the user on 2026-07-06** when
approving handover to the implementation plan. The former open questions and their resolutions
are recorded at the end.

| # | Decision | Recommendation | Rationale |
|---|---|---|---|
| 1 | Are engine docstrings/inline comments cleaned too, or only user-visible strings? | **Yes — clean docstrings and comments across `engine/src/threepowers/`** (rewrite the ID citation into plain-English rationale; never delete the docstring). Alternative: leave docstrings/comments as internal traceability and clean only help/echoed strings + docs + scaffold. | The repo is public, so "internal" comments are public text. Traceability survives without source citations: specs in `specs/`, `Covers:` in tests, requirement-tagged commits, and `docs/STATUS.md`. Cleaning all of engine source also makes the enforcement rule crisp and mechanically checkable (see Track C) instead of "strings yes, comments no", which no scanner can reliably distinguish. |
| 2 | Do `AGENTS.md` / `CLAUDE.md` keep their spec IDs? | **Yes — exempt, alongside `docs/STATUS.md`.** | They are maintainer/agent workflow documents; AGENTS.md's own convention ("tag every task and commit with its requirement ID") is *about* the IDs. Stripping them there would destroy the traceability the judiciary depends on. The exemption list becomes exactly: `specs/`, `plan/`, engine tests (`Covers:`), `.3powers/ledger.jsonl` + `verdicts/`, `docs/STATUS.md`, `AGENTS.md`, `CLAUDE.md`, memory files. |
| 3 | Scanner location and lifetime | **`plan/scratch/scan_public_ids.py`, disposable** — deleted in the same unit of work that closes Track B. Its regex and surface list live on inside the permanent test (Track C). | `plan/` is already internal-only; nothing under it ships. Putting the scanner in `engine/` would force tests/typing/coverage for a throwaway. |
| 4 | Enforcement pattern scope | **Forbid namespaced IDs (`XYZ-FR-###` / `XYZ-NFR-###`) generally on the scanned surfaces; allow bare `FR-###`/`NFR-###`; keep a small explicit allowlist for teaching examples using a reserved example namespace (e.g. `DEMO-FR-001`).** Alternative: forbid only the harvested list of known internal namespaces (3PWR, HARDN, CLIUX, …). | Bare `FR-###` is how scaffold templates legitimately instruct end users to number *their own* requirements — banning it would break the product's own format teaching. A general namespaced ban is future-proof (new internal specs are caught automatically); a namespace blocklist rots. The reserved example namespace keeps docs able to show the full namespaced format without tripping the test. |
| 5 | cli.py split shape | **Convert `threepowers/cli.py` into a `threepowers/cli/` package**; each command-group module owns its `cmd_*` functions *and* registers its own subparser via a `register(sub, common)` hook; `cli/__init__.py` assembles the parser and re-exports the public surface so `threepowers.cli:main` (pyproject script target) and every existing test import keep working unchanged. | Keeps help text next to the implementation it describes (so Track B's cleaned strings don't migrate twice), zero `pyproject.toml` change, zero test churn beyond none-or-mechanical imports. |
| 6 | Split any other file now? | **No.** cli.py is 5,671 lines on `main`; every other module is ≤ ~620 (`runner.py` 619, `gates.py` 576, `oracle.py` 572, `orchestrate.py` 566). List those as future candidates only, no action in this plan. | "Not a full engine rewrite" is the intent's own scope line. Modules under 650 lines are maintainable; splitting them buys churn, not clarity. |
| 7 | Delivery order relative to plan 030 | **Implementation starts only after `feat/030-run-identity-gates-ux` merges to `main`; the feature branch `feat/031-public-text-decruft-and-cli-split` is cut from `main` at that point.** Within this plan: A → B → C → D, as two delivery units on the feature branch (A+B+C, then D). | Plan 030's remaining phases (3–9) churn cli.py heavily, including a Rich-based terminal-UX refactor. Rewriting or splitting cli.py in parallel guarantees severe conflicts. Splitting *after* the text is clean means the moved lines are already final. |

---

## Why now

1. **Internal IDs leak into end-user text.** CLI help strings and echoed messages cite 3Powers'
   own internal requirement IDs — e.g. *"also cross-check the chain against the latest local anchor
   tag (HARDN-FR-005)"* and *"per-stage dispatch timeout in seconds (RUNLIVE-FR-004; default:
   configured, 1800)"*. To an end user these tokens are noise at best and confusing at worst; they
   read like error codes but resolve to nothing the user can see. The engine source carries
   ~1,100 occurrences of the pattern across nearly every module (cli.py alone: ~330); `docs/`
   carries ~37 outside the sanctioned STATUS.md; the **scaffold assets that `3pwr init` ships into
   end-user repos** (constitution, agent YAMLs, config YAMLs, prompt templates, adapter CONTRACT)
   are full of them — the leak literally installs itself into customers' repositories.
2. **No rule prevents regression.** Plan 022 established the de-jargon principle for docs and
   built `engine/tests/test_oss_readiness.py`, but nothing scans CLI text or scaffold assets, and
   the convention is not written down as a repo rule. Every new feature re-imports the habit.
3. **cli.py is past maintainability.** At 5,671 lines (on `main`; more after plan 030) it is 9×
   the next-largest module, holds ~45 command functions plus a 575-line parser assembly, and every
   plan touches it. It is the single biggest merge-conflict and review-cost driver in the repo.
4. **Timing is right.** Plan 030 is the last queued large cli.py change. Cleaning and splitting
   immediately after it merges hits the quietest window cli.py will see.

---

## Sequencing precondition (read first)

Plan 030 is mid-implementation on the unmerged branch `feat/030-run-identity-gates-ux` (phases 1–2
of 9 committed). Its remaining phases rewrite large parts of cli.py (gate diagnostics, progress
file, phase prompts, and the Rich terminal-UX refactor of `style.py`/`frame.py`).

**Hard rule: no implementation work starts until plan 030's branch has merged to `main`.** At that
point the feature branch `feat/031-public-text-decruft-and-cli-split` is cut fresh from the new
`main` and this plan file is committed there. Track A's scanner may be written early (it is
read-only and disposable), but its authoritative inventory run happens against post-030 `main`,
because 030 adds new user-visible text (and new spec namespaces
RUNID/GDIAG/GATECFG/GATEPIPE/PROGFILE/PHASEPR/TRIX) that must be swept too.

---

## What is in scope for stripping — and what is not

The distinction that drives everything below:

- **Must go:** parenthetical citations of 3Powers' *own internal* requirement IDs in publicly
  readable text — `"(HARDN-FR-005)"`, `"(3PWR-FR-059)"`, `"(CLIUX-FR-004/006/013)"`, and the
  sibling forms "(epic A3)" / "(plan 030)" / "(spec 017)". Where the citation carried meaning,
  rewrite it as plain-English rationale; where it carried none, delete it.
- **Stays — load-bearing or sanctioned:**
  - `engine/tests/**` — `Covers:` declarations are parsed by the `spec_conformance` gate
    (`engine/src/threepowers/conformance.py`) to trace spec→test; anti-gaming binding depends on
    them. **Out of scope entirely.**
  - `specs/`, `plan/`, `.3powers/ledger.jsonl`, `.3powers/verdicts/`, `.3powers/runs/` — internal
    and/or machine artifacts.
  - `docs/STATUS.md` — the deliberate traceability document (plan 022's sanctioned exception).
  - `AGENTS.md`, `CLAUDE.md`, memory files — maintainer/agent workflow docs (proposed decision 2).
- **Stays — legitimate format teaching:** text explaining the product's *mechanism*, e.g.
  "requirements are namespaced `<SPECID>-FR-###`", the scaffold spec template instructing users to
  write `FR-001`, `FR-002`, …, or a doc example using a clearly hypothetical namespace. These are
  the product teaching users its own convention, not internal citations. Track C's allowlist
  exists for exactly these.

---

## Track A — Inventory scanner (disposable)

### Problem

~1,100 engine-source occurrences, ~37 in cleanable docs, dozens across scaffold assets and the
repo's own `.3powers/` seeded copies — too many to rewrite from grep output alone, and the
must-go / format-teaching distinction needs a classified worklist, not a flat match list.

### Approach

A single disposable script, `plan/scratch/scan_public_ids.py` (stdlib only, no engine imports), that:

1. Walks the public surfaces: `engine/src/threepowers/**/*.py` (including `scaffold/**` assets),
   `docs/**` (minus `STATUS.md`), `README.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `CHANGELOG.md`,
   `.3powers/**` seeded copies (`README.md`, `memory/constitution.md`, `templates/**`, `agents/*.yaml`,
   `config/*.yaml`, `adapters/**`), and `.github/**` non-agent files. Exclusions per the scope
   section above.
2. Matches `\b([A-Z][A-Z0-9]{2,}-)?(FR|NFR)-[0-9]{2,3}\b` plus the sibling patterns
   `\(epic [A-Z][0-9]\)` and `\((plan|spec) [0-9]{3}\)`.
3. Classifies each hit by context: `help-string` (inside an argparse `help=`/`description=`),
   `echoed-message` (inside a `print`/styler/notify call), `docstring`, `comment`, `doc-prose`,
   `scaffold-asset`, `format-example` (bare `FR-###`/`NFR-###`, or `<SPECID>-` placeholder forms).
   Classification is heuristic — good enough to order the work, reviewed by a human during Track B.
4. Emits `plan/scratch/031-id-inventory.md`: one table per file, columns *line / kind / matched
   text / surrounding excerpt*, plus a summary count per kind and per namespace (the namespace
   census seeds Track C's reserved-example choice).

### Deliverables

- `plan/scratch/scan_public_ids.py` and `plan/scratch/031-id-inventory.md` — **both deleted in the
  final Track B commit**. Neither ships in `engine/`; the regex and surface list are transplanted
  into the permanent test (Track C) before deletion.

### Tests

None (disposable, never shipped). Sanity check: its total count over `engine/src/threepowers/`
must roughly match the raw grep census recorded in this plan (~1,100), or the walker has a hole.

---

## Track B — Rewrite/remove the findings

### Problem

The inventory's must-go entries have to become text an end user can act on. Two real examples of
the target transformation, from `cli.py` help text:

| Before | After |
|---|---|
| `"also cross-check the chain against the latest local anchor tag (HARDN-FR-005)"` | `"also cross-check the chain against the latest local anchor tag"` (the ID carried nothing) |
| `"per-stage dispatch timeout in seconds (RUNLIVE-FR-004; default: configured, 1800)"` | `"per-stage dispatch timeout in seconds (default: the configured value, or 1800)"` |

And a docstring example where the ID *did* carry meaning and becomes prose:

| Before | After |
|---|---|
| `"""Rotate the ledger signer (HARDN-FR-004): the OUTGOING key signs its successor."""` | `"""Rotate the ledger signer: the OUTGOING key signs its successor, so the chain of custody is unbroken."""` |

### Approach

Work through the inventory in five passes, each independently committable and gate-checked:

**B1 — cli.py help strings and echoed messages.** Every argparse `help=`/`description=` and every
user-echoed message (print/styler/notify/checklist lines). This is the highest-value pass and a
prerequisite for Track D (the split must move clean text).

**B2 — other engine modules' user-visible strings.** Error messages, warnings, and hints raised or
printed from `runner.py`, `orchestrate.py`, `gates.py`, `oracle.py`, `gitflow.py`, `scaffold.py`,
`runpreflight.py`, `steering.py`, and the rest (the census table in Track A orders them).

**B3 — engine docstrings and comments** (per proposed decision 1). Rewrite the citation into the
rationale it stood for; **every public module/class/function keeps a docstring** — this pass
rewrites, never deletes, so docstring-presence conventions and module doc headers survive.
`engine/tests/**` untouched.

**B4 — docs.** `docs/cli-reference.md` (14), `docs/threat-model.md` (11), `getting-started.md` (3),
`brownfield.md` (3), `migration-remove-speckit.md` (2), `engine-architecture.md` (2),
`troubleshooting.md` (1), `concepts.md` (1). `STATUS.md` untouched. Where a doc teaches the ID
*format*, convert any real internal namespace in the example to the reserved example namespace
(Track C, e.g. `DEMO-FR-001`).

**B5 — scaffold assets and the repo's own seeded copies, in lockstep.**
`engine/src/threepowers/scaffold/constitution.md` (26 hits, cites `3PWR-FR-###` throughout),
`scaffold/agents/*.yaml`, `scaffold/config/*.yaml`, `scaffold/templates/**` (agent prompt
templates), `scaffold/adapters/CONTRACT.md` — and the mirrored copies under `.3powers/`
(`memory/constitution.md`, `templates/**`, `agents/`, `config/`, `adapters/`, `README.md`). The two
sides must stay byte-consistent wherever a parity check exists (see Risks). The constitution
rewrite converts each `3PWR-FR-###` citation into the plain rule it encodes — the constitution is
the text most literally shipped into end-user repos and must stand alone.

### Deliverables

- All must-go inventory entries resolved (rewritten or deleted); format-teaching entries either
  left bare (`FR-###`) or converted to the reserved example namespace.
- Scanner + inventory deleted in the closing commit of this track.

### Tests

- Existing suite stays green after every pass: `(cd engine && uv run pytest)`, `ruff check .`,
  `mypy src` — several existing tests assert exact help/message text and will need their expected
  strings updated (mechanical, same commit as the text change).
- Trust-spine coverage (canonical, keys, ledger, verify, speclock, anchor) stays ≥95%; the
  `[tool.mutmut]` scope in `engine/pyproject.toml` is not widened or narrowed.
- `3pwr gate run --path engine` (self-application) green; see Risks for the seal caveat.
- Smoke: `uv tool install --force ./engine && 3pwr --help` and a spot-check of `3pwr verify --help`
  / `3pwr run --help` show no internal IDs.

---

## Track C — Durable convention + enforcement

### Problem

Without a written rule and a failing test, the next feature reintroduces the citations within a
week — every existing module demonstrates the habit is the default.

### Approach

**C1 — Convention text.** Extend the existing "Conventions" section of `AGENTS.md` (and the mirror
note in `CLAUDE.md`'s "Working in this repo") with the rule, stated positively:

> Internal requirement IDs (`3PWR-FR-###` and friends), epic letters, and plan/spec numbers live in
> `specs/`, `plan/`, engine tests (`Covers:` lines), commit messages, `docs/STATUS.md`, and this
> file — **never** in end-user-readable text: CLI help and messages, engine source docstrings and
> comments, `docs/` prose, or scaffold assets shipped by `3pwr init`. Docs that teach the ID
> format use the reserved example namespace (`DEMO-FR-###`) or bare `FR-###`.

This composes with plan 022's existing de-jargon rule (keep the *user's own* IDs in their
artifacts; strip *3Powers'* IDs everywhere user-facing).

**C2 — Permanent test.** Extend `engine/tests/test_oss_readiness.py` (same module, same
repo-root-relative discovery and skip-when-absent pattern it already uses) with a new section:

- Surfaces scanned: `docs/**` minus `STATUS.md`; `README.md`; `CONTRIBUTING.md`; `GOVERNANCE.md`;
  `CHANGELOG.md`; `engine/src/threepowers/**` (source *and* scaffold assets; `engine/tests/`
  excluded by construction — per proposed decision 1 the whole source tree is scannable once B3
  lands).
- Pattern: the namespaced form only — `\b[A-Z][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b` — plus
  `\(epic [A-Z][0-9]\)`. Bare `FR-###`/`NFR-###` is allowed (format teaching).
- Allowlist: the reserved example namespace (`DEMO-`) plus explicit placeholder forms
  (`<SPECID>-FR-###`, `XYZ-FR-###` if any doc uses them). Kept as a short frozen set in the test
  with a comment pointing at the AGENTS.md rule.
- Failure message: file, line, matched token, and the one-line rule — every failure actionable.
- Scanning the argparse *source* strings (via the file scan above) rather than spawning
  `3pwr --help` keeps the test hermetic and fast; since the whole cli source is scanned, help
  strings are covered by construction.

### Deliverables

- AGENTS.md + CLAUDE.md convention text (one small diff each).
- New test section in `engine/tests/test_oss_readiness.py` (with its own `Covers:` line once the
  spec for this plan is authored — see "Spec files" below).

### Tests

- The new test itself, red before B completes / green after — land it in the same PR as Track B,
  ordered last, so the PR is self-verifying.
- The full oss-readiness module still passes under mutmut's copied layout (it already skips when
  the docs tree is absent; the new section reuses that guard).

---

## Track D — Split cli.py into a package

### Problem

`engine/src/threepowers/cli.py` is 5,671 lines on `main` (larger after plan 030): ~45 `cmd_*`
functions, ~60 private helpers, a 575-line `build_parser()`, and `main()`. Every feature edits it;
review, merge, and navigation costs all scale with the single file.

### Approach

**Pure refactor. Identical behavior, identical (post-Track-B) help text, identical exit codes and
`--json` payloads. The `3pwr` entry point (`[project.scripts] "3pwr" = "threepowers.cli:main"` in
`engine/pyproject.toml`) keeps working with no pyproject change** because the package's
`__init__.py` exports `main`.

Target layout, grounded in the actual command groups and their current line ranges on `main`
(ranges shift after 030 merges; regroup by the same `cmd_*` names then):

| Module | Commands / contents | Source on `main` (approx.) | ~lines |
|---|---|---|---|
| `cli/__init__.py` | `main()`, parser assembly (calls each module's `register`), re-exports (`main`, `build_parser`, `cmd_*` for test imports) | 5074–5090, 5649–5671 | 120 |
| `cli/_common.py` | shared helpers: `_settings`, `_resolve_spec`, `_print`, `_resolve_ui`, `_styler`, `_verbosity`, `_compose`, `_ask*`, `_format_verdict`, `_notify*`, exit codes | 1–330, 2926–2952 | 420 |
| `cli/keys.py` | `keygen`, `rotate-key` | 331–453 | 130 |
| `cli/bootstrap.py` | `init` (+ layout/readiness/roles/notifications setup flows), `config roles setup`, `commit-stage` | 454–1278 | 830 |
| `cli/gate.py` | `gate run`, `conformance`, `coverage-check`, `scope-check`, `classify` | 1279–1390, 2906–2925, 4678–4723 | 200 |
| `cli/trust.py` | `verify`, `anchor`, `signoff`, `spec diff`, `advance`, `ledger show`, `revert` | 1391–1837, 1970–1999, 4608–4651 | 560 |
| `cli/exceptions.py` | `deviation`, `emergency` | 1838–1969 | 130 |
| `cli/oracle.py` | `roles-check`, `oracle seal/record/verify/dispatch` | 2000–2560 | 560 |
| `cli/observe.py` | `observe signal/coverage/log-action/verify-actions` | 2561–2713 | 155 |
| `cli/run.py` | `run` (+ the ~30 dispatch/phase/steering helpers), `status`, `git start`, `abort` | 2714–2905, 2953–4607, 4652–4677 | 1,900 |
| `cli/supply.py` | `provenance`, `deploy-gate`, `residual` | 4724–4846 | 125 |
| `cli/brownfield.py` | `characterize`, `eval`, `deps-check`, `ready` | 4847–5073 | 230 |

Each command module exposes `register(sub, common)` that adds its subparsers (help text moves with
the implementation) and `set_defaults(func=…)` — `build_parser()` in `__init__.py` becomes a short
loop over the modules in the current registration order, preserving `3pwr --help`'s command order
byte-for-byte.

`cli/run.py` at ~1,900 lines remains the largest but is a single coherent domain (the lifecycle
loop); a further `run.py` / `run_dispatch.py` split is noted as an optional follow-up inside the
implementation plan, decided by the implementer once 030's final shape is visible — not committed
to here.

**No other module is split in this plan** (proposed decision 6). Future candidates, listed for the
record only: `runner.py` (619), `gates.py` (576), `oracle.py` (572), `orchestrate.py` (566).

### Deliverables

- `engine/src/threepowers/cli/` package as above; `cli.py` deleted in the same commit.
- Test-suite changes limited to import paths **only if needed** — the `__init__.py` re-export list
  is derived from what `engine/tests/` actually imports from `threepowers.cli` today, so the
  default outcome is zero test edits.

### Tests

- Full `(cd engine && uv run pytest)` green with no behavioral test changes.
- `uv run ruff check .` and `uv run mypy src` green (mypy will newly see the package boundaries —
  any revealed type looseness is fixed minimally, not refactored).
- `uv tool install --force ./engine` then: `3pwr --version`, `3pwr --help`, one representative
  subcommand help per module, and a `3pwr verify` run in this repo — output compared against
  pre-split captures.
- `3pwr gate run --path engine` (self-application) green; trust-spine coverage ≥95% (the split does
  not touch trust-spine modules, but `diff_coverage` sees the moved lines — see Risks).

---

## Delivery order and dependencies

| Track | Depends on | Risk | Effort |
|---|---|---|---|
| A — Inventory scanner | plan 030 merged (for the authoritative run) | Low | Small |
| B — Rewrite/remove | A | Medium (breadth) | Medium–Large |
| C — Convention + enforcement | B (test must go green) | Low | Small |
| D — cli.py split | B (move clean text once); plan 030 merged | Medium | Medium |

Delivery happens as two units of work on the single feature branch — **no pull requests**, per the
branch-and-commit discipline in AGENTS.md/CLAUDE.md.

### Delivery unit 1 — A + B + C (text hygiene, self-verifying)

Scanner runs, passes B1–B5 land grouped by surface (each pass its own commit, gates green after
each), convention text + permanent test land last so the unit proves itself, scanner + inventory
deleted in the closing commit.

### Delivery unit 2 — D (mechanical split)

Pure code motion on already-clean text. Kept separate so the diff is reviewable as
"moved, not changed" (git detects the renames poorly for a file split — the commit message maps
each new module to its source line ranges to aid review).

---

## Spec files to create

Self-application: this plan gets specs like any other work (the specs themselves may cite IDs
freely — `specs/` is exempt).

| Path | Spec ID | Contents |
|---|---|---|
| `specs/<NNN>-public-text-hygiene/spec.md` | `PUBTXT` | Tracks A–C: the no-internal-IDs rule, surface list, exemptions, allowlist, enforcement test |
| `specs/<NNN+1>-cli-package-split/spec.md` | `CLIPKG` | Track D: module map, behavior-identity and entry-point invariants |

`<NNN>` is the next free workspace number **at implementation time** — plan 030's branch allocates
specs 020–026, so the numbers here can only be fixed after it merges.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Plan 030 merge conflicts.** 030's phases 3–9 rewrite cli.py, orchestrate.py, style.py, frame.py. | Hard sequencing rule (see "Sequencing precondition"): no implementation before 030 merges; the feature branch is cut from the post-030 `main`; the Track A inventory runs then. |
| **Re-seal / gate_gaming on constitution edits.** Plan 022 established that editing seeded/sealed assets (`scaffold/constitution.md`, this repo's `.3powers/memory/constitution.md`, approved specs) can trip `spec_integrity` or `gate_gaming` and may require a maintainer re-seal or a recorded deviation. | B5 is its own commit; before it lands, run `3pwr gate run --path engine` and `3pwr verify`; if either trips, the maintainer either re-seals (documented re-seal path) or records a signed `3pwr deviation` naming this plan's constitution rewrite — decided by the user at that point, recorded in the ledger either way. |
| **Enforcement regex too broad → false positives on legitimate text.** A user-facing doc example, or a future doc quoting an end user's own namespaced ID, would fail the permanent test. | The test forbids only the namespaced pattern, allows bare `FR-###`, and carries an explicit allowlist (reserved `DEMO-` namespace + placeholder forms). The failure message names the allowlist so a legitimate addition is a one-line, reviewed change. Note the `spec_conformance` gate itself is untouched — it reads only `Covers:` lines in tests, which stay. |
| **Docstring-presence regressions in B3.** Deleting a docstring whose only content was the citation would strip API documentation and could trip lint. | Rule in B3: rewrite, never delete — every touched docstring keeps (or gains) a plain-English sentence. `ruff` runs after each pass. |
| **Behavior drift in the D split.** Subtle module-import side effects, help-text ordering, or exit-code changes. | Pure-motion discipline: capture `3pwr --help` (and per-group `--help`) output before the split and diff after; full pytest; `uv tool install --force` smoke; registration loop preserves subcommand order explicitly. |
| **Test expectations pinned to exact strings.** Several engine tests assert help/message text verbatim; B1/B2 will break them. | Expected-string updates land in the same commit as each text change — never batched separately — so every commit is green. |
| **Scaffold ↔ `.3powers/` seeded-copy drift.** B5 edits both sides; a parity or non-clobbering check (init is seeded non-clobbering) could mask or flag drift. | The implementation plan lists each scaffold file with its seeded twin; both edited in the same commit; a fresh `3pwr init` in a scratch dir verifies the shipped result carries no IDs. |
| **`diff_coverage` on the split.** Moving ~5,700 lines makes the whole cli package "new" to a diff-based coverage gate. | cli command functions are already exercised by the existing test suite; the gate run uses `--base main` post-merge as usual. If `diff_coverage` still flags moved-but-uncovered legacy lines, that is surfaced to the user for a deviation decision rather than silently adding low-value tests. |

---

## Verification (post-delivery)

```bash
(cd engine && uv sync --extra dev && uv run pytest && uv run ruff check . && uv run mypy src)
3pwr gate run --path engine   # self-application, Standard tier
uv tool install --force ./engine
3pwr --help | grep -E '\b[A-Z][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b' && echo LEAK || echo clean
# fresh-init check: scaffold ships clean
(cd "$(mktemp -d)" && git init -q . && 3pwr init --yes && \
  grep -rE '\b[A-Z][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b' .3powers/ && echo LEAK || echo clean)
```

---

## Open questions — resolved 2026-07-06

All were answered by the user accepting the recommendations in the decisions table; the plan is
**finalized**. Resolutions: (1) clean all of `engine/src/threepowers/`, docstrings and comments
included; (2) `AGENTS.md`/`CLAUDE.md` stay exempt alongside `docs/STATUS.md`; (3) the reserved
example namespace is `DEMO-`; (4) prefer a documented maintainer re-seal, with a signed recorded
deviation as the fallback; (5) accept `cli/run.py` at ~1,900 lines — no further split in this
plan; (6) two sequential delivery units on the one feature branch; (7) yes — "(plan NNN)" /
"(epic X#)" references are stripped from public text on the same terms as requirement IDs. The
original questions follow for the record.

1. **Docstrings/comments (decision 1):** clean all of `engine/src/threepowers/` (recommended), or
   only user-visible strings + docs + scaffold, leaving docstrings/comments as internal
   traceability? This choice also sets the permanent test's scan surface (whole source tree vs.
   docs + scaffold only).
2. **AGENTS.md / CLAUDE.md exemption (decision 2):** confirm they keep their IDs alongside
   `docs/STATUS.md`, or should they be de-crufted too?
3. **Reserved example namespace (decision 4):** is `DEMO-` acceptable for format-teaching examples
   in docs/scaffold, or do you prefer another token (`EXMPL-`, `MYAPP-`, keep plan 022's `VUTIL-`
   from the validation-utils example)?
4. **Constitution re-seal path (risk 2):** if editing `scaffold/constitution.md` /
   `.3powers/memory/constitution.md` trips `spec_integrity`/`gate_gaming`, do you prefer a
   maintainer re-seal or a signed recorded deviation?
5. **`cli/run.py` residual size (Track D):** accept ~1,900 lines for the run/lifecycle module in
   this plan (recommended), or mandate the further `run.py`/`run_dispatch.py` split now?
6. **Delivery shape (decision 7):** two sequential delivery units on the one feature branch
   (A+B+C first, then D) as proposed, or a single combined unit? (No pull requests either way —
   AGENTS.md and CLAUDE.md both mandate branch-only delivery.)
7. **"(plan NNN)" / "(epic X#)" references (Track A step 2):** confirm these sibling forms are
   in scope for stripping from public text on the same terms as requirement IDs.
