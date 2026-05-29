"""Tests for the JSON API, exercising the full request/response cycle."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app


@pytest.fixture
def client(session):
    """A TestClient whose DB dependency is the isolated in-memory test session."""
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _food_id(client) -> int:
    cats = client.get("/api/categories").json()
    return next(c["id"] for c in cats if c["name"] == "Food")


def test_list_categories_includes_subcategories(client):
    resp = client.get("/api/categories")
    assert resp.status_code == 200
    food = next(c for c in resp.json() if c["name"] == "Food")
    sub_names = {s["name"] for s in food["subcategories"]}
    assert "Groceries" in sub_names


def test_create_manual_transaction_with_category_is_confirmed(client):
    food = _food_id(client)
    resp = client.post(
        "/api/transactions",
        json={
            "date": "2026-05-10T12:00:00",
            "amount": "9.99",
            "raw_merchant": "CORNER STORE",
            "category_id": food,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "confirmed"
    assert body["category_id"] == food


def test_create_transaction_without_category_goes_to_review(client):
    resp = client.post(
        "/api/transactions",
        json={
            "date": "2026-05-10T12:00:00",
            "amount": "9.99",
            "raw_merchant": "UNKNOWN VENDOR",
        },
    )
    assert resp.json()["status"] == "needs_review"


def test_update_with_learn_creates_rule_for_next_time(client):
    food = _food_id(client)
    # Two unknown transactions from the same merchant.
    first = client.post(
        "/api/transactions",
        json={"date": "2026-05-10T12:00:00", "amount": "5.00", "raw_merchant": "POKE BOWL"},
    ).json()
    client.post(
        "/api/transactions",
        json={"date": "2026-05-11T12:00:00", "amount": "6.00", "raw_merchant": "POKE BOWL"},
    )

    # Correct the first one and ask the system to learn it.
    client.patch(
        f"/api/transactions/{first['id']}",
        json={"category_id": food, "learn": True},
    )

    # A brand-new POKE BOWL transaction should now auto-categorize.
    third = client.post(
        "/api/transactions",
        json={"date": "2026-05-12T12:00:00", "amount": "7.00", "raw_merchant": "POKE BOWL"},
    ).json()
    assert third["status"] == "auto"
    assert third["category_id"] == food


def test_filter_transactions_by_status(client):
    client.post(
        "/api/transactions",
        json={"date": "2026-05-10T12:00:00", "amount": "5.00", "raw_merchant": "X"},
    )
    resp = client.get("/api/transactions", params={"status": "needs_review"})
    assert resp.status_code == 200
    assert all(t["status"] == "needs_review" for t in resp.json())
    assert len(resp.json()) == 1


def test_analysis_endpoint(client):
    food = _food_id(client)
    client.post(
        "/api/transactions",
        json={
            "date": "2026-05-10T12:00:00",
            "amount": "40.00",
            "raw_merchant": "LOBLAWS",
            "category_id": food,
        },
    )
    resp = client.get("/api/analysis", params={"month": "2026-05"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 40.0
    assert body["transaction_count"] == 1


def test_analysis_rejects_bad_month(client):
    resp = client.get("/api/analysis", params={"month": "not-a-month"})
    assert resp.status_code == 422
