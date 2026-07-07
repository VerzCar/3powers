"""Service layer over the inventory domain."""

from __future__ import annotations

from inventory.config.settings import InventoryConfig
from inventory.domain.models import StockItem, needs_reorder, release, reserve
from inventory.errors import InventoryError
from inventory.logging.logger import Logger, log_info


class InventoryService:
    """Tracks stock items and applies reservation and reorder policy."""

    def __init__(self, config: InventoryConfig, logger: Logger) -> None:
        self._config = config
        self._logger = logger
        self._items: dict[str, StockItem] = {}

    def add_item(self, item: StockItem) -> None:
        """Register (or replace) a SKU's stock item."""
        self._items[item.sku] = item

    def get(self, sku: str) -> StockItem:
        """The current stock item for a SKU, or a typed error when unknown."""
        try:
            return self._items[sku]
        except KeyError:
            raise InventoryError(f"unknown sku {sku}", "UNKNOWN_SKU") from None

    def reserve(self, sku: str, quantity: int) -> StockItem:
        """Reserve stock for a SKU and record the new availability."""
        updated = reserve(self.get(sku), quantity)
        self._items[sku] = updated
        log_info(
            self._logger,
            "reserved stock",
            sku=sku,
            quantity=quantity,
            available=updated.available,
        )
        return updated

    def release(self, sku: str, quantity: int) -> StockItem:
        """Release previously reserved stock for a SKU."""
        updated = release(self.get(sku), quantity)
        self._items[sku] = updated
        return updated

    def is_low(self, sku: str) -> bool:
        """Whether a SKU has reached its reorder threshold."""
        item = self.get(sku)
        return needs_reorder(item, self._config.threshold_for(sku))
