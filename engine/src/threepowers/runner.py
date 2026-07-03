"""The native executive runner — drive the lifecycle by dispatching headless coding agents directly.

This is the executive leg 3Powers now owns (EXEC-FR-001; amends 3PWR A1/A3). :class:`NativeRunner`
implements the same :class:`threepowers.orchestrate.Runner` protocol as the offline ``SimulatedRunner``,
so the pure :func:`threepowers.orchestrate.drive` state machine, the two mandatory human gates, the stage
tracker, and the ledger provenance are all reused unchanged. It walks the in-code ``LIFECYCLE_STEPS``:

* an **action** step is dispatched to the role's configured agent (:class:`CliAgentRunner`), which builds
  the invocation from a declarative manifest and runs the agent as an external process (EXEC-FR-004/005);
* a **verdict** step runs the deterministic gate suite **in-process** via an injected ``run_verdict``
  callable — never through a subprocess and never through a model (EXEC-FR-006);
* a **gate** step returns for the human decision.

The engine issues no model/agent API call itself; all model work happens inside the dispatched agent
process (EXEC-NFR-001). ``NativeRunner`` is pure given its injected callables, so the whole orchestration,
diagnostics, and provenance flow is exercised in tests with a fake agent and no network (EXEC-NFR-004).
A dispatch failure or a verdict that could not run returns ``verdict=""`` so the caller reports it as a
setup/dispatch failure, distinct from a real gate-red (EXEC-FR-016).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import agents, prompts
from .config import Settings
from .orchestrate import Event, LIFECYCLE_STEPS, Outcome

# Injected seams (EXEC-NFR-004): dispatch one action stage, or produce a verdict for one verify stage.
Dispatcher = Callable[[str, str], "DispatchResult"]  # (step_id, stage) -> result
VerdictFn = Callable[[str], str]  # (stage) -> "pass" | "fail" | "error"


@dataclass
class DispatchResult:
    """The outcome of dispatching one stage to an agent."""

    ok: bool
    detail: str = ""
    model: str = ""


def dispatch_agent(
    argv: list[str], *, cwd: Path, stdin: Optional[str] = None, timeout: int = 1800
) -> tuple[int, str, str]:
    """Run an agent invocation as an external process (no shell) and return ``(rc, stdout, stderr)``.

    Module-level so tests monkeypatch it to a fake agent — the engine never calls a model API itself
    (EXEC-NFR-001). ``argv`` comes only from a committed agent manifest via :func:`agents.build_command`,
    never from user input, so no shell/injection surface is opened.
    """
    try:
        proc = subprocess.run(  # noqa: S603 — argv from a trusted manifest, shell disabled
            argv,
            cwd=str(cwd),
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError as exc:
        return 127, "", f"agent command not found: {exc}"
    except subprocess.TimeoutExpired:
        return 124, "", f"agent timed out after {timeout}s"


class CliAgentRunner:
    """Dispatch a lifecycle stage to a headless coding-agent CLI described by a manifest (EXEC-FR-001/003).

    Assembles the engine-owned stage prompt (EXEC-FR-005), builds the invocation from the manifest, runs the
    agent in ``cwd`` (the working tree, or a sanitized worktree for the oracle role), and reports success or
    a dispatch failure (EXEC-FR-016). The provider/gateway environment is inherited by the child process, so
    an org routes model traffic through its own gateway with no engine change (EXEC-FR-012).
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
        dispatcher: Optional[Callable[..., tuple[int, str, str]]] = None,
    ) -> None:
        self.settings = settings
        self.manifest = manifest
        self.model = model
        self.cwd = cwd or settings.root
        self.intent = intent
        self.spec_text = spec_text
        self.timeout = timeout
        # Resolve the module-level default at construction time so a monkeypatched ``dispatch_agent``
        # (tests / a fake agent) is honored — the engine still issues no model call (EXEC-NFR-001).
        self._dispatcher = dispatcher or dispatch_agent

    def dispatch(self, step: str, stage: str) -> DispatchResult:
        prompt = prompts.assemble(step, intent=self.intent, spec_text=self.spec_text)
        argv, stdin = agents.build_command(self.manifest, prompt, model=self.model)
        rc, out, err = self._dispatcher(argv, cwd=self.cwd, stdin=stdin, timeout=self.timeout)
        if rc != 0:
            detail = (err.strip() or out.strip() or f"agent exited {rc}")[:400]
            return DispatchResult(False, detail=detail, model=self.model)
        return DispatchResult(True, detail=step, model=self.model)


class NativeRunner:
    """Drive the lifecycle headlessly via injected dispatch + verdict callables (EXEC-FR-001/006)."""

    def __init__(
        self,
        *,
        dispatch: Dispatcher,
        run_verdict: VerdictFn,
        steps: Optional[list[tuple[str, str, str]]] = None,
        start_index: int = 0,
    ) -> None:
        self._dispatch = dispatch
        self._verdict = run_verdict
        self._steps = steps if steps is not None else LIFECYCLE_STEPS
        self._i = start_index

    def _walk(self) -> Outcome:
        events: list[Event] = []
        while self._i < len(self._steps):
            sid, kind, stage = self._steps[self._i]
            self._i += 1
            if kind == "gate":
                return Outcome("gate", gate=sid, stage=stage, events=events)
            if kind == "verdict":
                v = self._verdict(stage)
                if v == "error":
                    # The gate suite could not run (e.g. no spec resolved) — a setup/dispatch failure,
                    # NOT a gate-red verdict (EXEC-FR-016). verdict="" signals the non-verdict failure.
                    return Outcome("failed", stage=stage, verdict="", events=events)
                events.append(Event("verdict", sid, stage, v))
                if v != "pass":
                    return Outcome("failed", stage=stage, verdict=v, events=events)
            else:  # action — dispatch to the agent
                res = self._dispatch(sid, stage)
                if not res.ok:
                    # A dispatch/execution failure — reported distinctly from a gate verdict (EXEC-FR-016).
                    return Outcome("failed", stage=stage, verdict="", events=events)
                events.append(Event("step", sid, stage))
        return Outcome("done", events=events)

    def run(self) -> Outcome:
        return self._walk()

    def resume(self, decision: str) -> Outcome:
        if decision == "reject":
            return Outcome("aborted", events=[Event("aborted")])
        return self._walk()
