#!/bin/bash

# Exit on error
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Load environment variables
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -i :$port > /dev/null 2>&1; then
        echo "Port $port is in use"
        return 1
    else
        echo "Port $port is available"
        return 0
    fi
}

# Function to kill process on port
kill_port() {
    local port=$1
    echo "Attempting to kill process on port $port"
    if [ "$(uname)" == "Darwin" ]; then
        lsof -ti :$port | xargs kill -9
    else
        fuser -k $port/tcp
    fi
}

BACKEND_PORT=${FRIDAY_API_PORT:-9001}

# Check and kill process on backend port if needed
if ! check_port $BACKEND_PORT; then
    kill_port $BACKEND_PORT
    sleep 2
    if ! check_port $BACKEND_PORT; then
        echo "Failed to free port $BACKEND_PORT"
        exit 1
    fi
fi

# Start the application
echo "Starting FRIDAY backend on port $BACKEND_PORT..."
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    if command -v python >/dev/null 2>&1; then
        PYTHON_BIN="python"
    else
        echo "No python interpreter found (expected python3 or python)"
        exit 1
    fi
fi
"$PYTHON_BIN" -m backend.main
