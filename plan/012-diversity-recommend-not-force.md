# Plan 012 — Model diversity: recommend, don't force (configurable granularity + deviation relief)

> **Cold start:** read [`docs/STATUS.md`](../docs/STATUS.md), then the spec
> [`3Powers_Spec_v0.2.md`](../3Powers_Spec_v0.2.md) §7 (oracle), §14 (emergency & deviation), §19
> (open question: *"What defines 'different model family'"*). Builds on plan 008 (structural oracle
> independence), plan 011 (physical read-path isolation), and plan 007 (the signed `deviation`
> mechanism, FR-057). This plan is a **markdown plan only** — no code is changed yet.

## Context

`3PWR-FR-022` says the system *"shall refuse to run when [oracle and coder] resolve to the same model
family."* Today that is a **hard wall**: `oracle record`, `oracle dispatch`, `independence()`, the
High-risk `advance`, and `roles-check` all refuse (exit non-zero / add a blocking reason) when the
families match. Two real-world frictions follow:

1. **Single-model users are blocked.** A solo developer running only Claude Code (or only Copilot on one
   model) cannot use the oracle ceremony at all — the engine refuses. We *recommend* model diversity, but
   we cannot make owning ≥2 model families a **requirement** to use 3Powers.
2. **"Diverse" is defined too coarsely.** Diversity is compared at the *family* level (`family_of()` = the
   part before the first `/`), so `anthropic/opus` vs `anthropic/sonnet` counts as *not* diverse — even
   though two different models plausibly have different blind spots. The spec itself (§19) flags the
   model-family taxonomy as an open question.

**Goal.** Keep `FR-022` and diversity as the recommended default, but make it (a) **configurable in
granularity** (family-level strict, or model-level lenient) and (b) **never a hard wall** — a same-model
setup proceeds through a **signed, warned, reversible `deviation`** (the §14/FR-057 escape valve), exactly
like a relaxed gate. This is *not* silently weakening a check (forbidden by FR-032); it is the
spec-sanctioned, recorded, reversible relaxation FR-057 already provides.

**Non-negotiable framing (from the product owner):** 3Powers must work across all providers; a single-model
user is *warned*, never *walled off*. Diversity stays the recommended posture, surfaced loudly whenever it
is relaxed.

## Scope

**In**
- **Configurable diversity granularity.** A `diversity_level: family | model` setting in
  `.3powers/config/roles.yaml` (default `family` — today's behaviour). At `model` level, a different
  *model* in the same family (e.g. `anthropic/opus` vs `anthropic/sonnet`) satisfies `FR-022`.
- **Deviation relief for diversity.** Extend the existing signed `deviation` mechanism so a
  `model_diversity` target can cover the same-model/same-family case. When an active, covering deviation is
  present, the refusal becomes a **loud warning + recorded flag**, and `independence()`/High-risk `advance`
  treat the diversity mismatch as **advisory, not blocking** — the deviation's reason, approver, and way
  back (`--until` / `--revoke`) are recorded in the ledger (FR-057).
- **Consistent everywhere the refusal bites:** `oracle record`, `oracle dispatch`, `independence()`,
  High-risk `advance`, and `roles-check`.

**Out (→ later / non-goals)**
- No change to Standard/Cosmetic behaviour — they already never force the oracle ceremony.
- No automatic model-family *taxonomy service* (a maintained provider→family map). `family_of()` stays the
  simple prefix rule; `model`-level comparison uses the full recorded model string.
- No weakening of the physical read-path isolation (FR-021, plan 011) or the Phase-A/B ordering (FR-062) —
  this plan touches **only** the model-diversity dimension of independence.

## Decisions (recommended)

| Area | Decision | Why |
|---|---|---|
| Granularity config | `roles.yaml` gains `diversity_level: family\|model` (default `family`); a comparison helper `oracle.diverse(coder, oracle, level)` centralises it | One source of truth (FR-049); default preserves today's behaviour |
| Coder's model at `model` level | Read the coder's actual model from an optional `roles.coder.model`; if unset while `diversity_level: model`, **fall back to family-level with a warning** | The oracle's actual model is already recorded (`oracle record`/`dispatch`); the coder's is not — make it explicit, degrade safely |
| Relief mechanism | Reuse the **signed `deviation`** (FR-057) with a recognised target token `model_diversity` (validated alongside gate names); never a new bespoke bypass | FR-057 is the spec's sanctioned, reversible, recorded "off the happy path"; avoids a second, weaker escape hatch |
| Blocking → advisory | With a covering `model_diversity` deviation active, the family/model-equality finding moves from `reasons` (blocking) to `advisory` (surfaced, non-blocking); a loud warning prints at record/dispatch/advance | Matches plan 008's advisory pattern and keeps determinism (NFR-001): the *decision* is ledger-derived (is a signed deviation active?), not a heuristic |
| Spec stays law | `FR-022` wording unchanged; specs/002 acceptance updated to *"…shall refuse unless a signed `model_diversity` deviation (FR-057) covers it; comparison granularity is configurable (family\|model)"* | Resolves the §19 open question without silently softening a `shall` (FR-032) |
| Tiers | Relief applies wherever the refusal currently appears (record/dispatch/advance/roles-check), at any tier | The product goal is "never a hard wall" — a recorded deviation is the uniform way through |

## Implementation (sequenced — for the follow-up build, not this doc)

### 1. `config.py` + `.3powers/config/roles.yaml`
- `roles.yaml`: add top-level `diversity_level: family` and an optional `roles.coder.model: "<family>/<model>"`
  (commented, for `model`-level comparison). Keep `diversity_enforced: true`.
- `config.Settings`: add `diversity_level()` and `coder_model()` readers (default `family`, `""`).

### 2. `oracle.py` — one comparison helper, wired into `independence()`
- `def diverse(coder: str, oracle: str, level: str) -> bool` — at `family` level compare `family_of()`; at
  `model` level compare the full `<family>/<model>` strings (falling back to family compare + a returned
  "fallback" flag when the coder model is unavailable).
- `independence(...)` gains `diversity_relaxed: bool = False` and `diversity_level: str = "family"`. The
  `FR-022` check uses `diverse(...)`; when it fails **and** `diversity_relaxed` is set, the finding is
  appended to `advisory` instead of `reasons` (same for the plan-011 dispatch-family check). No change to
  seal-binding, ordering, coverage, or isolation.

### 3. `deviations.py` — recognise the `model_diversity` target
- Add `MODEL_DIVERSITY = "model_diversity"` to the set of valid deviation targets (so `--gate
  model_diversity` validates), and a `covers_model_diversity(active, spec_id)` helper mirroring
  `covered_gates`. Emergency/gate logic is untouched.

### 4. `cli.py` — warn-and-proceed instead of refuse, when covered
- `cmd_oracle_record` / `cmd_oracle_dispatch`: replace the hard `if fam == coder: refuse` with:
  compute `diverse(...)`; if not diverse, look for an active `model_diversity` deviation (via a loaded
  ledger); **covered → print a loud warning, record a `diversity_deviation: <seq>` flag in the payload,
  proceed; not covered → refuse as today** with a message pointing to `3pwr deviation --gate model_diversity`.
- `cmd_advance` (High-risk branch): pass `diversity_relaxed = deviations.covers_model_diversity(active,
  spec)` and `diversity_level = s.diversity_level()` into `independence(...)`; record `diversity_relaxed`
  in the `stage_advance` payload; the existing deviation-audit line already lists active deviations.
- `cmd_deviation`: accept `model_diversity` as a `--gate` target (help text + validation update).
- `cmd_roles_check`: honour `diversity_level`; when a `model_diversity` deviation is active, exit `0` with a
  warning instead of non-zero (still prints the recommendation).

### 5. Tests — `engine/tests/test_diversity.py` (cite FR-022/FR-057)
- `diverse()` at family vs model level (Opus/Sonnet: not diverse at family, diverse at model; Opus/Opus:
  never diverse); model-level fallback-to-family when coder model unset.
- `independence()` with `diversity_relaxed=True`: same-family finding lands in `advisory`, `ok` stays True
  (all else valid); without it, blocking (unchanged).
- CLI: `oracle record`/`dispatch` in the coder's family **refused without** a deviation, **warned +
  recorded + proceeds with** an active `model_diversity` deviation; High-risk `advance` proceeds under the
  deviation and refuses without it; `deviation --revoke` restores the refusal (the way back, FR-057).
- Self-application (NFR-006): the new pure helpers hold High-risk coverage; keep the engine green.

### 6. Docs / config
- `specs/002-engine-trust-spine/spec.md`: update the `FR-022` acceptance (refuse *unless* a signed
  `model_diversity` deviation; configurable granularity).
- `docs/STATUS.md`: move plan 012 to done; note FR-022 is now recommend-not-force (deviation-relaxable) with
  configurable granularity, resolving the §19 taxonomy open question at the config level.
- `CLAUDE.md` / `AGENTS.md`: document `diversity_level`, `roles.coder.model`, and
  `3pwr deviation --gate model_diversity --approver <you> --note "single-model dev"`.
- `.3powers/config/roles.yaml`: the new keys + a comment that diversity is *recommended*, relaxable via a
  recorded deviation, never a silent drop.

## Verification (definition of done, for the build)

```bash
(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)          # green, + new diversity tests
# High-risk self-application stays green (NFR-006):
(cd engine && uv run python -m threepowers.cli --root .. gate run --path . --adapter python \
   --spec ../specs/002-engine-trust-spine/spec.md --tier High-risk --mutation --no-ledger \
   --paths src/threepowers/canonical.py src/threepowers/keys.py \
           src/threepowers/ledger.py src/threepowers/verify.py)

# Single-model user is warned, not walled off:
3pwr oracle record --spec-id <ID> --model anthropic/opus --tests <paths>        # refused: same family as coder
3pwr deviation --gate model_diversity --approver <you> --note "solo dev, single model" --until <iso>
3pwr oracle record --spec-id <ID> --model anthropic/opus --tests <paths>        # now: ⚠ warned + recorded, proceeds
3pwr advance --stage ship --spec-id <ID>                                        # proceeds under the deviation
3pwr deviation --revoke <seq>                                                   # the way back → refusal returns

# Model-level granularity (opt-in): Opus vs Sonnet qualifies without a deviation
#   set roles.yaml: diversity_level: model, coder.model: anthropic/sonnet
3pwr oracle record --spec-id <ID> --model anthropic/opus --tests <paths>        # OK — different model, same family
```

**Done when:** diversity comparison is configurable (`family`|`model`); a same-model/same-family setup is
**refused by default but proceeds through a signed, warned, reversible `model_diversity` deviation** that is
recorded in the ledger and undone by `--revoke`; `independence()`/High-risk `advance` treat a covered
mismatch as advisory (never blocking) while keeping seal-binding, ordering, coverage, and physical isolation
intact; the engine self-applies green at High-risk; and `FR-022` stays the law with its acceptance updated
to reflect the FR-057 relief.

## Residual (→ later)
- A maintained provider→family taxonomy (beyond the `family_of()` prefix rule) — only if model naming drift
  makes the prefix rule unreliable.
- Capturing the coder's actual model automatically at implementation time (rather than `roles.coder.model`),
  once a live headless coder dispatch exists (the fuller A3 leg from plan 011).
