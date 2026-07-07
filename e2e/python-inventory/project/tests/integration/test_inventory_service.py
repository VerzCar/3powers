from __future__ import annotations

import pytest

from inventory.config.settings import InventoryConfig
from inventory.domain.models import StockItem
from inventory.errors import InventoryError
from inventory.logging.logger import MemoryLogger
from inventory.service.inventory_service import InventoryService


def _service() -> tuple[InventoryService, MemoryLogger]:
    logger = MemoryLogger()
    config = InventoryConfig(default_reorder_threshold=5, thresholds={"WIDGET": 10})
    service = InventoryService(config, logger)
    service.add_item(StockItem(sku="WIDGET", on_hand=12))
    service.add_item(StockItem(sku="GADGET", on_hand=8))
    return service, logger


def test_reserve_updates_availability_across_the_domain() -> None:
    service, _ = _service()
    updated = service.reserve("WIDGET", 4)
    assert updated.available == 8
    assert service.get("WIDGET").reserved == 4


def test_reserve_records_one_structured_log_entry() -> None:
    service, logger = _service()
    service.reserve("GADGET", 2)
    assert len(logger.entries) == 1
    assert logger.entries[0].message == "reserved stock"
    assert logger.entries[0].fields["available"] == 6


def test_is_low_uses_per_sku_threshold() -> None:
    service, _ = _service()
    # WIDGET threshold is 10; reserving 3 leaves 9 available -> low.
    service.reserve("WIDGET", 3)
    assert service.is_low("WIDGET") is True
    # GADGET uses the default threshold 5; 8 available -> not low.
    assert service.is_low("GADGET") is False


def test_release_returns_units_to_availability() -> None:
    service, _ = _service()
    service.reserve("GADGET", 5)
    service.release("GADGET", 2)
    assert service.get("GADGET").available == 5


def test_unknown_sku_raises_typed_error() -> None:
    service, _ = _service()
    with pytest.raises(InventoryError) as excinfo:
        service.get("NOPE")
    assert excinfo.value.code == "UNKNOWN_SKU"


def test_reserving_more_than_available_propagates_domain_error() -> None:
    service, _ = _service()
    with pytest.raises(InventoryError) as excinfo:
        service.reserve("GADGET", 99)
    assert excinfo.value.code == "INSUFFICIENT_STOCK"
