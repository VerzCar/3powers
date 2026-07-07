"""Static configuration for the inventory service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from inventory.errors import InventoryError


@dataclass(frozen=True)
class InventoryConfig:
    """Reorder policy: a default low-stock threshold plus per-SKU overrides."""

    default_reorder_threshold: int
    thresholds: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.default_reorder_threshold < 0:
            raise InventoryError(
                f"default_reorder_threshold must be non-negative, "
                f"got {self.default_reorder_threshold}",
                "INVALID_QUANTITY",
            )

    def threshold_for(self, sku: str) -> int:
        """The reorder threshold for a SKU — its override, else the default."""
        return self.thresholds.get(sku, self.default_reorder_threshold)
