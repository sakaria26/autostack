#!/bin/bash
set -e

echo "Starting Autostack Setup..."

# Backend Setup
echo "--- Setting up Backend ---"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../autostack-engine"

if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.copy .env
    echo "WARNING: Please update .env with your GEMINI_API_KEY manually."
else
    echo ".env file exists."
fi

# Export variables from .env for the current shell session
echo "Loading environment variables from .env..."
export $(grep -v '^#' .env | xargs)

# Check/Install Poetry via PIP
if ! python3 -m poetry --version &> /dev/null; then
  echo "Poetry not found. Installing..."
  pip3 install poetry
fi

echo "Installing Backend Dependencies..."
python3 -m poetry install

echo "Starting Docker Services..."
docker compose --env-file .env -f deployments/docker/compose.yml up -d --build

echo "Initializing Database..."
python3 -m poetry run setup-database
python3 -m poetry run migrate-database

echo "--- Backend Setup Complete ---"
echo "To run backend: cd autostack-engine && python3 -m poetry run gateway"

# Frontend Setup
echo "--- Setting up Frontend ---"
cd "$SCRIPT_DIR/../autostack"

echo "Installing Frontend Dependencies..."
npm install

echo "--- Frontend Setup Complete ---"
echo "To run frontend: cd autostack && ng serve"

echo "Setup finished! Don't forget to set your GEMINI_API_KEY in autostack-engine/.env"
