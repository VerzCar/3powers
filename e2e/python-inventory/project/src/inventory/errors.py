"""Typed error handling for the inventory domain.

Every failure path raises an :class:`InventoryError` carrying a stable, machine
readable ``code`` so callers branch on the code rather than parsing messages.
"""

from __future__ import annotations

from typing import Literal

InventoryErrorCode = Literal[
    "INSUFFICIENT_STOCK",
    "INVALID_QUANTITY",
    "INVALID_RESERVATION",
    "UNKNOWN_SKU",
]


class InventoryError(Exception):
    """A domain error with a stable, typed code."""

    def __init__(self, message: str, code: InventoryErrorCode) -> None:
        super().__init__(message)
        self.code: InventoryErrorCode = code
