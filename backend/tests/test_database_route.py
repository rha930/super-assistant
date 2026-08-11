"""Tests for the database connectors route (GET /api/database/connectors)."""

from unittest.mock import patch

import pytest


@pytest.fixture
def client():
    # Disable auth so the endpoint is reachable anonymously in tests.
    with patch.dict("os.environ", {"AUTH_ENABLED": "False"}):
        import importlib

        import config as config_module

        importlib.reload(config_module)
        from app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as test_client:
            yield test_client


def _connectors_payload(monkeypatch, connectors):
    from services import database_service

    def _fake_list(self):
        return connectors

    monkeypatch.setattr(database_service.DatabaseConnectorService, "list_connectors", _fake_list)


class TestDatabaseConnectorsRoute:
    def test_returns_connector_list_standard_shape(self, client, monkeypatch):
        _connectors_payload(
            monkeypatch,
            [{"name": "analytics", "type": "postgresql", "status": "connected"}],
        )
        resp = client.get("/api/database/connectors")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert "message" in body
        assert body["data"]["connectors"] == [{"name": "analytics", "type": "postgresql", "status": "connected"}]

    def test_no_credentials_in_payload(self, client, monkeypatch):
        _connectors_payload(
            monkeypatch,
            [{"name": "analytics", "type": "postgresql", "status": "connected"}],
        )
        resp = client.get("/api/database/connectors")
        raw = resp.get_data(as_text=True)
        assert "url" not in raw
        assert "password" not in raw
        assert "://" not in raw

    def test_empty_list_when_none_configured(self, client, monkeypatch):
        _connectors_payload(monkeypatch, [])
        resp = client.get("/api/database/connectors")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["connectors"] == []
