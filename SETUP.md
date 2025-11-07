# Setup Guide

## Prerequisites

### System Requirements
- **Python:** 3.10 or higher
- **RAM:** 8GB minimum (16GB recommended for TTS)
- **Storage:** 10GB+ free space
- **GPU:** Optional but recommended for faster TTS generation

### Manual Steps

#### 1. Install Ollama

Ollama is required for LLM-based text annotation.

**macOS/Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows:**
Download installer from https://ollama.ai

**Verify installation:**
```bash
ollama --version
```

**Pull a model:**
```bash
ollama pull llama3.1:8b
# or
ollama pull mistral:7b
```

#### 2. Configure Environment

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and configure:
- `OLLAMA_MODEL`: The model you pulled (e.g., `llama3.1:8b`)
- `TTS_ENGINE`: Choose `coqui` or `piper`
- Other settings as needed

## Automated Setup

Run the setup command:
```bash
make setup
```

This will:
1. Check system requirements
2. Create Python virtual environment
3. Install all dependencies
4. Create necessary directories
5. Set up configuration files

## Verify Installation

```bash
# Activate virtual environment
source venv/bin/activate

# Run tests
make test

# Check system
make check-system
```

## Troubleshooting

### Ollama Not Found
- Ensure Ollama is in your PATH
- Restart terminal after installation
- Verify with `which ollama`

### TTS Model Download Issues
- Coqui TTS models download automatically on first use
- Ensure sufficient disk space (models can be 1-2GB)
- Check internet connection

### Python Version Issues
- Ensure Python 3.10+: `python3 --version`
- Use `python3` explicitly if `python` points to older version

### Permission Errors
- Use `python3 -m venv venv` instead of `virtualenv`
- Ensure write permissions in project directory

## Next Steps

After setup, see [README.md](README.md) for usage instructions.

