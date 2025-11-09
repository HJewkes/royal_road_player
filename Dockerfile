# Multi-stage Dockerfile for audiobook system with GPU support
# Supports: CUDA 11.8, CUDA 12.1, CPU, ROCm

ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE} AS base

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
        gcc \
        g++ \
        make \
        wget \
        git \
        curl \
        ffmpeg \
        libsndfile1-dev \
        libc-dev \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js (for frontend)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy backend requirements
COPY backend/requirements.txt /app/backend/requirements.txt

# Second stage: Install Python dependencies with PyTorch variants
FROM base AS pytorch

# Add parameter for PyTorch version
ARG TORCH_VERSION="cpu"

# Install PyTorch based on TORCH_VERSION
RUN if [ "$TORCH_VERSION" = "cuda118" ]; then \
        echo "Installing PyTorch with CUDA 11.8..." && \
        pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118; \
    elif [ "$TORCH_VERSION" = "cuda121" ]; then \
        echo "Installing PyTorch with CUDA 12.1..." && \
        pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121; \
    elif [ "$TORCH_VERSION" = "rocm" ]; then \
        echo "Installing PyTorch with ROCm..." && \
        pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2; \
    else \
        echo "Installing PyTorch CPU-only..." && \
        pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu; \
    fi

# Install Python dependencies (skip torch packages as they're already installed)
RUN cd /app/backend && \
    grep -v -E "^torch==|^torchvision==|^torchaudio==|^torch$" requirements.txt > requirements_no_torch.txt && \
    pip install --no-cache-dir -r requirements_no_torch.txt && \
    rm requirements_no_torch.txt

# Copy application code
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# Install frontend dependencies
RUN cd /app/frontend && \
    npm install && \
    npm run build

# Create data directories
RUN mkdir -p /app/data/books /app/data/databases /app/data/models /app/logs

# Set environment variables for data paths
ENV DATA_DIR=/app/data
ENV BOOKS_DIR=/app/data/books
ENV DATABASE_PATH=/app/data/databases/audiobook.db

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "-m", "uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
