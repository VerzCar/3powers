<!-- Thanks for contributing to 3Powers! Please read CONTRIBUTING.md if you haven't. -->

## What & why

<!-- What does this change, and why? Link the issue it closes. -->

Closes #

## Requirement trace

<!-- 3Powers is spec-driven: changes trace to a requirement. Note the requirement ID(s) this addresses,
     or link the spec/plan. If this introduces new intended behavior, say which spec it lands in. -->

- Requirement / spec:

## Checklist

- [ ] The change traces to a requirement (or a new one is filed in a spec).
- [ ] Engine stays green under its own gates: `uv run ruff check .`, `uv run mypy src`, `uv run pytest`.
- [ ] Relevant gates were run (`3pwr gate run …`) and the verdict is green (or a signed, reversible
      `3pwr deviation` covers any exception — described below).
- [ ] No gate was satisfied by weakening it (no disabled rules, blanket `# type: ignore`, deleted
      assertions, or lowered thresholds).
- [ ] Tests reference the requirement they exercise; trust-spine modules keep diff-coverage ≥95%.
- [ ] Docs updated if behavior or the CLI surface changed.

## Notes for reviewers

<!-- Anything worth calling out: trade-offs, follow-ups, any deviation recorded and why. -->
