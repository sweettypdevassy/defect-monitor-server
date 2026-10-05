#!/bin/bash
# Start Flask app with Gunicorn (production WSGI server)

cd /app

exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 1 \
    --timeout 1800 \
    --graceful-timeout 300 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    "src.app:app"
