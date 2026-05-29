"""Tests for the optional HTTP Basic auth gate."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app


@pytest.fixture
def client(session):
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_api_open_when_no_password_set(client, monkeypatch):
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    assert client.get("/api/categories").status_code == 200


def test_api_rejects_without_credentials_when_password_set(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    assert client.get("/api/categories").status_code == 401


def test_api_accepts_correct_credentials(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_USERNAME", "kayla")
    resp = client.get("/api/categories", auth=("kayla", "s3cret"))
    assert resp.status_code == 200


def test_api_rejects_wrong_password(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    resp = client.get("/api/categories", auth=("me", "wrong"))
    assert resp.status_code == 401
