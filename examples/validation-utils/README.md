# validation-utils — the runnable 3Powers sample

A tiny, pure **TypeScript input-validation library** used to demonstrate 3Powers end to end. It has no
purpose of its own beyond being something real for the judiciary to judge: a spec, an implementation, and
tests across the unit / integration / e2e layers.

- **Spec:** [`specs/001-validation-utils/spec.md`](../../specs/001-validation-utils/spec.md) (Spec ID
  `VUTIL`) — the acceptance criteria the gates trace to.
- **Language adapter:** `typescript` (Biome + tsc + Vitest + Stryker).

## Run it

From the repository root, with the `3pwr` CLI installed (see the top-level
[Getting Started](../../docs/getting-started.md)):

```bash
# Install the sample's dev tools once
(cd examples/validation-utils && npm install)

# Run the whole gate suite against it at the Standard tier
3pwr gate run --path examples/validation-utils \
              --spec specs/001-validation-utils/spec.md --tier Standard
```

You can also run the underlying tools directly during development:

```bash
cd examples/validation-utils
npm run check       # Biome format + lint
npm run typecheck   # tsc --noEmit
npm test            # Vitest (property-based tests via fast-check)
npm run mutation    # Stryker mutation testing (optional, slower)
```

## What the gates show you

At the Standard tier you'll see a verdict like this:

```
verdict FAIL  spec=VUTIL tier=Standard adapter=typescript
  ✓ format · biome
  ✓ lint · biome
  ✓ types · tsc
  ✓ tests · vitest
  ✓ diff_coverage · 3pwr-covdiff  (100.0% ≥ 80.0%)
  ✗ dependency_scan · osv-scanner
      - GHSA-… in <package>
  ✓ secret_scan
  ✓ gate_gaming
  ✓ spec_conformance · 3pwr-conformance  (5 requirements traced)
```

The `dependency_scan` failure is **intentional and instructive** — it flags real, current advisories in the
sample's transitive dev dependencies. It shows the gate suite doing its job: the failure names the class
(`vulnerable_dependency`) and the exact advisory and package, so a human can act without opening an agent
transcript. The library code itself is clean (100% diff-coverage on changed lines; all five `VUTIL`
requirements trace to a test).

## Layout

```
examples/validation-utils/
├── src/                 # the pure validation functions
├── tests/
│   ├── unit/            # per-function tests, including property-based tests (fast-check)
│   ├── integration/     # cross-function behavior
│   └── e2e/             # end-to-end usage
├── package.json         # scripts: check, typecheck, test, mutation
├── biome.json           # format + lint config
├── tsconfig.json        # TypeScript config
├── vitest.config.ts     # test runner config
└── stryker.conf.json    # mutation testing config
```

To see the full local trust spine in action — signing, `3pwr verify`, sign-off, and the `advance`
enforcement gate — follow [Getting Started](../../docs/getting-started.md).
