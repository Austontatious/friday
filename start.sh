#!/bin/bash

# Exit on error
set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the script directory
cd "$SCRIPT_DIR"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
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

# Check and kill processes on required ports
for port in ${FRIDAY_PORT:-8001} ${REACT_APP_BACKEND_PORT:-8002}; do
    if ! check_port $port; then
        kill_port $port
        sleep 2
        if ! check_port $port; then
            echo "Failed to free port $port"
            exit 1
        fi
    fi
done

# Start the application
echo "Starting FRIDAY AI Assistant..."
python friday.py 