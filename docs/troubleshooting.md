# Troubleshooting

The failures newcomers hit most, each with its symptom, cause, and the exact command that resolves it.
If your problem isn't here, check the [CLI reference](cli-reference.md) or open an issue.

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
3pwr signoff --approver <you> --stage spec --spec-id <ID> --spec specs/<feature>/spec.md
```
