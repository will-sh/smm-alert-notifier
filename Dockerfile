# Unified SMM Alert Receiver Dockerfile
# Supports both HTTP and SMTP alert reception

FROM python:3.11-slim AS base

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HTTP_PORT=18123
ENV SMTP_PORT=1025
ENV SMTP_HOST=0.0.0.0
ENV SMTP_USERNAME=admin
ENV SMTP_PASSWORD=admin

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY templates/ ./templates/

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose ports (HTTP + SMTP)
EXPOSE 18123 1025

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:18123/health', timeout=5)"

# Run the unified application
CMD ["python", "app.py"]

