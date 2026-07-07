# typescript-orders

An order-pricing service — the TypeScript sample project for the 3pwr end-to-end
testing kit. It is deliberately small, layered, and free of I/O so that lifecycle
runs against it are deterministic.

## Layers

- `src/config/` — static pricing configuration (currency, tax rules).
- `src/domain/` — pure pricing rules: line items, tax, currency rounding, and the
  typed `PricingError`.
- `src/service/` — an `OrderService` that composes the domain into a priced order.
- `src/logging/` — a small structured-logging abstraction the service depends on.

## Toolchain

| Concern    | Tool                                   |
| ---------- | -------------------------------------- |
| Format/lint | Biome (`biome ci .`)                  |
| Types      | `tsc --noEmit` (strict)                |
| Tests      | Vitest, LCOV coverage → `coverage/lcov.info` |
| Mutation   | Stryker (`stryker run`)                |

```bash
npm ci
npm run check       # Biome format + lint
npm run typecheck   # tsc --noEmit
npm test            # Vitest with coverage
```

This project carries committed source and `package-lock.json` only; dependencies
are installed into an ephemeral sandbox by the kit's harness, never committed.
