"""A small structured-logging abstraction.

The service depends on the :class:`Logger` protocol only, so callers can supply an
in-memory recorder in tests or a transport-backed logger in production without
touching domain code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class LogEntry:
    """One structured log record."""

    level: str
    message: str
    fields: dict[str, object] = field(default_factory=dict)


class Logger(Protocol):
    def log(self, entry: LogEntry) -> None: ...


class MemoryLogger:
    """Collects log entries in memory — the default in tests and I/O-free code."""

    def __init__(self) -> None:
        self.entries: list[LogEntry] = []

    def log(self, entry: LogEntry) -> None:
        self.entries.append(entry)


def log_info(logger: Logger, message: str, **fields: object) -> None:
    """Emit an info-level entry through any logger."""
    logger.log(LogEntry(level="info", message=message, fields=dict(fields)))
