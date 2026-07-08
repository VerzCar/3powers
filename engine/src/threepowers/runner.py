"""The native executive runner — drive the lifecycle by dispatching headless coding agents directly.

This is the executive leg 3Powers now owns. :class:`NativeRunner`
implements the same :class:`threepowers.orchestrate.Runner` protocol as the offline ``SimulatedRunner``,
so the pure :func:`threepowers.orchestrate.drive` state machine, the two mandatory human gates, the stage
tracker, and the ledger provenance are all reused unchanged. It walks the in-code ``LIFECYCLE_STEPS``:

* an **action** step is dispatched to the role's configured agent (:class:`CliAgentRunner`), which builds
  the invocation from a declarative manifest and runs the agent as an external process;
* a **verdict** step runs the deterministic gate suite **in-process** via an injected ``run_verdict``
  callable — never through a subprocess and never through a model;
* a **gate** step returns for the human decision.

The dispatch of an action step is hardened: each attempt is bounded by a **timeout** and **retried**
per policy, the stage's declared **artifact contract** is verified before advancing,
and a machine-readable **per-stage result** (agent, model, attempts, duration,
artifact, outcome) is recorded for ``--json``. None of this enters the deterministic
verdict.

The engine issues no model/agent API call itself; all model work happens inside the dispatched agent
process. ``NativeRunner`` is pure given its injected callables, so the whole
orchestration, diagnostics, and provenance flow is exercised in tests with a fake agent and no network.
A dispatch failure, an exhausted retry, or a missing artifact returns
``ok=False`` so the caller reports it as a setup/dispatch failure, distinct from a real gate-red.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, TYPE_CHECKING, Callable, Optional, Protocol

from . import agents, prompts
from .config import Settings
from .orchestrate import Event, LIFECYCLE_STEPS, Outcome

if TYPE_CHECKING:  # typing-only import (avoids a runtime import cycle)
    from .artifacts import ArtifactCheck
    from .transcripts import TranscriptSink

# Injected seams: dispatch one action stage, or produce a verdict for one verify stage.
Dispatcher = Callable[[str, str], "StageResult"]  # (step_id, stage) -> per-stage result
VerdictFn = Callable[[str], str]  # (stage) -> "pass" | "fail" | "error"


class TextSink(Protocol):
    """Anything transcript lines can be teed into (a file, a redacting writer)."""

    def write(self, s: str) -> object: ...
    def flush(self) -> None: ...


@dataclass
class DispatchResult:
    """The outcome of one dispatch attempt to an agent (a single try, before the retry/artifact policy)."""

    ok: bool
    detail: str = ""
    model: str = ""
    # The persisted transcript path for this attempt, when one was written.
    transcript: str = ""
    # The agent-reported token usage for this attempt (manifest-declared extraction);
    # None when the backend does not report usage. Strictly advisory — never enters the verdict.
    tokens: Optional[int] = None


@dataclass
class StageResult:
    """The machine-readable result of running one action stage end-to-end.

    Carries everything ``--json`` reports per dispatched stage: the agent + resolved model, the number of
    attempts, the wall-clock duration, a short artifact summary, and the outcome. ``ok`` drives the state
    machine; ``outcome`` classifies a failure for an actionable message:
    ``"ok"`` | ``"dispatch_failed"`` | ``"artifact_missing"``.
    """

    step: str
    stage: str
    ok: bool
    agent: str = ""
    model: str = ""
    attempts: int = 0
    duration_s: float = 0.0
    artifact: str = ""
    outcome: str = ""
    detail: str = ""
    # The persisted transcript path of the stage's LAST attempt: a failure message
    # names it, and the run-failure ledger record stores the path — never the content.
    transcript: str = ""
    # The accepted artifact's repo-relative path(s), recorded with the stage's ledger entry so the
    # committed artifact trail is reconstructable from the signed ledger alone.
    artifact_paths: list[str] = field(default_factory=list)
    # Advisory notes (e.g. the context-budget oversize warnings) — never a failure.
    warnings: list[str] = field(default_factory=list)
    # Per-phase results when the stage ran as context-sized phases, artifact order.
    phases: list[dict] = field(default_factory=list)
    # The agent-reported token usage for the stage (summed over phases when phased);
    # None when the backend does not report usage. Advisory — never enters the verdict.
    tokens: Optional[int] = None

    def as_dict(self) -> dict:
        d = {
            "step": self.step,
            "stage": self.stage,
            "ok": self.ok,
            "agent": self.agent,
            "model": self.model,
            "attempts": self.attempts,
            "duration_s": round(self.duration_s, 3),
            "artifact": self.artifact,
            "outcome": self.outcome,
            "detail": self.detail,
        }
        if self.transcript:
            d["transcript"] = self.transcript
        if self.artifact_paths:
            d["artifact_paths"] = self.artifact_paths
        if self.warnings:
            d["warnings"] = self.warnings
        if self.phases:
            d["phases"] = self.phases
        if self.tokens is not None:
            # Additive-only: the token field joins the payload only when the backend reported
            # usage, so every prior key stays present and prior parsers keep working.
            d["tokens"] = self.tokens
        return d


def dispatch_agent(
    argv: list[str],
    *,
    cwd: Path,
    stdin: Optional[str] = None,
    timeout: int = 1800,
    stream: bool = False,
    tee: Optional[TextSink] = None,
    echo_out: Optional[TextSink] = None,
    echo_err: Optional[TextSink] = None,
) -> tuple[int, str, str]:
    """Run an agent invocation as an external process (no shell) and return ``(rc, stdout, stderr)``.

    Module-level so tests monkeypatch it to a fake agent — the engine never calls a model API itself.
    ``argv`` comes only from a committed agent manifest via :func:`agents.build_command`,
    never from user input, so no shell/injection surface is opened.

    ``timeout`` bounds the attempt: an over-long agent is terminated and reported as a
    dispatch failure (rc 124), never a hang. ``tee`` receives every stdout/stderr line as it arrives —
    the persisted transcript sink. With ``stream`` set the lines are ALSO echoed live —
    to ``echo_out``/``echo_err`` when given (the run's live bar routes the
    conversation above itself through these), else straight to the process's own
    stdout/stderr; output is captured in both cases, so a streamed run never loses its output.
    """
    if tee is None and not stream:
        # The plain captured path — unchanged behavior for programmatic callers with no sink.
        try:
            # argv comes from a trusted manifest and the shell is disabled — no injection surface.
            proc = subprocess.run(
                argv,
                cwd=str(cwd),
                input=stdin,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return proc.returncode, (proc.stdout or ""), (proc.stderr or "")
        except FileNotFoundError as exc:
            return 127, "", f"agent command not found: {exc}"
        except subprocess.TimeoutExpired:
            return 124, "", f"agent timed out after {timeout}s"

    # The tee/stream path: pipe the child's output and pump it line by line into the capture
    # buffers, the transcript sink, and — when streaming — the terminal.
    def note(msg: str) -> None:
        if tee is not None:
            tee.write(msg + "\n")
            tee.flush()

    try:
        # argv comes from a trusted manifest and the shell is disabled — no injection surface.
        child = subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdin=subprocess.PIPE if stdin is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        msg = f"agent command not found: {exc}"
        note(msg)
        return 127, "", msg

    def pump(src: Optional[IO[str]], buf: list[str], echo: Optional[TextSink]) -> None:
        if src is None:
            return
        for line in src:
            buf.append(line)
            if tee is not None:
                tee.write(line)
                tee.flush()
            if echo is not None:
                echo.write(line)
                echo.flush()

    out_buf: list[str] = []
    err_buf: list[str] = []
    out_echo: Optional[TextSink] = (
        (echo_out if echo_out is not None else sys.stdout) if stream else None
    )
    err_echo: Optional[TextSink] = (
        (echo_err if echo_err is not None else sys.stderr) if stream else None
    )
    pumps = [
        threading.Thread(target=pump, args=(child.stdout, out_buf, out_echo), daemon=True),
        threading.Thread(target=pump, args=(child.stderr, err_buf, err_echo), daemon=True),
    ]
    for th in pumps:
        th.start()
    timed_out = False
    if stdin is not None and child.stdin is not None:
        try:
            child.stdin.write(stdin)
            child.stdin.close()
        except (BrokenPipeError, OSError):
            pass
    try:
        child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()
        timed_out = True
    for th in pumps:
        th.join(timeout=10)
    if timed_out:
        msg = f"agent timed out after {timeout}s"
        note(msg)
        return 124, "".join(out_buf), msg
    return child.returncode, "".join(out_buf), "".join(err_buf)


class CliAgentRunner:
    """Dispatch a lifecycle stage to a headless coding-agent CLI described by a manifest.

    Assembles the engine-owned stage prompt, builds the invocation from the manifest, runs the
    agent in ``cwd`` (the working tree, or a sanitized worktree for the oracle role), and reports success or
    a dispatch failure. The provider/gateway environment is inherited by the child process, so
    an org routes model traffic through its own gateway with no engine change.

    ``dispatch`` runs **one** attempt; retry/timeout/artifact policy lives in :func:`run_stage` so it stays
    pure and unit-testable.
    """

    def __init__(
        self,
        settings: Settings,
        manifest: dict,
        *,
        model: str = "",
        cwd: Optional[Path] = None,
        intent: str = "",
        spec_text: str = "",
        timeout: int = 1800,
        stream: bool = False,
        dispatcher: Optional[Callable[..., tuple[int, str, str]]] = None,
        transcripts: Optional["TranscriptSink"] = None,
        echo_out: Optional[TextSink] = None,
        echo_err: Optional[TextSink] = None,
    ) -> None:
        self.settings = settings
        self.manifest = manifest
        self.model = model
        self.cwd = cwd or settings.root
        self.intent = intent
        self.spec_text = spec_text
        self.timeout = timeout
        self.stream = stream
        # Where a streamed attempt's live echo goes: the run's live bar routes the
        # agent conversation above itself through these; None keeps the process's own stdout/stderr.
        self.echo_out = echo_out
        self.echo_err = echo_err
        # The per-run transcript sink: every attempt's output is persisted,
        # credential-redacted. None = no persistence (programmatic callers).
        self.transcripts = transcripts
        # Resolve the module-level default at construction time so a monkeypatched ``dispatch_agent``
        # (tests / a fake agent) is honored — the engine still issues no model call.
        self._dispatcher = dispatcher or dispatch_agent

    def dispatch(
        self,
        step: str,
        stage: str,
        *,
        spec_text: Optional[str] = None,
        context: str = "",
        file_scope: str = "",
    ) -> DispatchResult:
        """Run one fresh headless session for ``step``.

        The optional per-dispatch blocks let the orchestrator inject the approved spec text, the
        prior stage's artifact reference, and — for a build phase — that phase's tasks and declared
        file scope, so no stage depends on the agent rediscovering its inputs. Each
        call is a new agent process: no conversation state is carried between dispatches."""
        prompt = prompts.assemble(
            step,
            intent=self.intent,
            spec_text=self.spec_text if spec_text is None else spec_text,
            context=context,
            file_scope=file_scope,
            # A repo-local stage template supplies the instruction body when present; absent/empty/
            # unreadable falls back to the built-in instruction. Only the body
            # changes — the context blocks and their order stay fixed.
            body=prompts.stage_template_body(self.settings.stage_templates_dir, step),
        )
        argv, stdin = agents.build_command(self.manifest, prompt, model=self.model)
        # Persist this attempt's output to the run's transcript location: teed even
        # while streaming, so a streamed run no longer loses its output. The writer redacts
        # credential-shaped env values before any byte lands on disk.
        path: Optional[Path] = None
        writer = None
        if self.transcripts is not None:
            path, writer = self.transcripts.open(step)
        # Echo sinks ride as extra kwargs only when set, so monkeypatched fake dispatchers with the
        # historical signature keep working unchanged.
        extra: dict = {}
        if self.echo_out is not None:
            extra["echo_out"] = self.echo_out
        if self.echo_err is not None:
            extra["echo_err"] = self.echo_err
        try:
            rc, out, err = self._dispatcher(
                argv,
                cwd=self.cwd,
                stdin=stdin,
                timeout=self.timeout,
                stream=self.stream,
                tee=writer,
                **extra,
            )
        finally:
            if writer is not None:
                writer.close()
        rel = ""
        if path is not None:
            try:
                rel = str(path.relative_to(self.settings.root))
            except ValueError:
                rel = str(path)
        # Advisory usage capture: the manifest's `usage` hint extracts the agent-reported token
        # count from the attempt's output; an unreporting backend reads as None. Never enters
        # the verdict — it rides only the additive result/ledger/progress fields.
        tokens = agents.extract_usage(self.manifest, f"{out}\n{err}")
        if rc != 0:
            detail = (err.strip() or out.strip() or f"agent exited {rc}")[:400]
            if self.transcripts is not None:
                # The excerpt rides in messages and the failure ledger record — redact it like the
                # transcript itself; nothing persisted may carry a credential.
                detail = self.transcripts.redact_text(detail)
            return DispatchResult(
                False, detail=detail, model=self.model, transcript=rel, tokens=tokens
            )
        return DispatchResult(True, detail=step, model=self.model, transcript=rel, tokens=tokens)


# --------------------------------------------------------------------------- retry / artifact policy (pure)
def dispatch_with_retry(
    attempt: Callable[[], DispatchResult],
    *,
    retries: int,
    on_attempt: Optional[Callable[[int], None]] = None,
) -> tuple[DispatchResult, int]:
    """Run ``attempt`` until it succeeds or the retry budget is exhausted.

    A stage is tried at most ``retries + 1`` times; a successful attempt is never retried. Returns the final
    :class:`DispatchResult` and the number of attempts made (``≤ retries + 1``). Pure given ``attempt`` —
    unit-tested with a fake."""
    budget = max(0, int(retries))
    attempts = 0
    result = DispatchResult(False, detail="not attempted")
    while attempts <= budget:
        attempts += 1
        if on_attempt is not None:
            on_attempt(attempts)
        result = attempt()
        if result.ok:
            break
    return result, attempts


def run_stage(
    step: str,
    stage: str,
    *,
    attempt: Callable[[], DispatchResult],
    retries: int,
    verify_artifact: Optional[Callable[[], "ArtifactCheck"]] = None,
    on_attempt: Optional[Callable[[int], None]] = None,
    agent: str = "",
    model: str = "",
    clock: Callable[[], float] = time.monotonic,
) -> StageResult:
    """Dispatch one action stage under the retry/timeout policy, then verify its artifact.

    ``attempt`` runs a single (already timeout-bounded) dispatch; ``verify_artifact`` — called only after a
    successful dispatch — returns an :class:`threepowers.artifacts.ArtifactCheck` for the stage's declared
    contract, or ``None`` when the stage declares none. Returns a :class:`StageResult` that
    is ``ok`` only when the dispatch succeeded *and* the artifact was produced. Pure given its callables — no
    model, no network."""
    t0 = clock()
    result, attempts = dispatch_with_retry(attempt, retries=retries, on_attempt=on_attempt)
    if not result.ok:
        return StageResult(
            step=step,
            stage=stage,
            ok=False,
            agent=agent,
            model=result.model or model,
            attempts=attempts,
            duration_s=clock() - t0,
            outcome="dispatch_failed",
            detail=result.detail,
            transcript=result.transcript,
            tokens=result.tokens,
        )
    resolved = result.model or model
    if verify_artifact is not None:
        check = verify_artifact()
        if not check.ok:
            return StageResult(
                step=step,
                stage=stage,
                ok=False,
                agent=agent,
                model=resolved,
                attempts=attempts,
                duration_s=clock() - t0,
                outcome="artifact_missing",
                detail=f"stage '{step}' produced no expected artifact — {check.message}",
                transcript=result.transcript,
                tokens=result.tokens,
            )
        return StageResult(
            step=step,
            stage=stage,
            ok=True,
            agent=agent,
            model=resolved,
            attempts=attempts,
            duration_s=clock() - t0,
            outcome="ok",
            artifact=check.summary,
            transcript=result.transcript,
            artifact_paths=list(check.matched),  # recorded with the ledger entry
            tokens=result.tokens,
        )
    return StageResult(
        step=step,
        stage=stage,
        ok=True,
        agent=agent,
        model=resolved,
        attempts=attempts,
        duration_s=clock() - t0,
        outcome="ok",
        transcript=result.transcript,
        tokens=result.tokens,
    )


# --------------------------------------------------------------------------- working-tree change tracking (git)
def _git(cwd: Path, args: list[str]) -> tuple[int, str, str]:
    """Run a git command in ``cwd`` (module-level so tests can monkeypatch it)."""
    try:
        proc = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return 127, "", "git not found"


def _changed_files(cwd: Path) -> list[str]:
    """Repo-relative paths that are modified or untracked vs HEAD (empty when not a git repo).

    Engine-written transcripts (``.3powers/runs/``) are excluded even when the
    trust-spine ``.gitignore`` is absent: they are never a stage's artifact and must not satisfy an
    artifact contract or be swept into a checkpoint commit."""
    rc, out, _ = _git(cwd, ["status", "--porcelain", "--untracked-files=all"])
    if rc != 0:
        return []
    paths: list[str] = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        p = line[3:].strip().strip('"')
        if " -> " in p:  # a rename: XY old -> new
            p = p.split(" -> ", 1)[1].strip().strip('"')
        if p and not p.startswith(".3powers/runs/"):
            paths.append(p)
    return paths


def worktree_state(cwd: Path) -> dict[str, str]:
    """A content snapshot of the changed/untracked files — ``{path: sha256}``.

    Comparing a pre- and post-dispatch snapshot yields exactly the paths a stage produced, regardless of
    whether prior stages were committed (auto-commit) or accumulated (no auto-commit)."""
    state: dict[str, str] = {}
    for rel in _changed_files(cwd):
        fp = cwd / rel
        try:
            state[rel] = hashlib.sha256(fp.read_bytes()).hexdigest() if fp.is_file() else ""
        except OSError:
            state[rel] = ""
    return state


def produced_paths(pre: dict[str, str], post: dict[str, str]) -> list[str]:
    """The paths whose content changed between two :func:`worktree_state` snapshots (sorted, deduped).

    A path present in ``pre`` but absent from ``post`` also counts: the stage changed it back to its
    committed content (e.g. re-writing a deleted-then-regenerated artifact on a completion-gate
    re-run) — the dispatch really did produce it even though the working tree ends
    clean for that path."""
    changed = {p for p, h in post.items() if pre.get(p) != h}
    changed |= {p for p in pre if p not in post}
    return sorted(changed)


class NativeRunner:
    """Drive the lifecycle headlessly via injected dispatch + verdict callables.

    Collects one :class:`StageResult` per dispatched action stage in :attr:`stage_results` for the
    ``--json`` per-stage report. A failing action stage carries its outcome + detail into
    the :class:`~threepowers.orchestrate.Outcome` so the caller can name the stage and the missing
    artifact."""

    def __init__(
        self,
        *,
        dispatch: Dispatcher,
        run_verdict: VerdictFn,
        steps: Optional[list[tuple[str, str, str]]] = None,
        start_index: int = 0,
        on_progress: Optional[Callable[[Event], None]] = None,
    ) -> None:
        self._dispatch = dispatch
        self._verdict = run_verdict
        self._steps = steps if steps is not None else LIFECYCLE_STEPS
        self._i = start_index
        self.stage_results: list[StageResult] = []
        # Live event delivery: each event is surfaced the moment it happens — a
        # stage's step event BEFORE its dispatch, so the run's live bar tracks the walk in real
        # time instead of one whole segment late. The batched ``Outcome.events`` history is kept
        # unchanged; ``drive`` skips its replay when events were already delivered live.
        self._progress = on_progress

    @property
    def delivers_live_events(self) -> bool:
        """Whether events reach the caller the moment they happen — ``drive`` then
        skips the end-of-segment history replay so nothing is reported twice."""
        return self._progress is not None

    def _live(self, ev: Event) -> None:
        if self._progress is not None:
            self._progress(ev)

    def _walk(self) -> Outcome:
        events: list[Event] = []
        while self._i < len(self._steps):
            sid, kind, stage = self._steps[self._i]
            self._i += 1
            if kind == "gate":
                return Outcome("gate", gate=sid, stage=stage, events=events)
            if kind == "verdict":
                # Announce the suite BEFORE it runs — a long gate run shows live too.
                self._live(Event("step", sid, stage))
                v = self._verdict(stage)
                if v == "error":
                    # The gate suite could not run (e.g. no spec resolved) — a setup/dispatch failure,
                    # NOT a gate-red verdict. verdict="" signals the non-verdict failure.
                    return Outcome(
                        "failed",
                        stage=stage,
                        verdict="",
                        outcome="verdict_error",
                        detail="the deterministic gate suite could not run",
                        events=events,
                    )
                ev = Event("verdict", sid, stage, v)
                events.append(ev)
                self._live(ev)
                if v != "pass":
                    return Outcome(
                        "failed", stage=stage, verdict=v, outcome="gate_red", events=events
                    )
            else:  # action — dispatch to the agent under the retry/artifact policy
                # Announce the stage BEFORE dispatching it: the live bar names the
                # running step and stage for the whole — possibly minutes-long — dispatch.
                self._live(Event("step", sid, stage))
                res = self._dispatch(sid, stage)
                self.stage_results.append(res)
                if not res.ok:
                    # A dispatch/artifact failure — reported distinctly from a gate verdict,
                    # carrying the outcome + named detail.
                    return Outcome(
                        "failed",
                        stage=stage,
                        verdict="",
                        outcome=res.outcome,
                        detail=res.detail,
                        events=events,
                    )
                events.append(Event("step", sid, stage, res.artifact))
        return Outcome("done", events=events)

    def run(self) -> Outcome:
        return self._walk()

    def resume(self, decision: str) -> Outcome:
        if decision == "reject":
            return Outcome("aborted", events=[Event("aborted")])
        return self._walk()

    def dispatch_once(self, step: str, stage: str) -> StageResult:
        """Dispatch exactly ONE action stage outside the walk — the revise re-run.

        Re-uses the injected dispatcher unchanged, so the retry/timeout/artifact policy, the git
        hooks, and the completion gate all apply to a revision exactly as to a first run; the walk
        position is untouched, so the run stays paused at its gate."""
        res = self._dispatch(step, stage)
        self.stage_results.append(res)
        return res
