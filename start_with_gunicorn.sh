#!/bin/bash
# Start Flask app with Gunicorn (production WSGI server with auto-reload)

cd /app

# Kill any existing Flask/Gunicorn processes
pkill -f "python src/app.py" || true
pkill -f "gunicorn" || true

# Start with Gunicorn with reload on code changes
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 1 \
    --reload \
    --reload-extra-file src/database.py \
    --reload-extra-file src/app.py \
    --reload-extra-file src/defect_checker.py \
    --timeout 300 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    "src.app:app"

# Made with Bob
