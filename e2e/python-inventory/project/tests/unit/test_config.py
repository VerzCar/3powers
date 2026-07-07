from __future__ import annotations

import pytest

from inventory.config.settings import InventoryConfig
from inventory.errors import InventoryError


def test_threshold_falls_back_to_default() -> None:
    config = InventoryConfig(default_reorder_threshold=5)
    assert config.threshold_for("A") == 5


def test_per_sku_override_wins() -> None:
    config = InventoryConfig(default_reorder_threshold=5, thresholds={"A": 20})
    assert config.threshold_for("A") == 20
    assert config.threshold_for("B") == 5


def test_rejects_negative_default_threshold() -> None:
    with pytest.raises(InventoryError) as excinfo:
        InventoryConfig(default_reorder_threshold=-1)
    assert excinfo.value.code == "INVALID_QUANTITY"
