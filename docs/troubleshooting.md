# Troubleshooting

The failures newcomers hit most, each with its symptom, cause, and the exact command that resolves it.
The first block covers every **mid-run failure class** `3pwr run` can print (each entry is keyed to the
exact phrase the CLI uses); setup problems follow. If your problem isn't here, check the
[CLI reference](cli-reference.md) or open an issue.

Two tools cover most run diagnoses before you read further: `3pwr run --status --spec-id <NNN>` shows
*where* the run failed ("failed at <stage> (<class>)", from the signed ledger), and the failure message
always names the persisted **agent transcript** under `.3powers/runs/<NNN>/` — the agent's full
stdout/stderr for each attempt, credential-redacted. `<NNN>` is the run's numeric feature-folder id
(the tracker prints it; it names the run's `specs-src/<NNN>-*/` folder).

## "cannot start `3pwr run` — unmet prerequisites"

**Symptom** — the run refuses to start (exit `4`), listing prerequisites with fixes; no stage was
dispatched.

**Cause** — the auto run's preflight found a missing prerequisite: an unresolvable signing key, a coder
agent that is not configured/headless/installed, or an oracle sharing the coder's model family without
a recorded deviation.

**Fix** — apply the printed per-item fixes (they are exact commands), then re-check and re-run:

```bash
3pwr ready         # the same checks, re-runnable; exits 0 when the run will start
3pwr run "<intent>" --mode auto
```

## "dispatch failed at <stage>"

**Symptom** — the run stops with `✗ dispatch failed at <stage> — a stage could not be executed (a
setup/dispatch problem, not a gate verdict)`, exit `4`.

**Cause** — the stage's agent process could not run or exited non-zero after the retry budget: the CLI
crashed, isn't authenticated with its provider, or was killed. This is never a judgment on your code.

**Fix** — open the transcript path the message printed (the agent's own error is in there), fix the
named cause (often: log in with the provider's CLI), then resume — completed stages are not re-run:

```bash
3pwr run --resume --spec-id <NNN>
```

## "agent timed out after <N>s"

**Symptom** — a dispatch failure whose detail says `agent timed out after <N>s` (the attempt was
terminated at the per-stage timeout, exit `4`).

**Cause** — the agent exceeded the dispatch timeout (default 1800s). Big stages on slow models hit
this honestly; a hung CLI does too.

**Fix** — check the transcript for where it stalled, raise the bound if the work is legitimately long,
and resume:

```bash
3pwr run --resume --spec-id <NNN> --timeout 3600
```

## "artifact missing at <stage>"

**Symptom** — `✗ artifact missing at <stage> — stage '<step>' produced no expected artifact`, exit `4`.

**Cause** — the agent ran and exited cleanly but did not produce what the stage is responsible for
(e.g. Specify wrote no `spec.md`). Not a gate verdict — the stage's declared artifact contract wasn't
met.

**Fix** — read the transcript to see what the agent did instead (a common cause: it asked a question
rather than acting), then re-run the stage by resuming:

```bash
3pwr run --resume --spec-id <NNN>
```

## "gates red — the deterministic gate suite failed"

**Symptom** — the run stops at Verify with `✗ gates red`, exit `1` — distinct from every setup failure.

**Cause** — this is the judiciary working: the deterministic gate suite judged the built code against
the spec and a gate failed. The verdict is recorded in the signed ledger and written to
`.3powers/verdicts/latest.json`, exactly as a standalone gate run would.

**Fix** — inspect the verdict, fix (or have the agent fix) the failing gate's findings, then resume;
never satisfy a gate by weakening it:

```bash
3pwr gate run --spec <spec.md> --tier <tier>     # re-run and read the failing gate
3pwr run --resume --spec-id <NNN>
```

## "verdict error at <stage> — the deterministic gate suite could not run"

**Symptom** — `✗ verdict error at Verify`, exit `4` — reported distinctly, never mislabeled "gates
red".

**Cause** — the gate suite could not even start: no spec resolvable, no language adapter detected, or
an unknown risk tier.

**Fix** — make the inputs resolvable, then resume:

```bash
3pwr run --resume --spec-id <NNN> --spec specs-src/<feature>/spec.md --tier Standard
```

## "nothing to resume"

**Symptom** — `nothing to resume for <ID> — no recorded progress; start fresh: 3pwr run "<intent>"
--spec-id <ID>`, exit `2`. `<ID>` is the run's numeric feature-folder id.

**Cause** — `--resume` was asked to continue a run that recorded no progress: no stage ever completed
and no human gate is pending, so there is honestly nothing to continue from.

**Fix** — start fresh with the command the message names:

```bash
3pwr run "<intent>" --spec-id <NNN> --mode auto
```

## Signing key not found

**Symptom** — a gate run or `3pwr signoff` fails with an error like
`signing key not found` / `no signing key configured`, or the run aborts before writing a ledger entry.

**Cause** — the trust spine signs every ledger entry with a private key that lives **outside** the
repository, and the engine can't find yours. Either it was never created, or the environment variable
pointing at it isn't set in this shell.

**Fix** — create the signer once, then export the path it prints (add the export to your shell profile):

```bash
3pwr keygen
export THREEPOWERS_SIGNING_KEY_FILE="$HOME/.config/3powers/<repo>.key"
```

If the key exists but `3pwr verify` reports `key_custody`, the key is inside the working tree or its
permissions are too open — move it outside the repo and run `chmod 600 <keyfile>`.

## A gate shows as skipped (quarantined scanner)

**Symptom** — the verdict lists a gate like `secret_scan`, `dependency_scan`, or `sast` with a **skip**
status and a finding naming a missing tool.

**Cause** — that gate shells out to an optional external scanner that isn't installed. 3Powers
**quarantines** the gate — surfaces it as skipped, never silently passed — so the verdict stays honest.

**Fix** — install the named scanner and re-run the gates:

```bash
brew install gitleaks          # secret_scan (or betterleaks, preferred when available)
brew install osv-scanner       # dependency_scan
brew install semgrep           # sast
3pwr gate run --path <target> --spec <spec.md> --tier <tier>
```

On Linux, use your package manager or the scanners' release pages; the gate names the exact tool it wants.

## Coding-agent CLI not found

**Symptom** — `3pwr run "<intent>"` aborts immediately with a `command not found` / `FileNotFoundError`
naming your agent (e.g. `claude` or `copilot`), while `3pwr gate run` and `3pwr verify` work fine.

**Cause** — the autonomous lifecycle dispatches each stage to a **headless coding-agent CLI** through the
native executive, so that CLI must be installed and on your PATH. The role → agent mapping lives in
[`.3powers/config/roles.yaml`](../.3powers/config/roles.yaml). The deterministic gates, ledger, and
enforcement need no agent — only `3pwr run` does.

**Fix** — install the agent CLI your roles point at (or switch the role to one you have), then re-run;
`3pwr deps-check` reports installed tool versions and `--dry-run` sanity-checks the loop offline:

```bash
3pwr deps-check                                  # installed tools vs the supported ranges
3pwr run "<intent>" --mode auto --dry-run        # sanity-check the loop offline first
```

## The `spec_integrity` gate fails with `spec_modified`

**Symptom** — the `spec_integrity` gate is red with class `spec_modified`, naming an approving ledger
sequence number.

**Cause** — the spec was edited *after* a human sealed its hash at the Spec-stage sign-off. That's the
gate doing its job: an approved spec can't drift silently.

**Fix** — inspect the drift, then either re-approve the changed spec or revert it:

```bash
3pwr spec diff --spec-id <ID>
3pwr signoff --approver <you> --stage spec --spec-id <ID> --spec specs-src/<feature>/spec.md
```
