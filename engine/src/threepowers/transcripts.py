"""Persisted per-attempt agent transcripts, credential-redacted (AUTOX-FR-008, AUTOX-NFR-002).

Every stage attempt's stdout/stderr is teed to ``.3powers/runs/<spec-id>/<NN>-<step>-attempt<K>.log``
(the ``runs/`` directory init already creates) — including when the run streams to a TTY, which
previously captured nothing — so diagnosing a failed run never depends on scrollback or a 400-character
excerpt. Known credential-shaped environment values are redacted BEFORE any byte is persisted; the
environment passed through to the child agent process is untouched (EXEC-FR-012 / RUNLIVE-FR-009).
Failure messages and ledger records carry the transcript *path*, never the content.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import IO, Mapping, Optional

from .orchestrate import step_index

REDACTED = "«redacted»"

# Environment-variable NAMES whose values are treated as credentials (AUTOX-NFR-002). Deliberately
# broad — a redacted non-secret (e.g. a key *path*) costs a little readability; a leaked secret is
# unrecoverable. Values shorter than the floor are skipped so trivial strings ("1", "on") are never
# scrubbed out of ordinary output.
_CREDENTIAL_NAME = re.compile(r"(?i)(token|secret|passw(or)?d|credential|api[-_]?key|[-_]key|auth)")
_MIN_SECRET_LEN = 8


def credential_values(env: Optional[Mapping[str, str]] = None) -> list[str]:
    """The environment values that look like credentials, longest first (AUTOX-NFR-002).

    Longest-first matters: with overlapping values, replacing the longer one first can never leave a
    recognizable suffix of it behind."""
    src = os.environ if env is None else env
    vals = {
        v for k, v in src.items() if v and len(v) >= _MIN_SECRET_LEN and _CREDENTIAL_NAME.search(k)
    }
    return sorted(vals, key=len, reverse=True)


def redact(text: str, values: list[str]) -> str:
    """Replace every occurrence of each credential value with ``«redacted»``."""
    for v in values:
        text = text.replace(v, REDACTED)
    return text


def _safe_id(spec_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", spec_id or "RUN") or "RUN"


class RedactingWriter:
    """A minimal text sink that redacts credential values before every write (AUTOX-NFR-002).

    Line-buffered enough for our use: agent output is pumped line by line, so a credential value is
    always contained in one write call."""

    def __init__(self, fh: IO[str], values: list[str]) -> None:
        self._fh = fh
        self._values = values

    def write(self, s: str) -> None:
        self._fh.write(redact(s, self._values))

    def flush(self) -> None:
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


class TranscriptSink:
    """Allocates the per-attempt transcript files for one run (AUTOX-FR-008).

    One sink per ``3pwr run`` invocation, shared by the coder and oracle backends: attempts are
    numbered per step, and the path layout ``<NN>-<step>-attempt<K>.log`` orders files by lifecycle
    position. ``open`` returns ``(path, writer)`` — the writer redacts credentials on every write."""

    def __init__(self, root: Path, spec_id: str, env: Optional[Mapping[str, str]] = None) -> None:
        safe = _safe_id(spec_id)
        self.dir = root / ".3powers" / "runs" / safe
        self.rel_dir = f".3powers/runs/{safe}"
        self._values = credential_values(env)
        self._attempts: dict[str, int] = {}

    def redact_text(self, text: str) -> str:
        """Redact credential values from ``text`` (for excerpts persisted outside the transcript)."""
        return redact(text, self._values)

    def open(self, step: str) -> tuple[Path, RedactingWriter]:
        k = self._attempts.get(step, 0) + 1
        self._attempts[step] = k
        idx = max(step_index(step), 0)
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / f"{idx:02d}-{step}-attempt{k}.log"
        return path, RedactingWriter(path.open("w", encoding="utf-8"), self._values)
