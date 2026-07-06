# Plan 029 — Steering an autonomous run: file-based intent, human-gate notifications with approve / reject / revise, and the persistent live run frame (STEER, spec 019)

**Spec:** [`specs/019-run-steering/spec.md`](../specs/019-run-steering/spec.md)
(Spec ID `STEER`, Standard). The human-in-the-loop counterpart to the native executive: EXEC (009) and
RUNLIVE (011) built `3pwr run` and its live stream, AUTOX (014) made auto mode land at the two human
gates with a stable contract, CLIUX (015) gave the CLI its structured-output vocabulary and a single
in-place stage line, and GITX (018) made the run git-safe. STEER closes the three seams left in the
*operator's* loop. **Orchestration plumbing + a human-output presentation layer + one deliberately
opt-in, best-effort notification path** — no trust-spine module change
(`canonical`/`keys`/`ledger`/`verify` untouched), no gate threshold, verdict byte, exit-code contract,
`--json` schema, or ledger entry-format change (STEER-NFR-001/003); the only additions to the ledger
are new payload *kinds* (`revise`) on the existing `run` entry type via the existing append path.

## Why

Three seams remained. (1) **Intent was one CLI argument** — you could not point a run at an intent file
you had already written, nor combine that file with a short inline instruction. (2) **A pause was a
silent hang** unless you watched the terminal: the only signal was a printed resume line plus the
best-effort `--notify` hook — no first-class channels, no "here are your three choices" guidance, and no
way to hand the agent feedback short of editing files by hand; the gate offered approve or reject,
never *revise*. (3) **The live view was a single line** that agent stdout scrolled straight off-screen,
so the operator lost track of which stage the run was in and whether it was moving.

## What was done

- **File-based intent** (STEER-FR-001..004; new [`steering.py`](../engine/src/threepowers/steering.py)):
  `3pwr run --file <path>` reads a UTF-8 text file (markdown preferred) as the run's intent;
  `--file <path> "<inline>"` appends the inline text as an instruction by ONE pure, deterministic rule
  (file first — `steering.combine`), reused verbatim for revise feedback (STEER-FR-007's property). A
  missing / directory / empty / non-decodable file fails fast naming the path and the reason, exits
  with the setup code, and writes **no** ledger `start` entry; resolution happens before any side
  effect, and every downstream consumer — work-kind classification, feature-folder allocation, the
  authoring prompts, the signed `start` entry — sees only the resolved text, recorded verbatim.
- **Approve / reject / revise at the gate** (STEER-FR-005..008): every human-gate pause (non-interactive
  print, interactive prompt, and the notification message) now names the three actions with
  copy-pasteable commands carrying the spec id — approve (`--resume --approver <you>`, unchanged),
  reject (`3pwr abort`, the existing stop), revise (`--resume --revise "<feedback>"` /
  `--revise-file <path>`) — plus the path of the artifact under review
  (`steering.gate_artifact`: the feature's spec at `review-spec`, its plan at `review-plan`, the
  recorded verdict at `review-verify`/`signoff`). A revise re-dispatches the stage that OWNS the
  reviewed artifact (`steering.REVISE_TARGETS`) through the untouched native dispatch closure
  (`NativeRunner.dispatch_once`) — so the retry/timeout/artifact-contract, git-hook, and
  completion-gate policies all apply — with the ORIGINAL intent read back from the signed `start`
  entry, plus a deterministic `REVISION REQUESTED` context block naming the artifact and the feedback.
  The revision (feedback + outcome) is appended as a `run`/`revise` record on the existing append path,
  and the pause is re-recorded so the ledger-derived state stays paused at the *same* gate — a later
  plain `--resume` still records the human sign-off (revise never substitutes for approval, FR-006).
  Empty/whitespace feedback and a revise outside a paused gate are actionable usage errors leaving the
  artifact and gate state byte-identical.
- **Notifications** (STEER-FR-009..011, NFR-001/002; new
  [`notify.py`](../engine/src/threepowers/notify.py)): opt-in channels in
  [`.3powers/config/notifications.yaml`](../.3powers/config/notifications.yaml) (seeded by init's
  scaffold, disabled by default) — reference senders for **Slack**, **Microsoft Teams** (incoming
  webhooks via `urllib`), **email** (`smtplib`, STARTTLS default), and the **macOS desktop**
  (`osascript`), standard library only. Events (`gate` / `failure` / `completion`) route per channel,
  defaulting to all three; the gate message names the spec id, stage and gate, the artifact to review,
  and the three commands filled in; failure messages carry the class and the resume command. Loading is
  tolerant (missing = disabled; malformed/unknown key/type = one warning, fall back), delivery is
  bounded and never raises — a broken channel is at most a one-line stderr warning, and the run's
  output, exit code, verdict bytes, and ledger equal a run with notifications disabled. Secrets are
  referenced from the environment (`webhook_env` / `password_env`); no value is ever stored, logged, or
  echoed. With nothing configured no network call exists; the `--notify` hook fires alongside,
  unchanged, at every event site (`_notify_event` in `cli.py`).
- **The persistent live run frame** (STEER-FR-012..016, NFR-003/004; new
  [`frame.py`](../engine/src/threepowers/frame.py)): on a capable TTY, `orchestrate.Tracker` now pins a
  five-row header — a 3Powers border, the eight-stage strip (done ✓ / current ▶ / upcoming · — a pure
  function of the reached stage), a status line rendering running / paused-at-gate / failed / done /
  aborted as visibly distinct states per the AUTOX taxonomy, and a compact gate-guidance line while
  paused — above a **reserved ANSI scroll region** (DECSTBM) that the streamed event log and the
  dispatched agent's stdout scroll inside, so the frame never scrolls away. No third-party dependency,
  no network, **no alternate screen buffer**; each redraw is one cursor-save/address/restore write (no
  `\r`). `SIGWINCH` re-lays the frame out; teardown — idempotent, invoked by terminal events and by the
  run's `finally` alike — always resets the scroll region and restores the cursor, on Ctrl-C and
  failure paths too. Capability probing (`frame.supported`) degrades **totally**: off a TTY, under
  `--json` or `NO_COLOR`, on a dumb/width-unknown/too-small terminal the tracker keeps the plain
  streamed event log with no escapes and no in-place redraws — the CLIUX single in-place `\r` line is
  superseded (its test reworked honestly), and `--json` per-stage results and exit codes are
  byte-/behavior-identical.
- **Shipped config**: `notifications.yaml` added to the init scaffold and this repo's
  `.3powers/config/`; `Settings.notifications_config_path` added.

## Verification

- Engine green under its own dev tooling: `ruff check`, `ruff format --check`, `mypy src`, and
  `pytest` — **699 passed, 1 skipped** (30 new in
  [`tests/test_run_steering.py`](../engine/tests/test_run_steering.py), naming every
  `STEER-FR-001..016` and `STEER-NFR-001..005`): the file intent recorded verbatim; the deterministic
  file+inline combine property; all four bad-file classes failing fast with exit 4 and no `start`
  entry; `--file`+`--resume` refused; the three actions + artifact on the pause screen; revise
  re-dispatching with the original intent, the artifact path, and the feedback in the prompt, the
  artifact revised, and the same gate re-presented; file-sourced feedback and the shared resolution
  rule; empty feedback and out-of-gate revise rejected with the artifact untouched; the `revise`
  ledger record with `verify` green; repeated revises each recorded; approval after a revise still
  recording the sign-off; the gate/failure/completion channel messages with fields and commands; the
  broken-channel run byte-equal to a disabled-channel run; the no-channel run under a blocked socket;
  tolerant `notifications.yaml` loading (malformed, unknown type/key, disabled, four reference types);
  per-channel routing defaults + the `--notify` hook alongside; the missing-env-secret skip that names
  the variable and leaks no value (ledger scanned too); email/desktop delivery through their seams;
  the pinned frame's region + cursor-addressed redraw under 200 lines of streamed output; the
  deterministic stage-marks property; the distinct running/paused/failed frame states with gate
  guidance; the unchanged dependency set and a socketless render; the off-TTY/`--json`/`NO_COLOR`/
  small-terminal degradations with escape-free bytes and unchanged per-stage results; resize + double
  close idempotence with region reset and cursor restore (no alternate screen); the tracker routing
  events through an injected frame and releasing the terminal at the pause; deterministic
  rendering/resolution with `--json` clean under forced color; the width-unknown plain log; and the
  offline reconstruction with notifications unconfigured.
- Self-application (NFR-006 / STEER-NFR-005), diff-scoped to this branch: `3pwr gate run --path engine
  --adapter python --spec specs/019-run-steering/spec.md --tier Standard --base main` — **verdict
  PASS** (ledger entry #9): format ✓, lint ✓, types ✓, tests ✓, diff_coverage **91.48% ≥ 80%** ✓,
  sast ✓, dependency_scan ✓, secret_scan ✓, gate_gaming ✓, spec_conformance ✓ (**21 requirements
  traced**); `spec_integrity` correctly *skipped* — no Spec-stage sign-off recorded yet for `STEER`
  (a not-yet-approved spec is never blocked). One earlier red entry (#8) in the append-only ledger is
  the same suite before a formatting/conformance-binding fix, kept as history.

## Handoff — notes

- Spec 019 still needs the human spec-approval sign-off:
  `3pwr signoff --approver <you> --spec-id STEER --stage spec --spec specs/019-run-steering/spec.md`
  — after which the `spec_integrity` gate grades instead of skipping.
- Non-goals held: no full-screen/alternate-screen TUI; no third-party rendering or transport
  dependency (runtime deps stay `cryptography` + `PyYAML`, asserted by test); notifications carry no
  authority and there is **no inbound control channel**; no gate/threshold/verdict/ledger-format/
  exit-code/`--json` schema change; the desktop channel targets macOS (a full Windows/Linux pass stays
  the cross-platform residual, 3PWR-NFR-003); no i18n/message templates beyond the documented
  `notifications.yaml` keys.
- An intent file **inside the repository** counts as the developer's uncommitted work for GITX's
  clean-start guard — commit it first or keep it outside the tree (the guard's message names the fix);
  the tests exercise the outside-the-tree path. Noted as intended behavior, not a defect.
- The revise step per gate is the artifact-owning action step (`review-spec → specify`,
  `review-plan → plan`, `review-verify`/`signoff → implement`) — chosen over "the step immediately
  before the gate" because those steps carry hard artifact contracts, so a revise that changes nothing
  is an honest named failure, never a silent pass.
- The frame's gate guidance line is a compact form (the full copy-pasteable commands print in the body
  below) so it stays within one row at 80–100 columns.
