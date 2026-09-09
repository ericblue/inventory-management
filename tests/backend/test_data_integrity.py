"""
Referential integrity guards for the seed data in server/data/.

These tests read the JSON files directly rather than going through the API,
because the point is to catch a broken relationship between two files before
any endpoint gets a chance to paper over it.

Background: 8 of the 9 demand-forecast SKUs once referenced items that existed
nowhere else in the app. The Demand tab never noticed, because it renders
forecast records without joining to inventory - the break only surfaced when
the Restocking feature needed a unit cost per forecast item. Nothing in the
suite asserted cross-file integrity, so there was no way for it to be caught.

Invariants that are currently violated are marked xfail(strict=True) and are
tracked in docs/KNOWN-ISSUES.md. Strict means that fixing the data turns the
test into an unexpected pass and fails the run, forcing the marker to be
removed rather than quietly left behind.
"""
import json
from collections import Counter
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent.parent / "server" / "data"


def load(name):
    """Load a seed data file by name."""
    with open(DATA_DIR / f"{name}.json") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def inventory():
    return load("inventory")


@pytest.fixture(scope="module")
def orders():
    return load("orders")


@pytest.fixture(scope="module")
def demand_forecasts():
    return load("demand_forecasts")


@pytest.fixture(scope="module")
def backlog_items():
    return load("backlog_items")


@pytest.fixture(scope="module")
def transactions():
    return load("transactions")


@pytest.fixture(scope="module")
def purchase_orders():
    return load("purchase_orders")


@pytest.fixture(scope="module")
def inventory_skus(inventory):
    return {item["sku"] for item in inventory}


class TestSkuReferentialIntegrity:
    """Every SKU referenced anywhere must resolve to an inventory item."""

    def test_demand_forecast_skus_exist_in_inventory(
        self, demand_forecasts, inventory_skus
    ):
        """Test that every forecast SKU is a real inventory item.

        This is the specific break that shipped unnoticed. Without an inventory
        record there is no unit cost, so the item cannot be budgeted, priced,
        or ordered.
        """
        orphans = sorted(
            {f["item_sku"] for f in demand_forecasts} - inventory_skus
        )
        assert not orphans, f"demand_forecasts.json references unknown SKUs: {orphans}"

    def test_backlog_skus_exist_in_inventory(self, backlog_items, inventory_skus):
        """Test that every backlog SKU is a real inventory item."""
        orphans = sorted({b["item_sku"] for b in backlog_items} - inventory_skus)
        assert not orphans, f"backlog_items.json references unknown SKUs: {orphans}"

    def test_order_line_skus_exist_in_inventory(self, orders, inventory_skus):
        """Test that every order line item is a real inventory item."""
        orphans = sorted(
            {item["sku"] for order in orders for item in order["items"]}
            - inventory_skus
        )
        assert not orphans, f"orders.json references unknown SKUs: {orphans}"

    def test_purchase_orders_reference_real_backlog_items(
        self, purchase_orders, backlog_items
    ):
        """Test that purchase orders point at real backlog items."""
        backlog_ids = {b["id"] for b in backlog_items}
        orphans = sorted({p["backlog_item_id"] for p in purchase_orders} - backlog_ids)
        assert not orphans, f"purchase_orders.json references unknown backlog items: {orphans}"


class TestNameConsistency:
    """The same SKU must carry the same product name in every file."""

    def test_demand_forecast_names_match_inventory(self, demand_forecasts, inventory):
        """Test that forecast item names agree with inventory."""
        by_sku = {item["sku"]: item for item in inventory}
        mismatches = [
            (f["item_sku"], f["item_name"], by_sku[f["item_sku"]]["name"])
            for f in demand_forecasts
            if f["item_sku"] in by_sku and by_sku[f["item_sku"]]["name"] != f["item_name"]
        ]
        assert not mismatches, f"name disagreements: {mismatches}"

    def test_backlog_names_match_inventory(self, backlog_items, inventory):
        """Test that backlog item names agree with inventory."""
        by_sku = {item["sku"]: item for item in inventory}
        mismatches = [
            (b["item_sku"], b["item_name"], by_sku[b["item_sku"]]["name"])
            for b in backlog_items
            if b["item_sku"] in by_sku and by_sku[b["item_sku"]]["name"] != b["item_name"]
        ]
        assert not mismatches, f"name disagreements: {mismatches}"

    def test_order_line_names_match_inventory(self, orders, inventory):
        """Test that order line names agree with inventory."""
        by_sku = {item["sku"]: item for item in inventory}
        mismatches = sorted(
            {
                (item["sku"], item["name"], by_sku[item["sku"]]["name"])
                for order in orders
                for item in order["items"]
                if item["sku"] in by_sku and by_sku[item["sku"]]["name"] != item["name"]
            }
        )
        assert not mismatches, f"name disagreements: {mismatches}"


class TestDimensionConsistency:
    """Filter dimensions must use the same vocabulary across files."""

    def test_order_warehouses_match_inventory(self, orders, inventory):
        """Test that order warehouses use known warehouse names."""
        known = {item["warehouse"] for item in inventory}
        unknown = sorted(
            {o["warehouse"] for o in orders if o.get("warehouse")} - known
        )
        assert not unknown, f"orders.json uses unknown warehouses: {unknown}"

    def test_order_categories_match_inventory(self, orders, inventory):
        """Test that order categories use known category names.

        The warehouse and category filters are applied to inventory and orders
        with the same query parameter, so a value present in one file but not
        the other silently returns an empty result.
        """
        known = {item["category"] for item in inventory}
        unknown = sorted({o["category"] for o in orders if o.get("category")} - known)
        assert not unknown, f"orders.json uses unknown categories: {unknown}"


class TestIdentifierUniqueness:
    """Identifiers used for lookup must be unique."""

    def test_inventory_ids_unique(self, inventory):
        """Test that inventory ids are unique."""
        dupes = [i for i, n in Counter(x["id"] for x in inventory).items() if n > 1]
        assert not dupes, f"duplicate inventory ids: {dupes}"

    def test_inventory_skus_unique(self, inventory):
        """Test that inventory SKUs are unique."""
        dupes = [s for s, n in Counter(x["sku"] for x in inventory).items() if n > 1]
        assert not dupes, f"duplicate inventory SKUs: {dupes}"

    def test_backlog_ids_unique(self, backlog_items):
        """Test that backlog ids are unique."""
        dupes = [i for i, n in Counter(x["id"] for x in backlog_items).items() if n > 1]
        assert not dupes, f"duplicate backlog ids: {dupes}"

    def test_transaction_ids_unique(self, transactions):
        """Test that transaction ids are unique."""
        dupes = [i for i, n in Counter(x["id"] for x in transactions).items() if n > 1]
        assert not dupes, f"duplicate transaction ids: {dupes}"


class TestKnownIntegrityDefects:
    """Invariants that the seed data currently violates.

    Each is tracked in docs/KNOWN-ISSUES.md. These are strict xfails: fixing
    the underlying data will fail the run and prompt removal of the marker.
    """

    @pytest.mark.xfail(
        strict=True,
        reason="BUG-006: all 4 backlog items reference order numbers "
        "ORD-2025-0927..0930, but orders.json only reaches ORD-2025-0250",
    )
    def test_backlog_order_ids_exist_in_orders(self, backlog_items, orders):
        """Test that backlog items reference real orders."""
        known = {o["order_number"] for o in orders} | {o["id"] for o in orders}
        orphans = sorted({b["order_id"] for b in backlog_items} - known)
        assert not orphans, f"backlog_items.json references unknown orders: {orphans}"

    @pytest.mark.xfail(
        strict=True,
        reason="BUG-007: transactions.json uses warehouse codes A/B/C while "
        "every other file uses San Francisco/London/Tokyo",
    )
    def test_transaction_warehouses_match_inventory(self, transactions, inventory):
        """Test that transaction warehouses use known warehouse names."""
        known = {item["warehouse"] for item in inventory}
        unknown = sorted({t["warehouse"] for t in transactions} - known)
        assert not unknown, f"transactions.json uses unknown warehouses: {unknown}"

    @pytest.mark.xfail(
        strict=True,
        reason="BUG-008: 20 order records share 10 ids (201-210), so "
        "GET /api/orders/{id} can only ever reach the first of each pair",
    )
    def test_order_ids_unique(self, orders):
        """Test that order ids are unique."""
        dupes = sorted(i for i, n in Counter(o["id"] for o in orders).items() if n > 1)
        assert not dupes, f"duplicate order ids: {dupes}"

    @pytest.mark.xfail(
        strict=True,
        reason="BUG-008: the same 10 records also share order numbers",
    )
    def test_order_numbers_unique(self, orders):
        """Test that order numbers are unique."""
        dupes = sorted(
            n for n, c in Counter(o["order_number"] for o in orders).items() if c > 1
        )
        assert not dupes, f"duplicate order numbers: {dupes}"
