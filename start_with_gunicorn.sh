#!/bin/bash
# Start Flask app with Gunicorn (production WSGI server with auto-reload)

cd /app

# Kill any existing Flask/Gunicorn processes
pkill -f "python src/app.py" || true
pkill -f "gunicorn" || true

# Start with Gunicorn (production mode - no reload for stability)
# Note: --reload disabled to prevent worker restarts during ML training
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
