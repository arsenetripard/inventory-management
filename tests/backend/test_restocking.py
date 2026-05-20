"""
Tests for restocking-orders API endpoints.
"""
from datetime import datetime, timedelta

import pytest

from mock_data import restocking_orders


@pytest.fixture(autouse=True)
def reset_restocking_orders():
    """Ensure each test starts with an empty restocking_orders list."""
    restocking_orders.clear()
    yield
    restocking_orders.clear()


def _sample_request_body():
    return {
        "budget": 50000,
        "items": [
            {
                "sku": "SNR-420",
                "name": "Temperature Sensor Module",
                "quantity": 100,
                "unit_cost": 45.50,
                "line_total": 4550.00,
            },
            {
                "sku": "CTL-330",
                "name": "Logic Controller Board",
                "quantity": 25,
                "unit_cost": 120.00,
                "line_total": 3000.00,
            },
        ],
    }


class TestCreateRestockingOrder:
    """Test suite for POST /api/restocking-orders."""

    def test_create_returns_200(self, client):
        response = client.post("/api/restocking-orders", json=_sample_request_body())
        assert response.status_code == 200

    def test_create_returns_required_fields(self, client):
        response = client.post("/api/restocking-orders", json=_sample_request_body())
        data = response.json()

        assert "id" in data
        assert "submitted_date" in data
        assert "expected_delivery" in data
        assert "status" in data
        assert "budget" in data
        assert "total_value" in data
        assert "items" in data

    def test_create_sets_submitted_status(self, client):
        response = client.post("/api/restocking-orders", json=_sample_request_body())
        assert response.json()["status"] == "Submitted"

    def test_create_id_is_prefixed(self, client):
        response = client.post("/api/restocking-orders", json=_sample_request_body())
        assert response.json()["id"].startswith("RST-")

    def test_create_total_value_matches_line_totals(self, client):
        body = _sample_request_body()
        response = client.post("/api/restocking-orders", json=body)
        expected_total = sum(item["line_total"] for item in body["items"])
        assert response.json()["total_value"] == expected_total

    def test_create_preserves_items(self, client):
        body = _sample_request_body()
        response = client.post("/api/restocking-orders", json=body)
        items = response.json()["items"]
        assert len(items) == len(body["items"])
        assert items[0]["sku"] == body["items"][0]["sku"]
        assert items[0]["quantity"] == body["items"][0]["quantity"]

    def test_expected_delivery_is_14_days_after_submitted(self, client):
        response = client.post("/api/restocking-orders", json=_sample_request_body())
        data = response.json()

        submitted = datetime.fromisoformat(data["submitted_date"])
        expected = datetime.fromisoformat(data["expected_delivery"])
        delta = expected - submitted
        assert delta == timedelta(days=14)

    def test_submitted_date_is_timezone_aware(self, client):
        """Submitted date must include timezone info so JS parses it as UTC."""
        response = client.post("/api/restocking-orders", json=_sample_request_body())
        data = response.json()

        submitted = datetime.fromisoformat(data["submitted_date"])
        assert submitted.tzinfo is not None, \
            "submitted_date must be timezone-aware to avoid client timezone bugs"

    def test_create_persists_to_list(self, client):
        client.post("/api/restocking-orders", json=_sample_request_body())
        assert len(restocking_orders) == 1

    def test_create_validates_missing_fields(self, client):
        response = client.post("/api/restocking-orders", json={"budget": 50000})
        assert response.status_code == 422

    def test_create_validates_item_structure(self, client):
        bad_body = {
            "budget": 50000,
            "items": [{"sku": "SNR-420"}],
        }
        response = client.post("/api/restocking-orders", json=bad_body)
        assert response.status_code == 422


class TestGetRestockingOrders:
    """Test suite for GET /api/restocking-orders."""

    def test_get_empty_list(self, client):
        response = client.get("/api/restocking-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_returns_created_order(self, client):
        create_response = client.post("/api/restocking-orders", json=_sample_request_body())
        created_id = create_response.json()["id"]

        get_response = client.get("/api/restocking-orders")
        assert get_response.status_code == 200

        orders = get_response.json()
        assert len(orders) == 1
        assert orders[0]["id"] == created_id

    def test_get_returns_multiple_orders(self, client):
        client.post("/api/restocking-orders", json=_sample_request_body())
        client.post("/api/restocking-orders", json=_sample_request_body())

        response = client.get("/api/restocking-orders")
        assert len(response.json()) == 2
