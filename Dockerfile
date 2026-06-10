# Base image: small, stable, production-friendly Python runtime
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory inside container
WORKDIR /app

# Install system dependencies (minimal)
# filelock and uvicorn do not require compilation-heavy libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency list first (better Docker layer caching)
COPY requirements.txt .

# Install Python dependencies without cache (reduces image size)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code into container
COPY . .

# Expose FastAPI default port
EXPOSE 8000

# Start server
CMD ["uvicorn", "pyjdb:app", "--host", "0.0.0.0", "--port", "8000"]
