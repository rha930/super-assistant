"""Read-only database connector service for the agent.

Parses named database connectors from environment-derived definitions, reports
their live connection status for the Settings UI, and executes strictly
read-only (SELECT / WITH ... SELECT) queries with a bounded timeout and row cap.

Security notes:
- Connection URLs/credentials are kept private to this service. They are never
  returned by any method, logged, or included in error messages.
- Only single SELECT/WITH statements are allowed; every other statement type and
  multi-statement input is rejected before reaching a driver.
"""

import contextlib
import logging
import re
import sqlite3
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Statement-level keywords that indicate a write/DDL/dangerous operation.
_FORBIDDEN_KEYWORDS = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
        "EXEC",
        "EXECUTE",
        "CALL",
        "MERGE",
        "REPLACE",
        "PRAGMA",
        "ATTACH",
        "DETACH",
        "VACUUM",
    }
)

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _strip_sql_comments(sql: str) -> str:
    """Remove -- line comments and /* */ block comments from a SQL string."""
    # Block comments (non-greedy, across newlines).
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Line comments.
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql.strip()


class DatabaseConnectorService:
    """Manages named read-only database connectors."""

    SUPPORTED_TYPES = frozenset({"postgresql", "mysql", "sqlite"})

    def __init__(
        self,
        connector_defs: list[dict] | None = None,
        timeout_seconds: int = 10,
        max_rows: int = 100,
    ):
        """
        Args:
            connector_defs: [{name, type, url}] parsed from env; url kept private.
            timeout_seconds: per-query timeout.
            max_rows: maximum number of rows returned by a query.
        """
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.max_rows = max(1, int(max_rows))
        # name -> {type, url, is_configured}
        self._connectors: dict[str, dict] = {}
        for definition in connector_defs or []:
            self._register(definition)

    def _register(self, definition: dict) -> None:
        name = str(definition.get("name", "")).strip()
        if not name:
            return
        db_type = str(definition.get("type", "")).strip().lower()
        url = str(definition.get("url", "")).strip()
        is_configured = bool(url) and db_type in self.SUPPORTED_TYPES
        if db_type not in self.SUPPORTED_TYPES:
            logger.warning("Connector %r has unsupported type %r; marked not configured", name, db_type)
        self._connectors[name] = {"type": db_type, "url": url, "is_configured": is_configured}

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def list_connectors(self) -> list[dict]:
        """Return [{name, type, status}] — never includes url/credentials."""
        result: list[dict] = []
        for name, meta in self._connectors.items():
            if not meta["is_configured"]:
                status = "not_configured"
            elif self._check_connectivity(name, meta):
                status = "connected"
            else:
                status = "unreachable"
            result.append({"name": name, "type": meta["type"], "status": status})
        return result

    def is_available(self, connector_name: str) -> bool:
        """True if connector exists, is configured, and is currently reachable."""
        meta = self._connectors.get(connector_name)
        if not meta or not meta["is_configured"]:
            return False
        return self._check_connectivity(connector_name, meta)

    def _check_connectivity(self, name: str, meta: dict) -> bool:
        """Run a lightweight `SELECT 1` against the connector with a short timeout."""
        try:
            conn = self._connect(meta)
        except Exception as exc:  # noqa: BLE001 - connectivity is best-effort
            logger.warning("Connector %r unreachable: %s", name, type(exc).__name__)
            return False
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Connector %r connectivity check failed: %s", name, type(exc).__name__)
            return False
        finally:
            with contextlib.suppress(Exception):
                conn.close()

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------
    def execute_read_only_query(self, connector_name: str, sql: str) -> dict:
        """Validate and run a single read-only SELECT/WITH query.

        Returns { columns, rows, row_count, truncated }.
        Raises ValueError for an unknown connector or non-SELECT SQL.
        Raises RuntimeError for execution failures (sanitized message only).
        """
        meta = self._connectors.get(connector_name)
        if meta is None:
            raise ValueError(f"Unknown database connector '{connector_name}'.")
        if not meta["is_configured"]:
            raise ValueError(f"Database connector '{connector_name}' is not configured.")

        self._validate_read_only(sql)

        try:
            return self._run_query(meta, sql)
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001 - sanitize any driver error
            logger.warning("Query on connector %r failed: %s", connector_name, type(exc).__name__)
            raise RuntimeError(f"Query execution failed: {type(exc).__name__}") from None

    @staticmethod
    def _validate_read_only(sql: str) -> None:
        """Raise ValueError unless sql is a single SELECT/WITH ... SELECT statement."""
        if not sql or not sql.strip():
            raise ValueError("Empty SQL statement.")
        cleaned = _strip_sql_comments(sql)
        if not cleaned:
            raise ValueError("SQL contains no executable statement.")
        # Reject multiple statements — allow a single optional trailing semicolon.
        without_trailing = cleaned.rstrip(";").rstrip()
        if ";" in without_trailing:
            raise ValueError("Only a single SQL statement is permitted.")

        first_word = (_WORD_RE.search(without_trailing) or _EMPTY_MATCH).group(0).upper()
        if first_word not in {"SELECT", "WITH"}:
            raise ValueError("Only read-only SELECT (or WITH ... SELECT) queries are permitted.")

        # Strip quoted string literals so keywords inside them aren't flagged.
        for_keywords = re.sub(r"'[^']*'", " ", without_trailing)
        for_keywords = re.sub(r'"[^"]*"', " ", for_keywords)
        # Reject any forbidden keyword appearing as a standalone SQL token.
        tokens = {t.upper() for t in _WORD_RE.findall(for_keywords)}
        forbidden = tokens & _FORBIDDEN_KEYWORDS
        if forbidden:
            raise ValueError("Query contains a disallowed operation; only read-only SELECT is permitted.")

    def _run_query(self, meta: dict, sql: str) -> dict:
        conn = self._connect(meta)
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in (cursor.description or [])]
            # Fetch one extra row to detect truncation.
            fetched = cursor.fetchmany(self.max_rows + 1)
            truncated = len(fetched) > self.max_rows
            rows = [list(r) for r in fetched[: self.max_rows]]
            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "truncated": truncated,
            }
        finally:
            with contextlib.suppress(Exception):
                conn.close()

    # ------------------------------------------------------------------
    # Drivers
    # ------------------------------------------------------------------
    def _connect(self, meta: dict):
        """Open a connection for the connector using a driver-appropriate adapter."""
        db_type = meta["type"]
        url = meta["url"]
        if db_type == "sqlite":
            return self._connect_sqlite(url)
        if db_type == "postgresql":
            return self._connect_postgresql(url)
        if db_type == "mysql":
            return self._connect_mysql(url)
        raise ValueError(f"Unsupported connector type '{db_type}'.")

    def _connect_sqlite(self, url: str):
        # Accept both sqlite:///path and bare filesystem paths.
        path = url
        if url.startswith("sqlite:"):
            parsed = urlparse(url)
            path = parsed.path or ""
            # sqlite:///abs/path -> /abs/path ; sqlite://:memory: handled below
            if url in {"sqlite://:memory:", "sqlite:///:memory:"}:
                path = ":memory:"
        return sqlite3.connect(path, timeout=self.timeout_seconds)

    def _connect_postgresql(self, url: str):
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - driver optional
            raise RuntimeError("PostgreSQL driver not installed") from exc
        # statement_timeout is set in milliseconds via connection options.
        options = f"-c statement_timeout={self.timeout_seconds * 1000}"
        return psycopg.connect(url, connect_timeout=self.timeout_seconds, options=options)

    def _connect_mysql(self, url: str):
        try:
            import pymysql
        except ImportError as exc:  # pragma: no cover - driver optional
            raise RuntimeError("MySQL driver not installed") from exc
        parsed = urlparse(url)
        return pymysql.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=parsed.username or "",
            password=parsed.password or "",
            database=(parsed.path or "/").lstrip("/"),
            connect_timeout=self.timeout_seconds,
            read_timeout=self.timeout_seconds,
        )


# Sentinel used when a regex match is absent, avoiding an AttributeError.
class _EmptyMatch:
    @staticmethod
    def group(_index: int) -> str:
        return ""


_EMPTY_MATCH = _EmptyMatch()
