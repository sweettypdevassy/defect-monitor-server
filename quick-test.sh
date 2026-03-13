#!/bin/bash

# Quick Test Script for Defect Monitor Server
# This script helps you test the application quickly

set -e

echo "🧪 Defect Monitor Server - Quick Test"
echo "======================================"
echo ""

# Check if we're in the right directory
if [ ! -f "config/config.yaml" ]; then
    echo "❌ Error: Please run this script from the defect-monitor-server directory"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "📋 Checking prerequisites..."

if command_exists docker && command_exists docker-compose; then
    echo "✅ Docker and Docker Compose found"
    USE_DOCKER=true
elif command_exists python3; then
    echo "✅ Python 3 found"
    USE_DOCKER=false
else
    echo "❌ Neither Docker nor Python 3 found"
    echo "Please install Docker Desktop or Python 3"
    exit 1
fi

echo ""

# Check configuration
echo "🔧 Checking configuration..."
if grep -q "your.email@ibm.com" config/config.yaml; then
    echo "⚠️  WARNING: You need to update config/config.yaml with your credentials"
    echo ""
    echo "Please edit config/config.yaml and update:"
    echo "  - ibm.username (your IBM email)"
    echo "  - ibm.password (your IBM password)"
    echo "  - slack.webhook_url (your Slack webhook)"
    echo ""
    read -p "Have you updated the config? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Please update config/config.yaml first, then run this script again"
        exit 1
    fi
fi

echo "✅ Configuration looks good"
echo ""

# Test with Docker
if [ "$USE_DOCKER" = true ]; then
    echo "🐳 Testing with Docker..."
    echo ""
    
    echo "Building Docker image..."
    docker-compose build
    
    echo ""
    echo "Starting service..."
    docker-compose up -d
    
    echo ""
    echo "Waiting for service to start..."
    sleep 5
    
    echo ""
    echo "📊 Service Status:"
    docker-compose ps
    
    echo ""
    echo "📝 Recent Logs:"
    docker-compose logs --tail=20
    
    echo ""
    echo "✅ Service is running!"
    echo ""
    echo "🌐 Access the dashboard:"
    echo "   Home:      http://localhost:5000"
    echo "   Dashboard: http://localhost:5000/dashboard"
    echo ""
    echo "🧪 Test API:"
    echo "   curl http://localhost:5000/health"
    echo "   curl http://localhost:5000/api/status"
    echo ""
    echo "📋 View logs:"
    echo "   docker-compose logs -f"
    echo ""
    echo "🛑 Stop service:"
    echo "   docker-compose down"
    echo ""
    
    # Try to open browser
    if command_exists open; then
        read -p "Open dashboard in browser? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            open http://localhost:5000
        fi
    fi

# Test with Python
else
    echo "🐍 Testing with Python..."
    echo ""
    
    # Check if venv exists
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
        
        echo "Installing dependencies..."
        source venv/bin/activate
        pip install -r requirements.txt
    else
        echo "Using existing virtual environment..."
        source venv/bin/activate
    fi
    
    echo ""
    echo "Starting service..."
    echo "Press Ctrl+C to stop"
    echo ""
    
    python src/app.py
fi

# Made with Bob
