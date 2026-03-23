# Dockerfile for Defect Monitor Server
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for building numpy/scikit-learn
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY templates/ ./templates/
COPY config/ ./config/

# Create directories for data, logs, and static
RUN mkdir -p data logs static

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=src/app.py

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')"

# Copy startup script
COPY start_with_gunicorn.sh /app/
RUN chmod +x /app/start_with_gunicorn.sh

# Run the application with Gunicorn
CMD ["/app/start_with_gunicorn.sh"]