# Dockerfile for Trading Agent - Main Service
# This builds the Python backend with all dependencies

# Use Python 3.12 slim image (smaller size, faster builds)
FROM python:3.12-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies
# - build-essential: For compiling Python packages
# - chromium & chromium-driver: For Selenium web scraping
# - git: For installing packages from git repositories
# - curl: For health checks
RUN apt-get update && apt-get install -y \
    build-essential \
    chromium \
    chromium-driver \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for Chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user for security
RUN useradd -m -u 1000 trader && \
    chown -R trader:trader /app

# Copy requirements first (for better Docker layer caching)
# Docker caches layers, so if requirements.txt doesn't change,
# it won't reinstall packages
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
# --no-cache-dir: Reduces image size
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire application code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p data logs analysis_results paper_trading && \
    chown -R trader:trader /app

# Switch to non-root user
USER trader

# Expose port for API server (if running)
EXPOSE 8000

# Default command (can be overridden in docker-compose.yml)
# Keep container running for manual execution
CMD ["tail", "-f", "/dev/null"]
