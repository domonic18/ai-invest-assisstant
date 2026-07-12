#!/bin/bash
set -e

echo "Building Docker images..."

docker build -t web-api:latest -f docker/web/Dockerfile .
docker build -t collector:latest -f docker/collector/Dockerfile .

echo "Build complete."
