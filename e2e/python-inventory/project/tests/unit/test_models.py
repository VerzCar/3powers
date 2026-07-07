from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from inventory.domain.models import StockItem, needs_reorder, release, reserve
from inventory.errors import InventoryError


def test_available_is_on_hand_minus_reserved() -> None:
    item = StockItem(sku="A", on_hand=10, reserved=3)
    assert item.available == 7


def test_rejects_reserved_exceeding_on_hand() -> None:
    with pytest.raises(InventoryError) as excinfo:
        StockItem(sku="A", on_hand=1, reserved=2)
    assert excinfo.value.code == "INVALID_RESERVATION"


def test_rejects_negative_quantities() -> None:
    with pytest.raises(InventoryError) as excinfo:
        StockItem(sku="A", on_hand=-1)
    assert excinfo.value.code == "INVALID_QUANTITY"


def test_reserve_increases_reserved() -> None:
    item = reserve(StockItem(sku="A", on_hand=10), 4)
    assert item.reserved == 4
    assert item.available == 6


def test_reserve_rejects_over_available() -> None:
    with pytest.raises(InventoryError) as excinfo:
        reserve(StockItem(sku="A", on_hand=5, reserved=4), 2)
    assert excinfo.value.code == "INSUFFICIENT_STOCK"


def test_reserve_rejects_non_positive() -> None:
    with pytest.raises(InventoryError) as excinfo:
        reserve(StockItem(sku="A", on_hand=5), 0)
    assert excinfo.value.code == "INVALID_QUANTITY"


def test_release_decreases_reserved() -> None:
    item = release(StockItem(sku="A", on_hand=10, reserved=5), 2)
    assert item.reserved == 3


def test_release_rejects_over_reserved() -> None:
    with pytest.raises(InventoryError) as excinfo:
        release(StockItem(sku="A", on_hand=10, reserved=1), 2)
    assert excinfo.value.code == "INVALID_RESERVATION"


def test_needs_reorder_at_or_below_threshold() -> None:
    assert needs_reorder(StockItem(sku="A", on_hand=3), 3) is True
    assert needs_reorder(StockItem(sku="A", on_hand=4), 3) is False


@given(
    on_hand=st.integers(min_value=0, max_value=1000),
    take=st.integers(min_value=1, max_value=1000),
)
def test_reserve_preserves_on_hand_and_conserves_availability(on_hand: int, take: int) -> None:
    item = StockItem(sku="A", on_hand=on_hand)
    if take > item.available:
        with pytest.raises(InventoryError):
            reserve(item, take)
    else:
        updated = reserve(item, take)
        assert updated.on_hand == on_hand
        assert updated.available == item.available - take
