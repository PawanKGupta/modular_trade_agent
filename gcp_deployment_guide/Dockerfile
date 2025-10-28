# Dockerfile for Trading Agent - GCP Deployment
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set Python path
ENV PYTHONPATH=/app

# Create directories for data persistence
RUN mkdir -p /app/data /app/data/scrip_master /app/analysis_results /app/logs

# Default command (will be overridden by Cloud Run/Scheduler)
CMD ["python", "-m", "src.presentation.cli.application", "analyze", "--backtest"]
