# Spec: Database Connectors in Settings + Database Querying Tool for Agent

## Purpose
Let users see which databases the agent can connect to from the Settings/Config panel, and give the agent a tool to safely query those databases (read-only) to ground its responses in live data.

## Problem Statement
The agent currently has no visibility into or access to external databases. Users have no way to tell, from the UI, whether a database connection is configured/available, and there is no mechanism for the agent to run queries against a database as part of answering a question (unlike the existing GNews and knowledge-base tools, which ground responses in external data — see `specs/completed/gnews-news-articles-tool.spec.md` and `specs/knowledge-base-tool.spec.md`).

## Goals
- Support configuring one or more named database connectors (e.g., PostgreSQL, MySQL, SQLite) via environment variables, following the existing secret-handling convention (`backend/config.py`).
- Add a read-only "Database Connectors" section to the Settings/Config panel showing each configured connector's name, type, and live connection status (connected / unavailable), with no credentials ever exposed.
- Provide a `database_query` agent tool that can run **read-only** SQL queries against a selected connector and return structured results for the agent to use when generating a response.
- Keep the connector layer modular so new database types can be added without changing the agent or UI contract.
- Surface tool usage in `metadata.tool_calls`, consistent with the news-search and graph tools in `backend/services/strands_tools.py`.

## Non-Goals
- No UI for creating/editing connector credentials — connectors are defined via environment variables only (Phase 1).
- No write/DDL/DML operations (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, etc.) from the agent tool.
- No arbitrary multi-statement or stored-procedure execution.
- No connection pooling tuning UI or per-user database permissions.
- No support for NoSQL databases in Phase 1 (see Phase 2 Considerations).

---

## User Stories
- As a user, I can open Settings and see a list of database connectors the agent can use, along with whether each is currently reachable.
- As a user, I can ask the agent a question that requires live data from a configured database and get an answer grounded in query results.
- As a user, I can see when the agent ran a database query (tool activity indicator) and what query/connector was used.
- As an admin, I can configure database connectors via environment variables without ever exposing credentials to the frontend or logs.
- As an admin, I can be confident the agent cannot modify or delete data through this tool.

---

## Architecture

### High-Level Flow
```
User Message
    │
    ▼
┌───────────────────┐
│   Agent Service    │  (Ollama or Gemini via Strands)
└────────┬──────────┘
         │ Agent decides a DB lookup is needed
         ▼
┌────────────────────────┐       ┌────────────────────────┐
│  database_query tool    │──────▶│ DatabaseConnectorService│
│  (backend/services/     │       │ (backend/services/      │
│   strands_tools.py)     │       │  database_service.py)   │
└────────────────────────┘       └────────────┬───────────┘
                                               │ SELECT-only, timeout, row limit
                                               ▼
                                     ┌────────────────────┐
                                     │ Configured DB driver │
                                     │ (Postgres/MySQL/     │
                                     │  SQLite adapter)     │
                                     └────────────────────┘
                                               │
                                               ▼
                                     Rows returned → formatted →
                                     injected into agent prompt
```

### Component Map
| Component | File | Role |
|---|---|---|
| DatabaseConnectorService | `backend/services/database_service.py` (new) | Manages named connectors, validates/executes read-only SQL, reports connector status |
| Config | `backend/config.py` | Env vars & `DEFAULT_CONFIG["database_connectors"]` (no credentials) |
| Database tool factory | `backend/services/strands_tools.py` | `build_database_query_tool(db_service)` exposed to the agent |
| StrandsAgentService | `backend/services/strands_agent.py` | Registers the tool with the agent, heuristic for when to suggest DB lookups |
| ChatService | `backend/services/chat_service.py` | Constructs `DatabaseConnectorService`; passes it to the agent |
| Connectors route | `backend/routes/database.py` (new) | `GET /api/database/connectors` — read-only status list for Settings UI |
| ConfigPanel | `frontend/src/components/ConfigPanel.vue` | New "Database Connectors" read-only section |
| configStore | `frontend/src/stores/configStore.ts` | Loads connector status list from the new endpoint |

---

## Functional Requirements

### Connector Configuration & Status
1. Database connectors are defined via environment variables using an indexed naming scheme, e.g.:
   - `DB_CONNECTOR_1_NAME=analytics`
   - `DB_CONNECTOR_1_TYPE=postgresql` (one of `postgresql`, `mysql`, `sqlite`)
   - `DB_CONNECTOR_1_URL=postgresql://user:pass@host:5432/dbname` (environment-only; never stored in `DEFAULT_CONFIG`, never returned by any endpoint, never logged)
   - Additional connectors follow `DB_CONNECTOR_2_*`, `DB_CONNECTOR_3_*`, etc.
2. `DatabaseConnectorService` parses these env vars at startup into an internal registry of connectors: `{ name, type, is_configured }` (URL/credentials kept private to the service).
3. The service exposes `list_connectors() -> list[dict]` returning `{ name, type, status }` where `status` is one of `"connected"`, `"unreachable"`, `"not_configured"` — determined by a lightweight connectivity check (e.g., `SELECT 1`) with a short timeout, never including the connection string.
4. `GET /api/database/connectors` returns `{ "success": true, "message": "...", "data": { "connectors": [...] } }` using the standard response shape, listing all configured connectors and their status. No credentials are ever included in the response.
5. If no connectors are configured, the endpoint returns an empty list (not an error).

### Database Query Tool
6. `database_query(connector_name: str, sql: str) -> str` is exposed to the agent via `strands_tools.py`, following the same factory pattern as `build_news_search_tool` / `build_generate_graph_tool`.
7. The tool only allows single **read-only** statements: the query must start with `SELECT` (or `WITH ... SELECT` for CTEs) after stripping comments/whitespace; any other statement type (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT`, `EXEC`, multiple statements separated by `;`) is rejected before execution with a clear error message.
8. Queries are executed with a bounded timeout (default 10s, configurable via `DB_QUERY_TIMEOUT_SECONDS`) and a maximum row cap (default 100 rows, configurable via `DB_QUERY_MAX_ROWS`); results beyond the cap are truncated with a note to the agent.
9. If `connector_name` does not match a configured connector, or the connector status is not `"connected"`, the tool returns a clear error string (not a raised exception that breaks the chat flow).
10. Query execution errors (SQL syntax errors, permission errors, timeouts) are caught and returned as a short, sanitized error string — raw driver exceptions and connection strings are never surfaced to the model or the user.
11. Successful results are returned as a compact textual table (column headers + rows) capped to the row/byte limits, suitable for prompt injection.
12. Tool invocations are recorded in `metadata.tool_calls` with:
    - `name: "database_query"`
    - `status: "success" | "error"`
    - `duration` (milliseconds)
    - `inputs: { connector_name, sql }`
    - `outputs: { row_count, truncated: bool }` (no raw row data in metadata, only counts)

---

## Backend Requirements

### Configuration (`backend/config.py`)

```python
# Database Connectors — connection URLs are environment-only, never stored in DEFAULT_CONFIG
DB_QUERY_TIMEOUT_SECONDS = int(os.getenv("DB_QUERY_TIMEOUT_SECONDS", "10"))
DB_QUERY_MAX_ROWS = int(os.getenv("DB_QUERY_MAX_ROWS", "100"))

def _load_db_connectors_from_env() -> list[dict]:
    """Parse DB_CONNECTOR_<N>_NAME/TYPE/URL env vars into connector definitions."""
    ...
```

Add to `DEFAULT_CONFIG`:
```python
"database_connectors": {
    "timeout_seconds": DB_QUERY_TIMEOUT_SECONDS,
    "max_rows": DB_QUERY_MAX_ROWS,
    # Connector names/types are served dynamically via /api/database/connectors,
    # not baked into DEFAULT_CONFIG. Connection URLs are never stored here.
},
```

### DatabaseConnectorService (`backend/services/database_service.py`, new)

```python
class DatabaseConnectorService:
    SUPPORTED_TYPES = {"postgresql", "mysql", "sqlite"}

    def __init__(self, connector_defs: list[dict], timeout_seconds: int, max_rows: int):
        """connector_defs: [{ name, type, url }] parsed from env; url kept private."""

    def list_connectors(self) -> list[dict]:
        """Return [{ name, type, status }] — never includes url/credentials."""

    def is_available(self, connector_name: str) -> bool:
        """True if connector exists and last known status is 'connected'."""

    def execute_read_only_query(self, connector_name: str, sql: str) -> dict:
        """
        Validate SQL is a single SELECT/WITH statement, run it with a timeout
        and row cap, and return:
        { "columns": [...], "rows": [[...], ...], "row_count": int, "truncated": bool }
        Raises ValueError for invalid connector/non-SELECT SQL,
        RuntimeError for execution failures (sanitized message only).
        """
```

- Use driver-appropriate libraries behind a thin adapter (e.g., `psycopg[binary]` for PostgreSQL, `PyMySQL` for MySQL, Python's built-in `sqlite3` for SQLite); add only the drivers actually used to `backend/requirements.txt`.
- SQL validation: reject on any statement-separator (`;` other than a single optional trailing one), reject on keywords `INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXEC|CALL|MERGE` appearing as SQL keywords (case-insensitive), only allow statements beginning with `SELECT` or `WITH`.
- Apply a query timeout via driver-level statement timeout where supported (e.g., Postgres `statement_timeout`) or a thread/future-based timeout fallback.
- Apply the row cap by fetching `max_rows + 1` rows and truncating with a `truncated=True` flag if exceeded.

### Database Tool (`backend/services/strands_tools.py`)

```python
def build_database_query_tool(db_service: Any):
    """Return a @tool that runs a read-only SQL query via db_service."""

    def database_query(connector_name: str, sql: str) -> str:
        """Run a read-only SQL SELECT query against a configured database connector.

        Use this when the user asks a question that requires looking up
        current data from a connected database (e.g., "how many rows in
        the orders table", "show me the latest 5 customers").

        Only SELECT (or WITH ... SELECT) statements are permitted; write
        operations are rejected. Results are capped to a configurable
        maximum row count.

        Returns a formatted table of results or an error description.
        """
        ...

    return strands_tool(database_query)
```

### Agent Integration (`backend/services/strands_agent.py`)
- Register `database_query` tool with the Strands agent whenever `DatabaseConnectorService.list_connectors()` returns at least one `"connected"` connector.
- System prompt addition informing the model of available connector names (not URLs) so it can pass a valid `connector_name`.

### ChatService (`backend/services/chat_service.py`)
- Construct `DatabaseConnectorService` from `config.py` env-derived connector definitions.
- Pass the service instance to the agent when generating a response, mirroring the `GNewsService`/graph-artifact patterns.

### Connectors Route (`backend/routes/database.py`, new)
- `GET /api/database/connectors` → calls `DatabaseConnectorService.list_connectors()`, returns standard `{ success, message, data }` shape.
- Requires authentication (consistent with other routes under `backend/routes/`, per `AUTH_ENABLED`).
- Register blueprint in the Flask app factory alongside existing routes (`backend/routes/__init__.py`).

---

## Frontend Requirements
1. Add `getDatabaseConnectors()` to the API layer (e.g., `frontend/src/services/` alongside existing config/chat API calls), calling `GET /api/database/connectors`.
2. Extend `frontend/src/stores/configStore.ts` with `databaseConnectors: { name, type, status }[]` state and a `loadDatabaseConnectors()` action.
3. Add a new "Database Connectors" section to `frontend/src/components/ConfigPanel.vue` (read-only, positioned near the Provider/Model sections):
   - List each connector with its `name`, `type` (badge), and a status indicator (e.g., green "Connected" / gray "Unavailable" / gray "Not configured"), following the existing badge/warning style used for `geminiAvailable`.
   - Empty state: "No database connectors configured." when the list is empty.
   - No input fields for editing connectors (read-only display only, per Non-Goals).
4. Load connector status on `ConfigPanel` mount (alongside existing `configStore.loadConfig()` calls) and optionally provide a manual refresh button matching the model-list refresh icon pattern.

---

## Security / Validation
- Database connection URLs/credentials are read from environment variables only. They are never stored in `DEFAULT_CONFIG`, never returned by `/api/database/connectors` or any other endpoint, and never logged (including in error messages or tool-call metadata).
- The `database_query` tool enforces a strict allow-list: only single `SELECT`/`WITH ... SELECT` statements execute; all other statement types and multi-statement input are rejected before reaching the database driver.
- Use parameterization/driver-level execution (no string concatenation into a shell or ORM `exec` that could bypass validation); the raw SQL text is still sent as one statement to the driver, but is pre-validated to be read-only.
- Enforce a query timeout and row cap to prevent long-running or resource-exhausting queries from the agent.
- Sanitize all error messages before returning them to the tool/model layer — no stack traces, connection strings, or internal hostnames.
- `GET /api/database/connectors` requires authentication and returns only `{ name, type, status }` — never credentials.

---

## Testing Requirements
- Backend unit tests in `backend/tests/test_database_service.py`:
  - `list_connectors()` returns correct `status` for configured/unreachable/not-configured connectors (mocked driver connections).
  - `execute_read_only_query()` accepts valid `SELECT`/`WITH` statements and returns expected shape.
  - `execute_read_only_query()` rejects `INSERT`/`UPDATE`/`DELETE`/`DROP`/`CREATE`/multi-statement input with `ValueError`, without attempting execution.
  - `execute_read_only_query()` raises `RuntimeError` with a sanitized message on driver failure (no credentials/URL leaked).
  - Row cap truncation sets `truncated=True` when result exceeds `max_rows`.
  - Query timeout is enforced (simulated slow query raises a timeout error).
- Backend unit tests in `backend/tests/test_strands_tools.py` (extend existing file):
  - `database_query` tool returns formatted table text on success.
  - `database_query` tool returns a clear error string (not an exception) for an unknown `connector_name`.
  - `database_query` tool rejects non-SELECT SQL with an error string.
- Backend route test for `GET /api/database/connectors`:
  - Returns standard response shape with connector list, no credentials present in payload.
  - Returns empty list when no connectors configured.
- Frontend unit tests:
  - `configStore.loadDatabaseConnectors()` populates state from the API.
  - `ConfigPanel.vue` renders connector list with correct status badges and the empty state when none are configured.

---

## Acceptance Criteria
- [ ] `DatabaseConnectorService` parses `DB_CONNECTOR_<N>_*` env vars into named connectors with type validation.
- [ ] `GET /api/database/connectors` returns connector name/type/status with no credentials, using the standard `{ success, message, data }` shape.
- [ ] Settings/Config panel displays a "Database Connectors" section listing configured connectors and live status, with an empty state when none exist.
- [ ] `database_query` tool is registered with the agent only when at least one connector is `"connected"`.
- [ ] The tool executes only `SELECT`/`WITH ... SELECT` statements; all write/DDL/multi-statement attempts are rejected before execution.
- [ ] Query timeout and row cap are enforced and configurable via `DB_QUERY_TIMEOUT_SECONDS` / `DB_QUERY_MAX_ROWS`.
- [ ] Tool invocations appear in `metadata.tool_calls` with the shape defined in Functional Requirement 12 (counts only, no raw row data).
- [ ] No connection URL, credential, or raw driver error is ever logged, returned from an endpoint, or exposed to the model/user.
- [ ] All new backend/frontend unit tests pass; existing `pytest` and `npm test` suites remain green.

---

## Phase 2 Considerations
- UI-based connector creation/editing (with credentials handled via a secrets manager rather than plain env vars).
- Support for additional database types (e.g., SQL Server, MongoDB, Redis-as-data-source).
- Per-connector allow-listed tables/schemas to further restrict what the agent can query.
- Query result caching for repeated identical queries within a session.
- Natural-language-to-SQL assistance with a preview/confirmation step before execution.
- Audit log of all agent-executed queries, viewable by admins.
