FROM python:3.11-slim

WORKDIR /app

# System dependencies for numpy/scikit-learn/lightgbm/catboost only
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY templates/ ./templates/
COPY config/ ./config/
COPY static/ ./static/

# Create runtime directories
RUN mkdir -p data logs

ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=src/app.py

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/api/status', timeout=5)"

COPY start_with_gunicorn.sh /app/
RUN chmod +x /app/start_with_gunicorn.sh

CMD ["/app/start_with_gunicorn.sh"]
