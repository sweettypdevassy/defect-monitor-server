#!/bin/bash
# Start Flask app with Gunicorn (production WSGI server)

cd /app

# Kill any existing Flask/Gunicorn processes
pkill -f "python src/app.py" || true
pkill -f "gunicorn" || true

# Start Xvfb virtual display so Chromium can run headless=False
# (React apps that detect headless mode need a real display to execute JS)
Xvfb :99 -screen 0 1920x1080x24 -ac &
XVFB_PID=$!
echo "Started Xvfb with PID $XVFB_PID on DISPLAY=:99"
# Give Xvfb a moment to initialise
sleep 2

export DISPLAY=:99

# Start with Gunicorn (production mode)
# Timeout increased to 30 minutes (1800s) for long-running ML operations
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 1 \
    --timeout 1800 \
    --graceful-timeout 300 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    "src.app:app"

# Made with Bob
