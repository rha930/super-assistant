# AWS Strands Agent UI

A web application hosting an AWS Strands AI agent with a chat interface and configuration management panel.

## Project Structure

```
super_assist/
├── frontend/                 # Vue.js application
│   ├── src/
│   │   ├── components/      # Vue components
│   │   ├── stores/          # Pinia state management
│   │   ├── services/        # API and WebSocket services
│   │   ├── types/           # TypeScript types
│   │   ├── App.vue
│   │   ├── main.ts
│   │   └── style.css
│   ├── public/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── .env.local
│
├── backend/                  # Python Flask application
│   ├── routes/              # API route handlers
│   ├── services/            # Business logic
│   ├── models/              # Data models
│   ├── utils/               # Utility functions
│   ├── app.py              # Flask app factory
│   ├── config.py           # Configuration
│   ├── requirements.txt
│   └── .env
│
└── PROJECT_PLAN.md          # Detailed project plan
```

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.9+
- AWS account with Strands Agent access
- AWS credentials configured

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
# Edit .env with your AWS credentials
nano .env
```

5. Run the server:
```bash
python app.py
```

The backend will be available at `http://localhost:5000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## API Endpoints

### Chat
- `POST /api/chat/message` - Send a message to the agent
- `GET /api/chat/history/<conversation_id>` - Get conversation history
- `DELETE /api/chat/reset` - Reset the conversation

### Configuration
- `GET /api/config` - Get current configuration
- `POST /api/config` - Update configuration
- `POST /api/config/reset` - Reset to default configuration

### Health
- `GET /api/health` - Health check
- `GET /api/status` - Service status

## Development

### Frontend Development
```bash
cd frontend
npm run dev          # Start dev server
npm run build        # Build for production
npm run preview      # Preview production build
```

### Backend Development
```bash
cd backend
source venv/bin/activate
python app.py       # Run with Flask development server
```

## Configuration

### Frontend (`.env.local`)
- `VITE_API_URL` - Backend API URL (default: http://localhost:5000)
- `VITE_API_TIMEOUT` - API request timeout in ms (default: 30000)

### Backend (`.env`)
- `AWS_REGION` - AWS region
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `DEFAULT_TEMPERATURE` - Default model temperature (0-2)
- `DEFAULT_MAX_TOKENS` - Default max tokens (1-4000)
- `DEFAULT_TOP_P` - Default top-p sampling (0-1)
- `DEFAULT_SYSTEM_PROMPT` - Default system prompt
- `DEFAULT_MAX_ITERATIONS` - Default agent max iterations
- `DEFAULT_TIMEOUT` - Default timeout in seconds

## Next Steps

1. **Integrate AWS Strands Agent**
   - Implement actual agent invocation in `backend/services/strands_agent.py`
   - Set up proper agent credentials and configuration

2. **Add Real-time Updates**
   - Implement WebSocket support for streaming responses
   - Add streaming response handling in both frontend and backend

3. **Enhance UI**
   - Add message markdown rendering
   - Add tool execution visualization
   - Improve styling and UX

4. **Add Persistence**
   - Set up database (SQLite, PostgreSQL, etc.)
   - Implement conversation history persistence
   - Add conversation management UI

5. **Authentication & Security**
   - Add user authentication
   - Implement API key/JWT validation
   - Secure AWS credentials handling

## Troubleshooting

### CORS Issues
If you get CORS errors, ensure:
- Backend has CORS enabled (it's already enabled by default)
- Frontend API URL matches backend URL in `.env.local`

### Backend Connection Issues
- Check that backend is running on `http://localhost:5000`
- Verify `VITE_API_URL` in frontend `.env.local`
- Check browser console for API errors

### AWS Credentials
- Ensure AWS credentials are set in backend `.env`
- Verify IAM user has permissions for Strands Agent
- Check AWS region matches your setup

## License

MIT
