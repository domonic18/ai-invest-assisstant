#!/bin/bash
set -e

echo "Setting up local development environment..."

# Verify uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed. Please install uv first: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# Sync Python dependencies
cd backend
uv sync
cd ..

# Install Node dependencies
cd web
npm install
cd ..

# Install shared dependencies
cd shared
npm install || true
cd ..

# Create .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo ".env created from .env.example"
fi

echo "Setup complete. Run 'make infra' to start infrastructure services."
