# Trust-spine & gate tooling — compacted reference

> Free/open-source tool choices for the trust spine and the gate suite, with the offline/local
> constraint front of mind. Marks what 3Powers uses **now** vs **later**.

## Signing the ledger & artifacts

| Tool | Crypto | Offline | Role | 3Powers |
|---|---|---|---|---|
| **(built-in) Ed25519** | Ed25519 (`cryptography`) | ✅ sign+verify | ledger signatures | **now** — `3pwr keygen` / `verify`; private key kept outside the repo |
| minisign | Ed25519 | ✅ | standalone signer/verifier | optional interop (documented, not required) |
| cosign | Ed25519/keyless | ✅ self-managed key; keyless needs OIDC | sign artifacts + SBOM | **later** for build provenance |
| GPG / `ssh-keygen -Y sign` | RSA/Ed25519 | ✅ | alternatives | not used |

The engine signs the canonical bytes of each ledger entry's *core* and chains entries by `prev_hash`;
`verify` recomputes the chain + signatures locally. No network, no CI dependency.

## Provenance & SBOM

**As built:** `3pwr provenance` writes a signed record binding the artifact (by sha256) to its source
commit, repo, run, and an SBOM — **signed with the engine's own Ed25519 ledger identity**, so it needs no
`cosign` and no hosted CI. `3pwr deploy-gate` recomputes the hash, finds the record, and verifies the
signature — refusing any missing/mismatched/forged artifact. The SBOM is built in-core from lockfiles
(`package-lock.json`, `uv.lock`); **syft** is used when present for a richer CycloneDX SBOM.

Optional / future layers:
- **GitHub Artifact Attestations** (`actions/attest-build-provenance`, `gh attestation verify`): SLSA
  provenance, Sigstore-signed, verifiable offline with a pre-fetched trusted root — but
  GitHub-Actions-dependent, so only a *re-validation* layer, never the source of trust.
- **cosign** with a self-managed key, for OCI/registry artifacts, if/when needed.

## Gate suite (cheapest-first)

Three reference adapters ship today — TypeScript, Python, and Go.

| Gate | Language-agnostic? | TypeScript | Python (self-app) | Go | Notes |
|---|---|---|---|---|---|
| format | adapter | Biome | ruff format | gofmt | Biome `ci` covers format+lint |
| lint | adapter | Biome | ruff | go vet | |
| types | adapter | tsc | mypy | go build | |
| tests | adapter | Vitest (+v8 LCOV) | pytest+coverage | go test + gcov2lcov | must emit **LCOV** |
| diff-coverage | **core** | — | — | — | LCOV ∩ `git diff` |
| mutation | adapter | Stryker | mutmut | go-mutesting | opt-in via `--mutation` |
| spec-conformance | **core** | — | — | — | requirement ID → test trace |
| property tests | adapter lib | fast-check | hypothesis | rapid | where input is parsed/validated |

### Work-kind-shaped gates

- **defect regression** (**core**) — a `defect` change must ship a failing regression test
  (`*regression*`/`*reproduce*`, referencing the defect's requirement id). Deterministic trace, no tool.
- **design oracles** (adapter) — a `design` change unions `contract_check`, `component_contract`,
  `a11y_scan`, `visual_regression` (catalog in `.3powers/config/design-oracles.yaml`). The tool for each
  is adapter-supplied; an oracle the adapter doesn't declare — or whose tool isn't installed — is
  **quarantined**, never silently passed.

### Scanners

- **Secrets**: **betterleaks** (the maintained Gitleaks successor) — the core secret gate; **gitleaks** is the fallback (same `dir` CLI + JSON schema). Offline; quarantines if neither is installed. trufflehog (verified findings; needs network) is a later option.
- **Dependencies**: **osv-scanner** — wired as a core gate (respects `.gitignore`; quarantines if absent). trivy/grype are alternatives.
- **SAST**: **semgrep** — wired as a core gate against a **local, committed ruleset**
  (`.3powers/config/semgrep-rules.yml`); offline and deterministic (`--config auto` avoided), quarantines
  if absent. CodeQL (deeper, on a schedule) is a future option.

All core scanners **quarantine** (report `skip` + a surfaced finding) when the tool isn't
installed, so the suite stays runnable without silently passing.

All are free/OSS. Secrets, dependency policy, conformance, and provenance are the **language-agnostic
core gates**; everything else comes through the adapter contract.

## Offline verification (the whole point)

```bash
3pwr verify            # ledger chain + signatures, fully local
# later: cosign verify --offline <artifact>; gh attestation verify <artifact> (pre-cached root)
```
Everything required to reconstruct and check the record lives in the repo.
