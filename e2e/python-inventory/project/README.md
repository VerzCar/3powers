# python-inventory

An inventory-tracking service — the Python sample project for the 3pwr
end-to-end testing kit. It is deliberately small, layered, and free of I/O so
that lifecycle runs against it are deterministic.

## Layers

- `src/inventory/config/` — the reorder policy (default and per-SKU thresholds).
- `src/inventory/domain/` — pure stock rules: stock levels, reservations,
  reorder checks, and the typed `InventoryError`.
- `src/inventory/service/` — an `InventoryService` that composes the domain and
  tracks items.
- `src/inventory/logging/` — a small structured-logging abstraction the service
  depends on.

## Toolchain

| Concern     | Tool                                            |
| ----------- | ----------------------------------------------- |
| Format/lint | Ruff (`ruff format --check .`, `ruff check .`)  |
| Types       | mypy (strict) over `src`                        |
| Tests       | pytest + pytest-cov, LCOV → `coverage/lcov.info` |
| Mutation    | mutmut (opt-in)                                 |

```bash
uv sync
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest --cov=src --cov-report=lcov:coverage/lcov.info
```

This project carries committed source and `uv.lock` only; the virtual
environment is created inside an ephemeral sandbox by the kit's harness, never
committed.
