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

## Spec Kit version mismatch

**Symptom** — `3pwr deps-check` reports the installed `specify` version is outside the supported range,
or a `3pwr run` / `specify workflow run` step fails with an unexpected-schema or unknown-flag error.

**Cause** — the installed GitHub Spec Kit CLI has drifted from the range pinned in
[`.3powers/config/dependencies.yaml`](../.3powers/config/dependencies.yaml). Spec Kit is upstream
[`github/spec-kit`](https://github.com/github/spec-kit) installed from a git tag — not a fork.

**Fix** — check the drift, then reinstall the pinned tag:

```bash
3pwr deps-check
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@<pinned-tag>
```

See [Spec Kit reference — install & init](references/speckit.md#install--init) for the current pin.

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

## `3pwr run` fails: `specify` not installed

**Symptom** — `3pwr run "<intent>"` aborts immediately with `FileNotFoundError`/`specify: command not
found`, while `3pwr gate run` and `3pwr verify` work fine.

**Cause** — the autonomous lifecycle composes GitHub Spec Kit's `workflow run`, so it needs the
`specify` CLI (plus a coding-agent integration) on your machine. The deterministic gates, ledger, and
enforcement don't — only `3pwr run` does.

**Fix** — install Spec Kit at the pinned tag and add an integration, or stay on the gates-only path:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@<pinned-tag>
specify init . --integration copilot --here     # or: claude, gemini, codex, …
3pwr run "<intent>" --mode auto --dry-run       # sanity-check the loop offline first
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
