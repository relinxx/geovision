#!/bin/bash

# GeoVision Project Startup Script
# Starts both backend (FastAPI) and frontend (Vite) servers

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_PYTHON="$PROJECT_DIR/.venv_new/bin/python3"
BACKEND_LOG="/tmp/geovision_backend.log"
FRONTEND_LOG="/tmp/geovision_frontend.log"
BACKEND_PORT=8000
FRONTEND_PORT=3000

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}  GeoVision Project Startup Script${NC}"
echo -e "${BLUE}=======================================${NC}"
echo ""

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to kill process on port
kill_port() {
    local port=$1
    local pid
    pid=$(lsof -Pi :"$port" -sTCP:LISTEN -t 2>/dev/null | head -1)
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}Killing process on port $port (PID: $pid)${NC}"
        kill -9 "$pid" 2>/dev/null || true
        sleep 1
    fi
}

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down servers...${NC}"
    kill_port $BACKEND_PORT
    kill_port $FRONTEND_PORT
    echo -e "${GREEN}Servers stopped.${NC}"
    exit 0
}

# Set trap to cleanup on exit
trap cleanup INT TERM EXIT

# Check if directories exist
if [ ! -d "$BACKEND_DIR" ]; then
    echo -e "${RED}Error: Backend directory not found at $BACKEND_DIR${NC}"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR" ]; then
    echo -e "${RED}Error: Frontend directory not found at $FRONTEND_DIR${NC}"
    exit 1
fi

echo -e "${BLUE}Project Directory:${NC} $PROJECT_DIR"
echo ""

# Kill existing processes on ports
if check_port $BACKEND_PORT; then
    echo -e "${YELLOW}Port $BACKEND_PORT is in use. Stopping existing backend...${NC}"
    kill_port $BACKEND_PORT
fi

if check_port $FRONTEND_PORT; then
    echo -e "${YELLOW}Port $FRONTEND_PORT is in use. Stopping existing frontend...${NC}"
    kill_port $FRONTEND_PORT
fi

# Start Backend
echo ""
echo -e "${BLUE}Starting Backend Server...${NC}"
cd "$BACKEND_DIR"
if [ ! -f "$VENV_PYTHON" ]; then
    echo -e "${RED}Virtual environment not found at $VENV_PYTHON${NC}"
    echo -e "${YELLOW}Please run: python3 -m venv .venv_new && pip install -r requirements.txt${NC}"
    exit 1
fi
nohup "$VENV_PYTHON" -m uvicorn main:app --reload --host 0.0.0.0 --port $BACKEND_PORT > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to start
echo -n "Waiting for backend to start"
for i in {1..30}; do
    if curl -s http://localhost:$BACKEND_PORT/health >/dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}✓ Backend running on http://localhost:$BACKEND_PORT${NC}"
        break
    fi
    echo -n "."
    sleep 1
    if [ $i -eq 30 ]; then
        echo ""
        echo -e "${RED}✗ Backend failed to start${NC}"
        echo "Check log: $BACKEND_LOG"
        cat "$BACKEND_LOG" | tail -20
        exit 1
    fi
done

# Start Frontend
echo ""
echo -e "${BLUE}Starting Frontend Server...${NC}"
cd "$FRONTEND_DIR"
nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

# Wait for frontend to start
echo -n "Waiting for frontend to start"
for i in {1..30}; do
    if curl -s http://localhost:$FRONTEND_PORT >/dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}✓ Frontend running on http://localhost:$FRONTEND_PORT${NC}"
        break
    fi
    echo -n "."
    sleep 1
    if [ $i -eq 30 ]; then
        echo ""
        echo -e "${RED}✗ Frontend failed to start${NC}"
        echo "Check log: $FRONTEND_LOG"
        cat "$FRONTEND_LOG" | tail -20
        exit 1
    fi
done

# Summary
echo ""
echo -e "${GREEN}=======================================${NC}"
echo -e "${GREEN}  GeoVision is running!${NC}"
echo -e "${GREEN}=======================================${NC}"
echo ""
echo -e "${BLUE}Frontend:${NC}  http://localhost:$FRONTEND_PORT"
echo -e "${BLUE}Backend:${NC}   http://localhost:$BACKEND_PORT"
echo -e "${BLUE}API Docs:${NC}  http://localhost:$BACKEND_PORT/docs"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""

# Keep script running
while true; do
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${RED}Backend server stopped unexpectedly!${NC}"
        echo "Last 10 lines of log:"
        tail -10 "$BACKEND_LOG"
        exit 1
    fi
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo -e "${RED}Frontend server stopped unexpectedly!${NC}"
        echo "Last 10 lines of log:"
        tail -10 "$FRONTEND_LOG"
        exit 1
    fi
    sleep 5
done