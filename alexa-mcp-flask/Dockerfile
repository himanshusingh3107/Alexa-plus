# Production Dockerfile for Alexa+ MCP Flask Server
# Uses official Python 3.12 slim image for minimal footprint and enhanced security

FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5000 \
    PORT=5000

# Set container working directory
WORKDIR /app

# Install system dependencies (curl for container healthcheck) and clean apt cache
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root system user and group for secure execution
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/sh -m appuser

# Install Python package dependencies first for optimal Docker layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt gunicorn

# Copy all application code into the container
COPY . /app

# Set appropriate directory ownership and permissions for the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Expose port 5000 for inbound HTTP / SSE traffic
EXPOSE 5000

# Docker healthcheck querying the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Start the application using Waitress (default production WSGI via app.py)
# Alternative for Gunicorn:
# CMD ["gunicorn", "--workers=4", "--threads=4", "--bind=0.0.0.0:5000", "--timeout=120", "app:app"]
CMD ["python", "app.py"]
