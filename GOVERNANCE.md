# Governance

3Powers is an open-source project with a simple, transparent governance model. This document explains who
makes decisions, how, and how that can change over time.

## Guiding principle: the spec is the law

Governance in 3Powers mirrors what the tool enforces. Technical decisions trace back to the specification
([`3Powers_Spec_v0.2.md`](3Powers_Spec_v0.2.md)) and the
[constitution](.specify/memory/constitution.md). A change that alters intended behavior belongs in the
spec first — not as a quiet code fix. Disagreements are resolved by appeal to the spec; if the spec is
silent or wrong, the fix is to change the spec, with sign-off.

## Roles

- **Maintainers** review and merge contributions, triage issues, cut releases, and steward the roadmap.
  The current lead maintainer is **Carlo Verzeri** ([@VerzCar](https://github.com/VerzCar)).
- **Contributors** are anyone who opens an issue or a pull request. You don't need special permissions to
  contribute — see [CONTRIBUTING.md](CONTRIBUTING.md).

## How decisions are made

- **Everyday changes** proceed by *lazy consensus*: a pull request that has been reviewed, passes the
  gates, and draws no sustained objection can be merged by a maintainer.
- **Substantial changes** (new pillars, a change to the lifecycle, anything touching the spec or the trust
  model) should start as an issue or a plan document under [`plan/`](plan/) so the direction can be
  discussed before code is written.
- **Disputes** are decided by the maintainers, guided by the spec and constitution. The goal is consensus;
  where that isn't reached, the lead maintainer makes the final call and records the rationale.

## The roadmap

Direction is tracked openly:

- [`docs/STATUS.md`](docs/STATUS.md) — what's implemented vs. pending, validated against the spec.
- [`plan/`](plan/) — the continuous plan series, each with a verification section.

## Becoming a maintainer

Maintainership is earned through sustained, high-quality contribution — good PRs, thoughtful reviews, and
help with issues. Existing maintainers may invite an active contributor to join. Maintainers who become
inactive for an extended period may move to emeritus status.

## Changing this document

Governance changes are proposed via pull request and require maintainer approval. As the community grows,
we expect this model to evolve (for example, toward a small maintainer committee); such changes will be
recorded here.
