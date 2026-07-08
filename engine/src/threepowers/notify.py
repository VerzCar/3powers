"""Human-gate notifications — opt-in, best-effort channels for a paused/failed/completed run.

When ``3pwr run`` pauses at a human gate, fails, or completes, the operator may be away from the
terminal. This module routes those three event kinds to the channels configured in
``.3powers/config/notifications.yaml``: reference senders for **Slack**,
**Microsoft Teams**, **email**, and the **local desktop** (macOS first), all standard-library only —
no SDK, no new dependency.

The trust isolation is absolute: notifications are **disabled by default** and are a
convenience signal, never a trust or enforcement channel. A channel error, timeout, or absence never
blocks, delays, fails, or alters the run, its verdict bytes, its exit code, or the ledger —
:func:`dispatch` never raises; it returns at most one-line warnings. Secrets (webhook URLs, SMTP
credentials) are referenced from the ENVIRONMENT and never stored in the repo or written to the
ledger, transcripts, or warnings. With no channel configured,
no network call is made at any point.
"""

from __future__ import annotations

import json
import smtplib
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Mapping

import yaml

# The notifiable event kinds and the default routing.
EVENT_GATE = "gate"
EVENT_FAILURE = "failure"
EVENT_COMPLETION = "completion"
DEFAULT_EVENTS: tuple[str, ...] = (EVENT_GATE, EVENT_FAILURE, EVENT_COMPLETION)

# The reference channel types.
CHANNEL_TYPES: tuple[str, ...] = ("slack", "teams", "email", "desktop")

# Default environment variables the webhook channels read their URL from.
_DEFAULT_WEBHOOK_ENV = {"slack": "THREEPOWERS_SLACK_WEBHOOK", "teams": "THREEPOWERS_TEAMS_WEBHOOK"}
_DEFAULT_SMTP_PASSWORD_ENV = "THREEPOWERS_SMTP_PASSWORD"

# Keys the loader recognizes on a channel entry — anything else warns once.
_KNOWN_KEYS = {
    "type",
    "enabled",
    "events",
    "timeout_s",
    "webhook_env",
    "host",
    "port",
    "to",
    "from",
    "user",
    "password_env",
    "starttls",
}


@dataclass(frozen=True)
class Channel:
    """One configured notification channel: its type, the events it receives, and its options."""

    type: str
    events: tuple[str, ...] = DEFAULT_EVENTS
    options: Mapping[str, Any] = field(default_factory=dict)

    @property
    def timeout(self) -> float:
        """The per-delivery timeout in seconds (bounded so delivery can never stall a run)."""
        try:
            t = float(self.options.get("timeout_s") or 5.0)
        except (TypeError, ValueError):
            t = 5.0
        return t if 0 < t <= 30 else 5.0


def load_channels(path: Path) -> tuple[list[Channel], list[str]]:
    """The configured channels + at most one warning per problem, tolerantly.

    A missing file disables notifications silently; a malformed file, a non-list ``channels``, an
    unknown channel type, or an unknown key each yield a one-line warning and the offending part is
    skipped — the run always proceeds (mirrors the ``ui.yaml`` tolerance)."""
    if not path.exists():
        return [], []
    warnings: list[str] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return [], [f"{path.name} is malformed — notifications disabled for this run"]
    if data is None:
        return [], []
    if not isinstance(data, dict):
        return [], [f"{path.name} is not a mapping — notifications disabled for this run"]
    raw = data.get("channels")
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return [], [f"{path.name}: 'channels' must be a list — notifications disabled for this run"]
    channels: list[Channel] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            warnings.append(f"{path.name}: channel #{i + 1} is not a mapping — skipped")
            continue
        ctype = str(item.get("type") or "").strip().lower()
        if ctype not in CHANNEL_TYPES:
            warnings.append(
                f"{path.name}: channel #{i + 1} has unknown type {ctype!r} "
                f"(known: {', '.join(CHANNEL_TYPES)}) — skipped"
            )
            continue
        unknown = sorted(set(item) - _KNOWN_KEYS)
        if unknown:
            warnings.append(
                f"{path.name}: channel #{i + 1} ({ctype}) has unknown key(s) "
                f"{', '.join(unknown)} — ignored"
            )
        if item.get("enabled") is False:
            continue
        events_raw = item.get("events")
        if events_raw is None:
            events = DEFAULT_EVENTS
        else:
            listed = events_raw if isinstance(events_raw, list) else [events_raw]
            events = tuple(str(e).strip().lower() for e in listed if str(e).strip())
            bad = [e for e in events if e not in DEFAULT_EVENTS]
            if bad:
                warnings.append(
                    f"{path.name}: channel #{i + 1} ({ctype}) routes unknown event(s) "
                    f"{', '.join(bad)} — ignored"
                )
            events = tuple(e for e in events if e in DEFAULT_EVENTS) or DEFAULT_EVENTS
        channels.append(Channel(type=ctype, events=events, options=dict(item)))
    return channels, warnings


# --------------------------------------------------------------------------- reference senders (seams)
# Module-level so tests monkeypatch them — no live egress is ever needed to prove routing/content.
def _post_json(url: str, payload: dict, timeout: float) -> None:
    """POST a JSON payload (the Slack/Teams incoming-webhook shape). Standard library only."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # The URL comes from the operator's OWN environment variable — never from repo content.
    with urllib.request.urlopen(req, timeout=timeout):
        pass


def _send_email(
    host: str,
    port: int,
    msg: EmailMessage,
    *,
    user: str,
    password: str,
    starttls: bool,
    timeout: float,
) -> None:
    """Send one message over SMTP (standard library). Credentials come from the environment."""
    with smtplib.SMTP(host, port, timeout=timeout) as smtp:
        if starttls:
            smtp.starttls()
        if user:
            smtp.login(user, password)
        smtp.send_message(msg)


def _display_desktop(title: str, body: str, timeout: float) -> None:
    """A local desktop notification — macOS ``osascript`` first (the documented target platform)."""
    if sys.platform != "darwin":
        raise OSError("desktop notifications are supported on macOS only")
    # ensure_ascii must stay OFF: AppleScript cannot parse JSON's \uXXXX escapes, and the gate
    # message carries typographic characters (· — ⏸) — escaped, osascript fails on every gate.
    body_lit = json.dumps(body, ensure_ascii=False)
    title_lit = json.dumps(title, ensure_ascii=False)
    script = f"display notification {body_lit} with title {title_lit}"
    subprocess.run(
        ["osascript", "-e", script], check=True, capture_output=True, timeout=timeout, text=True
    )


def _deliver(channel: Channel, subject: str, message: str, env: Mapping[str, str]) -> str:
    """Deliver one message to one channel; ``""`` on success, else a one-line warning.

    Warnings NAME a missing environment variable but never leak its value."""
    opts = channel.options
    if channel.type in ("slack", "teams"):
        env_name = str(opts.get("webhook_env") or _DEFAULT_WEBHOOK_ENV[channel.type])
        url = env.get(env_name, "")
        if not url:
            return (
                f"channel {channel.type}: environment variable {env_name} is not set — "
                "channel skipped"
            )
        _post_json(url, {"text": message}, channel.timeout)
        return ""
    if channel.type == "email":
        host = str(opts.get("host") or "")
        to = opts.get("to")
        recipients = [str(t) for t in to] if isinstance(to, list) else [str(to or "")]
        recipients = [r for r in recipients if r]
        if not host or not recipients:
            return "channel email: 'host' and 'to' are required — channel skipped"
        user = str(opts.get("user") or "")
        password = ""
        if user:
            env_name = str(opts.get("password_env") or _DEFAULT_SMTP_PASSWORD_ENV)
            password = env.get(env_name, "")
            if not password:
                return (
                    f"channel email: environment variable {env_name} is not set — channel skipped"
                )
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = str(opts.get("from") or "3pwr@localhost")
        msg["To"] = ", ".join(recipients)
        msg.set_content(message)
        try:
            port = int(opts.get("port") or 587)
        except (TypeError, ValueError):
            port = 587
        _send_email(
            host,
            port,
            msg,
            user=user,
            password=password,
            starttls=bool(opts.get("starttls", True)),
            timeout=channel.timeout,
        )
        return ""
    if channel.type == "desktop":
        _display_desktop(subject, message, channel.timeout)
        return ""
    return f"channel {channel.type}: unknown type — skipped"


def dispatch(
    channels: list[Channel],
    event: str,
    subject: str,
    message: str,
    *,
    env: Mapping[str, str] | None = None,
) -> list[str]:
    """Fire ``event`` at every channel routed to it — best-effort, never raising.

    Returns the (possibly empty) list of one-line delivery warnings. A misconfigured, unreachable, or
    timing-out channel yields a warning and nothing else — the caller's run, verdict, exit code, and
    ledger are exactly what they would be with no channel configured. With ``channels`` empty this
    returns immediately and touches no network."""
    if not channels:
        return []
    import os

    resolved_env: Mapping[str, str] = os.environ if env is None else env
    warnings: list[str] = []
    for ch in channels:
        if event not in ch.events:
            continue
        try:
            warn = _deliver(ch, subject, message, resolved_env)
        except Exception as exc:  # delivery must NEVER take the run down
            warn = f"channel {ch.type}: delivery failed ({exc.__class__.__name__})"
        if warn:
            warnings.append(warn)
    return warnings


# --------------------------------------------------------------------------- message builders (pure)
def gate_message(
    spec_id: str,
    gate: str,
    stage: str,
    gate_fr: str,
    artifact: str,
    actions: list[tuple[str, str]],
) -> str:
    """The actionable gate-pause message: spec id, stage/gate, the artifact to review,
    and the exact approve/reject/revise commands with the spec id filled in. Pure and
    deterministic."""
    fr = f" ({gate_fr})" if gate_fr else ""
    lines = [f"3pwr run {spec_id}: paused at human gate '{gate}'{fr} — stage {stage}"]
    if artifact:
        lines.append(f"review: {artifact}")
    lines.extend(f"{name}: {cmd}" for name, cmd in actions)
    return "\n".join(lines)


def failure_message(spec_id: str, failure_class: str, stage: str) -> str:
    """The actionable failure message: the failure class, where, and how to resume."""
    where = f" at {stage}" if stage else ""
    return (
        f"3pwr run {spec_id}: {failure_class}{where} — resume: "
        f"3pwr run --resume --spec-id {spec_id}"
    )


def completion_message(spec_id: str) -> str:
    """The completion notice."""
    return f"3pwr run {spec_id}: lifecycle complete — advanced to Ship"
