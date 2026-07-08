#!/bin/bash
# Perfect Web Clone - Backend Startup Script
# 后端启动脚本

set -e

cd "$(dirname "$0")"

echo "=========================================="
echo "Perfect Web Clone Backend"
echo "=========================================="

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Install Playwright browser if not already installed
echo "Checking Playwright browser..."
playwright install chromium --with-deps 2>/dev/null || playwright install chromium

# Check for .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo "Please edit .env to add your ANTHROPIC_API_KEY"
    else
        echo "Warning: No .env file found. Create one with ANTHROPIC_API_KEY."
    fi
fi

# Start the server
echo ""
PORT="${PORT:-5001}"
export PORT

# Check if port is already in use and kill the process
if lsof -i :${PORT} -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port ${PORT} is already in use. Killing existing process..."
    lsof -ti :${PORT} | xargs kill -9 2>/dev/null || true
    sleep 1
    echo "Port ${PORT} cleared."
fi

echo "Starting server on http://localhost:${PORT}"
echo "API docs: http://localhost:${PORT}/docs"
echo ""

python main.py
