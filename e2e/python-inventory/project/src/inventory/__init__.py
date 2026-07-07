"""Inventory-tracking service — the public surface of the sample project.

A layered, I/O-free service: :mod:`inventory.config` holds the reorder policy,
:mod:`inventory.domain` holds pure stock rules (levels, reservations, reorder
checks), and :mod:`inventory.service` composes them. :mod:`inventory.logging` is
the small structured-logging abstraction the service depends on.
"""

from __future__ import annotations

from inventory.config.settings import InventoryConfig
from inventory.domain.models import StockItem, needs_reorder, release, reserve
from inventory.errors import InventoryError, InventoryErrorCode
from inventory.logging.logger import LogEntry, Logger, MemoryLogger, log_info
from inventory.service.inventory_service import InventoryService

__all__ = [
    "InventoryConfig",
    "InventoryError",
    "InventoryErrorCode",
    "InventoryService",
    "LogEntry",
    "Logger",
    "MemoryLogger",
    "StockItem",
    "log_info",
    "needs_reorder",
    "release",
    "reserve",
]
