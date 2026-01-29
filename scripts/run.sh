#!/bin/bash

# Autostack Unified Run Script (Linux/macOS)
# Starts backend (Docker + Gateway) and frontend (Angular)

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR/.."

echo -e "${GREEN}Starting Autostack...${NC}"

# 1. Check if Docker is running and set DOCKER_HOST
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

# Set DOCKER_HOST based on active context if on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    ACTIVE_CONTEXT=$(docker context show 2>/dev/null || echo "default")
    DOCKER_ENDPOINT=$(docker context inspect "$ACTIVE_CONTEXT" --format '{{.Endpoints.docker.Host}}' 2>/dev/null)
    if [ -n "$DOCKER_ENDPOINT" ]; then
        echo -e "${CYAN}Info: Setting DOCKER_HOST to $DOCKER_ENDPOINT (Context: $ACTIVE_CONTEXT)${NC}"
        export DOCKER_HOST="$DOCKER_ENDPOINT"
    fi
fi

# 2. Check for .env file
if [ ! -f "$BASE_DIR/autostack-engine/.env" ]; then
    echo -e "${YELLOW}Warning: .env file missing in autostack-engine. Running setup first...${NC}"
    "$SCRIPT_DIR/setup_autostack.sh"
fi

# 3. Check for GEMINI_API_KEY
if grep -q "GEMINI_API_KEY=$" "$BASE_DIR/autostack-engine/.env" || grep -q "GEMINI_API_KEY=\s*$" "$BASE_DIR/autostack-engine/.env"; then
    echo -e "${YELLOW}Warning: GEMINI_API_KEY is not set in autostack-engine/.env${NC}"
    echo -e "${YELLOW}The application may not function correctly without it.${NC}"
    echo -e "Press Ctrl+C to stop and add it, or wait 5 seconds to continue anyway..."
    sleep 5
fi

# 4. Start Docker Services
echo -e "${GREEN}Starting Docker services...${NC}"
cd "$BASE_DIR/autostack-engine"
docker compose --env-file .env -f deployments/docker/compose.yml up -d

# 5. Start Backend and Frontend simultaneously
echo -e "${GREEN}Launching Services...${NC}"
echo -e "Backend running on port 8000 (Proxy/Gateway)"
echo -e "Frontend running on http://localhost:4200"

# Use trap to kill background processes on exit
trap "kill 0" EXIT

# Start backend gateway in background
python3 -m poetry run gateway &

# Start frontend in foreground
cd "$BASE_DIR/autostack"
npm start
