"""The asynchronous hosted agent backend — dispatch a role's stage to a *hosted* agent run (RUNLIVE-FR-008).

Some enterprises expose their agent runtime only as an **asynchronous, hosted** run — the GitHub Copilot
coding agent is the motivating case: a REST call kicks off an Actions run that opens a pull request; there
is no local headless CLI to invoke. This backend satisfies the same agent-runner contract as
:class:`threepowers.runner.CliAgentRunner` — a ``dispatch(step, stage) -> DispatchResult`` — by *triggering*
the hosted run, *polling* it to completion, and *collecting* the produced changes (a branch or pull request)
into the working tree, so the very same in-process deterministic gate suite then judges the result
identically to a locally-dispatched stage (RUNLIVE-NFR-003).

It is **provider-neutral** (RUNLIVE-NFR-005): the trigger/poll/collect steps are *manifest-declared
commands* with ``{placeholder}`` substitution, so a Copilot shop wires them to ``gh api`` / ``gh pr
checkout`` with **no vendor code in the engine**. Credentials are inherited through the child process
environment and are never interpreted, logged, or stored by the engine (RUNLIVE-FR-009). The engine issues
no model/agent API call itself — the hosted run does (RUNLIVE-NFR-001). All timing seams (the command
runner, the sleep, the clock) are injectable, so the whole trigger→poll→collect flow is unit-tested with a
fake and no network (RUNLIVE-NFR-002).
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Optional

from . import prompts
from .config import Settings
from .runner import DispatchResult

# The manifest ``mode`` value that selects this backend (a CLI backend omits it or uses "cli").
MODE = "async-hosted"

CommandRunner = Callable[[list[str], Path], tuple[int, str, str]]


def run_hosted_command(argv: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run one manifest-declared hosted command (no shell), inheriting the environment (RUNLIVE-FR-009).

    Module-level so tests monkeypatch it — the engine issues no model call itself (RUNLIVE-NFR-001). The
    full environment is inherited so the org's credentials/config reach the child unread; the engine never
    interprets or logs a secret."""
    try:
        # argv comes only from a committed manifest (no shell), so there is no injection surface.
        proc = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, check=False)
        return proc.returncode, (proc.stdout or ""), (proc.stderr or "")
    except FileNotFoundError as exc:
        return 127, "", f"hosted command not found: {exc}"


def is_hosted(manifest: dict[str, Any]) -> bool:
    """Whether a manifest selects the async hosted backend (``mode: async-hosted``)."""
    return str(manifest.get("mode") or "").strip().lower() == MODE


def _subst(template: Any, mapping: dict[str, str]) -> list[str]:
    """Substitute ``{placeholder}`` tokens in a command template; a missing key renders empty, not an error."""
    out: list[str] = []
    for token in template or []:
        try:
            out.append(str(token).format_map(_Default(mapping)))
        except (ValueError, IndexError):
            out.append(str(token))
    return out


class _Default(dict):
    def __missing__(self, key: str) -> str:  # unknown {placeholder} → empty string
        return ""


class HostedAgentRunner:
    """Drive one stage through a hosted, asynchronous agent run (RUNLIVE-FR-008).

    The manifest declares (all optional except ``trigger_command``):

    * ``trigger_command``  argv template; its stdout's last non-empty line is the run id.
    * ``poll_command``     argv template (``{run_id}`` available); its output is classified to a status.
    * ``poll_status_field``  optional JSON field to read the status from (else the raw stdout is the status).
    * ``completed_values`` / ``failed_values``  status strings meaning done / failed (case-insensitive).
    * ``collect_command``  argv template that applies the produced branch/PR into the working tree.
    * ``poll_interval_s``  seconds between polls; ``timeout_s`` bounds the whole run.
    """

    def __init__(
        self,
        settings: Settings,
        manifest: dict[str, Any],
        *,
        model: str = "",
        cwd: Optional[Path] = None,
        intent: str = "",
        spec_text: str = "",
        timeout: int = 1800,
        poll_interval: Optional[int] = None,
        command_runner: Optional[CommandRunner] = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings
        self.manifest = manifest
        self.model = model
        self.cwd = cwd or settings.root
        self.intent = intent
        self.spec_text = spec_text
        self.timeout = timeout
        self.poll_interval = (
            poll_interval
            if poll_interval is not None
            else int(manifest.get("poll_interval_s") or 10)
        )
        self._run = command_runner or run_hosted_command
        self._sleep = sleep
        self._clock = clock

    def _classify(self, out: str) -> str:
        """Map a poll command's output to ``completed`` | ``failed`` | ``running`` (case-insensitive)."""
        field = str(self.manifest.get("poll_status_field") or "").strip()
        raw = out.strip()
        if field:
            try:
                raw = str(json.loads(out).get(field, "")).strip()
            except (json.JSONDecodeError, AttributeError):
                raw = ""
        low = raw.lower()
        completed = {
            str(v).lower() for v in (self.manifest.get("completed_values") or ["completed"])
        }
        failed = {str(v).lower() for v in (self.manifest.get("failed_values") or ["failed"])}
        if low in completed:
            return "completed"
        if low in failed:
            return "failed"
        return "running"

    def dispatch(
        self,
        step: str,
        stage: str,
        *,
        spec_text: Optional[str] = None,
        context: str = "",
        file_scope: str = "",
    ) -> DispatchResult:
        """Trigger → poll → collect one stage; a failed/timed-out hosted run is a dispatch failure naming the
        stage (RUNLIVE-FR-008), never a gate verdict. No credential is read or logged (RUNLIVE-FR-009).
        The per-dispatch prompt blocks mirror :meth:`CliAgentRunner.dispatch` so a hosted stage is judged
        and contextualized identically to a local one (RUNLIVE-NFR-003, PHASE-FR-005)."""
        prompt = prompts.assemble(
            step,
            intent=self.intent,
            spec_text=self.spec_text if spec_text is None else spec_text,
            context=context,
            file_scope=file_scope,
            # The same repo-local stage-template resolution as the local runner (AGENTX-FR-005).
            body=prompts.stage_template_body(self.settings.stage_templates_dir, step),
        )
        mapping = {
            "prompt": prompt,
            "model": self.model,
            "step": step,
            "stage": stage,
            "run_id": "",
        }

        trigger = self.manifest.get("trigger_command")
        if not trigger:
            return DispatchResult(False, detail="hosted manifest declares no `trigger_command`")
        rc, out, err = self._run(_subst(trigger, mapping), self.cwd)
        if rc != 0:
            return DispatchResult(
                False, detail=f"hosted trigger failed at {stage}: {_short(err or out, rc)}"
            )
        lines = [ln for ln in out.splitlines() if ln.strip()]
        run_id = lines[-1].strip() if lines else ""
        mapping["run_id"] = run_id

        poll = self.manifest.get("poll_command")
        if poll:
            deadline = self._clock() + self.timeout
            status = "running"
            while self._clock() < deadline:
                rc, out, err = self._run(_subst(poll, mapping), self.cwd)
                if rc != 0:
                    return DispatchResult(
                        False, detail=f"hosted poll failed at {stage}: {_short(err or out, rc)}"
                    )
                status = self._classify(out)
                if status == "completed":
                    break
                if status == "failed":
                    return DispatchResult(
                        False, detail=f"hosted run failed at {stage} (run {run_id or '?'})"
                    )
                self._sleep(self.poll_interval)
            if status != "completed":
                return DispatchResult(
                    False, detail=f"hosted run timed out at {stage} after {self.timeout}s"
                )

        collect = self.manifest.get("collect_command")
        if collect:
            rc, out, err = self._run(_subst(collect, mapping), self.cwd)
            if rc != 0:
                return DispatchResult(
                    False, detail=f"hosted collect failed at {stage}: {_short(err or out, rc)}"
                )
        return DispatchResult(True, detail=f"hosted run {run_id}".strip(), model=self.model)


def _short(text: str, rc: int) -> str:
    return (text.strip() or f"exit {rc}")[:300]
