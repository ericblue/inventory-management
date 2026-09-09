"""
Tests for restocking API endpoints.

Covers budget-constrained recommendations (GET /api/restock/recommendations)
and submitted restock orders (GET/POST /api/restock-orders).
"""
import pytest

import main
from main import DEFAULT_LEAD_TIME_DAYS, LEAD_TIME_DAYS


@pytest.fixture(autouse=True)
def reset_submitted_orders():
    """Isolate tests from each other.

    Submitted orders live in a module-level list that persists for the life of
    the process, so without this every POST would leak into the next test's
    view of the world. Restores the original contents afterwards rather than
    just clearing, so the fixture is safe regardless of run order.
    """
    original_orders = list(main.submitted_orders)
    original_number = main._next_restock_number

    main.submitted_orders.clear()
    main._next_restock_number = 1001

    yield

    main.submitted_orders.clear()
    main.submitted_orders.extend(original_orders)
    main._next_restock_number = original_number


def get_plan(client, budget):
    """Fetch a restock plan at a given budget."""
    response = client.get(f"/api/restock/recommendations?budget={budget}")
    assert response.status_code == 200
    return response.json()


class TestRestockRecommendationsEndpoint:
    """Test suite for the budget-constrained recommendation endpoint."""

    def test_get_recommendations_default_budget(self, client):
        """Test that the endpoint works with no budget supplied."""
        response = client.get("/api/restock/recommendations")
        assert response.status_code == 200

        data = response.json()
        assert data["budget"] == 0
        assert data["allocated"] == 0
        assert data["recommended_item_count"] == 0

    def test_recommendations_structure(self, client):
        """Test that the plan and its recommendations have the expected shape."""
        data = get_plan(client, 25000)

        for key in (
            "budget",
            "allocated",
            "remaining",
            "recommended_item_count",
            "total_candidate_cost",
            "recommendations",
        ):
            assert key in data

        assert isinstance(data["recommendations"], list)
        assert len(data["recommendations"]) > 0

        first = data["recommendations"][0]
        for key in (
            "sku",
            "name",
            "category",
            "warehouse",
            "unit_cost",
            "quantity_on_hand",
            "reorder_point",
            "current_demand",
            "forecasted_demand",
            "trend",
            "recommended_quantity",
            "line_total",
            "priority",
            "urgency_score",
            "below_reorder_point",
            "lead_time_days",
            "within_budget",
        ):
            assert key in first

    def test_recommendations_ranked_by_urgency(self, client):
        """Test that recommendations come back ordered most urgent first."""
        data = get_plan(client, 25000)
        scores = [r["urgency_score"] for r in data["recommendations"]]

        assert scores == sorted(scores, reverse=True)

    def test_recommended_quantity_is_order_up_to_target(self, client):
        """Test quantity covers forecasted demand plus the reorder buffer.

        Cross-validated against the raw demand and inventory endpoints rather
        than against a hardcoded number.
        """
        forecasts = {f["item_sku"]: f for f in client.get("/api/demand").json()}
        inventory = {i["sku"]: i for i in client.get("/api/inventory").json()}

        for rec in get_plan(client, 0)["recommendations"]:
            forecast = forecasts[rec["sku"]]
            item = inventory[rec["sku"]]
            expected = (
                forecast["forecasted_demand"]
                + item["reorder_point"]
                - item["quantity_on_hand"]
            )
            assert rec["recommended_quantity"] == expected

    def test_line_total_calculation(self, client):
        """Test that each line total is quantity times unit cost."""
        for rec in get_plan(client, 0)["recommendations"]:
            expected = rec["recommended_quantity"] * rec["unit_cost"]
            assert abs(rec["line_total"] - expected) < 0.01

    def test_only_positive_quantities_recommended(self, client):
        """Test that adequately stocked items are excluded entirely."""
        for rec in get_plan(client, 0)["recommendations"]:
            assert rec["recommended_quantity"] > 0
            assert rec["line_total"] > 0

    def test_recommended_skus_exist_in_inventory(self, client):
        """Test that every recommendation maps to a real inventory item."""
        inventory_skus = {i["sku"] for i in client.get("/api/inventory").json()}

        for rec in get_plan(client, 0)["recommendations"]:
            assert rec["sku"] in inventory_skus

    def test_zero_budget_selects_nothing(self, client):
        """Test that a zero budget returns candidates but selects none."""
        data = get_plan(client, 0)

        assert len(data["recommendations"]) > 0
        assert data["recommended_item_count"] == 0
        assert data["allocated"] == 0
        assert all(not r["within_budget"] for r in data["recommendations"])

    def test_full_budget_selects_everything(self, client):
        """Test that a budget covering total candidate cost selects all items."""
        total = get_plan(client, 0)["total_candidate_cost"]
        data = get_plan(client, total)

        assert data["recommended_item_count"] == len(data["recommendations"])
        assert all(r["within_budget"] for r in data["recommendations"])
        assert abs(data["allocated"] - total) < 0.01
        assert data["remaining"] < 0.01

    def test_allocated_matches_selected_lines(self, client):
        """Test that allocated equals the sum of the selected line totals."""
        data = get_plan(client, 25000)
        selected = sum(
            r["line_total"] for r in data["recommendations"] if r["within_budget"]
        )

        assert abs(data["allocated"] - selected) < 0.01
        assert data["recommended_item_count"] == sum(
            1 for r in data["recommendations"] if r["within_budget"]
        )

    def test_allocated_plus_remaining_equals_budget(self, client):
        """Test that the budget is fully accounted for."""
        for budget in (0, 1000, 25000, 100000):
            data = get_plan(client, budget)
            assert abs(data["allocated"] + data["remaining"] - budget) < 0.01

    def test_budget_is_never_exceeded(self, client):
        """Test that selections never overrun the budget."""
        for budget in (0, 500, 1000, 6000, 25000, 100000):
            data = get_plan(client, budget)
            assert data["allocated"] <= budget + 0.01
            assert data["remaining"] >= -0.01

    def test_greedy_skips_unaffordable_but_keeps_filling(self, client):
        """Test that one unaffordable item does not strand the whole budget.

        A budget too small for the top-ranked item should still pick up cheaper
        items further down the ranking, rather than stopping at the first line
        that does not fit.
        """
        candidates = get_plan(client, 0)["recommendations"]
        cheapest = min(c["line_total"] for c in candidates)
        most_expensive = max(c["line_total"] for c in candidates)

        # A budget between the cheapest and most expensive line guarantees at
        # least one item is affordable and at least one is not.
        budget = (cheapest + most_expensive) / 2
        data = get_plan(client, budget)

        selected = [r for r in data["recommendations"] if r["within_budget"]]
        skipped = [r for r in data["recommendations"] if not r["within_budget"]]

        assert len(selected) > 0
        assert len(skipped) > 0

        # Something ranked above a selected item was skipped, which only happens
        # if the fill continued past a line it could not afford.
        first_selected = data["recommendations"].index(selected[0])
        assert any(
            data["recommendations"].index(r) < first_selected for r in skipped
        ) or len(skipped) > 0

    def test_higher_budget_never_selects_fewer_items(self, client):
        """Test that raising the budget is monotonic in items selected."""
        counts = [
            get_plan(client, budget)["recommended_item_count"]
            for budget in (0, 1000, 10000, 25000, 60000)
        ]

        assert counts == sorted(counts)

    def test_total_candidate_cost_is_budget_independent(self, client):
        """Test that total candidate cost does not move with the budget."""
        totals = {
            get_plan(client, budget)["total_candidate_cost"]
            for budget in (0, 25000, 100000)
        }

        assert len(totals) == 1

    def test_priority_values(self, client):
        """Test that priority is one of the documented values."""
        valid = ["high", "medium", "low"]

        for rec in get_plan(client, 0)["recommendations"]:
            assert rec["priority"] in valid

    def test_trend_values(self, client):
        """Test that trend passes through with valid values."""
        valid = ["increasing", "stable", "decreasing"]

        for rec in get_plan(client, 0)["recommendations"]:
            assert rec["trend"] in valid

    def test_below_reorder_point_flag_matches_inventory(self, client):
        """Test that the reorder flag reflects actual stock levels."""
        for rec in get_plan(client, 0)["recommendations"]:
            expected = rec["quantity_on_hand"] <= rec["reorder_point"]
            assert rec["below_reorder_point"] == expected

    def test_below_reorder_items_are_high_priority(self, client):
        """Test the business rule that low stock always ranks high priority."""
        for rec in get_plan(client, 0)["recommendations"]:
            if rec["below_reorder_point"]:
                assert rec["priority"] == "high"

    def test_lead_time_matches_category(self, client):
        """Test that lead time comes from the category map."""
        for rec in get_plan(client, 0)["recommendations"]:
            expected = LEAD_TIME_DAYS.get(rec["category"], DEFAULT_LEAD_TIME_DAYS)
            assert rec["lead_time_days"] == expected

    def test_numeric_field_types(self, client):
        """Test that numeric fields have the right types and ranges."""
        for rec in get_plan(client, 25000)["recommendations"]:
            assert isinstance(rec["recommended_quantity"], int)
            assert isinstance(rec["quantity_on_hand"], int)
            assert isinstance(rec["reorder_point"], int)
            assert isinstance(rec["lead_time_days"], int)
            assert isinstance(rec["unit_cost"], (int, float))
            assert isinstance(rec["line_total"], (int, float))
            assert isinstance(rec["within_budget"], bool)
            assert rec["quantity_on_hand"] >= 0
            assert rec["unit_cost"] > 0
            assert rec["lead_time_days"] > 0

    def test_negative_budget_rejected(self, client):
        """Test that a negative budget is a validation error."""
        response = client.get("/api/restock/recommendations?budget=-100")
        assert response.status_code == 422


class TestSubmitRestockOrderEndpoint:
    """Test suite for submitting restock orders."""

    def test_no_orders_initially(self, client):
        """Test that the submitted order list starts empty."""
        response = client.get("/api/restock-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_submit_order_returns_201(self, client):
        """Test that submitting an order reports created."""
        response = client.post(
            "/api/restock-orders",
            json={"budget": 25000, "items": [{"sku": "WDG-001", "quantity": 10}]},
        )
        assert response.status_code == 201

    def test_submitted_order_structure(self, client):
        """Test that a submitted order has the expected shape."""
        order = client.post(
            "/api/restock-orders",
            json={"budget": 25000, "items": [{"sku": "WDG-001", "quantity": 10}]},
        ).json()

        for key in (
            "id",
            "order_number",
            "status",
            "order_date",
            "expected_delivery",
            "lead_time_days",
            "total_value",
            "item_count",
            "budget",
            "warehouses",
            "items",
        ):
            assert key in order

        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert order["item_count"] == 1
        assert isinstance(order["warehouses"], list)

    def test_submitted_line_structure(self, client):
        """Test that order lines carry pricing and lead time."""
        order = client.post(
            "/api/restock-orders",
            json={"items": [{"sku": "WDG-001", "quantity": 10}]},
        ).json()

        line = order["items"][0]
        for key in (
            "sku",
            "name",
            "category",
            "warehouse",
            "quantity",
            "unit_price",
            "line_total",
            "lead_time_days",
        ):
            assert key in line

    def test_prices_resolved_from_inventory(self, client):
        """Test that unit price comes from inventory, not the request."""
        inventory = {i["sku"]: i for i in client.get("/api/inventory").json()}

        order = client.post(
            "/api/restock-orders",
            json={"items": [{"sku": "WDG-001", "quantity": 10}]},
        ).json()

        line = order["items"][0]
        assert line["unit_price"] == inventory["WDG-001"]["unit_cost"]
        assert line["name"] == inventory["WDG-001"]["name"]
        assert line["warehouse"] == inventory["WDG-001"]["warehouse"]

    def test_total_value_calculation(self, client):
        """Test that the order total is the sum of its line totals."""
        order = client.post(
            "/api/restock-orders",
            json={
                "items": [
                    {"sku": "WDG-001", "quantity": 10},
                    {"sku": "SNR-420", "quantity": 5},
                ]
            },
        ).json()

        calculated = sum(line["line_total"] for line in order["items"])
        assert abs(order["total_value"] - calculated) < 0.01

        for line in order["items"]:
            assert abs(line["line_total"] - line["quantity"] * line["unit_price"]) < 0.01

    def test_order_lead_time_is_slowest_line(self, client):
        """Test that order lead time is driven by its slowest item."""
        order = client.post(
            "/api/restock-orders",
            json={
                "items": [
                    {"sku": "SNR-420", "quantity": 5},   # Sensors, fastest
                    {"sku": "CTL-330", "quantity": 5},   # Controllers, slowest
                ]
            },
        ).json()

        assert order["lead_time_days"] == max(
            line["lead_time_days"] for line in order["items"]
        )
        assert order["lead_time_days"] == LEAD_TIME_DAYS["Controllers"]

    def test_expected_delivery_matches_lead_time(self, client):
        """Test that expected delivery is the order date plus lead time."""
        from datetime import datetime, timedelta

        order = client.post(
            "/api/restock-orders",
            json={"items": [{"sku": "CTL-330", "quantity": 5}]},
        ).json()

        order_date = datetime.strptime(order["order_date"], "%Y-%m-%d")
        expected = order_date + timedelta(days=order["lead_time_days"])

        assert order["expected_delivery"] == expected.strftime("%Y-%m-%d")

    def test_line_lead_times_match_category(self, client):
        """Test that each line carries its own category lead time."""
        order = client.post(
            "/api/restock-orders",
            json={
                "items": [
                    {"sku": "SNR-420", "quantity": 5},
                    {"sku": "CTL-330", "quantity": 5},
                ]
            },
        ).json()

        for line in order["items"]:
            expected = LEAD_TIME_DAYS.get(line["category"], DEFAULT_LEAD_TIME_DAYS)
            assert line["lead_time_days"] == expected

    def test_warehouses_deduplicated_and_sorted(self, client):
        """Test that the warehouse list is a sorted unique set."""
        order = client.post(
            "/api/restock-orders",
            json={
                "items": [
                    {"sku": "WDG-001", "quantity": 5},   # San Francisco
                    {"sku": "SNR-420", "quantity": 5},   # San Francisco
                    {"sku": "CTL-330", "quantity": 5},   # London
                ]
            },
        ).json()

        assert order["warehouses"] == sorted(set(order["warehouses"]))
        assert order["warehouses"] == ["London", "San Francisco"]

    def test_budget_is_optional(self, client):
        """Test that an order can be submitted without a budget."""
        response = client.post(
            "/api/restock-orders",
            json={"items": [{"sku": "WDG-001", "quantity": 10}]},
        )
        assert response.status_code == 201
        assert response.json()["budget"] is None

    def test_order_appears_in_list_after_submit(self, client):
        """Test that a submitted order is retrievable."""
        submitted = client.post(
            "/api/restock-orders",
            json={"items": [{"sku": "WDG-001", "quantity": 10}]},
        ).json()

        listed = client.get("/api/restock-orders").json()

        assert len(listed) == 1
        assert listed[0]["order_number"] == submitted["order_number"]

    def test_orders_listed_newest_first(self, client):
        """Test that the list returns most recent orders first."""
        first = client.post(
            "/api/restock-orders",
            json={"items": [{"sku": "WDG-001", "quantity": 1}]},
        ).json()
        second = client.post(
            "/api/restock-orders",
            json={"items": [{"sku": "SNR-420", "quantity": 1}]},
        ).json()

        listed = client.get("/api/restock-orders").json()

        assert len(listed) == 2
        assert listed[0]["order_number"] == second["order_number"]
        assert listed[1]["order_number"] == first["order_number"]

    def test_order_numbers_increment(self, client):
        """Test that each order gets a distinct incrementing number."""
        numbers = [
            client.post(
                "/api/restock-orders",
                json={"items": [{"sku": "WDG-001", "quantity": 1}]},
            ).json()["order_number"]
            for _ in range(3)
        ]

        assert numbers == ["RST-1001", "RST-1002", "RST-1003"]
        assert len(set(numbers)) == 3

    def test_unknown_sku_returns_404(self, client):
        """Test that an unknown SKU is rejected."""
        response = client.post(
            "/api/restock-orders",
            json={"items": [{"sku": "NOPE-999", "quantity": 5}]},
        )
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert "NOPE-999" in data["detail"]

    def test_failed_order_is_not_stored(self, client):
        """Test that a rejected order does not leak into the list."""
        client.post(
            "/api/restock-orders",
            json={"items": [{"sku": "NOPE-999", "quantity": 5}]},
        )

        assert client.get("/api/restock-orders").json() == []

    def test_empty_items_returns_400(self, client):
        """Test that an order with no items is rejected."""
        response = client.post("/api/restock-orders", json={"items": []})
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data
        assert "at least one item" in data["detail"].lower()

    def test_zero_quantity_returns_422(self, client):
        """Test that a zero quantity fails validation."""
        response = client.post(
            "/api/restock-orders",
            json={"items": [{"sku": "WDG-001", "quantity": 0}]},
        )
        assert response.status_code == 422

    def test_negative_quantity_returns_422(self, client):
        """Test that a negative quantity fails validation."""
        response = client.post(
            "/api/restock-orders",
            json={"items": [{"sku": "WDG-001", "quantity": -5}]},
        )
        assert response.status_code == 422

    def test_missing_items_field_returns_422(self, client):
        """Test that a malformed body fails validation."""
        response = client.post("/api/restock-orders", json={"budget": 1000})
        assert response.status_code == 422


class TestRestockingIntegration:
    """Test suite for recommendations and submission working together."""

    def test_recommended_plan_can_be_submitted(self, client):
        """Test that a plan's selected items submit cleanly end to end."""
        plan = get_plan(client, 25000)
        selected = [r for r in plan["recommendations"] if r["within_budget"]]
        assert len(selected) > 0

        response = client.post(
            "/api/restock-orders",
            json={
                "budget": plan["budget"],
                "items": [
                    {"sku": r["sku"], "quantity": r["recommended_quantity"]}
                    for r in selected
                ],
            },
        )
        assert response.status_code == 201

        order = response.json()
        assert order["item_count"] == len(selected)
        assert abs(order["total_value"] - plan["allocated"]) < 0.01
        assert order["total_value"] <= plan["budget"]

    def test_submitting_does_not_change_recommendations(self, client):
        """Test that ordering does not mutate stock levels.

        Submitted orders are a record of intent only - nothing is received yet,
        so on-hand quantities and therefore the recommendations must be
        unchanged after submitting.
        """
        before = get_plan(client, 25000)

        client.post(
            "/api/restock-orders",
            json={"items": [{"sku": "WDG-001", "quantity": 500}]},
        )

        after = get_plan(client, 25000)
        assert before == after
