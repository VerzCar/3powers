# go-ratelimit

A small **in-memory rate-limiter** — the Go sample project for the 3pwr
end-to-end testing kit. It is deliberately layered and free of I/O (no network,
no database, no wall-clock dependence — time is injected) so that lifecycle runs
against it are deterministic.

## Layers

- **errors** (`errors.go`) — one typed `LimiterError` carrying a stable `Code`.
- **clock** (`clock.go`) — a `Clock` abstraction; `SystemClock` in production,
  `ManualClock` in tests.
- **logging** (`logging.go`) — a small `Logger` interface with an in-memory and
  a no-op implementation.
- **strategies** (`tokenbucket.go`, `slidingwindow.go`) — two `Limiter`
  implementations behind one interface.
- **registry** (`registry.go`) — a concurrency-safe registry that tracks named
  limiters.

## Toolchain

| Concern     | Tool                                                    |
| ----------- | ------------------------------------------------------- |
| Format      | `gofmt -l .` (must be empty)                            |
| Lint        | `go vet ./...`                                          |
| Types/build | `go build ./...`                                        |
| Tests       | `go test` + `gcov2lcov`, LCOV → `coverage/lcov.info`    |
| Mutation    | opt-in (High-risk tier)                                 |

```bash
go mod download
gofmt -l .
go vet ./...
go build ./...
go test -covermode=atomic -coverprofile=cover.out ./... \
  && gcov2lcov -infile cover.out -outfile coverage/lcov.info
```

This project carries committed source and `go.mod` only; the module cache,
`cover.out`, and `coverage/` are created inside an ephemeral sandbox by the
kit's harness, never committed.
