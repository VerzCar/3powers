"""The lifecycle loop: ``run``, ``status``, ``git start``, ``abort`` — plus the
run's dispatch, phase, and steering helpers."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional


import threepowers.cli as _cli
from .. import (
    agents,
    artifacts,
    autofix,
    completion,
    deviations,
    gitflow,
    hosted,
    keys,
    lifecycle,
    notify,
    orchestrate,
    phases,
    progress,
    prompts,
    runlock,
    runner as runnermod,
    runpreflight,
    steering,
    style,
    transcripts,
    workkind,
    workspace,
)
from . import trust
from ..config import Settings
from ..gates import PrerequisiteError
from ..gates import fixed_paths as auto_fixed_paths
from ..ledger import Ledger
from ..runner import CliAgentRunner, NativeRunner, TextSink
from ..verdict import STATUS_PASS
from ._common import (
    EXIT_FAIL,
    EXIT_OK,
    EXIT_PAUSED,
    EXIT_SETUP,
    EXIT_USAGE,
    _compose,
    _detection_line,
    _effective_gates_or_none,
    _notify_event,
    _print,
    _settings,
    _spec_approval_payload,
    _styler,
    _verbosity,
)

if TYPE_CHECKING:
    from ._common import AddCommon, SubParsers


def cmd_status(args: argparse.Namespace) -> int:
    """Per-spec lifecycle stage, derived from the ledger."""
    s = _settings(args.root)
    ledger_entries = Ledger(s.ledger_path).entries()
    states = lifecycle.derive(ledger_entries)
    if args.spec_id:
        states = {k: v for k, v in states.items() if k == args.spec_id}
    rows = [
        {
            "spec_id": st.spec_id,
            "stage": st.stage,
            "last_verdict": st.last_verdict,
            "signed_off": st.signed_off,
            "aborted": st.aborted,
            # The most recent unresolved run failure, if any.
            "failed": st.failed,
            "failed_stage": st.failed_stage,
            "failed_class": st.failed_class,
            "failed_at": st.failed_at,
        }
        for st in states.values()
    ]
    if args.json:
        print(json.dumps(rows, indent=2))
        return EXIT_OK
    sst = _styler(args)
    out: list[str] = []
    if _verbosity(args) != "quiet":
        out.append(sst.header("status", args.spec_id or "all tracked specs"))
    if not rows:
        out.append(sst.status_row("info", "no tracked specs in the ledger"))
    else:
        table_rows = []
        for r in rows:
            flags = []
            if r["signed_off"]:
                flags.append("signed-off")
            if r["aborted"]:
                flags.append("ABORTED")
            if r["failed"]:
                # Distinct from paused-at-gate and from in-progress.
                flags.append(
                    f"failed at {r['failed_stage'] or '?'} ({r['failed_class']}) at "
                    f"{r['failed_at'] or '?'}"
                )
            state = (
                "fail"
                if (r["failed"] or r["aborted"])
                else ("pass" if r["last_verdict"] == "pass" else "info")
            )
            table_rows.append(
                [
                    sst.mark(state),
                    str(r["spec_id"]),
                    str(r["stage"]),
                    str(r["last_verdict"]),
                    " ".join(flags),
                ]
            )
        out.append(sst.table(table_rows, headers=["", "spec", "stage", "verdict", "notes"]))
    # Surface active deviations + overdue emergency cleanups.
    active = deviations.active_deviations(ledger_entries)
    overdue_seqs = {d.get("seq") for d in deviations.overdue_emergencies(ledger_entries)}
    for d in active:
        kind = "emergency" if d.get("emergency") else "deviation"
        tag = " — CLEANUP OVERDUE" if d.get("seq") in overdue_seqs else ""
        out.append(
            sst.status_row(
                "warn" if tag else "todo",
                f"{kind} #{d.get('seq')}: gates={','.join(d.get('gates', []))} "
                f"by {d.get('approver', '?')}{tag}",
            )
        )
    # Surface each run's git lifecycle state: its dedicated branch and the committed
    # stages — derived from the signed ledger alone, consistent with the existing status semantics.
    for r in rows:
        run_branch = gitflow.branch_from_ledger(ledger_entries, str(r["spec_id"]))
        if run_branch:
            done_steps = gitflow.committed_steps(ledger_entries, str(r["spec_id"]))
            out.append(
                sst.status_row(
                    "info",
                    f"{r['spec_id']}: run branch {run_branch}",
                    f"committed stages: {', '.join(done_steps) or '—'}",
                )
            )
    # Surface oracle authoring records + advisory peek/touch findings.
    for e in ledger_entries:
        if e.get("type") != "oracle" or (e.get("payload") or {}).get("kind") != "record":
            continue
        p = e["payload"]
        out.append(
            sst.status_row(
                "info",
                f"oracle record #{e.get('seq')} {e.get('spec_id', '') or '(global)'}: "
                f"model={p.get('model', '?')} family={p.get('model_family', '?')}",
            )
        )
        for finding in p.get("advisory_findings", []):
            out.append(sst.status_row("warn", f"advisory (not a blocker): {finding}", indent=6))
    print("\n".join(out))
    return EXIT_OK


def cmd_git_start(args: argparse.Namespace) -> int:
    """Establish the run's dedicated branch for a MANUAL drive.

    The command-by-command `/3pwr.*` path gets the same guarantees as `3pwr run`: a working git
    repository, the clean-start guard, and one dedicated branch named
    from the run's <NNN>-<slug> workspace identity — bound to the run in the signed ledger so a
    later resume or `advance` recovers it offline. Idempotent: an already-established
    run re-enters its recorded branch and appends nothing new."""
    s = _settings(args.root)
    gst = _styler(args)
    cond = gitflow.precondition(s.root)
    if cond:
        print(f"error: {cond}", file=sys.stderr)
        return EXIT_USAGE
    ledger = Ledger(s.ledger_path)
    entries = ledger.entries()
    prefs = gitflow.load_prefs(s.git_config_path)
    if prefs.malformed and not args.json:
        print(
            "warning: .3powers/config/git.yaml is malformed — using the default git preferences",
            file=sys.stderr,
        )
    # Resolve the run's feature identity: an explicit --feature wins, else the ledger's binding.
    feature_dir: Optional[Path] = None
    if args.feature:
        p = Path(args.feature)
        feature_dir = p if p.is_absolute() else (s.root / p)
        if not feature_dir.is_dir():
            print(f"error: feature folder not found: {args.feature}", file=sys.stderr)
            return EXIT_USAGE
    else:
        feature_dir = _run_feature_dir_from_ledger(s, entries, args.spec_id)
    recorded_branch = gitflow.branch_from_ledger(entries, args.spec_id)
    identity = feature_dir.name if feature_dir is not None else workspace.slugify(args.spec_id)
    branch = recorded_branch or gitflow.run_branch_name(prefs.branch_prefix, identity)
    # The clean-start guard — the run's own recorded paths and its feature folder are
    # tolerated; only unrelated changes refuse, relaxable via the signed deviation.
    covered = deviations.covered_gates(deviations.active_deviations(entries), args.spec_id)
    if deviations.GIT_CLEAN_START not in covered:
        prefix = ""
        if feature_dir is not None:
            try:
                prefix = feature_dir.relative_to(s.root).as_posix() + "/"
            except ValueError:
                prefix = ""
        unrelated = gitflow.unrelated_changes(
            gitflow.uncommitted(s.root),
            gitflow.recorded_run_paths(entries, args.spec_id),
            prefix,
        )
        if unrelated:
            print(gitflow.clean_start_refusal(unrelated), file=sys.stderr)
            return EXIT_FAIL
    # Idempotent manual drive: re-enter the run's already-recorded branch (or create it off base
    # the first time) — the same re-entering intent a resume uses, never the fresh guard.
    b_err = gitflow.ensure_run_branch(s.root, branch, prefs.base_branch, mode="resume")
    if b_err:
        print(f"error: {b_err}", file=sys.stderr)
        return EXIT_FAIL
    appended: Optional[int] = None
    if not recorded_branch:
        # Bind the branch to the run — the same additive field on the existing run/start payload
        # the orchestrated path records.
        try:
            sk = keys.resolve_signer(s.root)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_USAGE
        payload: dict[str, Any] = {"kind": "start", "mode": "manual", "branch": branch}
        if feature_dir is not None:
            try:
                payload["feature_dir"] = feature_dir.relative_to(s.root).as_posix()
            except ValueError:
                payload["feature_dir"] = feature_dir.as_posix()
        appended = ledger.append("run", payload, sk, spec_id=args.spec_id)["seq"]
    rows = [
        gst.status_row(
            "pass",
            f"on run branch {branch}" + (" (recorded)" if recorded_branch else " (bound)"),
            f"ledger seq={appended}" if appended is not None else "already bound in the ledger",
        )
    ]
    _print(
        {"branch": branch, "spec_id": args.spec_id, "ledger_seq": appended},
        args.json,
        _compose(args, gst, title="git start", subject=args.spec_id, rows=rows),
    )
    return EXIT_OK


def _run_feature_dir_from_ledger(s: Settings, entries: list[dict], spec_id: str) -> Optional[Path]:
    """The run's bound feature folder, read back from the signed ``run``/``start`` entry.

    The latest ``start`` entry carrying a ``feature_dir`` wins — recovered offline from the ledger
    alone, no modification-time scan. ``None`` for a run recorded before folder binding existed
    (legacy fallback applies)."""
    rel = ""
    for e in entries:
        if e.get("spec_id") != spec_id or e.get("type") != "run":
            continue
        payload = e.get("payload", {})
        if payload.get("kind") == "start" and payload.get("feature_dir"):
            rel = str(payload["feature_dir"])
    return (s.root / rel) if rel else None


def _ledger_run_numbers(entries: list[dict]) -> list[int]:
    """The ``<NNN>`` run numbers recorded in the signed ledger's ``run`` entries (read-only).

    Every ``run`` entry's ``spec_id`` with its leading digits parsed to an int \u2014 the ledger side of
    the fresh-run id union, so a fresh run never reuses a number that survives only in the ledger
    (its folder and branch long gone). Read-only over ``Ledger.entries()``: never a ledger write,
    gate, or verdict input (notifications-style isolation)."""
    numbers: list[int] = []
    for e in entries:
        if e.get("type") != "run":
            continue
        digits = ""
        for ch in str(e.get("spec_id") or ""):
            if not ch.isdigit():
                break
            digits += ch
        if digits:
            numbers.append(int(digits))
    return numbers


def _run_pending_gate(ledger: Ledger, spec_id: str) -> str:
    st = lifecycle.derive(ledger.entries()).get(spec_id)
    return st.pending_gate if st else ""


def _run_intent_from_ledger(entries: list[dict], spec_id: str) -> str:
    """The run's resolved intent, read back from the latest signed ``run``/``start`` entry.

    A revise re-dispatches the paused stage WITH the original intent — recovered from
    the ledger alone, never re-asked."""
    intent = ""
    for e in entries:
        if e.get("spec_id") != spec_id or e.get("type") != "run":
            continue
        payload = e.get("payload", {})
        if payload.get("kind") == "start" and payload.get("intent"):
            intent = str(payload["intent"])
    return intent


def _gate_pause_rows(rst: style.Styler, spec_id: str, artifact: str) -> list[str]:
    """The three human-gate actions, each with its copy-pasteable command, plus the artifact under
    review — one source for the pause screen and the interactive prompt."""
    rows = []
    if artifact:
        rows.append(f"  {rst.dim('review:'.ljust(9))}{artifact}")
    rows.extend(
        f"  {rst.dim((name + ':').ljust(9))}{rst.bold(cmd)}"
        for name, cmd in steering.gate_actions(spec_id)
    )
    return rows


def _run_signoff(
    s: Settings,
    ledger: Ledger,
    sk,
    spec_id: str,
    gate: str,
    approver: Optional[str],
    note: Optional[str],
) -> None:
    """Record the human's gate approval as a signed sign-off.

    The spec-approval gate additionally seals the approved document's hash into the
    signed entry — same capture as a manual `3pwr signoff --stage spec`.
    """
    stage = "Spec" if gate == "review-spec" else "Review"
    label = orchestrate.MANDATORY_GATES.get(gate, "")
    payload = {
        "approver": approver or "human",
        "stage": stage,
        "note": note
        or (f"approved gate '{gate}' ({label})" if label else f"approved gate '{gate}'"),
    }
    if stage == "Spec":
        payload.update(_spec_approval_payload(s, None))
    ledger.append("signoff", payload, sk, spec_id=spec_id)


def _record_run_failure(
    ledger: Ledger,
    sk,
    spec_id: str,
    *,
    stage: str,
    failure_class: str,
    attempts: int,
    detail: str,
    transcript: str = "",
) -> None:
    """Append the signed run-failure record before exiting.

    Stage, failure class, attempt count, and a bounded detail ride in a ``run``/``failure`` entry via
    the existing append API — additive content only, so ``3pwr verify`` stays green.
    The transcript field carries the persisted path, never the output itself."""
    payload: dict[str, Any] = {
        "kind": "failure",
        "stage": stage or "",
        "class": failure_class,
        "attempts": int(attempts),
        "detail": (detail or "")[:400],
    }
    if transcript:
        payload["transcript"] = transcript
    ledger.append("run", payload, sk, spec_id=spec_id)


def _resolve_runner_kind(args: argparse.Namespace) -> str:
    """The executive runner to use: --dry-run forces ``sim``; else --runner, defaulting to
    ``native``."""
    if args.dry_run:
        return "sim"
    return getattr(args, "runner", None) or "native"


def _resolve_coder_agent(s: Settings, args: argparse.Namespace) -> str:
    """The coder agent backend: --agent wins, else --integration/roles.coder.integration."""
    return getattr(args, "agent", None) or runpreflight.resolve_coder_integration(
        s, args.integration
    )


def _resolve_run_spec(
    s: Settings, args: argparse.Namespace, feature_dir: Optional[Path] = None
) -> Optional[Path]:
    """The spec the native run resolves: --spec if given, else the run's bound feature folder
    (no modification-time scan), else the newest feature spec under specs-src/ (legacy)."""
    if getattr(args, "spec", None):
        p = Path(args.spec)
        return p if p.exists() else None
    if feature_dir is not None:
        return workspace.spec_path(feature_dir)
    specs = sorted(workspace.find_specs(s.root), key=lambda q: q.stat().st_mtime, reverse=True)
    return specs[0] if specs else None


def _native_verdict(
    s: Settings,
    args: argparse.Namespace,
    tier: str,
    kinds: list[str],
    *,
    ledger: Optional[Ledger] = None,
    sk=None,
    feature_dir: Optional[Path] = None,
    out: Optional[dict[str, Any]] = None,
) -> str:
    """Run the deterministic gate suite IN-PROCESS for the native verify stage.

    Returns ``pass`` / ``fail``; returns ``error`` when the gates cannot even run (no spec resolvable, no
    adapter detected, bad tier, or a missing gate prerequisite) so the caller reports a
    setup/dispatch problem, never a false gate-red. The engine computes the verdict itself
    — no subprocess dispatch, no model.

    When a ledger + signer are supplied, the verdict is recorded exactly as a standalone
    ``3pwr gate run`` records it — written to ``verdicts/latest.json`` and appended as a signed
    ``verdict`` entry — so an in-run red or green is never invisible to the trust spine.
    The verdict bytes themselves are unchanged. When ``out`` is given, the computed
    verdict dict is stashed under ``out['verdict']`` so the caller can render a red verdict's failed
    gates inline."""
    spec_path = _resolve_run_spec(s, args, feature_dir)
    if spec_path is None:
        return "error"
    try:
        adapter_name = _cli.detect_adapter(s, s.root)
        # The same effective configuration as a standalone gate run: the
        # committed gates.yaml overrides plus startup auto-detection; the one detection line is
        # human output only. Degrades to None — run_gates loads the adapter.
        eff = _effective_gates_or_none(s, adapter_name, s.root)
        if eff is not None and eff.detected and not getattr(args, "json", False):
            print(_detection_line(eff.detected))
        verdict = _cli.run_gates(
            s,
            s.root,
            tier=tier,
            spec_path=spec_path,
            adapter_name=adapter_name,
            work_kind=kinds,
            auto_fix=bool(getattr(args, "auto_fix", False)),
            manifest=eff.manifest if eff is not None else None,
        )
    except PrerequisiteError as exc:
        # No gate ran — say exactly what to install, then report the setup failure.
        print(str(exc), file=sys.stderr)
        return "error"
    except (KeyError, LookupError, FileNotFoundError, ValueError, OSError):
        return "error"
    if out is not None:
        out["verdict"] = verdict.to_dict()
    if ledger is not None and sk is not None:
        s.verdicts_dir.mkdir(parents=True, exist_ok=True)
        verdict.write(s.verdicts_dir / "latest.json")
        ledger.append(
            "verdict",
            verdict.to_dict(),
            sk,
            spec_id=verdict.spec_id,
            requirement_ids=verdict.requirement_ids(),
        )
    return "pass" if verdict.result == STATUS_PASS else "fail"


def _auto_fix_loop(
    s: Settings,
    args: argparse.Namespace,
    *,
    tier: str,
    kinds: list[str],
    feature_dir: Optional[Path],
    ledger: Ledger,
    sk,
    coder,
    retries: int,
    initial_verdict: dict[str, Any],
    out: dict[str, Any],
    report: Callable[[str], None] = lambda _m: None,
) -> autofix.AutoFixResult:
    """Drive the bounded, code-only auto-fix loop over a red Verify verdict.

    Wires the pure :func:`autofix.run_loop` to this run's collaborators: it dispatches the run's
    already-constructed ``coder`` as a fresh session with the failed-gate hand-back prompt, and
    re-runs the deterministic gate suite via :func:`_native_verdict` — which records an honest signed
    verdict on every pass. It performs NO other action: it never records a deviation/advisory, edits
    gate config, or mutates a verdict. ``out`` receives the latest verdict dict on each re-check so
    the caller can read the final (green or still-red) verdict. Returns the loop's outcome."""
    cfg = s.auto_fix()

    def _dispatch(prompt: str, scope: Sequence[str]) -> bool:
        spec_path = _resolve_run_spec(s, args, feature_dir)
        spec_text = _dispatch_spec_text(s, "implement", spec_path)
        result, _attempts = runnermod.dispatch_with_retry(
            lambda: coder.dispatch(
                "implement",
                "Build",
                spec_text=spec_text,
                context=prompt,
                file_scope="\n".join(scope),
            ),
            retries=retries,
        )
        return result.ok

    def _recompute() -> tuple[str, dict[str, Any]]:
        outcome = _native_verdict(
            s, args, tier, kinds, ledger=ledger, sk=sk, feature_dir=feature_dir, out=out
        )
        return outcome, out.get("verdict") or {}

    return autofix.run_loop(
        verdict=initial_verdict,
        max_attempts=cfg.max_attempts,
        scope_to_failed=cfg.scope_to_failed,
        dispatch=_dispatch,
        recompute=_recompute,
        snapshot=lambda: runnermod.worktree_state(s.root),
        report=report,
    )


def build_coder_runner(
    s: Settings, args: argparse.Namespace, *, spec_id: str, stream: bool = False
):
    """Build the coder backend exactly as a live run does — for the standalone ``3pwr gate fix``.

    Resolves the coder integration (``--integration``/``--agent`` wins, else
    ``roles.coder.integration``) and constructs its dispatch backend with a transcript sink keyed by
    ``spec_id``. Returns ``(runner, agent_name)``; ``(None, "")`` when no coder integration is
    configured, so the caller can refuse with an actionable message. Raises ``FileNotFoundError``
    when the resolved agent has no manifest."""
    coder_agent = _resolve_coder_agent(s, args)
    if not coder_agent:
        return None, ""
    manifest = agents.load_agent(s, coder_agent)
    timeout = _dispatch_timeout(s, args)
    sink = transcripts.TranscriptSink(s.root, spec_id)
    coder = _make_agent_runner(
        s,
        manifest,
        model=str(s.role("coder").get("model") or ""),
        intent=getattr(args, "intent", "") or "",
        timeout=timeout,
        stream=stream,
        transcripts_sink=sink,
    )
    return coder, coder_agent


def _deviation_proceed_notices(
    verdict_payload: dict[str, Any], entries: list[dict[str, Any]], spec_id: str
) -> Optional[list[str]]:
    """The proceed notices when EVERY red gate of a Verify verdict is covered by an active,
    signed deviation scoped to ``spec_id`` (a global deviation applies too) — one
    ``proceeding past <gate> under deviation seq=N`` line per red gate. ``None`` when any red
    gate is uncovered (the run must stop at gate-red, as today) or when the verdict carries no
    red gate at all. Consumes the same shared coverage helper as ``advance``, so the two
    enforcement points cannot drift; the recorded verdict itself stays honestly red — only the
    run's proceed decision consults deviations."""
    reds = deviations.red_gates(verdict_payload)
    if not reds:
        return None
    active = deviations.active_deviations(entries)
    if deviations.uncovered_red_gates(verdict_payload, active, spec_id):
        return None
    notices: list[str] = []
    for gate in sorted(reds):
        dev = deviations.covering_deviation(gate, active, spec_id)
        seq = dev.get("seq") if dev else None
        notices.append(f"proceeding past {gate} under deviation seq={seq}")
    return notices


def _dispatch_timeout(s: Settings, args: argparse.Namespace) -> int:
    """The per-stage dispatch timeout: --timeout wins, else the configured default."""
    v = getattr(args, "timeout", None)
    return int(v) if v else s.dispatch_timeout()


def _dispatch_retries(s: Settings, args: argparse.Namespace) -> int:
    """The dispatch retry budget: --retries wins, else the configured default."""
    v = getattr(args, "retries", None)
    return int(v) if v is not None else s.dispatch_retries()


def _run_stream(args: argparse.Namespace) -> bool:
    """Whether to echo agent output live.

    On by default only on a real TTY and never under ``--json`` (pipes/JSON stay clean). An
    explicit ``--stream`` opts in off a TTY as well — the persisted transcript is always written
    either way — but ``--json`` still wins, so machine-readable output is never interleaved with
    live event noise."""
    if args.json:
        return False
    return bool(sys.stdout.isatty()) or bool(getattr(args, "stream", False))


def _resolve_show_prompts(s: Settings, args: argparse.Namespace) -> bool:
    """Whether to echo each stage's assembled agent prompt live, before its dispatch.

    Display only — it never changes what is sent to the agent, the persisted transcript, the
    ``--json`` payload, the verdict, exit codes, or the ledger. Precedence: the
    ``--show-prompts`` / ``--no-show-prompts`` flag wins, else the ``ui.yaml`` ``show_prompts``
    preference, else the default (off). Forced off under ``--json`` and ``--quiet`` — a machine or
    silenced run never carries the echo. Tolerant of a not-yet-initialized repo."""
    if getattr(args, "json", False):
        return False
    if _verbosity(args) == "quiet":
        return False
    flag = getattr(args, "show_prompts", None)
    if flag is not None:
        return bool(flag)
    try:
        prefs, _ = s.load_ui()
    except (FileNotFoundError, OSError):
        return False
    return bool(prefs.get("show_prompts", False))


def _make_agent_runner(
    s: Settings,
    manifest: dict,
    *,
    model: str,
    intent: str,
    timeout: int,
    stream: bool,
    transcripts_sink: Optional[transcripts.TranscriptSink] = None,
    echo: Optional[TextSink] = None,
    subagent_models: Optional[dict[str, str]] = None,
    raw_events: bool = False,
    show_prompts: bool = False,
    prompt_styler: Optional[style.Styler] = None,
):
    """Build the backend that dispatches a role's stages: a local headless CLI
    (:class:`CliAgentRunner`) or, when the manifest declares ``mode: async-hosted``, the async hosted
    backend (:class:`HostedAgentRunner`). Both satisfy the same ``dispatch(step, stage) ->
    DispatchResult`` contract, so the
    verdict is judged identically. The transcript sink persists each local attempt's
    output; a hosted backend's output lives with its hosting service. ``echo`` routes the
    streamed agent conversation above the run's live bar instead of raw stdout.
    ``subagent_models`` (roles.yaml, keyed by step) threads a per-stage cheaper sub-agent model into
    the local dispatch; a hosted backend has no such mechanism and ignores it (backend-neutral).
    ``raw_events`` (from ``--raw-events``) shows a stream-json backend's underlying events verbatim
    instead of the rendered assistant text deltas. ``show_prompts`` (from ``--show-prompts`` /
    ``ui.yaml``) echoes each stage's assembled prompt above the live bar before its dispatch —
    display only; a hosted backend has no live echo path and ignores it (backend-neutral)."""
    if hosted.is_hosted(manifest):
        return hosted.HostedAgentRunner(
            s, manifest, model=model, cwd=s.root, intent=intent, timeout=timeout
        )
    return CliAgentRunner(
        s,
        manifest,
        model=model,
        cwd=s.root,
        intent=intent,
        timeout=timeout,
        stream=stream,
        transcripts=transcripts_sink,
        echo_out=echo,
        echo_err=echo,
        subagent_models=subagent_models,
        raw_events=raw_events,
        show_prompts=show_prompts,
        prompt_styler=prompt_styler,
    )


def _dispatch_spec_text(s: Settings, step: str, spec_path: Optional[Path]) -> str:
    """The approved-spec text a stage's prompt reloads.

    Stages after the ``review-spec`` human gate (plan, tasks, oracle, implement, advance) get the
    approved specification injected, so no stage depends on the agent rediscovering the law. Stages
    before approval (specify, clarify) author/refine the spec and get none. Deterministic given the
    tree."""
    if orchestrate.step_index(step) <= orchestrate.step_index("review-spec"):
        return ""
    if spec_path is None:
        return ""
    try:
        return spec_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _prior_artifact_ref(s: Settings, step: str, result: runnermod.StageResult) -> str:
    """A reference to (digest of) an accepted stage artifact for the NEXT stage's prompt."""
    if not result.artifact_paths:
        return ""
    path = result.artifact_paths[0]
    try:
        digest = hashlib.sha256((s.root / path).read_bytes()).hexdigest()[:12]
    except OSError:
        digest = ""
    tail = f" (sha256 {digest})" if digest else ""
    return f"prior stage '{step}' accepted artifact: {path}{tail} — read it before starting."


def _implement_phases(s: Settings, spec_path: Optional[Path]) -> list[phases.Phase]:
    """The ordered phases declared by the feature's tasks artifact, or ``[]``.

    An empty result — no tasks artifact, or one that declares no phases — means the implement stage
    runs the whole task set as a single fresh session, preserving the pre-phase behavior as the
    degenerate case."""
    if spec_path is None:
        return []
    tasks_art = workspace.find_artifact(workspace.feature_dir_of(spec_path), "tasks")
    if tasks_art is None:
        return []
    try:
        return phases.parse_phases(tasks_art.read_text(encoding="utf-8"))
    except OSError:
        return []


def _report_phase_estimates(
    s: Settings, result: runnermod.StageResult, spec_path: Optional[Path], *, coder_model: str
) -> None:
    """Per-phase context estimates + the advisory oversize warnings after the tasks stage.

    Each phase's deterministic estimate is reported; an over-budget phase gets a warning naming the
    phase, its estimate, and the budget, advising a split — and the run proceeds. Written to stderr
    (never the --json stdout) and carried on the stage result; no gate or verdict is touched."""
    phase_list = _implement_phases(s, spec_path)
    if not phase_list:
        return
    budget = s.context_budget(coder_model)
    prompt_text = prompts.resolve_body("implement", s.stage_templates_dir)
    for ph in phase_list:
        est = phases.phase_estimate(
            s.root,
            ph,
            spec_path=spec_path,
            constitution_path=s.constitution_path,
            prompt_text=prompt_text,
        )
        print(
            f"  · phase {ph.index} '{ph.name}': estimated ~{est} tokens (budget {budget})",
            file=sys.stderr,
        )
        warn = phases.oversize_warning(ph, est, budget)
        if warn:
            result.warnings.append(warn)
            print(f"  ⚠ {warn}", file=sys.stderr)


def _implement_report(s: Settings, transcript_rel: str) -> str:
    """The implement agent's completion report, extracted from the stage's persisted transcript.

    Deterministic given the transcript bytes: the text from the last ``- **Stage**:`` marker onward
    (the fixed report shape the implement agent template mandates), within the tail read window. A
    missing or unreadable transcript, or one carrying no report marker, yields ``""`` — the
    changelog record then simply omits the folded report. Never raises."""
    if not transcript_rel:
        return ""
    tail = transcripts.tail_text(s.root / transcript_rel, limit=4000)
    marker = tail.rfind("- **Stage**:")
    return tail[marker:].strip() if marker >= 0 else ""


def _warn_if_unanswered(s: Settings, ph: phases.Phase, transcript_rel: str, spec_id: str) -> None:
    """Advisory stall check after one phase session ends.

    Scans the last 500 bytes of the session's persisted transcript for unanswered-question
    patterns and, on a match, prints a warning naming the phase plus the run's ``--status`` hint.
    Strictly advisory: it never raises, never retries, and never changes a stage
    outcome, ledger entry, or exit code — a missing/unreadable transcript reads as empty and stays
    silent."""
    if not transcript_rel:
        return
    tail = transcripts.tail_text(s.root / transcript_rel, limit=500)
    if not transcripts.unanswered_question(tail):
        return
    print(
        f"  ⚠ phase {ph.index} ended with a possible unanswered question — review the transcript",
        file=sys.stderr,
    )
    print(
        f"    (run: 3pwr run --status --spec-id {spec_id} to see the full transcript path)",
        file=sys.stderr,
    )


def _dispatch_phased(
    s: Settings,
    step: str,
    stage: str,
    *,
    backend,
    agent_name: str,
    retries: int,
    spec_text: str,
    context: str,
    phase_list: list[phases.Phase],
    verify_artifact,
    ledger: Ledger,
    sk,
    spec_id: str,
    variables: Optional[dict[str, str]] = None,
    run_branch: str = "",
    commit_relaxed: bool = False,
    prefs: Optional[gitflow.GitPrefs] = None,
) -> runnermod.StageResult:
    """Run the implement stage phase by phase.

    Each phase is a NEW headless session whose prompt reloads that phase's handoff set — the approved
    spec, the constitution/rules, the phase's tasks, the declared file scope — with no conversation
    state carried between phases. Phases marked parallel with disjoint declared scopes
    and no dependency are dispatched concurrently; results are recorded in deterministic artifact
    order via one ledger entry appended AFTER collection, from this thread — parallel completion never
    touches the trust spine concurrently. Any phase failure fails the stage naming the
    phase(s); later phases are recorded as explicitly skipped, never as passed.

    Commit granularity rides here too: once every phase has succeeded, each phase's produced source
    lands as ONE commit — ``implement(phase N/M): <description>`` — issued sequentially in
    deterministic phase order from THIS collecting thread only, never from a batch worker (git index
    lock contention). Each phase commit carries ONLY the paths inside that phase's declared scope; the
    ledger ``phases`` entry and ``progress.md`` ride the trailing implement record commit the caller's
    post-stage hook makes. A commit failure fails the stage with :data:`gitflow.CLASS_COMMIT_FAILED`;
    ``--commit-relaxed`` / a signed ``git_stage_commit`` deviation skips the per-phase commits, exactly
    as it skips the post-stage commit."""
    t0 = time.monotonic()
    # The worktree snapshot BEFORE any phase runs — differenced against the post-collection snapshot
    # to attribute each phase's produced paths to its declared scope for the per-phase commits below.
    pre_all = runnermod.worktree_state(s.root)
    sched = phases.schedule(phase_list)
    batches = sched.batches
    # Visible parallelism: render the scheduler's decision metadata as pre-batch log lines — batch
    # number, parallel vs serial, the named reason for every serialized `[P]` phase, and the
    # executing agent/model per phase (the `roles.yaml` `subagent_models` override for this stage
    # when set, else the stage backend's model).
    phase_model = s.subagent_models().get(step, "") or str(backend.model)
    for line in _prebatch_log_lines(sched, agent_name=agent_name, model=phase_model):
        print(line, file=sys.stderr)
    try:
        constitution = s.constitution_path.read_text(encoding="utf-8")
    except OSError:
        constitution = ""
    total = len(phase_list)
    attempt_counts: list[int] = []  # list.append is atomic — safe across the batch threads
    # Advisory per-phase usage: distinct keys per phase, so concurrent batch threads never
    # collide. Feeds the additive ledger fields and the progress table — never the verdict.
    tokens_by_phase: dict[int, int] = {}
    cost_by_phase: dict[int, float] = {}
    # Each phase's agent-written `COMMIT:` description, keyed by phase index — read in the worker
    # (a transcript read, never a commit) and folded into that phase's commit subject on the
    # collecting thread below. Distinct keys per phase, so concurrent batch threads never collide.
    desc_by_phase: dict[int, str] = {}
    # Each phase's authored completion report, keyed by phase index — combined in phase order into
    # the stage's business changelog prose so an N-phase run's changelog covers every phase's
    # requirements (the collector below folds them into one record).
    reports_by_phase: dict[int, str] = {}

    def run_one(ph: phases.Phase) -> tuple[bool, str]:
        ctx = phases.handoff_context(
            ph,
            total,
            constitution_text=constitution,
            spec_id=spec_id,
            completed_summary=phases.completed_phases_summary(phase_list, ph.index),
        )
        if context:
            ctx = f"{context}\n\n{ctx}"
        file_scope = "\n".join(ph.file_scope)
        res, attempts = runnermod.dispatch_with_retry(
            lambda: backend.dispatch(
                step,
                stage,
                spec_text=spec_text,
                context=ctx,
                file_scope=file_scope,
                variables=variables,
            ),
            retries=retries,
        )
        attempt_counts.append(attempts)
        if res.tokens is not None:
            tokens_by_phase[ph.index] = res.tokens
        if res.cost is not None:
            cost_by_phase[ph.index] = res.cost
        # The phase's agent-written `COMMIT:` line, extracted from its transcript here (a read, never
        # a commit); the collecting thread folds it into this phase's commit subject, falling back to
        # the phase description when the agent wrote no usable line.
        cdesc = gitflow.agent_commit_description(s.root, res.transcript)
        if cdesc:
            desc_by_phase[ph.index] = cdesc
        rep = _implement_report(s, res.transcript)
        if rep:
            reports_by_phase[ph.index] = rep
        _warn_if_unanswered(s, ph, res.transcript, spec_id)
        return res.ok, ("" if res.ok else res.detail)

    prun = phases.run_phases(batches, run_one)
    results = [r.as_dict() for r in prun.results]
    for r in results:
        # Additive per-phase token field — present only when that phase's backend reported usage.
        tok = tokens_by_phase.get(int(r["phase"]))
        if tok is not None:
            r["tokens"] = tok
        # Additive per-phase cost field, in step with tokens — present only when reported.
        pcost = cost_by_phase.get(int(r["phase"]))
        if pcost is not None:
            r["cost"] = pcost
    stage_tokens = sum(tokens_by_phase.values()) if tokens_by_phase else None
    stage_cost = sum(cost_by_phase.values()) if cost_by_phase else None
    # The stage's business changelog prose: every phase's authored report in deterministic phase
    # order, so the collected changelog covers all phases' requirements.
    combined_report = "\n\n".join(reports_by_phase[i] for i in sorted(reports_by_phase))

    def _result(
        ok: bool, outcome: str, detail: str = "", artifact: str = "", paths: list[str] | None = None
    ) -> runnermod.StageResult:
        # Per-phase transcripts share the run's sink; the stage result names its directory so a
        # phased failure still points at the persisted output.
        sink = getattr(backend, "transcripts", None)
        return runnermod.StageResult(
            step=step,
            stage=stage,
            ok=ok,
            agent=agent_name,
            model=str(backend.model),
            attempts=sum(attempt_counts),
            duration_s=time.monotonic() - t0,
            artifact=artifact,
            outcome=outcome,
            detail=detail,
            transcript=sink.rel_dir if sink is not None else "",
            artifact_paths=paths or [],
            phases=results,
            report=combined_report,
            tokens=stage_tokens,
            cost=stage_cost,
        )

    # Per-phase commit granularity — issued ONLY from this collecting thread (never a batch worker:
    # git index lock contention), in deterministic phase order, and ONLY once every phase succeeded.
    # Each phase's produced source is the intersection of the run's produced set (pre → post
    # worktree diff) with that phase's declared scope; engine-owned state (the ledger, progress.md)
    # is deliberately excluded here — it rides the trailing implement record commit the caller's
    # post-stage hook makes. A commit failure fails the stage with CLASS_COMMIT_FAILED. The
    # `--commit-relaxed` / signed `git_stage_commit` deviation escape hatch skips these commits,
    # exactly as it skips the post-stage commit.
    gprefs = prefs or gitflow.GitPrefs()
    if prun.ok and run_branch and not commit_relaxed:
        produced_all = set(runnermod.produced_paths(pre_all, runnermod.worktree_state(s.root)))
        for ph in sorted(phase_list, key=lambda p: p.index):
            phase_paths = sorted(
                p
                for p in produced_all & set(ph.file_scope)
                if not p.startswith(gitflow.ENGINE_STATE_PREFIX)
            )
            if not phase_paths:
                continue
            desc = desc_by_phase.get(ph.index) or ph.name
            commit = gitflow.commit_stage(
                s.root,
                phase_paths,
                message=gitflow.phase_commit_message(ph.index, total, desc),
                author_name=gprefs.author_name,
                author_email=gprefs.author_email,
            )
            if commit.error:
                return _result(
                    False,
                    gitflow.CLASS_COMMIT_FAILED,
                    detail=f"phase {ph.index} '{ph.name}' could not be committed — {commit.error}",
                )

    ledger.append("run", {"kind": "phases", "step": step, "results": results}, sk, spec_id=spec_id)

    if not prun.ok:
        return _result(False, "dispatch_failed", detail=prun.failure_detail)
    check = verify_artifact()
    if not check.ok:
        return _result(
            False,
            "artifact_missing",
            detail=f"stage '{step}' produced no expected artifact — {check.message}",
        )
    return _result(True, "ok", artifact=check.summary, paths=list(check.matched))


def _feature_folder_value(s: Settings, feature_dir: Optional[Path]) -> str:
    """The run's feature folder as a repo-relative POSIX path — the ``$FEATURE_FOLDER`` value.

    Substituted into the stage template's instruction body so the agent writes the stage's
    markdown artifact FLAT into the allocated folder — the same location the workspace computes
    and the completion gate asserts. ``""`` when the run has no bound folder: an unfilled
    variable renders empty and the template's default-destination sentence applies."""
    if feature_dir is None:
        return ""
    try:
        return feature_dir.relative_to(s.root).as_posix()
    except ValueError:
        return feature_dir.as_posix()


def _oracle_destination_value(feature_dir: Optional[Path]) -> str:
    """The run's keyed oracle-test destination — the ``$ORACLE_DESTINATION`` value.

    Keys the run's oracle by its feature-folder id (mirroring how ``oracle dispatch`` re-keys the
    collected files): the runnable oracle tests go under ``tests/oracle/<id>/`` — one concrete id
    shared by the ledger records, the seal/record commands, and the folder the user browses, so
    which oracle belongs to which spec is self-evident. No placeholder ever reaches the agent on
    the run path; ``""`` when the run has no bound folder."""
    if feature_dir is None:
        return ""
    return f"tests/oracle/{feature_dir.name}/"


def _progress_safe(update: Callable[[], Any]) -> None:
    """Run one progress-file update, degrading any error to a stderr warning.

    The progress file is an operator convenience view of the signed ledger — an IO problem writing
    it must never fail a run or a stage, so every trigger call goes through this guard."""
    try:
        update()
    except Exception as exc:  # any progress-write problem degrades to a warning, never a failure
        print(f"warning: progress.md not updated — {exc}", file=sys.stderr)


def _commit_engine_state(
    s: Settings,
    *,
    spec_id: str,
    step: str,
    run_branch: str,
    commit_relaxed: bool,
    prefs: Optional[gitflow.GitPrefs],
) -> None:
    """Commit the engine's trust-spine state (the ledger + the run's ``progress.md``) at a judgment
    step, so a paused or finished run leaves a clean working tree.

    A no-op when the run does not commit — no run branch (dry-run / simulated), or the per-stage
    commit is relaxed on the signed record (``--commit-relaxed`` / the ``git_stage_commit``
    deviation) — the same escape hatch the producing-stage commits honour. Otherwise it delegates to
    :func:`gitflow.commit_engine_state`, which stages ONLY engine-owned state and is itself a no-op
    when nothing engine-owned is dirty. A genuine git failure degrades to a stderr warning (never
    crashing the judgment step it follows), consistent with the run's other best-effort
    ledger-riding commits; the normal path leaves the tree clean."""
    if not run_branch or commit_relaxed:
        return
    gprefs = prefs or gitflow.GitPrefs()
    outcome = gitflow.commit_engine_state(
        s.root,
        message=gitflow.engine_state_commit_message(spec_id, step),
        author_name=gprefs.author_name,
        author_email=gprefs.author_email,
    )
    if outcome.error:
        print(f"warning: engine state not committed — {outcome.error}", file=sys.stderr)


def _prebatch_log_lines(sched: phases.Schedule, *, agent_name: str, model: str) -> list[str]:
    """The per-batch dispatch log rendered before a phased implement stage runs.

    One group per scheduled batch, in run order: its 1-based number and whether its phases run in
    parallel or serially, then one line per phase naming the executing ``agent / model`` and — for a
    serialized ``[P]`` phase — the scheduler's named reason it did not parallelize (a dependency not
    yet complete, a file-scope overlap, or no declared file scope). ``model`` already reflects the
    ``roles.yaml`` ``subagent_models`` override for the stage when one is set. Pure and deterministic
    given the schedule."""
    by_batch: dict[int, list[phases.PhaseDecision]] = {}
    for d in sched.decisions:
        by_batch.setdefault(d.batch_index, []).append(d)
    lines: list[str] = []
    for bi in sorted(by_batch):
        members = sorted(by_batch[bi], key=lambda d: d.index)
        mode = "parallel" if len(members) > 1 else "serial"
        lines.append(f"  batch {bi + 1} — {len(members)} phase(s), {mode}")
        for d in members:
            reason = f" — serialized: {d.serialization_reason}" if d.serialization_reason else ""
            lines.append(f"    · phase {d.index} ({d.name}) → {agent_name} / {model}{reason}")
    return lines


def _completion_tracker(st: style.Styler) -> str:
    """The run-completion stage tracker: every stage through Ship rendered as completed.

    A finished run has *reached and completed* Ship, so — unlike the live tracker, which marks the
    reached stage ``▶`` (current) — every stage up to and including Ship is ``✓`` ("ready to push").
    Observe is omitted from the row; it is surfaced separately as the post-run follow-on pointer/CTA
    rather than a pending row. Uses the same done glyph as :func:`orchestrate.render_tracker`."""
    done = "v" if st.ascii_only else "✓"
    cells = [st.ok(f"{done} {stage}") for stage in orchestrate.STAGES if stage != "Observe"]
    return "  ".join(cells)


def _completion_summary_lines(feature_dir: Optional[Path], st: style.Styler) -> list[str]:
    """The "All stages are done." statement plus the run's changelog-derived business summary.

    The highlight bullets come from the implement stage's ``changelog.md`` record — capped at five by
    :func:`completion.read_changelog_highlights`. When the record is absent or carried no authored
    entries the summary degrades to the single-line fallback, never an error (a legacy run without a
    changelog still completes cleanly)."""
    lines = [f"  {st.bold('All stages are done.')}"]
    highlights = (
        completion.read_changelog_highlights(feature_dir) if feature_dir is not None else []
    )
    if highlights:
        lines.append(f"  {st.dim('what shipped:')}")
        lines += [f"    · {h}" for h in highlights]
    else:
        lines.append(f"  {st.dim('what shipped: recorded in this run’s changelog.md')}")
    return lines


def _spec_ref_value(root: Path, feature_dir: Optional[Path]) -> str:
    """The governing spec's repo-relative path for the ``observe coverage --spec`` CTA.

    Resolves the feature's ``spec.md`` (either layout) to a repo-relative POSIX path; falls back to a
    ``<path/to/spec.md>`` placeholder when the run has no bound folder (a dry run) or the spec cannot
    be located, so the printed command always reads sensibly."""
    if feature_dir is not None:
        spec = workspace.spec_path(feature_dir)
        if spec is not None:
            try:
                return spec.relative_to(root).as_posix()
            except ValueError:
                return spec.as_posix()
    return "<path/to/spec.md>"


def _observe_cta_lines(
    st: style.Styler,
    *,
    root: Path,
    feature_dir: Optional[Path],
    run_branch: str,
) -> list[str]:
    """The Observe call-to-action block printed at run completion.

    States the settled current state — the run branch, Ship reached, every run-produced change
    committed (a clean working tree, guaranteed by the per-phase + engine-state commits) — then the
    next actions: measure production coverage of the spec, register the checks that watch it, and
    push/merge the run branch. Closes with the harness's iteration rule: a production lesson returns
    as a NEW ``3pwr run`` intent, never an ad-hoc patch."""
    ptr = ">" if st.ascii_only else "▶"
    branch = run_branch or "(this run’s branch)"
    spec_ref = _spec_ref_value(root, feature_dir)
    new_run = st.bold('3pwr run "<intent>"')
    return [
        f"  {st.dim(ptr + ' Observe — the post-run follow-on')}",
        f"    on branch {st.bold(branch)}: Ship reached, every run-produced change committed.",
        "    next:",
        f"      · measure production coverage of the spec: "
        f"{st.bold(f'3pwr observe coverage --spec {spec_ref}')}",
        f"      · register the checks that watch it in {st.bold('.3powers/config/observability.yaml')}",
        f"      · push / merge {st.bold(branch)} to ship it",
        f"    a production lesson returns as a NEW {new_run} — never an ad-hoc patch.",
    ]


def _native_runner(
    s: Settings,
    args: argparse.Namespace,
    start_index: int,
    *,
    ledger: Ledger,
    sk,
    spec_id: str,
    stream: bool,
    feature_dir: Optional[Path] = None,
    run_branch: str = "",
    git_prefs: Optional[gitflow.GitPrefs] = None,
    commit_relaxed: bool = False,
    revise: str = "",
    echo: Optional[TextSink] = None,
    on_progress: Optional[Callable[[orchestrate.Event], None]] = None,
    verdict_box: Optional[dict[str, Any]] = None,
    progress_reporter: Optional[progress.Reporter] = None,
    mode: str = "auto",
) -> NativeRunner:
    """Build the native executive runner: dispatch each stage to the role's agent, verify
    its declared artifact, retry/timeout-bound the dispatch,
    run the mandatory pre/post-stage git hooks — branch isolation + the agentically-messaged,
    3pwr-authored stage commit (superseding the earlier opt-out
    checkpoint) — write the oracle/implement records and run the deterministic completion gate per
    producing stage, and run the gate suite in-process at Verify."""
    intent = args.intent or ""
    wk = workkind.classify(intent)
    # The resolved --discovery/--no-discovery override (None = decide by work-kind); getattr
    # tolerates namespaces built by callers that never registered the flag.
    discovery_override: Optional[bool] = getattr(args, "discovery", None)
    tier = args.tier or wk.suggested_tier or s.default_tier()
    timeout = _dispatch_timeout(s, args)
    retries = _dispatch_retries(s, args)
    prefs = git_prefs or gitflow.GitPrefs()

    coder_agent = _resolve_coder_agent(s, args)
    oracle_agent = runpreflight.resolve_oracle_integration(s)
    coder_manifest = agents.load_agent(s, coder_agent)
    # Optional per-stage cheaper sub-agent models (roles.yaml `subagent_models`); an empty map
    # changes nothing. Surface a likely-typo model once here (advisory, never a gate) before the
    # walk, then thread the map into both role runners keyed by step.
    subagent_models = s.subagent_models()
    for warning in s.subagent_model_warnings():
        print(f"  ⚠ {warning}", file=sys.stderr)
    # One transcript sink per run, shared by both roles: every stage attempt's output is persisted
    # under .3powers/runs/<spec-id>/, credential-redacted.
    sink = transcripts.TranscriptSink(s.root, spec_id)
    raw_events = bool(getattr(args, "raw_events", False))
    # Opt-in, display-only echo of each stage's assembled prompt (flag > ui.yaml > off). The styler
    # is the run's own — enabled on a color TTY, disabled (plain, no escapes) off-TTY / NO_COLOR /
    # --json — so the echo degrades exactly like the rest of the human output.
    show_prompts = _resolve_show_prompts(s, args)
    prompt_styler = _styler(args) if show_prompts else None
    coder = _make_agent_runner(
        s,
        coder_manifest,
        model=str(s.role("coder").get("model") or ""),
        intent=intent,
        timeout=timeout,
        stream=stream,
        transcripts_sink=sink,
        echo=echo,
        subagent_models=subagent_models,
        raw_events=raw_events,
        show_prompts=show_prompts,
        prompt_styler=prompt_styler,
    )
    try:
        oracle_manifest = agents.load_agent(s, oracle_agent) if oracle_agent else coder_manifest
    except FileNotFoundError:
        oracle_manifest = coder_manifest
    oracle_runner = _make_agent_runner(
        s,
        oracle_manifest,
        model=str(s.role("oracle").get("model") or ""),
        intent=intent,
        timeout=timeout,
        stream=stream,
        transcripts_sink=sink,
        echo=echo,
        subagent_models=subagent_models,
        raw_events=raw_events,
        show_prompts=show_prompts,
        prompt_styler=prompt_styler,
    )

    # The prior accepted artifact's reference — injected into the next stage's prompt so each stage
    # knows the committed context boundary it continues from.
    prior_box: dict[str, str] = {"ref": ""}

    def dispatch(step: str, stage: str) -> runnermod.StageResult:
        # Discovery runs only when the work warrants it: feature/design kinds, or the explicit
        # --discovery/--no-discovery override. The skip is a short-circuit BEFORE the pre-stage
        # git hook, the dispatch, the artifact verify, the ledger recording, and the stage commit
        # — nothing is written, no run/stage entry is appended, and the prior-context handoff
        # (prior_box) stays untouched, so the walk proceeds straight to Specify.
        if step == "discovery" and not workkind.discovery_enabled(
            wk.kinds, override=discovery_override
        ):
            return runnermod.StageResult(
                step=step,
                stage=stage,
                ok=True,
                outcome="skipped",
                detail="discovery skipped (work-kind)",
            )
        # The mandatory PRE-STAGE git hook: every stage of a live run happens on the
        # run's dedicated branch — strayed mid-run (e.g. the user switched away), it switches back
        # before dispatching; a switch git refuses is a named failure, never forced. Once a run is
        # under way its branch legitimately exists, so this re-enters it (mode="resume") rather than
        # tripping the fresh guard.
        if run_branch:
            b_err = gitflow.ensure_run_branch(s.root, run_branch, prefs.base_branch, mode="resume")
            if b_err:
                return runnermod.StageResult(
                    step=step,
                    stage=stage,
                    ok=False,
                    outcome=gitflow.CLASS_BRANCH_FAILED,
                    detail=b_err,
                )
        # The oracle role (Phase A) runs under its own agent/model — a different family than the
        # coder's. Physical read-path isolation stays with `3pwr oracle dispatch`, which a
        # High-risk `advance` enforces; the run routes the oracle stage to its backend here.
        backend = oracle_runner if step == "oracle" else coder
        agent_name = oracle_agent if step == "oracle" else coder_agent
        contract = artifacts.contract_for(step)
        pre = runnermod.worktree_state(s.root)
        produced_box: dict[str, list[str]] = {}

        def verify() -> artifacts.ArtifactCheck:
            post = runnermod.worktree_state(s.root)
            produced = runnermod.produced_paths(pre, post)
            produced_box["paths"] = produced
            # A None contract verifies leniently, so this always runs.
            check = artifacts.verify(contract, produced)
            if not check.ok:
                # A completion-gate re-run may regenerate a committed artifact
                # byte-identical to HEAD — an empty diff. The stage still satisfies its contract
                # when every artifact its PRIOR run/stage entry recorded is still on disk; the
                # completion gate then re-asserts disk ∧ ledger. A fresh stage has no prior entry,
                # so nothing is weakened for a first run.
                prior = completion.recorded_stage_artifacts(ledger.entries(), spec_id).get(step)
                if prior and all((s.root / p).is_file() for p in prior):
                    return artifacts.ArtifactCheck(
                        ok=True, expected=check.expected, matched=list(prior), produced=produced
                    )
            return check

        # Assemble the stage's context — the approved spec text (post-approval stages) and the
        # prior stage's accepted artifact reference — plus the template variables carrying the
        # run's concrete destinations: the feature folder (the agent-authored markdown stages)
        # and the keyed oracle destination. Substituted into the instruction body, so the
        # template itself names where the artifact lands — no separate context line, and no
        # placeholder token ever reaches the agent.
        spec_path = _resolve_run_spec(s, args, feature_dir)
        spec_text = _dispatch_spec_text(s, step, spec_path)
        variables: dict[str, str] = {}
        if step in ("discovery", "specify", "clarify", "plan", "tasks", "oracle"):
            variables["FEATURE_FOLDER"] = _feature_folder_value(s, feature_dir)
        if step == "oracle":
            variables["ORACLE_DESTINATION"] = _oracle_destination_value(feature_dir)
        ctx_parts = [prior_box["ref"]]
        if revise:
            # The revise re-dispatch carries the human's gate feedback + the artifact under review
            # — assembled deterministically upstream.
            ctx_parts.append(revise)
        context = "\n".join(p for p in ctx_parts if p)

        phase_list = _implement_phases(s, spec_path) if step == "implement" else []
        if phase_list:
            # A phased tasks artifact: one fresh session per phase, parallel where the declared
            # scopes are disjoint; a phaseless artifact stays a single dispatch.
            result = _dispatch_phased(
                s,
                step,
                stage,
                backend=backend,
                agent_name=agent_name,
                retries=retries,
                spec_text=spec_text,
                context=context,
                phase_list=phase_list,
                verify_artifact=verify,
                ledger=ledger,
                sk=sk,
                spec_id=spec_id,
                variables=variables,
                run_branch=run_branch,
                commit_relaxed=commit_relaxed,
                prefs=prefs,
            )
        elif step == "advance":
            # The Ship advance runs its deterministic enforcement core IN-PROCESS: no agent
            # dispatch on the green path — the engine records the signed `stage_advance` entry
            # exactly as `3pwr advance` does. Only a REFUSAL dispatches an agent, with the
            # `advance.agent.md` remediation template carrying the named refusal reasons so the
            # agent can fix the blockers honestly, commit on the run branch, and re-run advance.
            check = trust.advance_check(s, spec_id=spec_id)
            if check.ok:
                try:
                    entry = ledger.append(
                        "stage_advance",
                        trust.advance_payload(stage, check),
                        sk,
                        spec_id=spec_id,
                    )
                    result = runnermod.StageResult(
                        step=step,
                        stage=stage,
                        ok=True,
                        outcome="ok",
                        artifact=f"advanced (ledger seq={entry['seq']})",
                    )
                except FileNotFoundError as exc:
                    # No signer resolvable — a setup failure, not a gate-red, on the same
                    # dispatch-failure class the runner uses for a stage that could not run.
                    result = runnermod.StageResult(
                        step=step,
                        stage=stage,
                        ok=False,
                        outcome="dispatch_failed",
                        detail=str(exc),
                    )
            else:
                result = runnermod.run_stage(
                    step,
                    stage,
                    attempt=lambda: backend.dispatch(
                        step,
                        stage,
                        spec_text=spec_text,
                        context=context,
                        variables={"REFUSAL_REASONS": "\n".join(check.reasons)},
                    ),
                    retries=retries,
                    verify_artifact=verify,
                    agent=agent_name,
                    model=str(backend.model),
                )
        else:
            result = runnermod.run_stage(
                step,
                stage,
                attempt=lambda: backend.dispatch(
                    step, stage, spec_text=spec_text, context=context, variables=variables
                ),
                retries=retries,
                verify_artifact=verify,
                agent=agent_name,
                model=str(backend.model),
            )
        if result.ok:
            if step in completion.RECORD_STEPS and feature_dir is not None:
                # The oracle/implement stages leave a markdown *record* in the feature folder. For a
                # phased implement this runs on the collecting thread AFTER all phases completed, one
                # record in deterministic order. The implement record is the agent-authored
                # changelog.md — a simple, non-blocking Keep-a-Changelog release note for the run
                # (informational, never a gate); the top-level CHANGELOG.md is hand-maintained and
                # untouched.
                if step == "implement":
                    # The agent-authored changelog prose: the phased collector's combined per-phase
                    # reports, or the single session's report from its transcript.
                    report = result.report or _implement_report(s, result.transcript)
                else:
                    report = ""
                rel = completion.write_record(
                    s.root,
                    feature_dir,
                    step,
                    spec_id=spec_id,
                    work_kinds=wk.kinds,
                    report=report,
                    on_finding=lambda msg: print(f"  ⚠ {msg}", file=sys.stderr),
                )
                if rel not in result.artifact_paths:
                    result.artifact_paths.append(rel)
                if rel not in produced_box.get("paths", []):
                    produced_box.setdefault("paths", []).append(rel)
            ref = _prior_artifact_ref(s, step, result)
            if ref:
                prior_box["ref"] = ref
            if step == "tasks":
                # Report each phase's deterministic context estimate; warn (never block) on an
                # over-budget phase.
                _report_phase_estimates(s, result, spec_path, coder_model=str(coder.model))
            # Record the completion itself — lightweight, additive: resume progress lives in the
            # signed ledger, not only in checkpoint
            # commits, so a failed `--no-auto-commit` run still resumes from the next stage.
            stage_payload: dict[str, Any] = {"kind": "stage", "step": step, "stage": stage}
            if result.artifact_paths:
                stage_payload["artifacts"] = result.artifact_paths
            if result.tokens is not None:
                # Additive advisory field (never in the verdict): the stage's agent-reported
                # token usage; absent when the backend does not report usage.
                stage_payload["tokens"] = result.tokens
            if result.cost is not None:
                # Additive advisory field, in step with tokens: the stage's agent-reported run
                # cost (USD); absent when the backend reports no cost.
                stage_payload["cost"] = result.cost
            ledger.append("run", stage_payload, sk, spec_id=spec_id)
            if progress_reporter is not None:
                # The stage-complete trigger, BEFORE the post-stage commit below,
                # so the committed progress.md already shows this stage ✓ done.
                if result.phases:
                    _progress_safe(
                        lambda: progress_reporter.phase_tokens(
                            {
                                int(ph["phase"]): int(ph["tokens"])
                                for ph in result.phases
                                if ph.get("tokens") is not None
                            }
                        )
                    )
                    _progress_safe(
                        lambda: progress_reporter.phase_costs(
                            {
                                int(ph["phase"]): float(ph["cost"])
                                for ph in result.phases
                                if ph.get("cost") is not None
                            }
                        )
                    )
                _progress_safe(
                    lambda: progress_reporter.stage_completed(
                        step, stage, tokens=result.tokens, cost=result.cost
                    )
                )
        if result.ok and run_branch and not commit_relaxed:
            # The mandatory POST-STAGE git hook (superseding the earlier
            # opt-out checkpoint): the stage's produced paths land as exactly ONE commit on the run
            # branch — never a blanket `add -A` — with an agent-written message carrying the stage
            # and spec id (deterministic fallback) and the 3pwr author applied
            # per-commit. A stage that produced nothing forces no empty
            # commit; paths a human already committed by hand are a no-op keeping the human's own
            # author. After it, no run-produced change is left uncommitted.
            #
            # For a PHASED implement the produced source was already committed one-commit-per-phase
            # from the collecting thread inside `_dispatch_phased`; those paths re-stage to an empty
            # index here (a no-op), so this hook does NOT double-commit them. It carries only what is
            # still dirty — the changelog record, the ledger `phases`+`stage` entries, and
            # `progress.md` — making this the single TRAILING implement record commit.
            produced = produced_box.get("paths", [])
            if produced and s.ledger_path.is_file():
                # The engine's ledger rides every producing stage commit: the
                # signed entries that recorded this stage land atomically with its artifact, so
                # the trust state at each stage boundary is recoverable from git history alone.
                # A stage that produced nothing still forces no commit.
                ledger_rel = str(s.ledger_path.relative_to(s.root))
                if ledger_rel not in produced:
                    produced = [*produced, ledger_rel]
            if produced and feature_dir is not None:
                # The run's progress file rides the same stage commit: committed
                # alongside the stage artifact and the ledger whenever it exists — never forcing a
                # commit for a stage that produced nothing, never duplicating a listed path.
                prog = feature_dir / progress.FILENAME
                try:
                    prog_rel = str(prog.relative_to(s.root))
                except ValueError:
                    prog_rel = ""
                if prog_rel and prog.is_file() and prog_rel not in produced:
                    produced = [*produced, prog_rel]
            desc = gitflow.agent_commit_description(s.root, result.transcript)
            commit = gitflow.commit_stage(
                s.root,
                produced,
                message=gitflow.stage_commit_message(spec_id, step, desc),
                author_name=prefs.author_name,
                author_email=prefs.author_email,
            )
            if commit.error:
                # Clean-stop would be violated — a named, recorded failure on the
                # setup/dispatch path, never silently carried on.
                return runnermod.StageResult(
                    step=step,
                    stage=stage,
                    ok=False,
                    agent=agent_name,
                    model=str(backend.model),
                    attempts=result.attempts,
                    duration_s=result.duration_s,
                    outcome=gitflow.CLASS_COMMIT_FAILED,
                    detail=f"stage '{step}' could not be committed — {commit.error}",
                    transcript=result.transcript,
                )
            if commit.sha:
                payload: dict[str, Any] = {
                    "kind": "checkpoint",
                    "step": step,
                    "stage": stage,
                    "commit": commit.sha,
                }
                if result.artifact_paths:
                    # The accepted artifact's path rides in the signed stage entry, so the committed
                    # artifact trail is reconstructable from the ledger alone.
                    payload["artifacts"] = result.artifact_paths
                if result.tokens is not None:
                    # The same additive advisory token field as the stage entry — never a
                    # verdict input.
                    payload["tokens"] = result.tokens
                if result.cost is not None:
                    # The same additive advisory cost field as the stage entry — never a
                    # verdict input.
                    payload["cost"] = result.cost
                ledger.append("run", payload, sk, spec_id=spec_id)
        if result.ok and feature_dir is not None and completion.is_producing(step):
            # The deterministic completion gate: the stage's declared markdown must
            # exist on disk AND be recorded in a matching signed ledger entry before the run may
            # advance — else the run blocks with a named, classified failure and the stage must be
            # re-run. Pure given (disk state, ledger entries, step); one ledger
            # read serves the check.
            recorded = completion.recorded_stage_artifacts(ledger.entries(), spec_id)
            chk = completion.check_step(s.root, feature_dir, step, recorded)
            if not chk.ok:
                return runnermod.StageResult(
                    step=step,
                    stage=stage,
                    ok=False,
                    agent=agent_name,
                    model=str(backend.model),
                    attempts=result.attempts,
                    duration_s=result.duration_s,
                    outcome=chk.failure_class,
                    detail=chk.message,
                    transcript=result.transcript,
                )
        if result.ok and step == "advance":
            # The advance produces no artifact, so the post-stage hook above committed nothing;
            # its signed `stage_advance` entry, the run/stage entry, and `progress.md` are
            # engine-owned trust state — commit them here so the finished run leaves a clean tree.
            # A no-op when the run does not commit (dry-run, --commit-relaxed).
            _commit_engine_state(
                s,
                spec_id=spec_id,
                step="advance",
                run_branch=run_branch,
                commit_relaxed=commit_relaxed,
                prefs=prefs,
            )
        return result

    def run_verdict(stage: str) -> str:
        # The in-run verdict is recorded exactly as a standalone `3pwr gate run` records it:
        # a red or green at Verify is never invisible to the trust spine. The
        # verdict dict lands in ``verdict_box`` so a red one renders its failed gates inline.
        box = verdict_box if verdict_box is not None else {}
        outcome = _native_verdict(
            s,
            args,
            tier,
            wk.kinds,
            ledger=ledger,
            sk=sk,
            feature_dir=feature_dir,
            out=box,
        )
        if outcome == "fail" and mode == "auto":
            # Bounded, code-only auto-remediation, tried FIRST — before the deviation-proceed check
            # below and entirely independent of it: it only hands the red gates back to the coder and
            # re-runs the suite (recording an honest signed verdict each pass), never a deviation, a
            # config edit, or a verdict mutation. A signed deviation stays the human's last resort for
            # a residual red. `gate_gaming` stays the backstop. Only entered when the verdict names
            # failed gates to hand back and the loop is enabled in auto mode.
            redv = box.get("verdict") or {}
            if s.auto_fix().enabled and autofix.failed_gate_names(redv):
                report = (
                    (lambda m: None)
                    if getattr(args, "json", False)
                    else (lambda m: print(f"  ↳ {m}"))
                )
                fix = _auto_fix_loop(
                    s,
                    args,
                    tier=tier,
                    kinds=wk.kinds,
                    feature_dir=feature_dir,
                    ledger=ledger,
                    sk=sk,
                    coder=coder,
                    retries=retries,
                    initial_verdict=redv,
                    out=box,
                    report=report,
                )
                if fix.fixed:
                    outcome = "pass"
                    # The coder's remediation lands as the verify stage's commit on the run branch,
                    # so no run-produced change is left uncommitted. Best-effort — a commit problem
                    # warns, never fails the now-green run.
                    code_fixed = sorted({p for a in fix.attempts for p in a.changed_files})
                    if code_fixed and run_branch and not commit_relaxed:
                        paths = list(code_fixed)
                        if s.ledger_path.is_file():
                            ledger_rel = str(s.ledger_path.relative_to(s.root))
                            if ledger_rel not in paths:
                                paths.append(ledger_rel)
                        commit = gitflow.commit_stage(
                            s.root,
                            paths,
                            message=gitflow.stage_commit_message(
                                spec_id, "verify", "apply auto-fix code remediation"
                            ),
                            author_name=prefs.author_name,
                            author_email=prefs.author_email,
                        )
                        if commit.error:
                            print(
                                f"warning: auto-fix remediation not committed — {commit.error}",
                                file=sys.stderr,
                            )
                else:
                    # Stash the given-up loop so the terminal gate-red branch can print the
                    # step-by-step human remediation summary after the live bar has closed.
                    box["auto_fix"] = fix
        if outcome == "fail":
            # The recorded verdict stays honestly red; only the PROCEED decision consults the
            # active signed deviations — the same shared coverage helper `advance` uses, so a
            # deviation recorded mid-run is honoured here exactly as at a standalone advance.
            notices = _deviation_proceed_notices(
                box.get("verdict") or {}, ledger.entries(), spec_id
            )
            if notices is not None:
                if not getattr(args, "json", False):
                    for line in notices:
                        print(f"  ↳ {line}")
                outcome = "pass"
        # An --auto-fix run's fixed paths join the run's produced set: they land
        # as the verify stage's commit on the run branch, so no run-produced change is left
        # uncommitted. The signed ledger rides along, as on every stage commit.
        fixed = auto_fixed_paths(box.get("verdict") or {})
        if fixed and run_branch and not commit_relaxed:
            paths = list(fixed)
            if s.ledger_path.is_file():
                ledger_rel = str(s.ledger_path.relative_to(s.root))
                if ledger_rel not in paths:
                    paths.append(ledger_rel)
            commit = gitflow.commit_stage(
                s.root,
                paths,
                message=gitflow.stage_commit_message(
                    spec_id, "verify", "apply configured auto-fixes"
                ),
                author_name=prefs.author_name,
                author_email=prefs.author_email,
            )
            if commit.error:
                print(f"warning: auto-fixed paths not committed — {commit.error}", file=sys.stderr)
        # The verdict entry (and any auto-fix verdict/remediation entries above) is engine-owned
        # trust state: commit it so the verify — and, on the review-verify pass, the review — verdict
        # leaves a clean working tree. A no-op when the verdict produced no code commit above yet
        # still appended a ledger entry, which is the common green-verify case.
        _commit_engine_state(
            s,
            spec_id=spec_id,
            step="verify",
            run_branch=run_branch,
            commit_relaxed=commit_relaxed,
            prefs=prefs,
        )
        return outcome

    return NativeRunner(
        dispatch=dispatch, run_verdict=run_verdict, start_index=start_index, on_progress=on_progress
    )


def _run_make_runner(
    s: Settings,
    args: argparse.Namespace,
    mode: str,
    *,
    start_index: int,
    ledger: Ledger,
    sk,
    spec_id: str,
    stream: bool,
    feature_dir: Optional[Path] = None,
    run_branch: str = "",
    git_prefs: Optional[gitflow.GitPrefs] = None,
    commit_relaxed: bool = False,
    revise: str = "",
    echo: Optional[TextSink] = None,
    on_progress: Optional[Callable[[orchestrate.Event], None]] = None,
    verdict_box: Optional[dict[str, Any]] = None,
    progress_reporter: Optional[progress.Reporter] = None,
):
    kind = _resolve_runner_kind(args)
    if kind == "sim":
        return orchestrate.SimulatedRunner(
            verdict=("fail" if args.simulate_fail else "pass"), start_index=start_index
        )
    return _native_runner(
        s,
        args,
        start_index,
        ledger=ledger,
        sk=sk,
        spec_id=spec_id,
        stream=stream,
        feature_dir=feature_dir,
        run_branch=run_branch,
        git_prefs=git_prefs,
        commit_relaxed=commit_relaxed,
        revise=revise,
        echo=echo,
        on_progress=on_progress,
        verdict_box=verdict_box,
        progress_reporter=progress_reporter,
        mode=mode,
    )


def _run_revise(
    s: Settings,
    args: argparse.Namespace,
    ledger: Ledger,
    sk,
    spec_id: str,
    gate: str,
    feedback: str,
    *,
    feature_dir: Optional[Path],
    run_branch: str,
    git_prefs: Optional[gitflow.GitPrefs],
    commit_relaxed: bool,
    rst: style.Styler,
) -> int:
    """Revise-with-message at a paused human gate.

    Re-dispatches the stage that owns the artifact under review — with the ORIGINAL intent (read back
    from the signed ``start`` entry), the current artifact, and the human's feedback — records the
    revision (feedback + outcome) via the existing run-entry append path, and returns the run to the
    SAME gate for review: the pause is re-recorded so approval still requires the human sign-off. The
    revise dispatch runs under the very same retry/artifact/git/completion policy as a first run."""
    step, stage = steering.revise_target(gate)
    if not step:
        print(f"error: gate '{gate}' has no revisable stage", file=sys.stderr)
        return EXIT_USAGE
    gate_stage = next(
        (stg for sid, _kind, stg in orchestrate.LIFECYCLE_STEPS if sid == gate), stage
    )
    artifact = steering.gate_artifact(s.root, feature_dir, gate)
    if _resolve_runner_kind(args) == "sim":
        # --dry-run / the simulator dispatch nothing — the revise is
        # recorded and the gate re-presented, so the whole loop stays visible offline.
        result = runnermod.StageResult(
            step=step, stage=stage, ok=True, outcome="ok", detail="simulated (dry-run)"
        )
    else:
        args.intent = _run_intent_from_ledger(ledger.entries(), spec_id)
        runner = _native_runner(
            s,
            args,
            0,
            ledger=ledger,
            sk=sk,
            spec_id=spec_id,
            stream=_run_stream(args),
            feature_dir=feature_dir,
            run_branch=run_branch,
            git_prefs=git_prefs,
            commit_relaxed=commit_relaxed,
            revise=steering.revise_context(
                gate, artifact, feedback, templates_dir=s.stage_templates_dir
            ),
        )
        try:
            result = runner.dispatch_once(step, stage)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_SETUP
    # The revision is auditable from the ledger alone: feedback + outcome ride the
    # EXISTING run-entry append path — no new entry type, no signing change, `3pwr verify` unchanged.
    ledger.append(
        "run",
        {
            "kind": "revise",
            "gate": gate,
            "step": step,
            "feedback": feedback,
            "ok": result.ok,
            "outcome": result.outcome or ("ok" if result.ok else "failed"),
            "detail": (result.detail or "")[:400],
        },
        sk,
        spec_id=spec_id,
    )
    # The run returns to the SAME gate: re-record the pause so the ledger-derived
    # state stays paused-at-gate and a later plain --resume still records the human sign-off.
    ledger.append("run", {"kind": "gate", "gate": gate, "stage": gate_stage}, sk, spec_id=spec_id)
    if not result.ok:
        detail = f" — {result.detail}" if result.detail else ""
        _notify_event(
            s,
            args,
            notify.EVENT_FAILURE,
            notify.failure_message(spec_id, "revise failed", gate_stage),
            spec_id,
        )
        human = (
            f"{orchestrate.render_tracker(gate_stage, rst)}\n"
            f"  {rst.err('✗')} revise failed at '{step}'{detail}\n"
            f"  the artifact under review is unchanged; the run remains paused at '{gate}'."
        )
        _print(
            {
                "status": "revise_failed",
                "gate": gate,
                "step": step,
                "detail": result.detail,
                "spec_id": spec_id,
                "stages": [result.as_dict()],
            },
            args.json,
            human,
        )
        return EXIT_SETUP
    _notify_event(
        s,
        args,
        notify.EVENT_GATE,
        "revised — "
        + notify.gate_message(
            spec_id,
            gate,
            gate_stage,
            orchestrate.MANDATORY_GATES.get(gate, ""),
            artifact,
            steering.gate_actions(spec_id),
        ),
        spec_id,
    )
    action_rows = "\n".join(_gate_pause_rows(rst, spec_id, artifact))
    human = (
        f"{orchestrate.render_tracker(gate_stage, rst)}\n"
        f"  {rst.ok('✓')} revised '{step}' with your feedback — back at "
        f"{rst.warn('HUMAN GATE')} '{gate}' for review:\n{action_rows}"
    )
    _print(
        {
            "status": "paused_at_gate",
            "gate": gate,
            "gate_fr": orchestrate.MANDATORY_GATES.get(gate, ""),
            "stage": gate_stage,
            "spec_id": spec_id,
            "revised": step,
            "stages": [result.as_dict()],
        },
        args.json,
        human,
    )
    return EXIT_PAUSED


def _gate_decision(gate: str, fr: str) -> str:
    """The three-action interactive choice at a paused human gate: approve / revise /
    reject — the same vocabulary the non-interactive pause prints as commands.

    Empty input and EOF mean reject — the conservative default: nothing advances without an explicit
    approval. An unrecognized answer re-prompts."""
    aliases = {
        "a": "approve",
        "approve": "approve",
        "y": "approve",
        "yes": "approve",
        "r": "revise",
        "revise": "revise",
        "x": "reject",
        "reject": "reject",
        "n": "reject",
        "no": "reject",
    }
    while True:
        try:
            raw = (
                input(f"  gate '{gate}'{fr} — [a]pprove / [r]evise / reject [x]? ").strip().lower()
            )
        except EOFError:
            return "reject"
        if not raw:
            return "reject"
        decision = aliases.get(raw)
        if decision:
            return decision
        print("  answer a (approve), r (revise), or x (reject)")


def _prompt_line(prompt: str) -> str:
    """One line of interactive input; EOF reads as empty (never raises at a gate pause)."""
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def cmd_run(args: argparse.Namespace) -> int:
    """Drive the whole lifecycle loop (§6). ``auto`` stops only at the two mandatory human
    gates (spec approval, sign-off); ``commit`` stops at every gate. By default the
    **native** executive dispatches each stage to a headless agent directly and runs the
    gate suite in-process at Verify; ``--runner sim`` uses the offline simulator (also
    forced by ``--dry-run``). The engine makes no model call itself and never enters the
    deterministic verdict."""
    s = _settings(args.root)
    ledger = Ledger(s.ledger_path)
    mode = args.mode or s.default_mode()  # --mode wins; else the `3pwr init` default
    spec_id = args.spec_id or "RUN"
    rst = _styler(args)  # human-output styler (color per --json/--yes/NO_COLOR/ui.yaml)

    if args.status:
        st = lifecycle.derive(ledger.entries()).get(spec_id)
        if st is None:
            _print(
                {"spec_id": spec_id, "found": False},
                args.json,
                _compose(
                    args,
                    rst,
                    title="3pwr run · status",
                    subject=spec_id,
                    rows=[rst.status_row("info", f"no run recorded for {spec_id}")],
                ),
            )
            return EXIT_OK
        rows = [f"  {orchestrate.render_tracker(st.stage, rst)}"]
        if st.pending_gate:
            rows.append(
                rst.status_row(
                    "warn",
                    f"paused at '{st.pending_gate}'",
                    f"`3pwr run --resume --spec-id {spec_id} --approver <you>`",
                )
            )
        if st.failed:
            # A recorded, unresolved run failure — distinct from paused and in-progress.
            rows.append(
                rst.status_row(
                    "fail",
                    f"failed at {st.failed_stage or '?'} ({st.failed_class}) at {st.failed_at or '?'}",
                    f"`3pwr run --resume --spec-id {spec_id}`",
                )
            )
            if st.failed_transcript:
                rows.append("      " + rst.dim(f"agent transcript: {st.failed_transcript}"))
        # The run's git lifecycle state: its dedicated branch and the per-stage
        # committed indication — a deterministic function of the ledger and the local branches,
        # no model and no network.
        entries_st = ledger.entries()
        run_branch_st = gitflow.branch_from_ledger(entries_st, spec_id)
        committed_st = gitflow.committed_steps(entries_st, spec_id)
        if run_branch_st:
            on_it = gitflow.current_branch(s.root) == run_branch_st
            rows.append(
                rst.status_row(
                    "info",
                    f"run branch {run_branch_st}" + (" (checked out)" if on_it else ""),
                    f"committed stages: {', '.join(committed_st) or '—'}",
                )
            )
        _print(
            {
                "spec_id": spec_id,
                "stage": st.stage,
                "pending_gate": st.pending_gate,
                "failed": st.failed,
                "failed_stage": st.failed_stage,
                "failed_class": st.failed_class,
                "failed_at": st.failed_at,
                "failed_transcript": st.failed_transcript,
                "branch": run_branch_st,
                "committed_steps": committed_st,
            },
            args.json,
            _compose(args, rst, title="3pwr run · status", subject=spec_id, rows=rows),
        )
        return EXIT_OK

    # Advisory per-working-tree run lock (`.3powers/run.lock`): a second concurrent `3pwr run` in
    # the SAME checkout fails fast; separate clones / `git worktree` checkouts each hold their own
    # and never contend. A stale lock (a crashed run — a dead pid, or an mtime past a generous TTL)
    # self-heals; a lock-write failure degrades to a warning and never wedges the run. Held across
    # BOTH the fresh and resume paths — before the clean-start guard and any side effect — and
    # released in the `finally`. Filesystem-only: never a gate, a verdict, or a ledger entry. The
    # `--status` query above never takes it, so status stays available while a run is live.
    run_lock_path = s.root / gitflow.ENGINE_STATE_PREFIX / runlock.LOCK_FILENAME
    try:
        run_lock = runlock.acquire(run_lock_path)
    except runlock.RunLockHeld as exc:
        print(f"cannot start `3pwr run` — {exc}", file=sys.stderr)
        return EXIT_SETUP
    if run_lock.warning and not args.json:
        print(run_lock.warning, file=sys.stderr)
    try:
        return _cmd_run_locked(args, s, ledger, mode, spec_id, rst)
    finally:
        runlock.release(run_lock)


def _cmd_run_locked(
    args: argparse.Namespace,
    s: Settings,
    ledger: Ledger,
    mode: str,
    spec_id: str,
    rst: style.Styler,
) -> int:
    """Drive the run's lifecycle under the advisory run lock — every path with a side effect.

    Split out of :func:`cmd_run` so the per-working-tree run lock is taken once at the top and
    released in the caller's ``finally`` across BOTH the fresh and resume paths, while a lock-free
    ``--status`` query stays available even while a run is live. The pre-computed run context
    (settings, ledger, mode, resolved spec id, output styler) is threaded in unchanged.
    """
    # File-based intent: resolve --file (+ the optional inline instruction)
    # BEFORE any side effect — a bad file fails fast with the setup exit code and no ledger entry
    # is written; every downstream consumer sees ONLY the resolved intent.
    if getattr(args, "file", None):
        if args.resume:
            print(
                "error: --file feeds a fresh run's intent — to revise at a paused gate use "
                "--revise/--revise-file",
                file=sys.stderr,
            )
            return EXIT_USAGE
        resolved_intent, ierr = steering.resolve_intent(args.file, args.intent)
        if ierr:
            print(f"error: {ierr}", file=sys.stderr)
            return EXIT_SETUP
        args.intent = resolved_intent

    # Resolve the coder + oracle agents from config/flags — provider-agnostic.
    coder_int = _resolve_coder_agent(s, args)
    oracle_int = runpreflight.resolve_oracle_integration(s)
    coder_model = str(s.role("coder").get("model") or "")
    oracle_model = str(s.role("oracle").get("model") or "")

    # Preflight — a live run must not dispatch a stage until its prerequisites hold:
    # a resolvable signer, a headless coder agent, and a different-family oracle agent — the SAME
    # shared check set init's readiness and `3pwr ready` report, so they cannot
    # disagree. --dry-run needs none of this: it dispatches nothing and is always available offline.
    if not args.dry_run and not args.status:
        prqs = runpreflight.check_auto(
            s,
            coder_agent=coder_int,
            oracle_agent=oracle_int,
            entries=ledger.entries(),
            spec_id=spec_id,
        )
        missing = runpreflight.unmet(prqs)
        if missing:
            # Fail fast, BEFORE any dispatch, with a named prerequisite + fix and the offline
            # alternatives — never "gates red", never the incident path.
            # Exits with the setup/dispatch code, distinct from usage and gates-red.
            obj = {
                "status": "preflight_failed",
                "spec_id": spec_id,
                "missing": [{"prerequisite": p.name, "fix": p.fix} for p in missing],
                "alternatives": list(runpreflight.OFFLINE_ALTERNATIVES),
            }
            if args.json:
                print(json.dumps(obj, indent=2))
            else:
                est = _styler(args, sys.stderr)
                lines = [
                    est.err("✗ cannot start `3pwr run` — unmet prerequisites")
                    + " (no stage was dispatched):"
                ]
                for p in missing:
                    lines.append(f"  {est.mark('fail')} {est.bold(p.name)}: {p.fix}")
                lines.append("  always available offline:")
                for alt in runpreflight.OFFLINE_ALTERNATIVES:
                    lines.append(f"    • {alt}")
                print("\n".join(lines), file=sys.stderr)
            return EXIT_SETUP

    # The signer itself (a live run just verified it in preflight; --dry-run still needs one to
    # append its ledger records).
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_SETUP

    interactive = (not args.json) and (not args.no_input) and sys.stdin.isatty()
    stream = _run_stream(args)  # stream agent output live on a TTY
    tracker = orchestrate.Tracker(sys.stdout, mode, st=rst, subject=spec_id)

    # The git discipline: applied to every LIVE native run — mandatory, with the recorded
    # signed deviation as the only relaxation. --dry-run / the simulator dispatch
    # nothing and write nothing, so the git hooks are a no-op there.
    git_on = _resolve_runner_kind(args) == "native"
    git_prefs = gitflow.load_prefs(s.git_config_path)
    if git_on and git_prefs.malformed and not args.json:
        print(
            "warning: .3powers/config/git.yaml is malformed — using the default git preferences",
            file=sys.stderr,
        )
    covered_guards = deviations.covered_gates(
        deviations.active_deviations(ledger.entries()), spec_id
    )
    clean_start_relaxed = deviations.GIT_CLEAN_START in covered_guards
    commit_relaxed = deviations.GIT_STAGE_COMMIT in covered_guards
    if git_on and (getattr(args, "no_auto_commit", False) or not s.auto_commit()):
        # The plain opt-out is SUPERSEDED: the stage commit is mandatory; the only
        # relaxation is the signed `git_stage_commit` deviation — warned, never silent.
        if not commit_relaxed and not args.json:
            print(
                "warning: --no-auto-commit / defaults.auto_commit is superseded — "
                "the per-stage commit is mandatory; relax it on the record with "
                '`3pwr deviation --gate git_stage_commit --approver <you> --note "<why>"`',
                file=sys.stderr,
            )
    run_branch = ""
    # The Verify stage's full verdict dict lands here (filled by _native_verdict), so a gate-red
    # event can render each failed gate inline with the run's resolved identity.
    verdict_box: dict[str, Any] = {}
    # The run's progress-file reporter — bound once the live run's feature folder
    # is resolved below; absent (a dry-run / simulated / folder-less run), no file is written.
    progress_box: dict[str, progress.Reporter] = {}

    def on_event(ev: orchestrate.Event) -> None:
        if ev.kind == "failed" and (ev.step == "gate_red" or ev.detail == "fail"):
            # Enrich the gate-red event with the failed verdict + the resolved spec id at the one
            # choke point every runner path flows through.
            if verdict_box.get("verdict"):
                ev.data.setdefault("verdict", verdict_box["verdict"])
            ev.data.setdefault("spec_id", spec_id)
        rep = progress_box.get("reporter")
        if rep is not None:
            # The progress file's lifecycle triggers, at the same choke point:
            # stage start, gate verdict pass/fail, human-gate pause, run failure, completion. The
            # stage-complete trigger fires inside the runner's dispatch, before the stage commit.
            if ev.kind == "step":
                _progress_safe(lambda: rep.stage_started(ev.step, ev.stage))
            elif ev.kind == "verdict":
                failed_names = progress.failed_gate_names(verdict_box.get("verdict") or {})
                _progress_safe(lambda: rep.verdict(ev.detail, failed_names))
            elif ev.kind == "gate-stop":
                _progress_safe(lambda: rep.paused(ev.step, ev.stage))
            elif ev.kind == "failed":
                _progress_safe(lambda: rep.failed(ev.step, ev.stage, ev.detail))
            elif ev.kind == "done":
                _progress_safe(lambda: rep.completed())
        if not args.json:
            tracker.on_event(ev)

    def _record_dispatch(start_index: int) -> None:
        """Record one signed executive-dispatch provenance entry per stage in the next live
        segment; the oracle stage carries the oracle integration/model. No-op for --dry-run
        (it dispatches nothing) so the offline simulation records nothing. Keyed on the actual
        start index, so a resume that skipped committed checkpoints records only the stages it will
        dispatch."""
        if args.dry_run:
            return
        for step, _stage in orchestrate.segment_actions_from(start_index):
            if step == "discovery" and not workkind.discovery_enabled(
                workkind.classify(args.intent or "").kinds,
                override=getattr(args, "discovery", None),
            ):
                # A discovery the dispatch closure will short-circuit is never announced as a
                # dispatch: no provenance entry for a stage that will not run.
                continue
            is_oracle = step == "oracle"
            ledger.append(
                "run",
                runpreflight.provenance_payload(
                    step,
                    oracle_int if is_oracle else coder_int,
                    oracle_model if is_oracle else coder_model,
                ),
                sk,
                spec_id=spec_id,
            )

    def _make_runner(start_index: int):
        return _cli._run_make_runner(
            s,
            args,
            mode,
            start_index=start_index,
            ledger=ledger,
            sk=sk,
            spec_id=spec_id,
            stream=stream,
            feature_dir=feature_dir,
            run_branch=run_branch,
            git_prefs=git_prefs,
            commit_relaxed=commit_relaxed,
            # The streamed agent conversation prints ABOVE the live bar, into ordinary scrollback;
            # with no bar (off-TTY/degraded) the echo stays the process's stdout.
            echo=(tracker.echo_sink() if (stream and tracker.live) else None),
            # Live event delivery: the bar learns a stage is running the moment its
            # dispatch starts, not one whole segment later; on_event self-guards under --json.
            on_progress=on_event,
            verdict_box=verdict_box,
            progress_reporter=progress_box.get("reporter"),
        )

    def _stages() -> list[dict]:
        """The per-stage machine-readable results of the dispatched stages, for --json."""
        return [sr.as_dict() for sr in getattr(runner, "stage_results", [])]

    # The run's bound feature folder — resolved per branch below.
    feature_dir: Optional[Path] = None

    if args.resume:
        revising = bool(
            getattr(args, "revise", None) is not None or getattr(args, "revise_file", None)
        )
        pending = _run_pending_gate(ledger, spec_id)
        completed = orchestrate.last_completed_step(ledger.entries(), spec_id)
        feedback = ""
        if revising:
            # The third gate action: a revise outside a paused gate, or with
            # empty feedback, is an actionable error leaving the artifact and gate state unchanged.
            if not pending:
                st_now = lifecycle.derive(ledger.entries()).get(spec_id)
                where = f"stage {st_now.stage}" if st_now else "no recorded run"
                print(
                    f"error: nothing to revise — {spec_id} is not paused at a human gate "
                    f"(current state: {where})",
                    file=sys.stderr,
                )
                return EXIT_USAGE
            feedback, ferr = steering.resolve_feedback(
                getattr(args, "revise_file", None), getattr(args, "revise", None)
            )
            if ferr:
                print(f"error: {ferr}", file=sys.stderr)
                return EXIT_USAGE
        if not pending and not completed:
            # No recorded progress at all — say so honestly and name the fresh start.
            print(
                f"nothing to resume for {spec_id} — no recorded progress; start fresh: "
                f'3pwr run "<intent>" --spec-id {spec_id}',
                file=sys.stderr,
            )
            return EXIT_USAGE
        if pending and not revising:
            # A human gate was awaiting approval — record the sign-off before continuing.
            _run_signoff(s, ledger, sk, spec_id, pending, args.approver, args.note)
        # A resume resolves the EXISTING feature folder recorded for the run — never allocating a new
        # one; a run recorded before folder binding falls back to the resolvable spec's folder.
        entries_now = ledger.entries()  # one read serves resume + the completion checks
        feature_dir = _run_feature_dir_from_ledger(s, entries_now, spec_id)
        if feature_dir is None:
            legacy_spec = _resolve_run_spec(s, args)
            feature_dir = workspace.feature_dir_of(legacy_spec) if legacy_spec else None
        if git_on and feature_dir is not None:
            # Rebind the run's progress file to the recorded workspace: the
            # resumed segment's triggers keep updating specs-src/<NNN>-<slug>/progress.md.
            progress_box["reporter"] = progress.Reporter(
                feature_dir,
                spec_id=spec_id,
                tier=args.tier
                or workkind.classify(args.intent or "").suggested_tier
                or s.default_tier(),
            )
        if git_on:
            # The pre-stage git hook on resume: recover the run's branch from
            # the signed ledger alone (a run recorded before branch binding derives the same
            # deterministic name from its workspace identity), refuse a dirty start whose changes
            # the run did not produce, and
            # re-enter the EXISTING branch — never a new one, never a new run number.
            run_branch = gitflow.branch_from_ledger(entries_now, spec_id)
            if not run_branch:
                identity = (
                    feature_dir.name if feature_dir is not None else workspace.slugify(spec_id)
                )
                run_branch = gitflow.run_branch_name(git_prefs.branch_prefix, identity)
            if not clean_start_relaxed:
                prefix = ""
                if feature_dir is not None:
                    try:
                        prefix = feature_dir.relative_to(s.root).as_posix() + "/"
                    except ValueError:
                        prefix = ""
                unrelated = gitflow.unrelated_changes(
                    gitflow.uncommitted(s.root),
                    gitflow.recorded_run_paths(entries_now, spec_id),
                    prefix,
                )
                if unrelated:
                    print(gitflow.clean_start_refusal(unrelated), file=sys.stderr)
                    return EXIT_SETUP
            # Resume re-enters the EXISTING ledger-recorded branch — never a new one.
            b_err = gitflow.ensure_run_branch(
                s.root, run_branch, git_prefs.base_branch, mode="resume"
            )
            if b_err:
                print(b_err, file=sys.stderr)
                return EXIT_SETUP
        if revising:
            # Re-dispatch the paused stage with the original intent, the current artifact, and the
            # feedback, then return to the SAME gate.
            return _run_revise(
                s,
                args,
                ledger,
                sk,
                spec_id,
                pending,
                feedback,
                feature_dir=feature_dir,
                run_branch=run_branch,
                git_prefs=git_prefs,
                commit_relaxed=commit_relaxed,
                rst=rst,
            )
        # Re-enter after the later of the approved gate and the last committed checkpoint, so a mid-run
        # failure resumes from the next uncompleted stage without re-dispatching a committed one
        # — then intersect with the on-disk completion check: a recorded stage whose
        # artifact is broken becomes the re-entry point, never skipped on its ledger entry alone.
        start_index = orchestrate.resume_start_index(entries_now, spec_id, pending)
        start_index, broken = completion.resume_entry_index(
            entries_now, spec_id, start_index, root=s.root, feature_dir=feature_dir
        )
        if broken is not None and not args.json:
            print(f"  ⟲ resume re-enters at '{broken.step}' — {broken.message}", file=sys.stderr)
        runner = _make_runner(start_index)
        _record_dispatch(start_index)  # provenance for the resumed segment only
    else:
        wk = workkind.classify(args.intent or "")  # shape the tier + oracle, not the sign-off
        if git_on and not clean_start_relaxed:
            # The pre-stage git hook's clean-start guard, BEFORE any side effect: a
            # fresh run owns no paths yet, so any uncommitted change outside the engine's own state
            # blocks — naming the paths and the signed deviation, never discarding them.
            unrelated = gitflow.unrelated_changes(gitflow.uncommitted(s.root), set())
            if unrelated:
                print(gitflow.clean_start_refusal(unrelated), file=sys.stderr)
                return EXIT_SETUP
        # Bind the run's feature folder: an explicit --spec names it; otherwise a
        # LIVE run auto-allocates specs-src/<NNN>-<slug>/ deterministically from the intent.
        # --dry-run and the simulator dispatch nothing and write no artifacts, so they allocate
        # nothing.
        if getattr(args, "spec", None):
            spec_arg = Path(args.spec)
            feature_dir = workspace.feature_dir_of(spec_arg) if spec_arg.exists() else None
        elif _resolve_runner_kind(args) != "sim":
            # The fresh-run id is the next-free over the UNION of on-disk folders, existing run
            # branches, and the signed ledger's run ids \u2014 so a fresh run always gets a brand-new
            # folder AND branch even when a prior run survives only on an unmerged branch or only in
            # the ledger. `workspace` stays pure: the git/ledger inputs are gathered here (read-only,
            # notifications-style isolation) and passed in as plain lists.
            branch_numbers = gitflow.run_branch_numbers(
                s.root, git_prefs.branch_prefix, remote=git_prefs.remote
            )
            ledger_numbers = _ledger_run_numbers(ledger.entries())
            try:
                feature_dir = workspace.allocate_feature_dir(
                    s.root,
                    args.intent or "",
                    branch_numbers=branch_numbers,
                    ledger_numbers=ledger_numbers,
                )
            except FileExistsError:
                target = workspace.feature_folder_name(
                    s.root / workspace.SPECS_DIR,
                    args.intent or "",
                    branch_numbers=branch_numbers,
                    ledger_numbers=ledger_numbers,
                )
                print(
                    f"cannot start `3pwr run` — the feature folder {workspace.SPECS_DIR}/{target} "
                    "is already allocated (another run?); no folder is ever overwritten",
                    file=sys.stderr,
                )
                return EXIT_SETUP
        if not args.spec_id and feature_dir is not None:
            # The workspace's NNN is the run's real identity: derived once here,
            # immediately after the feature folder is bound, so every downstream consumer —
            # ledger writes, gate messages, resume hints, notifications, oracle dispatch, and
            # the branch name below — reads the derived value, never the pre-derivation default.
            # An explicit --spec-id always wins.
            spec_id = feature_dir.name.split("-")[0]
            tracker.retitle(spec_id)
        if git_on and feature_dir is not None:
            # The run's human-readable progress file: bound to the allocated
            # workspace and the resolved identity, written at every lifecycle trigger below. A
            # dry-run / simulated run allocates no folder and writes no file.
            progress_box["reporter"] = progress.Reporter(
                feature_dir,
                spec_id=spec_id,
                tier=args.tier or wk.suggested_tier or s.default_tier(),
            )
        if git_on:
            # Create + switch to the run's dedicated branch off the configured base BEFORE any
            # stage commit: the branch name reuses the workspace's <NNN>-<slug> identity
            # — the git hook allocates no number and derives no slug — and the run never commits
            # on the base branch. Detached HEAD / unborn repo: created off the current commit.
            identity = feature_dir.name if feature_dir is not None else workspace.slugify(spec_id)
            run_branch = gitflow.run_branch_name(git_prefs.branch_prefix, identity)
            # A fresh run never adopts a prior run's branch: if the computed branch already exists
            # (defense-in-depth — the union id allocation makes this unreachable in the happy path)
            # the guard refuses and we point the user at an explicit resume, never a stale checkout.
            # A fresh create branches off the up-to-date base after a best-effort, offline-safe
            # fetch (opt-in via git.yaml `fetch_base`/`remote`); the local base is never mutated.
            b_err = gitflow.ensure_run_branch(
                s.root,
                run_branch,
                git_prefs.base_branch,
                mode="fresh",
                remote=git_prefs.remote,
                fetch_base=git_prefs.fetch_base,
            )
            if b_err == gitflow.FRESH_BRANCH_EXISTS:
                print(
                    f"cannot start a fresh `3pwr run` — the run branch '{run_branch}' already "
                    "exists, so a fresh run would continue prior work; a fresh run always starts "
                    f"clean. To continue that run instead: 3pwr run --resume --spec-id {spec_id}",
                    file=sys.stderr,
                )
                return EXIT_SETUP
            if b_err:
                print(b_err, file=sys.stderr)
                return EXIT_SETUP
        start_payload: dict[str, Any] = {
            "kind": "start",
            "intent": args.intent or "",
            "mode": mode,
            "integration": args.integration,
            "inferred_kinds": wk.kinds,
            "suggested_tier": wk.suggested_tier,
        }
        if run_branch:
            # The additive branch binding on the existing run/start payload: a later
            # resume recovers the branch from the signed ledger alone — no branch scan, no
            # guessing; no new entry type and no signing change.
            start_payload["branch"] = run_branch
        if feature_dir is not None:
            # The additive folder binding on the existing run/start payload: a later
            # resume reads it back from the signed ledger alone — no mtime scan.
            try:
                start_payload["feature_dir"] = feature_dir.relative_to(s.root).as_posix()
            except ValueError:
                start_payload["feature_dir"] = feature_dir.as_posix()
        ledger.append("run", start_payload, sk, spec_id=spec_id)
        if not args.json and _verbosity(args) != "quiet":
            print(rst.header(f"3pwr run · {mode} mode", spec_id))
            print(
                rst.kv(
                    [
                        ("intent", args.intent or "—"),
                        ("work kinds", ", ".join(wk.kinds) or "—"),
                        ("suggested tier", wk.suggested_tier),
                    ]
                )
            )
            print("  " + rst.dim("you still approve the spec"))
            # Surface where the full per-attempt agent output lands: the persisted transcript is
            # ground truth (always written, even when the live view is off), so the run is
            # followable after the fact — especially off a TTY / without --stream.
            print("  " + rst.dim(f"full agent output: {transcripts.run_dir_rel(spec_id)}/"))
        runner = _make_runner(0)
        _record_dispatch(0)  # provenance for the first segment (up to the spec-approval gate)
    first_resuming = False  # start_index already positions native/sim runners; resume==run for both

    try:
        if not args.json:
            # The live bar is on screen BEFORE the first dispatch produces any output, so the run
            # shows its heartbeat from the first moment. No-op off-TTY/degraded.
            tracker.begin()
        result = orchestrate.drive(runner, mode, on_event, resuming=first_resuming)
        while result.status == "paused_at_gate":
            ledger.append(
                "run",
                {"kind": "gate", "gate": result.gate, "stage": result.stage},
                sk,
                spec_id=spec_id,
            )
            # Before pausing for the human gate: persist the engine's trust state (this gate entry,
            # the ledger, progress.md) so the tree the user reviews at the pause is clean — the same
            # clean-tree guarantee a finished run gives.
            _commit_engine_state(
                s,
                spec_id=spec_id,
                step=result.gate or result.stage,
                run_branch=run_branch,
                commit_relaxed=commit_relaxed,
                prefs=git_prefs,
            )
            gate_artifact = steering.gate_artifact(s.root, feature_dir, result.gate)
            _notify_event(
                s,
                args,
                notify.EVENT_GATE,
                notify.gate_message(
                    spec_id,
                    result.gate,
                    result.stage,
                    result.gate_fr,
                    gate_artifact,
                    steering.gate_actions(spec_id),
                ),
                spec_id,
            )
            if not interactive:
                fr = f" ({result.gate_fr})" if result.gate_fr else ""
                action_rows = "\n".join(_gate_pause_rows(rst, spec_id, gate_artifact))
                human = (
                    f"{orchestrate.render_tracker(result.stage, rst)}\n"
                    f"  {rst.warn('⏸ HUMAN GATE')} '{result.gate}'{fr}"
                    f" — review, then choose:\n{action_rows}"
                )
                _print(
                    {
                        "status": "paused_at_gate",
                        "gate": result.gate,
                        "gate_fr": result.gate_fr,
                        "stage": result.stage,
                        "spec_id": spec_id,
                        "stages": _stages(),
                    },
                    args.json,
                    human,
                )
                # Paused-at-gate is distinguishable from completed by exit code alone.
                return EXIT_PAUSED
            fr = f" ({result.gate_fr})" if result.gate_fr else ""
            for line in _gate_pause_rows(rst, spec_id, gate_artifact):
                print(line)  # the three actions, on-screen at the interactive pause too
            while True:
                decision = _gate_decision(result.gate, fr)
                if decision != "revise":
                    break
                # Revise-with-message, inline: take the feedback here, re-run the
                # paused stage with it, and come back to the SAME gate for a fresh decision.
                feedback = _prompt_line("  feedback for the revision (required): ")
                if not feedback:
                    print("  revise needs feedback — nothing was changed")
                    continue
                rc_rev = _run_revise(
                    s,
                    args,
                    ledger,
                    sk,
                    spec_id,
                    result.gate,
                    feedback,
                    feature_dir=feature_dir,
                    run_branch=run_branch,
                    git_prefs=git_prefs,
                    commit_relaxed=commit_relaxed,
                    rst=rst,
                )
                if rc_rev != EXIT_PAUSED:
                    return rc_rev  # the revise failed with its own actionable report
            if decision == "reject":
                reason = _prompt_line("  reason (optional): ")
                payload: dict[str, Any] = {"kind": "complete", "stage": result.stage}
                if reason:
                    payload["reason"] = reason
                ledger.append("run", payload, sk, spec_id=spec_id)
                why = f" — {reason}" if reason else ""
                _print(
                    {
                        "status": "rejected",
                        "gate": result.gate,
                        "spec_id": spec_id,
                        **({"reason": reason} if reason else {}),
                    },
                    args.json,
                    f"  ⊘ gate '{result.gate}' rejected — run stopped{why}",
                )
                return EXIT_FAIL
            _run_signoff(s, ledger, sk, spec_id, result.gate, args.approver, args.note)
            # The sign-off is engine-owned trust state: commit it before driving the next segment,
            # so the approved gate leaves a clean working tree.
            _commit_engine_state(
                s,
                spec_id=spec_id,
                step="signoff",
                run_branch=run_branch,
                commit_relaxed=commit_relaxed,
                prefs=git_prefs,
            )
            _record_dispatch(
                orchestrate.resume_start_index(ledger.entries(), spec_id, result.gate)
            )  # provenance for the next segment (no re-record)
            if not args.json:
                # The gate pause finalized the bar; the approved run's next segment gets it back on
                # screen immediately.
                tracker.begin()
            result = orchestrate.drive(runner, mode, on_event, resuming=True)
    except FileNotFoundError as exc:  # a role's agent manifest is missing on the live path
        print(str(exc), file=sys.stderr)
        return EXIT_SETUP
    finally:
        # The live bar never outlives the run — its last state left as ordinary lines, cursor
        # restored, on normal exit, interruption, and failure alike.
        # Idempotent: a bar already finalized by a terminal event is a no-op here.
        tracker.close()

    if result.status == "failed":
        # Every terminal failure is recorded as a signed run-failure ledger entry BEFORE exiting,
        # so `--status`/`3pwr status` can say "failed at <stage> (<class>)"
        # afterwards. Attempts come from the failing stage's dispatch result.
        failed_srs = [sr for sr in getattr(runner, "stage_results", []) if not sr.ok]
        attempts = failed_srs[-1].attempts if failed_srs else 1
        transcript = failed_srs[-1].transcript if failed_srs else ""

        def record(cls: str) -> None:
            _record_run_failure(
                ledger,
                sk,
                spec_id,
                stage=result.stage,
                failure_class=cls,
                attempts=attempts,
                detail=result.detail or result.verdict,
                transcript=transcript,
            )

        transcript_line = f"\n  agent transcript: {transcript}" if transcript else ""
        if result.is_gate_red:
            # A real deterministic-gate verdict failed at Verify: report gate-red,
            # show Verify reached. No incident/observe-signal suggestion — that is not the remedy.
            record("gates_red")
            reached = result.stage or "Verify"
            _notify_event(
                s,
                args,
                notify.EVENT_FAILURE,
                notify.failure_message(spec_id, "gates red", reached),
                spec_id,
            )
            human = (
                f"{orchestrate.render_tracker(reached, rst)}\n"
                f"  {rst.err('✗')} gates red — the deterministic gate suite failed. Inspect with "
                f"`3pwr gate run --id {spec_id}`, fix the failing gate(s), then "
                f"`3pwr run --resume --spec-id {spec_id}`."
            )
            # When the auto-fix loop tried and gave up, print the step-by-step human remediation
            # summary — the per-gate panels plus a "what I tried / what's left for you" block.
            # Human output only; never in the --json payload.
            fix = verdict_box.get("auto_fix")
            if fix is not None and not args.json:
                human += "\n" + autofix.give_up_summary(
                    fix, verdict_box.get("verdict") or {}, rst, run_id=spec_id
                )
            _print(
                {"status": "gates_red", "stage": reached, "spec_id": spec_id, "stages": _stages()},
                args.json,
                human,
            )
            return EXIT_FAIL
        reached = result.stage or "an early stage"
        if result.outcome == "verdict_error":
            # The gate suite could not even run (no spec resolvable, no adapter, bad tier) — a
            # setup problem, never a false gate-red.
            record("verdict_error")
            _notify_event(
                s,
                args,
                notify.EVENT_FAILURE,
                notify.failure_message(spec_id, "verdict error", reached),
                spec_id,
            )
            human = (
                f"{orchestrate.render_tracker(result.stage, rst)}\n"
                f"  {rst.err('✗')} verdict error at {reached} — the deterministic gate suite could not run "
                "(not a gate verdict). Check the spec resolves (--spec), an adapter is detected, "
                f"and the tier exists, then resume: `3pwr run --resume --spec-id {spec_id}`."
            )
            _print(
                {
                    "status": "verdict_error",
                    "stage": result.stage,
                    "detail": result.detail,
                    "spec_id": spec_id,
                    "stages": _stages(),
                },
                args.json,
                human,
            )
            return EXIT_SETUP
        if result.is_artifact_missing:
            # A stage produced no declared artifact: distinct from a gate-red and from a
            # bare dispatch failure — name the stage and the expected artifact; committed checkpoints let a
            # resume pick up here without re-running completed stages.
            record("artifact_missing")
            _notify_event(
                s,
                args,
                notify.EVENT_FAILURE,
                notify.failure_message(spec_id, "artifact missing", reached),
                spec_id,
            )
            human = (
                f"{orchestrate.render_tracker(result.stage, rst)}\n"
                f"  {rst.err('✗')} artifact missing at {reached} — {result.detail}\n"
                "  the stage's agent ran but did not produce what the stage is responsible for "
                f"(not a gate verdict). Re-run or resume: `3pwr run --resume --spec-id {spec_id}`."
                f"{transcript_line}"
            )
            _print(
                {
                    "status": "artifact_missing",
                    "stage": result.stage,
                    "detail": result.detail,
                    "transcript": transcript,
                    "spec_id": spec_id,
                    "stages": _stages(),
                },
                args.json,
                human,
            )
            return EXIT_SETUP
        if result.outcome in (gitflow.CLASS_COMMIT_FAILED, gitflow.CLASS_BRANCH_FAILED):
            # The mandatory git hook could not hold its guarantee: the stage
            # commit failed, or the run branch could not be created/switched (never forced).
            # Named, recorded, and exiting on the setup/dispatch path — never a
            # gate verdict.
            record(result.outcome)
            _notify_event(
                s,
                args,
                notify.EVENT_FAILURE,
                notify.failure_message(spec_id, "git discipline failed", reached),
                spec_id,
            )
            human = (
                f"{orchestrate.render_tracker(result.stage, rst)}\n"
                f"  {rst.err('✗')} git discipline failed at {reached} — {result.detail}\n"
                "  the run isolates its work on a dedicated branch and commits every producing "
                f"stage. Fix the repository state, then resume: "
                f"`3pwr run --resume --spec-id {spec_id}`."
            )
            _print(
                {
                    "status": result.outcome,
                    "stage": result.stage,
                    "detail": result.detail,
                    "spec_id": spec_id,
                    "stages": _stages(),
                },
                args.json,
                human,
            )
            return EXIT_SETUP
        if result.outcome in (completion.CLASS_ABSENT, completion.CLASS_UNRECORDED):
            # The deterministic stage-completion gate blocked the run: the
            # stage's declared markdown and its matching signed ledger entry must BOTH exist. The
            # named class is recorded and surfaced by both status commands; the stage
            # must be re-run — the non-gate-red setup/dispatch exit path.
            record(result.outcome)
            _notify_event(
                s,
                args,
                notify.EVENT_FAILURE,
                notify.failure_message(spec_id, "stage completion failed", reached),
                spec_id,
            )
            human = (
                f"{orchestrate.render_tracker(result.stage, rst)}\n"
                f"  {rst.err('✗')} stage completion failed at {reached} — {result.detail}\n"
                "  a stage is complete only when its artifact is on disk AND recorded in the signed "
                f"ledger (not a gate verdict). Re-run the stage: `3pwr run --resume --spec-id {spec_id}`."
            )
            _print(
                {
                    "status": result.outcome,
                    "stage": result.stage,
                    "detail": result.detail,
                    "spec_id": spec_id,
                    "stages": _stages(),
                },
                args.json,
                human,
            )
            return EXIT_SETUP
        # A dispatch/execution failure — NOT a gate verdict: name the stage, never say
        # "gates red", never route to the incident/observe-signal path; exit with the setup/dispatch code.
        record("dispatch_failed")
        _notify_event(
            s,
            args,
            notify.EVENT_FAILURE,
            notify.failure_message(spec_id, "dispatch failed", reached),
            spec_id,
        )
        detail = f" — {result.detail}" if result.detail else ""
        human = (
            f"{orchestrate.render_tracker(result.stage, rst)}\n"
            f"  {rst.err('✗')} dispatch failed at {reached} — a stage could not be executed (a setup/dispatch "
            f"problem, not a gate verdict){detail}.\n"
            "  confirm the coder integration is headless and available (`3pwr run` reports "
            f"prerequisites), then re-run — or resume: `3pwr run --resume --spec-id {spec_id}`."
            f"{transcript_line}"
        )
        _print(
            {
                "status": "dispatch_failed",
                "stage": result.stage,
                "detail": result.detail,
                "transcript": transcript,
                "spec_id": spec_id,
                "stages": _stages(),
            },
            args.json,
            human,
        )
        return EXIT_SETUP
    if result.status == "aborted":
        _notify_event(s, args, notify.EVENT_FAILURE, f"3pwr run {spec_id}: aborted", spec_id)
        _print(
            {"status": "aborted", "spec_id": spec_id, "stages": _stages()},
            args.json,
            f"  {rst.dim('⊘')} run aborted",
        )
        return EXIT_FAIL

    ledger.append("run", {"kind": "complete", "stage": "Ship"}, sk, spec_id=spec_id)
    # The completing run's final engine-state commit: the `complete` entry and the ledger it rides
    # in are engine-owned trust state, so a FINISHED run leaves a clean working tree — nothing
    # run-produced left uncommitted.
    _commit_engine_state(
        s,
        spec_id=spec_id,
        step="complete",
        run_branch=run_branch,
        commit_relaxed=commit_relaxed,
        prefs=git_prefs,
    )
    _notify_event(s, args, notify.EVENT_COMPLETION, notify.completion_message(spec_id), spec_id)
    human = "\n".join(
        [
            _completion_tracker(rst),
            f"  {rst.ok('✓ complete — ready to push')}",
            *_completion_summary_lines(feature_dir, rst),
            "",
            *_observe_cta_lines(rst, root=s.root, feature_dir=feature_dir, run_branch=run_branch),
        ]
    )
    _print({"status": "done", "spec_id": spec_id, "stages": _stages()}, args.json, human)
    return EXIT_OK


def cmd_abort(args: argparse.Namespace) -> int:
    """Record an abort for a spec's run."""
    s = _settings(args.root)
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    entry = Ledger(s.ledger_path).append(
        "abort", {"reason": args.reason or ""}, sk, spec_id=args.spec_id
    )
    abt = _styler(args)
    print(
        _compose(
            args,
            abt,
            title="abort",
            subject=args.spec_id,
            rows=[
                abt.status_row("warn", f"aborted '{args.spec_id}'", f"ledger seq={entry['seq']}")
            ],
        )
    )
    return EXIT_OK


def _register_status(sub: SubParsers, common: AddCommon) -> None:
    stp = common(sub.add_parser("status", help="per-spec lifecycle stage from the ledger"))
    stp.add_argument("--spec-id", dest="spec_id", help="the run's numeric id, e.g. 002")
    stp.set_defaults(func=cmd_status)


def _register_git(sub: SubParsers, common: AddCommon) -> None:
    gitp = sub.add_parser("git", help="git run discipline: establish the run branch")
    gitsub = gitp.add_subparsers(dest="git_cmd", required=True)
    gits = common(
        gitsub.add_parser(
            "start",
            help="establish + bind the run's dedicated branch for a manual drive "
            "(clean-start guarded)",
        )
    )
    gits.add_argument(
        "--spec-id", dest="spec_id", required=True, help="the run's numeric id, e.g. 002"
    )
    gits.add_argument(
        "--feature",
        help="the run's feature folder (specs-src/<NNN>-<slug>); default: the ledger's recorded binding",
    )
    gits.set_defaults(func=cmd_git_start)


def _register_run(sub: SubParsers, common: AddCommon) -> None:
    rnp = common(sub.add_parser("run", help="drive the full lifecycle loop (auto/commit modes)"))
    rnp.add_argument(
        "intent", nargs="?", help="the human's one-paragraph intent (omit with --resume/--status)"
    )
    rnp.add_argument(
        "--file",
        default=None,
        help="read the run's intent from a text file (markdown preferred); inline intent text is "
        "appended to it as an instruction",
    )
    rnp.add_argument(
        "--mode",
        choices=["auto", "commit"],
        default=None,
        help="auto = stop only at the two human gates (spec approval, sign-off); commit = stop at "
        "every gate (default: the value recorded by `3pwr init`, else auto)",
    )
    rnp.add_argument(
        "--integration",
        default="auto",
        help="the coder agent backend (a manifest in .3powers/agents/); the oracle should use a "
        "different model family",
    )
    rnp.add_argument(
        "--runner",
        choices=["native", "sim"],
        default=None,
        help="executive runner: native (default; drive headless agents directly) or "
        "sim (offline). --dry-run forces sim.",
    )
    rnp.add_argument(
        "--agent",
        default=None,
        help="override the coder agent backend for this run (e.g. claude, codex, copilot)",
    )
    rnp.add_argument(
        "--spec",
        default=None,
        help="spec.md the native verify stage gates against (default: the newest under specs-src/)",
    )
    rnp.add_argument(
        "--tier",
        default=None,
        help="risk tier for the native verify stage (default: the inferred/suggested tier)",
    )
    rnp.add_argument(
        "--auto-fix",
        dest="auto_fix",
        action="store_true",
        help="when a format/lint check fails at the verify stage and a fix command is configured, "
        "run the fix and re-check (opt-in; never the default)",
    )
    rnp.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="per-stage dispatch timeout in seconds (default: the configured value, or 1800)",
    )
    rnp.add_argument(
        "--retries",
        type=int,
        default=None,
        help="retries for a failed dispatch before the stage is reported failed "
        "(default: the configured value, or 1)",
    )
    rnp.add_argument(
        "--stream",
        action="store_true",
        help="echo the agent's live output even when stdout is not a TTY (still off under --json; "
        "the full per-attempt transcript is always written under .3powers/runs/)",
    )
    rnp.add_argument(
        "--raw-events",
        dest="raw_events",
        action="store_true",
        help="show a stream-json backend's underlying events verbatim instead of the rendered "
        "assistant text (diagnostic)",
    )
    rnp.add_argument(
        "--show-prompts",
        dest="show_prompts",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="echo each stage's assembled agent prompt live before its dispatch (display only; "
        "overrides ui.yaml show_prompts; off under --json/--quiet)",
    )
    rnp.add_argument(
        "--no-auto-commit",
        dest="no_auto_commit",
        action="store_true",
        help="SUPERSEDED: the per-stage commit is mandatory; this flag only warns. "
        "Relax on the record: `3pwr deviation --gate git_stage_commit`",
    )
    rnp.add_argument(
        "--spec-id",
        dest="spec_id",
        help="the run's numeric id, e.g. 002 (default: derived from the allocated feature "
        "folder; resolves to specs-src/<NNN>-*/)",
    )
    rnp.add_argument(
        "--notify", help='command fired on gate/failure/completion: `<cmd> "<message>"`'
    )
    rnp.add_argument(
        "--resume",
        action="store_true",
        help="continue after a human gate (records the sign-off first)",
    )
    rnp.add_argument(
        "--revise",
        default=None,
        help="with --resume, at a paused human gate: re-run the paused stage with this feedback "
        "and return to the same gate",
    )
    rnp.add_argument(
        "--revise-file",
        dest="revise_file",
        default=None,
        help="read the revise feedback from a text file (same resolution rule as --file)",
    )
    rnp.add_argument(
        "--status", action="store_true", help="show the run's stage tracker from the ledger"
    )
    rnp.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="simulate the loop offline (no live agents)",
    )
    rnp.add_argument(
        "--simulate-fail",
        dest="simulate_fail",
        action="store_true",
        help="(dry-run) simulate a red gate verdict",
    )
    rnp.add_argument(
        "--no-input",
        dest="no_input",
        action="store_true",
        help="never prompt; stop at gates and print the resume command",
    )
    rnp.add_argument(
        "--discovery",
        dest="discovery",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="force (--discovery) or skip (--no-discovery) the Discovery stage "
        "(default: run it for feature/design work, skip it otherwise)",
    )
    rnp.add_argument("--approver", help="human approver recorded at gate sign-offs")
    rnp.add_argument("--note", help="note recorded with the gate sign-off")
    rnp.set_defaults(func=cmd_run)


def _register_abort(sub: SubParsers, common: AddCommon) -> None:
    abp = common(sub.add_parser("abort", help="record an abort for a spec's run"))
    abp.add_argument(
        "--spec-id", dest="spec_id", required=True, help="the run's numeric id, e.g. 002"
    )
    abp.add_argument("--reason")
    abp.set_defaults(func=cmd_abort)
