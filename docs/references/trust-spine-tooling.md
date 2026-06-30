# Trust-spine & gate tooling — compacted reference

> Free/open-source tool choices for the trust spine and the gate suite, with the offline/local
> constraint (3PWR-NFR-004) front of mind. Marks what 3Powers uses **now** (plan 001) vs **later**.

## Signing the ledger & artifacts

| Tool | Crypto | Offline | Role | 3Powers |
|---|---|---|---|---|
| **(built-in) Ed25519** | Ed25519 (`cryptography`) | ✅ sign+verify | ledger signatures | **now** — `3pwr keygen` / `verify`; private key kept outside the repo (NFR-005) |
| minisign | Ed25519 | ✅ | standalone signer/verifier | optional interop (documented, not required) |
| cosign | Ed25519/keyless | ✅ self-managed key; keyless needs OIDC | sign artifacts + SBOM | **later (003)** for build provenance |
| GPG / `ssh-keygen -Y sign` | RSA/Ed25519 | ✅ | alternatives | not used |

The engine signs the canonical bytes of each ledger entry's *core* and chains entries by `prev_hash`;
`verify` recomputes the chain + signatures locally. No network, no CI dependency.

## Provenance & SBOM (plan 003)

- **GitHub Artifact Attestations** (`actions/attest-build-provenance`, `gh attestation verify`): SLSA
  provenance, Sigstore-signed, **verifiable offline** with a pre-fetched trusted root — but
  **GitHub-Actions-dependent**, so it can only be an A4 *re-validation* layer, never the source of trust.
- **SLSA** provenance format (aim L3); **syft** for the SBOM (CycloneDX/SPDX); **cosign** to sign the
  artifact + SBOM with the *same* independent key as the ledger (3PWR-FR-068). Primary path is
  local-signer-first so provenance is produced and verified with no hosted CI (3PWR-NFR-004).

## Gate suite (cheapest-first)

| Gate | Language-agnostic? | TS (now) | Python (002, self-app) | Notes |
|---|---|---|---|---|
| format | adapter | Biome | ruff format | Biome `ci` covers format+lint |
| lint | adapter | Biome | ruff | |
| types | adapter | tsc | mypy | |
| tests | adapter | Vitest (+v8 LCOV) | pytest+coverage | must emit **LCOV** |
| diff-coverage | **core** | — | — | LCOV ∩ `git diff` (FR-029) |
| mutation | adapter | Stryker | mutmut | wired, non-blocking in 001 |
| spec-conformance | **core** | — | — | requirement ID → test trace (FR-030) |
| property tests | adapter lib | fast-check | hypothesis | where input is parsed/validated (FR-024) |

### Scanners (plan 002–003)

- **Secrets**: gitleaks (offline, pre-commit/CI) + trufflehog (verified findings; needs network).
- **Dependencies**: trivy (offline w/ cached DB) and/or osv-scanner, grype.
- **SAST**: semgrep (fast, 30+ langs) on every change; CodeQL (deeper) on a schedule.

All are free/OSS. Secrets, dependency policy, conformance, and provenance are the **language-agnostic
core gates** (3PWR-FR-028); everything else comes through the adapter contract.

## Offline verification (the whole point)

```bash
3pwr verify            # ledger chain + signatures, fully local
# later: cosign verify --offline <artifact>; gh attestation verify <artifact> (pre-cached root)
```
Everything required to reconstruct and check the record lives in the repo (3PWR-FR-071, NFR-010).
