#!/bin/bash
# Start Flask app with Gunicorn (production WSGI server with auto-reload)

cd /app

# Kill any existing Flask/Gunicorn processes
pkill -f "python src/app.py" || true
pkill -f "gunicorn" || true

# Start with Gunicorn (production mode - no reload for stability)
# Note: --reload disabled to prevent worker restarts during ML training
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 1 \
    --timeout 900 \
    --graceful-timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    "src.app:app"

# Made with Bob
