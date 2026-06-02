# Docker Deployment Guide

This guide covers deploying the audiobook system using Docker with GPU support.

## Prerequisites

- Docker 20.10+ installed
- Docker Compose 2.0+ installed
- For GPU support: NVIDIA Docker runtime (nvidia-docker2) or AMD ROCm

## Quick Start

### CPU-only (Default)

```bash
# Build and run CPU version
docker-compose --profile cpu up --build

# Or run directly
docker build --build-arg TORCH_VERSION=cpu -t audiobook:latest .
docker run -p 8000:8000 -v $(pwd)/data:/app/data audiobook:latest
```

### NVIDIA GPU (CUDA 11.8)

```bash
# Build and run CUDA 11.8 version
docker-compose --profile cuda118 up --build

# Or run directly
docker build --build-arg TORCH_VERSION=cuda118 -t audiobook:cuda118 .
docker run --gpus all -p 8000:8000 -v $(pwd)/data:/app/data audiobook:cuda118
```

### NVIDIA GPU (CUDA 12.1+)

```bash
# Build and run CUDA 12.1 version
docker-compose --profile cuda121 up --build

# Or run directly
docker build --build-arg TORCH_VERSION=cuda121 -t audiobook:cuda121 .
docker run --gpus all -p 8000:8000 -v $(pwd)/data:/app/data audiobook:cuda121
```

### AMD GPU (ROCm)

```bash
# Build and run ROCm version
docker-compose --profile rocm up --build

# Or run directly
docker build --build-arg TORCH_VERSION=rocm -t audiobook:rocm .
docker run --device=/dev/kfd --device=/dev/dri --security-opt seccomp=unconfined \
    -p 8000:8000 -v $(pwd)/data:/app/data audiobook:rocm
```

## Building Images

### Build Arguments

- `TORCH_VERSION`: PyTorch variant to install
  - `cpu` - CPU-only (default)
  - `cuda118` - CUDA 11.8
  - `cuda121` - CUDA 12.1+
  - `rocm` - AMD ROCm

### Examples

```bash
# CPU-only
docker build --build-arg TORCH_VERSION=cpu -t audiobook:cpu .

# CUDA 11.8
docker build --build-arg TORCH_VERSION=cuda118 -t audiobook:cuda118 .

# CUDA 12.1
docker build --build-arg TORCH_VERSION=cuda121 -t audiobook:cuda121 .
```

## Docker Compose Profiles

The `docker-compose.yml` file uses profiles to manage different configurations:

- `cpu` - CPU-only version
- `cuda118` - CUDA 11.8 GPU version
- `cuda121` - CUDA 12.1 GPU version
- `rocm` - AMD ROCm GPU version

### Usage

```bash
# Start CPU version
docker-compose --profile cpu up -d

# Start GPU version (CUDA 11.8)
docker-compose --profile cuda118 up -d

# Stop
docker-compose down
```

## Volume Mounts

The following directories are mounted as volumes:

- `./data` → `/app/data` - Books, databases, models
- `./logs` → `/app/logs` - Application logs

## Environment Variables

Set via `docker-compose.yml` or `-e` flag:

- `TTS_GPU` - Enable GPU (true/false)
- `WEB_HOST` - Web server host (default: 0.0.0.0)
- `WEB_PORT` - Web server port (default: 8000)
- `AUDIO_OUTPUT_FORMAT` - Audio output format (m4b, mp3, wav, etc.)
- `AUDIO_BITRATE` - Audio bitrate (128k, 192k, 256k)

## GPU Support

### NVIDIA GPU Setup

1. Install NVIDIA Docker runtime:
   ```bash
   # Ubuntu/Debian
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
       sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   sudo apt-get update && sudo apt-get install -y nvidia-docker2
   sudo systemctl restart docker
   ```

2. Verify GPU access:
   ```bash
   docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
   ```

### AMD GPU Setup

1. Install ROCm Docker support (see ROCm documentation)

2. Run with device access:
   ```bash
   docker run --device=/dev/kfd --device=/dev/dri \
       --security-opt seccomp=unconfined ...
   ```

## Troubleshooting

### GPU Not Detected

- Verify NVIDIA Docker runtime: `docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi`
- Check Docker Compose GPU configuration
- Ensure `TTS_GPU=true` environment variable is set

### FFmpeg Not Found

FFmpeg is included in the Docker image. If you see errors, check:
- Container logs: `docker logs <container-name>`
- FFmpeg version: `docker exec <container-name> ffmpeg -version`

### Model Download Issues

Models are downloaded on first use. To pre-download:
- Mount HuggingFace cache: `-v ~/.cache/huggingface:/root/.cache/huggingface`
- Or set `HF_HOME` environment variable

## Production Deployment

For production, consider:

1. **Reverse Proxy**: Use nginx or Traefik in front of the container
2. **SSL/TLS**: Configure HTTPS via reverse proxy
3. **Resource Limits**: Set CPU/memory limits in docker-compose.yml
4. **Logging**: Configure log rotation and external logging
5. **Backups**: Regular backups of `/app/data` volume
6. **Monitoring**: Add health checks and monitoring

### Example Production docker-compose.yml

```yaml
services:
  audiobook:
    # ... existing config ...
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## Health Check

The container includes a health check endpoint at `/health`. Docker will automatically check this:

```bash
# Check health status
docker ps  # Look for "healthy" status

# Manual check
curl http://localhost:8000/health
```
