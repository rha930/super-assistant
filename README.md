# Super Agent

A web application hosting an AI agent with a chat interface and configuration management panel. Powered by Ollama for local LLM inference.

## Project Structure

```
super-assistant/
├── frontend/                 # Vue.js application
│   ├── src/
│   │   ├── components/      # Vue components
│   │   ├── stores/          # Pinia state management
│   │   ├── services/        # API services
│   │   ├── types/           # TypeScript types
│   │   ├── App.vue
│   │   ├── main.ts
│   │   └── style.css
│   ├── public/
│   ├── index.html
│   ├── Dockerfile
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                  # Python Flask application
│   ├── routes/              # API route handlers
│   ├── services/            # Business logic
│   ├── models/              # Data models
│   ├── middleware/          # Auth middleware
│   ├── utils/               # Utility functions
│   ├── app.py              # Flask app factory
│   ├── config.py           # Configuration
│   ├── Dockerfile
│   └── requirements.txt
│
├── docker-compose.yml       # Docker orchestration
└── PROJECT_PLAN.md          # Detailed project plan
```

## Quick Start (Docker — Recommended)

### Prerequisites
- Docker & Docker Compose
- [Ollama](https://ollama.com) running on the host machine with at least one model pulled

### 1. Configure environment variables

Create a `.env` file in the project root:
```bash
# Ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma4

# Auth
AUTH_ENABLED=True
AUTH_SECRET_KEY=your-secret-key-here

# Optional
FLASK_ENV=development
VITE_API_URL=http://localhost:5000
```

### 2. Start the application

```bash
docker compose up --build
```

This starts both the backend and frontend:
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:5000

### 3. Create a user (if auth is enabled)

```bash
docker compose exec backend python manage_users.py create --username yourname --display-name "Your Name"
```

### Stopping the application

```bash
docker compose down
```

To also remove persisted data (chat history, users):
```bash
docker compose down -v
```

---

## Local Development (Without Docker)

### Prerequisites
- Node.js 18+
- Python 3.10+
- Ollama running locally

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit with your settings
python app.py
```

The backend will be available at `http://localhost:5000`

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`

## API Endpoints

### Auth
- `POST /api/auth/login` - Log in and receive a JWT token
- `POST /api/auth/logout` - Log out
- `GET /api/auth/me` - Get current authenticated user

### Chat
- `POST /api/chat/message` - Send a message to the agent
- `POST /api/chat/stream` - Stream a response from the agent
- `GET /api/chat/history/<conversation_id>` - Get conversation history
- `DELETE /api/chat/reset` - Reset the conversation

### Configuration
- `GET /api/config` - Get current configuration
- `POST /api/config` - Update configuration
- `POST /api/config/reset` - Reset to default configuration

### Health
- `GET /api/health` - Health check
- `GET /api/status` - Service status

## Docker Architecture

```
┌─────────────────────────────────────────────┐
│  docker compose                             │
│                                             │
│  ┌──────────────┐    ┌──────────────────┐   │
│  │  frontend     │    │  backend          │   │
│  │  :5173        │───▶│  :5000            │   │
│  │  (Vite/Vue)   │    │  (Gunicorn/Flask) │   │
│  └──────────────┘    └────────┬─────────┘   │
│                               │              │
└───────────────────────────────┼──────────────┘
                                │
                       ┌────────▼─────────┐
                       │  Ollama (host)    │
                       │  :11434           │
                       └──────────────────┘
```

- **backend** connects to Ollama on the host via `host.docker.internal`
- **backend-data** volume persists chat history (SQLite) and user data
- **frontend** hot-reloads from the mounted `src/` directory in development

## Development

### Frontend
```bash
cd frontend
npm run dev          # Start dev server
npm run build        # Build for production
npm run preview      # Preview production build
```

### Backend
```bash
cd backend
source venv/bin/activate
python app.py       # Run with Flask development server
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL (`host.docker.internal` in Docker) |
| `OLLAMA_MODEL` | `gemma4` | Default LLM model |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | Request timeout for Ollama |
| `AUTH_ENABLED` | `True` | Enable/disable authentication |
| `AUTH_SECRET_KEY` | *(required)* | JWT signing key |
| `AUTH_USERS_FILE` | `./users.json` | Path to user store |
| `HISTORY_BACKEND_TYPE` | `local` | Chat history backend (`local` or `redis`) |
| `HISTORY_DB_PATH` | `./chat_history.db` | SQLite path for local history |
| `HISTORY_REDIS_URL` | `redis://redis:6379/0` | Redis URL (if using redis backend) |
| `VITE_API_URL` | `http://localhost:5000` | Backend URL for the frontend |
| `VITE_API_TIMEOUT` | `30000` | Frontend API timeout (ms) |
| `DEFAULT_TEMPERATURE` | `0.7` | Model temperature (0–2) |
| `DEFAULT_MAX_TOKENS` | `1000` | Max response tokens |
| `DEFAULT_TOP_P` | `0.9` | Top-p sampling (0–1) |
| `DEFAULT_SYSTEM_PROMPT` | `You are a helpful AI assistant.` | Default system prompt |

## Troubleshooting

### Ollama not reachable from Docker
- Ensure Ollama is running on the host: `ollama list`
- Verify `OLLAMA_BASE_URL` is set to `http://host.docker.internal:11434` in your `.env`
- On Linux, ensure `extra_hosts` mapping is working (Docker 20.10+)

### CORS Issues
- Backend has CORS enabled by default
- Ensure `VITE_API_URL` in the frontend matches the backend URL

### Backend Connection Issues
- Check that the backend container is healthy: `docker compose ps`
- View logs: `docker compose logs backend`

### Container Logs
```bash
docker compose logs -f           # All services
docker compose logs -f backend   # Backend only
docker compose logs -f frontend  # Frontend only
```

## License

MIT
