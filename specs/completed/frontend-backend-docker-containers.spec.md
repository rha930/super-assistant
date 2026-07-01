# Spec: Containerize Frontend and Backend with Docker

## Purpose
Provide a repeatable, local-first container setup for all application services so the stack can be started consistently across machines with minimal host dependencies.

## Problem Statement
Running frontend and backend directly on host requires manual environment setup and version alignment. This causes onboarding friction and environment drift. Additionally, the application now has multiple runtime dependencies (Ollama, optional Redis, SQLite data, auth credentials) that must be coordinated.

## Goals
- Add Docker support for frontend, backend, and supporting services.
- Support one-command local startup with Docker Compose.
- Keep behavior equivalent to current local development flow.
- Allow environment-based configuration without hardcoding secrets.
- Manage persistent data (SQLite DB, user credentials) across container restarts.

## Non-Goals
- No production orchestration (Kubernetes/ECS) in this feature.
- No CI/CD container publishing in this feature.
- No reverse proxy/TLS termination in this feature.
- No containerizing Ollama itself (expected to run on host or separate GPU instance).

## User Stories
- As a developer, I can run the full stack with a single Docker Compose command.
- As a developer, I can rebuild containers after code changes.
- As a developer, I can configure credentials and service URLs via environment variables.
- As a developer, I can optionally enable Redis for chat history via a Compose profile.
- As a developer, persistent data survives container restarts.

---

## Service Inventory

| Service | Type | Image | Ports | Required |
|---------|------|-------|-------|----------|
| **backend** | Flask API server | `python:3.10-slim` | `5000:5000` | Yes |
| **frontend** | Vite dev server (Vue 3) | `node:20-alpine` | `5173:5173` | Yes |
| **redis** | Chat history store (optional) | `redis:7-alpine` | `6379:6379` | No (profile: `redis`) |

**External dependency (not containerized):**
- **Ollama** — LLM runtime, expected at `http://host.docker.internal:11434` or `OLLAMA_BASE_URL`.

---

## Functional Requirements
1. Repository must include a backend Dockerfile.
2. Repository must include a frontend Dockerfile.
3. Repository must include a root-level `docker-compose.yml` to orchestrate all services.
4. Compose must expose frontend on host port 5173 and backend on host port 5000.
5. Frontend container must communicate with backend container via internal network hostname.
6. Backend must reach Ollama on the host via `host.docker.internal` or configurable URL.
7. Backend env vars must be provided through Compose env configuration.
8. Startup commands must be documented in README/SETUP docs.
9. Services must be independently restartable (`docker compose restart frontend|backend`).
10. Persistent data (SQLite DB, users.json) must use named volumes or bind mounts.

---

## Architecture Requirements

### Compose Network
- Use default Compose bridge network for service-to-service DNS.
- Backend reachable as `http://backend:5000` from frontend container.
- Redis reachable as `redis://redis:6379/0` from backend container.

### Port Mapping
| Service | Host | Container |
|---------|------|-----------|
| Frontend | 5173 | 5173 |
| Backend | 5000 | 5000 |
| Redis | 6379 | 6379 |

### Service Dependencies
- Frontend declares `depends_on: [backend]`.
- Backend declares `depends_on: [redis]` only when Redis profile is active.

### Host Access (Ollama)
- Backend must reach host-network Ollama.
- On Docker Desktop (macOS/Windows): use `host.docker.internal`.
- On Linux: use `extra_hosts: ["host.docker.internal:host-gateway"]`.

---

## Backend Container Requirements

### Dockerfile (`backend/Dockerfile`)
1. Base image: `python:3.10-slim`.
2. Working directory: `/app`.
3. Install system deps if needed (`gcc` for bcrypt wheel build).
4. Copy and install `requirements.txt` first (layer caching).
5. Copy application source.
6. Create data directory for SQLite: `mkdir -p /app/data`.
7. Default command: `gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:create_app()` (or `python app.py` for dev).
8. Expose port `5000`.

### Environment Variables
All backend env vars must be configurable via Compose. Full list:

**Server:**
| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | `development` | Flask environment |
| `FLASK_DEBUG` | `False` | Debug mode |
| `PORT` | `5000` | Listening port |
| `HOST` | `0.0.0.0` | Listening address |

**Ollama / Model:**
| Variable | Default (Container) | Description |
|----------|---------------------|-------------|
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `gemma4` | Default model |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | Ollama request timeout |
| `AGENT_MODEL` | `${OLLAMA_MODEL}` | Agent model override |

**Model Defaults:**
| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_TEMPERATURE` | `0.7` | Temperature |
| `DEFAULT_MAX_TOKENS` | `1000` | Max tokens |
| `DEFAULT_TOP_P` | `0.9` | Top-P |
| `DEFAULT_SYSTEM_PROMPT` | `You are a helpful AI assistant.` | System prompt |
| `DEFAULT_MAX_ITERATIONS` | `10` | Max agent iterations |
| `DEFAULT_TIMEOUT` | `30` | Agent timeout |

**Context / History:**
| Variable | Default (Container) | Description |
|----------|---------------------|-------------|
| `CONTEXT_MAX_MESSAGES` | `12` | Max context messages |
| `CONTEXT_MAX_INPUT_CHARS` | `12000` | Max context characters |
| `HISTORY_BACKEND_TYPE` | `local` | `local` (SQLite) or `redis` |
| `HISTORY_DB_PATH` | `/app/data/chat_history.db` | SQLite path (must be on volume) |
| `HISTORY_MAX_MESSAGES_PER_CONVERSATION` | `200` | Retention limit |
| `HISTORY_REDIS_URL` | `redis://redis:6379/0` | Redis URL (container hostname) |
| `HISTORY_REDIS_PREFIX` | `chat` | Redis key prefix |

**Authentication:**
| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_ENABLED` | `True` | Enable/disable auth |
| `AUTH_SECRET_KEY` | _(required)_ | JWT signing key — must be set in `.env` |
| `AUTH_TOKEN_EXPIRY_HOURS` | `24` | Token TTL |
| `AUTH_USERS_FILE` | `/app/data/users.json` | User store path (must be on volume) |

### Data Persistence
Backend produces stateful data that must survive container restarts:

| Data | Path in Container | Volume |
|------|--------------------|--------|
| Chat history (SQLite) | `/app/data/chat_history.db` | `backend-data` |
| User credentials | `/app/data/users.json` | `backend-data` |

Both map to the same named volume mounted at `/app/data`.

### `.dockerignore` (`backend/.dockerignore`)
```
__pycache__/
*.pyc
.env
.venv/
.pytest_cache/
tests/
data/
users.json
*.egg-info/
```

---

## Frontend Container Requirements

### Dockerfile (`frontend/Dockerfile`)
1. Base image: `node:20-alpine`.
2. Working directory: `/app`.
3. Copy `package.json` and `package-lock.json` first (layer caching).
4. Run `npm ci`.
5. Copy remaining source.
6. Default command: `npx vite --host 0.0.0.0 --port 5173`.
7. Expose port `5173`.

### Environment Variables
| Variable | Default (Container) | Description |
|----------|---------------------|-------------|
| `VITE_API_URL` | `http://localhost:5000` | Backend URL as seen by browser (host network) |
| `VITE_API_TIMEOUT` | `30000` | API timeout in ms |

**Important:** `VITE_API_URL` must point to `http://localhost:5000` (not `http://backend:5000`) because the browser runs on the host, not inside Docker.

### `.dockerignore` (`frontend/.dockerignore`)
```
node_modules/
dist/
.env
```

### Volumes (Dev Mode)
- Mount `./frontend/src` to `/app/src` for hot-reload during development.
- Keep `node_modules` container-managed via anonymous volume to avoid host mismatch.

---

## Redis Container Requirements (Optional)

### Compose Profile: `redis`
Redis is included as an optional service behind a Compose profile. It is only needed when `HISTORY_BACKEND_TYPE=redis`.

```yaml
redis:
  image: redis:7-alpine
  profiles: ["redis"]
  ports:
    - "6379:6379"
  volumes:
    - redis-data:/data
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 3s
    retries: 3
```

To start with Redis: `docker compose --profile redis up`.

---

## Compose Configuration Requirements

### File: `docker-compose.yml` (repository root)

**Services:** `backend`, `frontend`, `redis` (profile-gated).

**Build contexts:**
- Backend: `context: ./backend`, `dockerfile: Dockerfile`.
- Frontend: `context: ./frontend`, `dockerfile: Dockerfile`.

**Environment handling:**
- Support `.env` file at repository root via `env_file: [.env]`.
- Provide sensible defaults in `environment:` block.
- Never hardcode real secrets in Compose file.

**Volumes:**
```yaml
volumes:
  backend-data:       # SQLite DB + users.json
  redis-data:         # Redis persistence (optional)
```

**Health checks:**
```yaml
backend:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:5000/api/health"]
    interval: 15s
    timeout: 5s
    retries: 3
    start_period: 10s
```

**Host access (Ollama):**
```yaml
backend:
  extra_hosts:
    - "host.docker.internal:host-gateway"
```

### Example `.env.example` (tracked in repo)
```env
# Ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma4

# Auth (REQUIRED — generate with: python -c "import secrets; print(secrets.token_hex(32))")
AUTH_SECRET_KEY=
AUTH_ENABLED=True

# History backend: local (SQLite) or redis
HISTORY_BACKEND_TYPE=local

# Frontend
VITE_API_URL=http://localhost:5000
```

---

## Developer Experience Requirements

### Commands
| Action | Command |
|--------|---------|
| Build all | `docker compose build` |
| Start all | `docker compose up` |
| Start with Redis | `docker compose --profile redis up` |
| Start detached | `docker compose up -d` |
| Stop all | `docker compose down` |
| Stop + remove volumes | `docker compose down -v` |
| Rebuild one service | `docker compose build backend` |
| Restart one service | `docker compose restart frontend` |
| View logs | `docker compose logs -f backend` |
| Create first user | `docker compose exec backend python manage_users.py create --username admin` |
| Run backend tests | `docker compose exec backend pytest` |
| Run backend lint | `docker compose exec backend ruff check .` |

### Troubleshooting Notes (for docs)
- **Port collision:** Change host ports in `.env` or Compose overrides.
- **Ollama unreachable:** Verify Ollama is running on host; check `OLLAMA_BASE_URL`.
- **Auth issues:** Ensure `AUTH_SECRET_KEY` is set in `.env`. Create initial user with `manage_users.py`.
- **SQLite locked:** Only one backend worker if using SQLite (WAL mode mitigates but doesn't eliminate).
- **macOS/Windows:** `host.docker.internal` works natively. **Linux:** requires `extra_hosts` mapping.

---

## Security Requirements
- Never commit actual credentials or `AUTH_SECRET_KEY`.
- Use `.env` for secrets; ensure `.env` is in root `.gitignore`.
- Track `.env.example` with placeholder values.
- Minimize image size by excluding unnecessary files from build contexts.
- Backend container runs as non-root user where possible.
- Redis should not be exposed to host unless needed for debugging (remove `ports` in production profile).

---

## Performance and Reliability Requirements
- Containers must start successfully on clean machine after `docker compose up --build`.
- Backend health endpoint (`/api/health`) should respond within 15 seconds of container start.
- Frontend should load and be able to call backend API without CORS/network errors.
- SQLite WAL mode should be enabled for concurrent read access.
- Named volumes ensure data survives `docker compose down` (but not `down -v`).

---

## Acceptance Criteria
1. Running `docker compose up --build` starts frontend and backend without manual host dependency installs.
2. Opening `http://localhost:5173` shows the login page (when auth enabled) or chat UI.
3. `http://localhost:5000/api/health` returns healthy response.
4. `http://localhost:5000/api/models` returns available models from host Ollama.
5. Frontend API calls are successfully routed to backend in containerized setup.
6. Creating a user via `docker compose exec backend python manage_users.py create --username admin` works.
7. Login, chat, conversation history, model switching all work end-to-end.
8. Secrets are configurable via `.env` and not hardcoded in tracked files.
9. `docker compose down` + `docker compose up` preserves chat history and user accounts.
10. `docker compose --profile redis up` starts Redis and backend uses it when `HISTORY_BACKEND_TYPE=redis`.

---

## Test Cases

### Integration
- Build both images from clean checkout.
- Start Compose stack and verify all containers are healthy/running.
- Create a user, log in, send a chat message, verify response.
- Restart backend container; verify chat history and users persist.
- Switch model via config panel; verify next chat uses selected model.

### Redis Profile
- Start with `--profile redis` and `HISTORY_BACKEND_TYPE=redis`.
- Send messages; verify history stored in Redis (`docker compose exec redis redis-cli KEYS '*'`).

### Negative
- Start with missing `AUTH_SECRET_KEY` — verify warning logged but app starts (ephemeral key).
- Start when Ollama is not running — verify `/api/status` shows disconnected, `/api/models` returns 503, chat returns error gracefully.
- Start when port 5173 or 5000 is already occupied — verify clear error message.

### Regression
- Existing non-container local run instructions (`pip install` + `npm run dev`) still work.

---

## Implementation Notes
- Prefer keeping Docker configuration focused on development workflow first.
- Ollama runs on host GPU — do not attempt to containerize it; document the external dependency clearly.
- Backend entrypoint should run `manage_users.py` or similar seed script only if `users.json` doesn't exist yet (optional).
- Consider adding Compose profiles later (e.g., `dev` for source mounts, `prod` for built assets) after baseline is stable.
- `gunicorn` with 2 workers is suitable for dev; SQLite works with WAL mode across workers for reads, but writes may contend — document this trade-off.
