# AGENTS.md — super-assistant

Instructions for AI coding agents working in this repository. Mirrors `.github/copilot-instructions.md`.

## Project Overview
- **Backend**: Python 3.10, Flask (`backend/`). Services in `backend/services/`, routes in `backend/routes/`, models in `backend/models/`. Local LLM via Ollama; optional Gemini provider.
- **Frontend**: Vue 3 (SFC + TypeScript), Pinia, Vite, Tailwind (`frontend/`). Stores in `frontend/src/stores/`, components in `frontend/src/components/`, API layer in `frontend/src/services/`.
- **Infra**: `docker-compose.yml` (backend :5000, frontend :5173, redis :6379 profile-gated).
- **Specs**: `specs/` holds active specs; `specs/completed/` holds finished ones.

## Conventions
- API responses use the shape `{ "success": bool, "message": str, "data": ... }`.
- Backend config lives in `backend/config.py` (`DEFAULT_CONFIG`) and is edited via `ConfigService`. Secrets (e.g. API keys) are environment-only — never store them in `DEFAULT_CONFIG`, return them from an endpoint, or log them.
- Keep services modular so backends/providers can be swapped without changing callers.
- Do not create markdown docs to describe changes unless explicitly asked. (Spec files are a deliberate exception — see workflow.)

## Testing
- **Backend**: `cd backend && python -m pytest tests/ -v`
- **Frontend**: `cd frontend && npm test` (runs `vitest run`). If the `vitest` binary isn't on PATH, run `./node_modules/.bin/vitest run`.
- Run the relevant suite after changes and before considering a spec complete.

## Spec Format
Specs are Markdown files named in kebab-case with a `.spec.md` suffix (e.g. `provider-selection-ollama-or-gemini.spec.md`). Follow the structure used by existing specs in `specs/completed/`, typically including:
`Purpose`, `Problem Statement`, `Goals`, `Non-Goals`, `User Stories`, `Architecture`, `Functional Requirements`, `Backend Requirements`, `Frontend Requirements`, `Security/Validation`, `Testing Requirements`, `Acceptance Criteria`, and `Phase 2 Considerations`.

## Spec-Driven Workflow
Work proceeds in three explicit stages. Do not skip ahead — creating a spec is not permission to implement it.

### 1. Create the spec
- When the user asks to create a spec, write a new `specs/<name>.spec.md` following the Spec Format above.
- Ground the spec in the actual codebase (reference real files, services, endpoints, config keys).
- Do **not** create branches or write implementation code at this stage.

### 2. Review
- Present the spec for the user to review. Incorporate requested changes.
- Wait for the user to explicitly instruct implementation before proceeding.

### 3. Implement
- Only begin once the user instructs to implement a specific spec.
- **Create a branch that reflects the spec name** before making code changes:
  - Branch name: `spec/<spec-file-name-without-.spec.md>` (kebab-case), e.g. spec `provider-selection-ollama-or-gemini.spec.md` → branch `spec/provider-selection-ollama-or-gemini`.
  - Create it with: `git checkout -b spec/<name>`
- Implement the spec's requirements on that branch, keeping changes scoped to the spec.
- Add/adjust tests per the spec's Testing Requirements and run the relevant suites until green.

### 4. Complete
- When the spec's Acceptance Criteria are met and tests pass, **move the spec file to `specs/completed/`**:
  - `git mv specs/<name>.spec.md specs/completed/<name>.spec.md`
- Report completion (branch name, summary of changes, test results). Do not push, merge, or delete branches unless the user asks.
