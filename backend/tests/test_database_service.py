"""Tests for the DatabaseConnectorService (read-only DB connector layer)."""

import sqlite3

import pytest

from services.database_service import DatabaseConnectorService


@pytest.fixture
def sqlite_db(tmp_path):
    """Create a temporary SQLite database with a seeded table."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)")
    conn.executemany(
        "INSERT INTO customers (id, name) VALUES (?, ?)",
        [(i, f"Customer {i}") for i in range(1, 11)],
    )
    conn.commit()
    conn.close()
    return str(db_path)


def _svc(sqlite_path, *, max_rows=100, extra=None):
    defs = [{"name": "analytics", "type": "sqlite", "url": f"sqlite:///{sqlite_path}"}]
    if extra:
        defs.extend(extra)
    return DatabaseConnectorService(connector_defs=defs, timeout_seconds=5, max_rows=max_rows)


# ---------------------------------------------------------------------------
# list_connectors / status
# ---------------------------------------------------------------------------
class TestListConnectors:
    def test_connected_status_for_valid_sqlite(self, sqlite_db):
        connectors = _svc(sqlite_db).list_connectors()
        assert connectors == [{"name": "analytics", "type": "sqlite", "status": "connected"}]

    def test_not_configured_for_unsupported_type(self, sqlite_db):
        extra = [{"name": "mongo", "type": "mongodb", "url": "mongodb://host/db"}]
        connectors = _svc(sqlite_db, extra=extra).list_connectors()
        mongo = next(c for c in connectors if c["name"] == "mongo")
        assert mongo["status"] == "not_configured"

    def test_not_configured_for_missing_url(self, sqlite_db):
        extra = [{"name": "empty", "type": "postgresql", "url": ""}]
        connectors = _svc(sqlite_db, extra=extra).list_connectors()
        empty = next(c for c in connectors if c["name"] == "empty")
        assert empty["status"] == "not_configured"

    def test_unreachable_when_connection_fails(self, sqlite_db, monkeypatch):
        svc = _svc(sqlite_db)

        def _boom(*_args, **_kwargs):
            raise ConnectionError("host down")

        monkeypatch.setattr(svc, "_connect", _boom)
        connectors = svc.list_connectors()
        assert connectors[0]["status"] == "unreachable"

    def test_status_never_includes_url(self, sqlite_db):
        connectors = _svc(sqlite_db).list_connectors()
        assert all("url" not in c and "credentials" not in c for c in connectors)


# ---------------------------------------------------------------------------
# execute_read_only_query — happy path
# ---------------------------------------------------------------------------
class TestExecuteReadOnly:
    def test_select_returns_expected_shape(self, sqlite_db):
        result = _svc(sqlite_db).execute_read_only_query(
            "analytics", "SELECT id, name FROM customers ORDER BY id LIMIT 3"
        )
        assert result["columns"] == ["id", "name"]
        assert result["row_count"] == 3
        assert result["truncated"] is False
        assert result["rows"][0] == [1, "Customer 1"]

    def test_with_cte_is_allowed(self, sqlite_db):
        sql = "WITH recent AS (SELECT id FROM customers) SELECT COUNT(*) FROM recent"
        result = _svc(sqlite_db).execute_read_only_query("analytics", sql)
        assert result["row_count"] == 1
        assert result["rows"][0][0] == 10

    def test_row_cap_truncation(self, sqlite_db):
        result = _svc(sqlite_db, max_rows=5).execute_read_only_query(
            "analytics", "SELECT id FROM customers ORDER BY id"
        )
        assert result["row_count"] == 5
        assert result["truncated"] is True


# ---------------------------------------------------------------------------
# execute_read_only_query — rejection & errors
# ---------------------------------------------------------------------------
class TestValidationAndErrors:
    @pytest.mark.parametrize(
        "sql",
        [
            "INSERT INTO customers (id, name) VALUES (99, 'x')",
            "UPDATE customers SET name = 'x'",
            "DELETE FROM customers",
            "DROP TABLE customers",
            "CREATE TABLE t (id INT)",
            "ALTER TABLE customers ADD COLUMN c INT",
            "TRUNCATE TABLE customers",
        ],
    )
    def test_rejects_write_statements(self, sqlite_db, sql):
        with pytest.raises(ValueError):
            _svc(sqlite_db).execute_read_only_query("analytics", sql)

    def test_rejects_multi_statement(self, sqlite_db):
        with pytest.raises(ValueError):
            _svc(sqlite_db).execute_read_only_query("analytics", "SELECT * FROM customers; DROP TABLE customers")

    def test_rejects_write_hidden_in_comment_prefixed(self, sqlite_db):
        # Leading comment then a DELETE — still must be rejected.
        with pytest.raises(ValueError):
            _svc(sqlite_db).execute_read_only_query("analytics", "-- harmless\nDELETE FROM customers")

    def test_allows_keyword_inside_string_literal(self, sqlite_db):
        # 'DROP' as data, not an operation, should be permitted.
        result = _svc(sqlite_db).execute_read_only_query(
            "analytics", "SELECT id FROM customers WHERE name = 'DROP' LIMIT 1"
        )
        assert result["row_count"] == 0

    def test_unknown_connector_raises_value_error(self, sqlite_db):
        with pytest.raises(ValueError):
            _svc(sqlite_db).execute_read_only_query("nope", "SELECT 1")

    def test_driver_failure_raises_sanitized_runtime_error(self, sqlite_db, monkeypatch):
        svc = _svc(sqlite_db)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("connection to postgresql://user:secret@host failed")

        monkeypatch.setattr(svc, "_run_query", _boom)
        with pytest.raises(RuntimeError) as exc_info:
            svc.execute_read_only_query("analytics", "SELECT 1")
        # No credentials/URL leaked in the sanitized message.
        assert "secret" not in str(exc_info.value)
        assert "postgresql://" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------
class TestIsAvailable:
    def test_true_for_reachable_connector(self, sqlite_db):
        assert _svc(sqlite_db).is_available("analytics") is True

    def test_false_for_unknown_connector(self, sqlite_db):
        assert _svc(sqlite_db).is_available("missing") is False


# ---------------------------------------------------------------------------
# get_schema
# ---------------------------------------------------------------------------
class TestGetSchema:
    def test_returns_tables_and_columns(self, sqlite_db):
        schema = _svc(sqlite_db).get_schema("analytics")
        tables = {t["name"]: t["columns"] for t in schema["tables"]}
        assert "customers" in tables
        assert tables["customers"] == ["id", "name"]

    def test_unknown_connector_returns_empty(self, sqlite_db):
        assert _svc(sqlite_db).get_schema("missing") == {"tables": []}

    def test_never_includes_sqlite_internal_tables(self, sqlite_db):
        schema = _svc(sqlite_db).get_schema("analytics")
        assert all(not t["name"].startswith("sqlite_") for t in schema["tables"])
