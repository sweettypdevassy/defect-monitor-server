#!/bin/bash

echo "=========================================="
echo "Restarting Defect Monitor Server"
echo "=========================================="

# Stop the container
echo "Stopping container..."
docker-compose down

# Clean Python cache
echo "Cleaning Python cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# Rebuild the image to ensure fresh code
echo "Rebuilding Docker image..."
docker-compose build --no-cache defect-monitor-server

# Start the container
echo "Starting container..."
docker-compose up -d

# Wait for server to start
echo "Waiting for server to start..."
sleep 5

# Show logs
echo "=========================================="
echo "Server logs:"
echo "=========================================="
docker-compose logs -f defect-monitor-server

# Made with Bob
