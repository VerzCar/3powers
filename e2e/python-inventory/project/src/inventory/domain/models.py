"""Pure inventory domain rules — stock levels, reservations, reorder checks.

All operations are pure functions over immutable :class:`StockItem` values: they
return a new item rather than mutating in place, and raise :class:`InventoryError`
on any invalid transition.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from inventory.errors import InventoryError


@dataclass(frozen=True)
class StockItem:
    """On-hand and reserved quantities for a single SKU."""

    sku: str
    on_hand: int
    reserved: int = 0

    def __post_init__(self) -> None:
        if self.on_hand < 0:
            raise InventoryError(
                f"on_hand must be non-negative, got {self.on_hand}", "INVALID_QUANTITY"
            )
        if self.reserved < 0:
            raise InventoryError(
                f"reserved must be non-negative, got {self.reserved}", "INVALID_QUANTITY"
            )
        if self.reserved > self.on_hand:
            raise InventoryError(
                f"reserved ({self.reserved}) cannot exceed on_hand ({self.on_hand})",
                "INVALID_RESERVATION",
            )

    @property
    def available(self) -> int:
        """Units free to reserve — on hand minus already reserved."""
        return self.on_hand - self.reserved


def reserve(item: StockItem, quantity: int) -> StockItem:
    """Reserve ``quantity`` units, returning the updated item."""
    if quantity <= 0:
        raise InventoryError(
            f"reserve quantity must be positive, got {quantity}", "INVALID_QUANTITY"
        )
    if quantity > item.available:
        raise InventoryError(
            f"cannot reserve {quantity}; only {item.available} available for {item.sku}",
            "INSUFFICIENT_STOCK",
        )
    return replace(item, reserved=item.reserved + quantity)


def release(item: StockItem, quantity: int) -> StockItem:
    """Release ``quantity`` previously reserved units, returning the updated item."""
    if quantity <= 0:
        raise InventoryError(
            f"release quantity must be positive, got {quantity}", "INVALID_QUANTITY"
        )
    if quantity > item.reserved:
        raise InventoryError(
            f"cannot release {quantity}; only {item.reserved} reserved for {item.sku}",
            "INVALID_RESERVATION",
        )
    return replace(item, reserved=item.reserved - quantity)


def needs_reorder(item: StockItem, threshold: int) -> bool:
    """Whether available stock has fallen to or below the reorder threshold."""
    return item.available <= threshold
