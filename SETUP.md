# Development Setup Guide

## Backend Setup (Python)

### 1. Create Virtual Environment
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
# Copy .env.example to .env (or create .env)
# Add your AWS credentials:
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
```

### 4. Run Backend
```bash
python app.py
```

Backend runs at: `http://localhost:5000`

---

## Frontend Setup (Vue.js)

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Development Server
```bash
npm run dev
```

Frontend runs at: `http://localhost:5173`

### 3. Build for Production
```bash
npm run build
```

---

## Testing the Connection

1. Start the backend: `python app.py`
2. Start the frontend: `npm run dev`
3. Open `http://localhost:5173` in your browser
4. You should see the Strands Agent UI

---

## API Testing

Test the API endpoints:

```bash
# Health check
curl http://localhost:5000/api/health

# Get configuration
curl http://localhost:5000/api/config

# Send a message
curl -X POST http://localhost:5000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, agent!"}'
```

---

## Environment Variables

### Frontend (.env.local)
```
VITE_API_URL=http://localhost:5000
VITE_API_TIMEOUT=30000
```

### Backend (.env)
```
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
FLASK_ENV=development
FLASK_DEBUG=True
PORT=5000
```

---

## Troubleshooting

### Port Already in Use
Change the port in backend `config.py` or frontend `vite.config.ts`

### Module Not Found Errors (Python)
Make sure virtual environment is activated: `source venv/bin/activate`

### Cannot Connect to Backend
Check that:
- Backend is running on port 5000
- `VITE_API_URL` in frontend matches backend URL
- No firewall blocking connections

### Node Modules Issues
```bash
rm -rf node_modules package-lock.json
npm install
```
