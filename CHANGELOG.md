# Changelog

All notable changes to 3Powers are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

3Powers entries are grouped by the development milestones (v0.1 → v0.5 → v1.0) described in the
spec's scope phasing and tracked in detail in [`docs/STATUS.md`](docs/STATUS.md). Each item notes the
plan document under [`plan/`](plan/) that delivered it. Releases are tagged on `main`; the current
release is the first stable release candidate, **v1.0.0-rc.1**.

## [1.0.0-rc.1] — v1.0: lifecycle & ecosystem (release candidate)

### Changed

- **Public text hygiene.** All end-user-readable text — CLI help and messages, engine source
  docstrings and comments, `docs/` prose, and the scaffold assets `3pwr init` ships — no longer
  cites 3Powers' internal requirement IDs, epic letters, or plan/spec numbers; every citation was
  rewritten as the plain-English rationale it stood for. Format teaching keeps bare `FR-###` and
  uses the reserved `DEMO-` example namespace. The rule is written down (AGENTS.md) and enforced
  by a permanent test, so a fresh `3pwr init` always ships clean.
- **CLI package layout.** The engine's single `cli.py` module became the `threepowers/cli/`
  package — one module per command group, each owning its handlers and registering its own
  subparsers. A pure refactor: identical commands, help text, exit codes, and `--json` payloads;
  the `3pwr` entry point is unchanged.

### Added

- **v1.0 readiness & lifecycle hardening.** The run-artifact base folder is now **`specs-src/`**
  (the legacy `specs/` base and split layout stay read-resolvable); the tasks artifact is
  **`implementation-plan.md`** and the implement record is an engine-generated, requirement-traced
  **`changelog.md`** (the legacy `tasks.md`/`implement.md` names stay readable); every build phase
  runs the coding gates over its file scope as the agent's own advisory check, and a dedicated
  Verification phase always closes the plan — the Verify stage remains the sole signed verdict; the
  plan artifact drops its judiciary framing (no role→model table — roles live in `roles.yaml`
  alone); oracle artifacts are keyed by the run's `<NNN>-<slug>` folder id everywhere, and
  `oracle.md` is an authored, engine-validated, implementation-agnostic Tests Specification; each
  stage and each phase provably runs in a **fresh headless session**, with `[P]` sub-agent parallel
  dispatch explicit in the handoff; per-stage and per-phase **token consumption** is recorded
  additively (a Tokens column in `progress.md` and the status commands — verdict bytes unchanged);
  the secret/dependency/SAST scanners honor a committed **`.3powers/config/scan.yaml`** (per-tool
  ignore globs, auditable in review — the core ed25519 private-key check always runs); the
  observability registry (`observability.yaml`) ships with explanatory headers and a docs section;
  and `3pwr init` now flags the seeded constitution as **mandatory to adapt**, with a "How to adapt"
  guide, a mandatory-content checklist, and a "how to update" rule in the template itself.
- **Per-adapter end-to-end notebook kit.** A top-level `e2e/` folder carries one small,
  enterprise-baseline sample project per language adapter (TypeScript, Python, Go), each driven
  through a complete real `3pwr run` by a committed Jupyter notebook — `./e2e/run.sh <lang>` for the
  agent-driven lifecycle, `--check` for the deterministic no-agent path (baseline gates +
  `3pwr run --dry-run`). Every run provisions a throwaway sandbox and never writes into the repo;
  the headless integration is configured once in `e2e/config/` and shared by all projects.
- **Run identity, configurable gate tooling, diagnostics & progress.** The run's auto-allocated
  `<NNN>-<slug>` folder id is its identity everywhere (ledger entries, oracle folder, gate messages,
  resume hints); gate failures list the individual gate results with copy-pasteable resume commands;
  a committed **`.3powers/config/gates.yaml`** lets a project pin its own format/lint/type/test
  commands (precedence: `gates.yaml` > auto-detected project tooling > adapter manifest — inspect
  with `3pwr gate config show`), with an opt-in `--auto-fix` for the format/lint gates only; and
  every run maintains a durable, human-readable **`progress.md`** in its feature folder.

- **Run steering (STEER).** Three operator seams around `3pwr run` closed. *File-based intent*:
  `3pwr run --file my-intent.md ["<inline>"]` uses the file's contents as the intent, appending inline
  text as an instruction by one pure deterministic rule (file first); only the resolved text is
  recorded — verbatim — in the signed `start` entry, and a missing/empty/binary/directory file fails
  fast with the setup exit code and no ledger entry. *Approve / reject / revise*: every human-gate
  pause now presents three actions with copy-pasteable commands and the artifact under review;
  `3pwr run --resume --spec-id <ID> --revise "<feedback>"` (or `--revise-file`) re-dispatches the
  paused stage with the original intent, the current artifact, and the feedback — under the full
  retry/artifact/git/completion policy — records the revision (feedback + outcome) via the existing
  run-entry append path, and returns to the *same* gate; approval still requires the human sign-off.
  *Notifications*: opt-in, best-effort channels in `.3powers/config/notifications.yaml` — Slack,
  Microsoft Teams, email, and macOS desktop, standard-library only, secrets referenced from the
  environment — fire actionable messages on gate pause / failure / completion with per-channel event
  routing; a broken channel never blocks or alters the run, and with none configured no network call
  is made (`--notify` keeps working alongside). *The persistent live frame*: on a capable TTY the run
  pins the eight-stage tracker (done/current/upcoming marks, active step, running / paused-at-gate /
  failed states with gate guidance) above a reserved ANSI scroll region agent stdout streams into —
  no new dependency, no alternate screen; off-TTY / `--json` / `NO_COLOR` / dumb terminals keep the
  plain streamed log escape-free, and teardown always restores the terminal, on Ctrl-C too.

- **Git-integrated run lifecycle (GITX).** Git handling is now a mandatory pre/post-stage hook on every
  live run and the manual `/3pwr.*` drive: a working git repository is a run precondition (reported by
  the shared `ready`/init/preflight check set); every run is isolated to a dedicated branch
  `3pwr/<NNN>-<slug>` — reusing the SRCX run identity, created off the configured base, bound to the run
  as one additive `branch` field on the signed `run`/`start` entry, and re-entered on resume; a run
  refuses to start atop uncommitted changes it did not produce (naming the paths, leaving them
  untouched) and leaves nothing it produced uncommitted after any stage; each producing stage is exactly
  one commit staging only the run's produced paths, with an agent-written `COMMIT:` message
  (deterministic `3pwr(<spec-id>): <step>` fallback) authored per-commit as the configured `3pwr`
  identity — the developer's git config is never mutated and no history is rewritten. The discipline is
  mandatory: `--no-auto-commit` is superseded (warns, no longer disables) and the only relaxations are
  the signed, revocable `git_clean_start`/`git_stage_commit`/`git_run_branch` deviations. New:
  `3pwr git start` (manual-drive branch establishment), git-aware `advance` boundary checks,
  `.3powers/config/git.yaml` (branch prefix / base / 3pwr author, tolerant defaults), and the run
  branch + committed stages surfaced by both status commands.

- **Run artifact workspace (SRCX).** Every `3pwr run` auto-allocates one flat feature folder with a
  deterministic `<NNN>-<slug>` identity; every producing stage leaves a ledger-tracked markdown in
  it; and a deterministic artifact-∧-ledger stage-completion gate governs `advance` and `--resume`
  (two named failure classes — an artifact missing on disk, or present but unrecorded).
- **Per-stage agent templates + the headless-CLI / role→model setup (AGENTX).** One editable, merged
  agent template per dispatched stage (`.3powers/templates/agents/<stage>.agent.md`, built-in
  fallback when absent), a per-integration model catalog (`.3powers/config/models.yaml`), and an
  init + `3pwr config roles setup` flow that binds every role — planner, coder, oracle, reviewer —
  to a complete `roles.yaml` block so `3pwr run` needs no manual role editing.
- **A first-class CLI experience (CLIUX).** A zero-dependency structured-output toolkit every
  command renders through (headers, key/value blocks, aligned tables, status rows), a consistent
  color + status-glyph vocabulary, a persistent colorized auto-mode stage header, and
  `--quiet`/`--verbose` + an opt-in `.3powers/config/ui.yaml` — human output only; `--json`, exit
  codes, and verdict bytes are byte-for-byte unchanged.
- **Auto full-mode readiness & the run error contract (AUTOX).** One shared readiness/preflight
  check set (`3pwr ready`, init, and the run can never disagree), signed run-failure ledger records
  surfaced by both status commands, persisted credential-redacted per-attempt transcripts, a stable
  exit-code/JSON status contract (0 done · 1 gates-red · 2 usage · 3 paused · 4 setup/dispatch), and
  checkpoint-independent resume.
- **Phased execution (PHASE).** A per-feature artifact workspace, hard plan/tasks artifact
  contracts, context-budgeted phases against an advisory budget (warn, never block), one fresh
  headless session per phase, and parallel subagent dispatch for `[P]` phases with disjoint file
  scopes.
- **Open-source launch readiness (OSSRD).** A CI workflow gates every pull request to `main` (engine
  lint, types, tests, and offline ledger verification, as required checks); a
  [glossary](docs/glossary.md) defines every term of art (trust spine, oracle, Phase A/B, residual,
  A1–A6, verdict, quarantine, work kind, the requirement-ID scheme); a
  [troubleshooting guide](docs/troubleshooting.md) covers the common failures with exact fixes.
  Entry docs were calibrated to what [STATUS](docs/STATUS.md) validates (the sanitized-headless claim is
  scoped to the oracle leg; the autonomous path's Spec Kit + coding-agent dependency is stated up front),
  the Spec Kit pin is sourced to upstream `github/spec-kit` everywhere it appears, prerequisites are
  split hard / per-path / optional, gate names match the engine's canonical identifiers across all docs,
  and implementation status lives only in STATUS.
- **Trust-spine hardening (HARDN).** A versioned [`docs/threat-model.md`](docs/threat-model.md) states what
  the ledger proves, against whom, under which assumptions. Key custody is enforced (`keygen`/`rotate-key`
  refuse in-repo keys; `verify` fails a `key_custody` violation; the secret gate's core `ed25519-priv` check
  always runs). Key rotation is a signed `key_rotation` entry authored by the outgoing key — `verify` walks
  the succession, so a bare committed-pubkey swap is a named *unrotated key change*. Opt-in `3pwr anchor` +
  `3pwr verify --anchored` record the head with an external git-tag witness and catch wholesale ledger
  regeneration by a key holder. `$THREEPOWERS_SIGNER_CMD` delegates signing to an external (hardware-capable)
  process boundary — no readable seed, loud failure, unchanged verification. The self-reported oracle model
  is cross-checked against the ledger-attested dispatch (contradiction blocks a High-risk advance; without a
  dispatch the claim is labelled self-reported). The `spec_conformance` gate now requires requirement IDs
  **bound to test declarations** (`untraced_requirement` for comment-only mentions) with ≥1 assertion per
  bound test (`weak_test`), `gate_gaming` flags newly added assertion-free requirement-referencing tests,
  and a per-tier `diff_mutation` knob runs mutation over changed files.
- **Spec-lock (SLOCK): the `spec_integrity` gate.** A Spec-stage `3pwr signoff` now seals the approved document's
  raw-bytes SHA-256 inside the signed ledger entry; a new `spec_integrity` gate (cheapest-first, before any
  test, at every tier) and `advance` fail a spec silently modified after approval (`spec_modified`), unless
  a fresh Spec-stage sign-off supersedes it or a signed `spec_integrity` deviation covers it. The read-only
  `3pwr spec diff` reports the mismatch with a textual diff when the sign-off commit is known. Tampering
  with the recorded hash is caught by the existing `verify` — no new trust primitive.
- **Work-kind-shaped gates.** `3pwr classify` infers the kind of change (defect, design, feature, …) and a
  suggested risk tier, and the gate suite adapts. A **defect** fix must ship a failing regression test; a
  **design** change is judged by design oracles (visual-regression, accessibility, and contract checks),
  which are quarantined — surfaced as skipped — when a tool isn't wired up.
- **Go language adapter** — a third reference adapter alongside TypeScript and Python, proving the adapter
  contract is language-agnostic.
- **One-command lifecycle** — `3pwr run` drives all eight stages with a live tracker, stopping only at the
  two human gates (spec approval, sign-off) in `auto` mode.
- **Observe & feedback loop** — `3pwr observe signal | coverage | log-action | verify-actions`: route a
  production signal to a new requirement, report which NFRs have a live check, and keep a tamper-evident,
  attributable agent-action log.
- **Headless, read-path-isolated oracle authoring** — `3pwr oracle dispatch` authors the oracle inside a
  sanitized Git worktree where the implementation is physically absent, attested in the ledger.
- **Structural oracle independence** — `3pwr oracle seal | record | verify`: a spec-only sealed bundle, a
  recorded authoring model that must differ from the coder's, and ledger-proven independence enforced at
  the High-risk tier.
- **Emergency & deviation paths** — `3pwr emergency` and `3pwr deviation`: signed, reversible, time-bound
  exceptions that are always recorded and never silently weaken a gate.
- **Brownfield adoption** — report-only runs, diff-scoped gating, and `3pwr characterize` to reconstruct a
  spec and pin a legacy module's current behavior.
- **Portability tooling** — `3pwr deps-check` (drift against supported versions, including Spec Kit) and a
  provider-agnostic Spec Kit extension.
- Root `LICENSE` (Apache-2.0) and this open-source documentation set (README, CONTRIBUTING, SECURITY,
  GOVERNANCE, Code of Conduct, per-component READMEs).

### Changed

- The secret gate now prefers **betterleaks** (a maintained Gitleaks successor), falling back to gitleaks,
  and quarantines when neither is present.
- Model diversity is now **recommend-not-force**: a same-family oracle proceeds under a signed, reversible
  exception rather than being blocked outright, so single-model users are never walled off.
- Per-tier required test layers (unit / integration / e2e) are enforced as a per-change union.
- **Self-application at High-risk:** the trust-spine modules pass their own High-risk bar (≥95%
  diff-coverage plus mutation), so 3Powers is genuinely built with 3Powers at the strictest tier.

## [0.5.0] — Full judiciary

### Added

- The complete cheapest-first gate suite, including **mutation testing**, **`sast`**, and the
  `dependency_scan`, `secret_scan`, `gate_gaming`, and `spec_conformance` gates.
- **Build provenance + SBOM**, signed by the independent identity and verified at a deploy gate.
- Two-way requirement ↔ task coverage, scope discipline, residual review, and the prompt/constitution eval
  harness. (plans 004–005)

## [0.1.0] — Trust-spine MVP

### Added

- The signed, hash-chained verdict **ledger**, offline `3pwr verify`, the local `3pwr advance` enforcement
  gate, and full reversibility via `3pwr revert`.
- The deterministic gate runner with the format / lint / types / tests / `diff_coverage` floor, emitting one
  normalized verdict.
- Two reference language adapters (TypeScript, Python), self-application of the engine on its own code, and
  supply-chain scanners. (plans 001–003)

[1.0.0-rc.1]: https://github.com/VerzCar/3powers/releases/tag/v1.0.0-rc.1
[0.5.0]: https://github.com/VerzCar/3powers/releases/tag/v0.5.0
