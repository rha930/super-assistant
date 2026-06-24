#!/bin/bash

# Setup script for AWS Strands Agent UI

echo "🚀 Setting up AWS Strands Agent UI..."
echo ""

# Backend setup
echo "📦 Setting up backend..."
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

echo "✅ Backend setup complete"
echo ""

# Frontend setup
echo "📦 Setting up frontend..."
cd ../frontend

# Install dependencies
npm install

echo "✅ Frontend setup complete"
echo ""

echo "🎉 Setup complete!"
echo ""
echo "To start development:"
echo ""
echo "  Backend:"
echo "    cd backend"
echo "    source venv/bin/activate"
echo "    python app.py"
echo ""
echo "  Frontend:"
echo "    cd frontend"
echo "    npm run dev"
echo ""
