# Spec: Add Unit Tests and Coverage for Frontend and Backend

## Purpose
Establish reliable unit testing and measurable code coverage for both frontend and backend to reduce regressions and improve confidence in feature delivery.

## Problem Statement
The project currently lacks a clearly defined unit test and coverage standard across application layers. This makes it difficult to detect regressions early and evaluate test quality over time.

## Goals
- Add unit test frameworks and baseline test suites for frontend and backend.
- Enable automated coverage reports for both codebases.
- Define minimum coverage thresholds and enforcement policy.
- Provide local and CI-friendly test commands.

## Non-Goals
- No end-to-end (E2E) framework setup in this feature.
- No load/performance testing in this feature.
- No snapshot-heavy UI testing strategy in this initial phase.

## User Stories
- As a developer, I can run unit tests locally for frontend and backend.
- As a developer, I can generate coverage reports and see what is untested.
- As a maintainer, I can enforce minimum coverage in CI to prevent regressions.

## Functional Requirements
1. Frontend must have a unit test runner and coverage support.
2. Backend must have a unit test runner and coverage support.
3. Repository must expose simple commands to run tests and coverage for each side.
4. Coverage output must include line/function/branch metrics where supported.
5. Coverage thresholds must be configurable and enforced in CI.
6. Test runs must return non-zero exit code on failures or threshold violations.

## Tooling Requirements
### Frontend
- Recommended stack:
  - `vitest`
  - `@vue/test-utils`
  - `jsdom`
  - coverage provider supported by Vitest (v8 preferred)
- Test file naming:
  - `*.spec.ts` or `*.test.ts`
- Target folders:
  - stores
  - services
  - critical components (logic-focused)

### Backend
- Recommended stack:
  - `pytest`
  - `pytest-cov`
- Test file naming:
  - `test_*.py`
- Target folders:
  - routes
  - services
  - models
  - config utilities

## Coverage Requirements
### Initial Baseline Thresholds
- Frontend global coverage:
  - Lines: >= 70%
  - Functions: >= 70%
  - Branches: >= 60%
- Backend global coverage:
  - Lines: >= 75%
  - Branches: >= 65%

### Critical Module Expectations
- Core chat service logic (frontend and backend) should target >= 80% line coverage.
- Config load/save flows should target >= 80% line coverage.

### Exclusions
- Exclude generated files, build output, and test utilities from coverage.
- Exclude framework bootstrapping files only when they have no business logic.
- Any exclusion must be documented in config with rationale comments.

## Test Scope Requirements
### Frontend Unit Tests
1. Store tests:
   - state initialization
   - action behavior
   - error/loading transitions
2. Service/API tests:
   - request mapping
   - response normalization
   - error handling
3. Component tests (logic-focused):
   - emits/interactions
   - conditional rendering states (loading/error/empty)
   - prop-driven behavior

### Backend Unit Tests
1. Service tests:
   - chat orchestration logic
   - config resolution and defaults
2. Route tests:
   - response status and payload shape
   - validation failures
3. Model/utility tests:
   - serialization/parsing
   - boundary and invalid inputs

## Configuration Requirements
### Frontend
- Add testing configuration in frontend project (Vitest config section or separate config file).
- Add scripts in [frontend/package.json](frontend/package.json):
  - `test`
  - `test:watch`
  - `test:coverage`
- Coverage output formats:
  - text summary in terminal
  - lcov file for CI tooling

### Backend
- Add pytest config (for example in `pyproject.toml` or `pytest.ini`).
- Add scripts/documented commands for:
  - running tests
  - running tests with coverage
- Coverage output formats:
  - terminal summary
  - xml and/or html for CI artifacts

## CI Requirements
1. CI pipeline must run frontend and backend unit tests on pull requests.
2. CI must fail when:
   - any unit test fails
   - coverage falls below configured thresholds
3. CI should publish coverage artifacts (lcov/html/xml) for debugging.
4. Optional: add coverage comment/report integration on pull requests.

## Developer Experience Requirements
- Document commands in setup/readme docs for both stacks.
- Ensure tests can run from clean install with minimal setup.
- Keep unit tests deterministic and independent (no network dependency by default).
- Mock external providers/services in unit scope.

## Security and Reliability Considerations
- Do not use real credentials in tests.
- Isolate environment variables via test fixtures/mocks.
- Ensure test data does not leak secrets into logs/artifacts.

## Acceptance Criteria
1. Frontend unit tests execute successfully with coverage report generation.
2. Backend unit tests execute successfully with coverage report generation.
3. Coverage thresholds are enforced and cause failures when unmet.
4. CI runs both suites on PRs and blocks merge on failure.
5. Core chat/config paths have meaningful tests and improved coverage.

## Test Cases
- Frontend:
  - store action success and failure paths
  - API service maps backend payload and handles non-200 responses
  - config panel logic updates state correctly
- Backend:
  - chat route returns expected response contract for valid input
  - invalid request payload returns structured error
  - config service fallback/default logic works when values are missing
- Coverage enforcement:
  - intentionally reduce coverage in a sample branch and verify CI fails

## Rollout Plan
1. Add test tooling and configs for frontend/backend.
2. Add baseline tests for critical stores/services/routes.
3. Enable coverage reporting locally.
4. Enable threshold enforcement.
5. Enable CI gating and artifact publishing.

## Implementation Notes
- Start with realistic baseline thresholds to avoid blocking adoption.
- Raise thresholds incrementally as test suite matures.
- Prefer behavior-focused tests over implementation-detail assertions.
