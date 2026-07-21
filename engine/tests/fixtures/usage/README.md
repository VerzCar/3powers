# Usage fixtures — provenance and honesty note

These fixtures pin each supported backend's token/cost extraction (`threepowers.agents`) and back
the per-backend drift guards in `tests/test_agents.py`. A drift guard is only as honest as the
fixture it compares against, so this file records **which fixtures were captured from a live CLI**
and **which were modelled from vendor research and are pending live re-verification**. Do not treat
a modelled fixture as proof of a live-verified schema.

## Real-captured (observed from the live CLI)

- `copilot_summary.txt` — the copilot CLI's current terminal summary block. The token line
  `Tokens     ↑ 241.6k (192.8k cached, 46.9k written) • ↓ 5.2k (1.2k reasoning)` is genuine current
  output (padded columns, a two-term `(… cached, … written)` input parenthetical, and a
  `(… reasoning)` output parenthetical). The hardened regex fallback extracts non-cached written
  (46.9k) + output (5.2k) = 52100.

## Modelled — pending live re-verification

The **structured** shapes below were modelled from vendor documentation/research, not captured from
a live CLI in this environment. Their field *paths* are the drift-guard's subject: if a real capture
later shows a different schema, the parametrized extraction test in `tests/test_agents.py` fails
(rather than silently zeroing), which is exactly the signal to update the fixture. Until then, treat
the inner field names as provisional.

- `claude_stream_modelusage.jsonl` — Claude Code `--output-format stream-json` transcript whose
  `result` event carries the whole-tree `modelUsage` per-model map (camelCase `inputTokens`/
  `outputTokens`/`costUSD`) plus the flat top-level `usage` block and `total_cost_usd`.
- `codex_json.jsonl` — Codex `exec --json` stream ending in a `turn.completed` event whose `usage`
  object reports `input_tokens`/`cached_input_tokens`/`output_tokens`.
- `opencode.jsonl` — opencode `run --format json` stream emitting one `step_finish` event per step
  (`part.tokens.{input,output}`, `part.cost`) with no cumulative summary.
- `copilot_events.jsonl` — copilot `~/.copilot/session-state/<uuid>/events.jsonl` ending in a
  `session.shutdown` event whose `usage` object mirrors the summary line's counts.
- `aider_analytics.jsonl` — aider `--analytics-log` JSONL with one `message_send` event per turn
  (`properties.{prompt_tokens,completion_tokens,cost,total_cost}`).

## Legacy — retained for regression only

`aider.txt`, `claude.json`, `claude_stream.jsonl`, `codex.jsonl`, `codex.txt`, `copilot.txt` are the
earlier prose/blob shapes. They remain so the older-CLI fallbacks stay covered, but they are **not**
the current primary path for their backend and must not be used to assert current-format behavior.
`copilot.txt` in particular is the OLD single-term `(… written)` summary; the drift guard asserts it
resolves to a *different* number than `copilot_summary.txt`, so a format regression cannot pass
silently.
