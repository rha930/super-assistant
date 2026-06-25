# Spec: Containerize Frontend and Backend with Docker

## Purpose
Provide a repeatable, local-first container setup for both frontend and backend services so the app can be started consistently across machines with minimal host dependencies.

## Problem Statement
Running frontend and backend directly on host requires manual environment setup and version alignment. This causes onboarding friction and environment drift.

## Goals
- Add Docker support for both frontend and backend services.
- Support one-command local startup with Docker Compose.
- Keep behavior equivalent to current local development flow.
- Allow environment-based configuration without hardcoding secrets.

## Non-Goals
- No production orchestration (Kubernetes/ECS) in this feature.
- No CI/CD container publishing in this feature.
- No reverse proxy/TLS termination in this feature.

## User Stories
- As a developer, I can run both services with a single Docker Compose command.
- As a developer, I can rebuild containers after code changes.
- As a developer, I can configure backend credentials and API URL via environment variables.

## Functional Requirements
1. Repository must include a backend Dockerfile.
2. Repository must include a frontend Dockerfile.
3. Repository must include a root-level docker-compose file to run both services.
4. Compose must expose frontend on host port 5173 and backend on host port 5000.
5. Frontend container must communicate with backend container via internal network hostname.
6. Backend env vars must be provided through Compose env configuration.
7. Startup commands must be documented in README/SETUP docs.
8. Services must be independently restartable (`docker compose restart frontend|backend`).

## Architecture Requirements
- Compose network:
  - Use default compose bridge network for service-to-service DNS.
  - Backend should be reachable as `http://backend:5000` from frontend container.
- Port mapping:
  - Frontend: `5173:5173`
  - Backend: `5000:5000`
- Service dependencies:
  - Frontend should declare dependency on backend startup (`depends_on`).

## Backend Container Requirements
1. Base image must be a slim Python image (recommended: `python:3.10-slim`).
2. Working directory should be set to backend app directory.
3. Dependencies installed from `backend/requirements.txt`.
4. Container command must start Flask app on `0.0.0.0:5000`.
5. Required environment variables supported:
   - `AWS_REGION`
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `PORT` (default `5000`)
6. Include `.dockerignore` patterns to reduce build context size.

## Frontend Container Requirements
1. Base image should support Node and Vite dev server (recommended: `node:20-alpine` for dev image).
2. Working directory should be frontend app directory.
3. Dependencies installed from lock file when available.
4. Container command must run Vite dev server bound to all interfaces (`--host 0.0.0.0`).
5. Frontend env vars supported:
   - `VITE_API_URL` (should target backend service URL in container network)
   - `VITE_API_TIMEOUT`
6. Frontend must be reachable from host browser at `http://localhost:5173`.

## Compose Configuration Requirements
- File location: repository root (e.g., `docker-compose.yml`).
- Services:
  - `backend`
  - `frontend`
- Build contexts:
  - backend service build context points to backend directory or root with Dockerfile path.
  - frontend service build context points to frontend directory or root with Dockerfile path.
- Environment handling:
  - Support `.env` file and explicit `environment` keys.
  - Do not hardcode real secrets in compose file.
- Volumes (dev mode):
  - Mount source code for live iteration where possible.
  - Keep `node_modules` container-managed to avoid host/container mismatch.

## Developer Experience Requirements
- Commands must be documented:
  - Build: `docker compose build`
  - Start: `docker compose up`
  - Stop: `docker compose down`
  - Rebuild one service: `docker compose build frontend` / `docker compose build backend`
- Logs:
  - `docker compose logs -f frontend`
  - `docker compose logs -f backend`
- Include troubleshooting notes for common port collision and env var issues.

## Security Requirements
- Never commit actual cloud credentials.
- Use environment variable injection for secrets.
- Recommend `.env` in `.gitignore` if not already ignored.
- Minimize image size by excluding unnecessary files from build contexts.

## Performance and Reliability Requirements
- Containers must start successfully on clean machine after `docker compose up --build`.
- Backend health endpoint (`/api/health`) should respond from host when stack is up.
- Frontend should load and be able to call backend API without CORS/network errors.

## Acceptance Criteria
1. Running `docker compose up --build` starts both services without manual host dependency installs.
2. Opening `http://localhost:5173` shows the UI.
3. `http://localhost:5000/api/health` returns healthy response.
4. Frontend API calls are successfully routed to backend in containerized setup.
5. Secrets are configurable via environment variables and not hardcoded in tracked files.

## Test Cases
- Integration:
  - Build both images from clean checkout.
  - Start compose stack and verify both containers are healthy/running.
  - Load frontend and send a test chat request that reaches backend.
- Negative:
  - Start with missing required backend credentials and verify clear error behavior.
  - Start when port 5173 or 5000 is already occupied and verify documented remediation works.
- Regression:
  - Existing non-container local run instructions still work.

## Implementation Notes
- Prefer keeping Docker configuration focused on development workflow first.
- If backend relies on local model runtime not in compose, document external dependency clearly.
- Consider adding optional compose profiles later (e.g., `dev`, `prod`) after baseline setup is stable.
