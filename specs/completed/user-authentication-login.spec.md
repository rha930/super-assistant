# Spec: User Authentication & Login Page

## Purpose
Add lightweight authentication so each user has an identity, a login page, and protected access to the chat application.

## Problem Statement
The application currently has no authentication. All users share the same anonymous session, there is no access control, and the `user_id` used for chat history is either a header value or `"anonymous"`. This prevents user-scoped features (history, preferences) from working correctly and leaves the application open to unauthorized access.

## Goals
- Require users to log in before accessing the chat interface.
- Support simple credential-based authentication (username + password).
- Issue a session token (JWT) on successful login and validate it on every API request.
- Protect all existing API routes behind authentication middleware.
- Derive `user_id` from the authenticated session instead of trusting client headers.
- Keep the implementation simple — no external identity provider in Phase 1.

## Non-Goals
- No OAuth / SSO / SAML integration in this phase (Phase 2 consideration).
- No role-based access control (RBAC) or permissions beyond authenticated vs. unauthenticated.
- No self-service registration UI — users are provisioned manually or via API/CLI.
- No password recovery flow in this phase.
- No multi-factor authentication (MFA) in this phase.

---

## User Stories
- As a user, I see a login page when I open the application without an active session.
- As a user, I can log in with my username and password.
- As a user, I am redirected to the chat interface after successful login.
- As a user, my session persists across page refreshes (until expiry or logout).
- As a user, I can log out and be returned to the login page.
- As a user, I see a clear error message if my credentials are wrong.
- As an admin, I can create user accounts via CLI or API.

---

## Architecture

### Authentication Flow
```
┌──────────────┐     POST /api/auth/login      ┌──────────────┐
│  Login Page  │ ──────────────────────────────▶│   Backend    │
│  (Vue)       │◀────────────────────────────── │   Auth Route │
│              │     { token, user }            │              │
└──────┬───────┘                                └──────┬───────┘
       │                                               │
       │  Store token in localStorage                  │  Verify credentials
       │                                               │  Hash comparison (bcrypt)
       ▼                                               │  Issue JWT
┌──────────────┐     Authorization: Bearer <token>     │
│  Chat App    │ ──────────────────────────────▶┌──────▼───────┐
│  (Vue)       │◀────────────────────────────── │  Auth        │
│              │     Protected response         │  Middleware   │
└──────────────┘                                │  (validate)  │
                                                └──────────────┘
```

---

## Backend Requirements

### New Dependencies
Add to `requirements.txt`:
```
PyJWT>=2.8.0
bcrypt>=4.0.0
```

### New Configuration
Add to `config.py` / `.env`:
```python
# Authentication
AUTH_ENABLED = os.getenv('AUTH_ENABLED', 'True') == 'True'
AUTH_SECRET_KEY = os.getenv('AUTH_SECRET_KEY', '')  # MUST be set in production
AUTH_TOKEN_EXPIRY_HOURS = int(os.getenv('AUTH_TOKEN_EXPIRY_HOURS', '24'))
AUTH_USERS_FILE = os.getenv('AUTH_USERS_FILE', './users.json')
```

> **Security:** `AUTH_SECRET_KEY` must be a strong random value. If empty at startup, the server should generate a random key and log a warning that it will not persist across restarts.

### User Storage (Phase 1: Local JSON File)

`users.json`:
```json
{
  "users": [
    {
      "id": "user_001",
      "username": "robert",
      "password_hash": "$2b$12$...",
      "display_name": "Robert H.",
      "created_at": "2026-06-25T00:00:00Z",
      "active": true
    }
  ]
}
```

- Passwords are **never stored in plaintext** — always bcrypt hashed.
- File is read on startup and cached in memory; writes flush to disk.

### New Service: `services/auth_service.py`

```python
class AuthService:
    def __init__(self, users_file: str, secret_key: str, token_expiry_hours: int):
        """Load users from file, initialize JWT config."""

    def authenticate(self, username: str, password: str) -> dict | None:
        """Verify credentials. Returns user dict (without hash) or None."""

    def generate_token(self, user: dict) -> str:
        """Create a signed JWT with user_id, username, exp claims."""

    def validate_token(self, token: str) -> dict | None:
        """Decode and validate JWT. Returns payload or None if invalid/expired."""

    def create_user(self, username: str, password: str, display_name: str) -> dict:
        """Hash password, create user record, persist to file. Returns user dict."""

    def list_users(self) -> list[dict]:
        """Return all users (without password hashes)."""
```

### New Route: `routes/auth.py`

#### `POST /api/auth/login`
**Request:**
```json
{
  "username": "robert",
  "password": "mypassword"
}
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "token": "eyJhbGciOi...",
    "user": {
      "id": "user_001",
      "username": "robert",
      "display_name": "Robert H."
    },
    "expires_in": 86400
  }
}
```

**Failure Response (401):**
```json
{
  "success": false,
  "message": "Invalid username or password",
  "data": null
}
```

> **Security:** Error message must NOT reveal whether the username or password was incorrect.

#### `POST /api/auth/logout`
Placeholder for future server-side token revocation. Returns success immediately.

#### `GET /api/auth/me`
Returns the current authenticated user from the JWT. Used by the frontend to validate an existing token on page load.

**Success Response (200):**
```json
{
  "success": true,
  "message": "Success",
  "data": {
    "id": "user_001",
    "username": "robert",
    "display_name": "Robert H."
  }
}
```

#### `POST /api/auth/users` *(Admin — future gating)*
Create a new user account.

**Request:**
```json
{
  "username": "newuser",
  "password": "securepassword",
  "display_name": "New User"
}
```

### Authentication Middleware

Create `middleware/auth.py`:

```python
def require_auth(f):
    """Decorator that validates JWT from Authorization header.
    Sets g.current_user with user payload on success.
    Returns 401 on missing/invalid/expired token."""
```

- Extract token from `Authorization: Bearer <token>` header.
- Decode and validate using `AuthService.validate_token()`.
- Set `flask.g.current_user` with the decoded payload.
- All routes except `/api/auth/login` and `/api/health` must be protected.

### Impact on Existing Routes

- **Remove `_resolve_user_id()` function** from `routes/chat.py`.
- **Replace all `user_id` resolution** with `g.current_user['user_id']` from the auth middleware.
- The `X-User-Id` header is no longer needed or trusted.

---

## Frontend Requirements

### New Component: `LoginPage.vue`

A centered, minimal login form:
- Username input field
- Password input field
- "Sign In" button
- Error message display area
- Respects the current theme (light/dark/system)
- Loading state on submit

### New Store: `stores/authStore.ts`

```typescript
interface AuthState {
  token: string | null
  user: { id: string; username: string; display_name: string } | null
  isAuthenticated: boolean
  loginError: string | null
  loading: boolean
}

actions: {
  login(username: string, password: string): Promise<boolean>
  logout(): void
  checkAuth(): Promise<boolean>   // validate stored token via GET /api/auth/me
  loadToken(): void               // load token from localStorage on init
}
```

### API Client Changes (`services/api.ts`)

- Add a request interceptor that attaches `Authorization: Bearer <token>` to every request if a token exists in the auth store.
- Add a response interceptor that catches `401` responses and redirects to the login page (clears stored token).
- Remove any `X-User-Id` header logic.

### Routing / View Gating (`App.vue`)

Since there is no `vue-router`, use conditional rendering:

```vue
<template>
  <LoginPage v-if="!authStore.isAuthenticated" />
  <div v-else id="app" class="h-screen flex flex-col app-bg app-text">
    <!-- existing header + main content -->
  </div>
</template>
```

- On app mount, call `authStore.checkAuth()` to validate any stored token.
- Show a brief loading state while the token is being validated.

### Header Updates

- Display the logged-in user's `display_name` in the header.
- Add a logout button/icon.

---

## CLI User Management

Provide a script `backend/manage_users.py` for creating users without the server running:

```bash
# Create a user
python manage_users.py create --username robert --display-name "Robert H."
# Will prompt for password securely via getpass

# List users
python manage_users.py list
```

---

## Security Requirements

| Requirement | Implementation |
|---|---|
| Password storage | bcrypt hash with salt (cost factor 12) |
| Token signing | HMAC-SHA256 via PyJWT |
| Token expiry | Configurable, default 24 hours |
| Transport | HTTPS required in production (enforced at deployment, not app layer) |
| Brute force protection | Rate limit `/api/auth/login` — max 5 attempts per minute per IP |
| Token in client | `localStorage` (acceptable for internal tool; `httpOnly` cookie is Phase 2 option) |
| Secret key | Must be set via env var; log warning if auto-generated |
| Input validation | Username: alphanumeric + underscore, 3–30 chars. Password: minimum 8 chars. |

---

## File Structure

```
backend/
  services/
    auth_service.py          # New — authentication logic
  routes/
    auth.py                  # New — login/logout/me/users endpoints
  middleware/
    __init__.py              # New
    auth.py                  # New — require_auth decorator
  manage_users.py            # New — CLI user management script
  users.json                 # New — user store (gitignored)
frontend/
  src/
    components/
      LoginPage.vue          # New — login form
    stores/
      authStore.ts           # New — auth state management
```

Add to `.gitignore`:
```
users.json
```

---

## Testing Requirements

1. **Unit tests** — `auth_service.py`: password hashing/verification, JWT generation/validation, token expiry, invalid token handling.
2. **Unit tests** — `middleware/auth.py`: valid token passes, missing token returns 401, expired token returns 401, malformed token returns 401.
3. **Integration test** — Login flow: create user → POST login → receive token → use token on protected endpoint → success.
4. **Integration test** — Rejected access: call protected endpoint without token → 401.
5. **Frontend test** — Login page renders, submits credentials, stores token, shows error on failure.

---

## Phase 2 Considerations

- **OAuth / SSO integration** — Support external identity providers (Okta, Azure AD, AWS Cognito).
- **Role-based access control** — Admin vs. standard user roles; gate user management endpoints.
- **httpOnly cookie tokens** — Move JWT out of localStorage for XSS mitigation.
- **Password reset flow** — Email-based or admin-triggered reset.
- **Session revocation** — Server-side token blacklist on logout.
- **MFA** — TOTP-based second factor.
- **Database-backed user store** — Replace `users.json` with SQLite or PostgreSQL.
