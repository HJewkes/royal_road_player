.PHONY: help setup teardown rebuild check-system install dev test test-coverage lint format format-check run clean

help: ## Show available commands
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

check-system: ## Validate system prerequisites
	@echo "🔍 Checking system requirements..."
	@python3 --version || (echo "❌ Python 3.10+ required" && exit 1)
	@python_version=$$(python3 --version 2>&1 | awk '{print $$2}' | cut -d. -f1,2); \
	if [ "$$(echo "$$python_version >= 3.12" | bc 2>/dev/null || echo 0)" = "1" ]; then \
		echo "⚠️  Warning: Python $$python_version detected. Coqui TTS requires Python <3.12."; \
		echo "   Consider using Python 3.11 for TTS support, or use Piper TTS instead."; \
	fi
	@echo "✅ System checks passed"

install-ollama: ## Install Ollama (if not present)
	@echo "📥 Checking Ollama installation..."
	@if ! command -v ollama > /dev/null 2>&1; then \
		echo "📦 Installing Ollama..."; \
		curl -fsSL https://ollama.ai/install.sh | sh || (echo "❌ Failed to install Ollama. Please install manually from https://ollama.ai" && exit 1); \
	else \
		echo "✅ Ollama already installed: $$(ollama --version)"; \
	fi

install-tts-coqui: ## Install Coqui TTS
	@echo "📥 Installing Coqui TTS..."
	@if [ ! -d venv ]; then \
		echo "❌ Virtual environment not found. Run 'make setup' first." && exit 1; \
	fi
	@. venv/bin/activate && pip install TTS>=0.22.0 || (echo "❌ Failed to install Coqui TTS" && exit 1)
	@echo "✅ Coqui TTS installed. Models will download on first use."

setup-tts-model: ## Check and setup TTS model
	@echo "📥 Checking TTS model setup..."
	@if [ ! -d venv ]; then \
		echo "❌ Virtual environment not found. Run 'make setup' first." && exit 1; \
	fi
	@. venv/bin/activate && PYTHONPATH=backend python scripts/setup_tts.py || (echo "⚠️  TTS model setup failed" && exit 1)
	@echo "✅ TTS model ready"

install-tts-piper: ## Install Piper TTS (requires manual download)
	@echo "📥 Piper TTS installation..."
	@echo "⚠️  Piper TTS requires manual setup:"
	@echo "   1. Download from: https://github.com/rhasspy/piper/releases"
	@echo "   2. Extract to a directory"
	@echo "   3. Set PIPER_PATH in .env file"
	@echo "   Or use: pip install piper-tts (if available)"

install-tts: install-tts-coqui ## Install TTS system (defaults to Coqui)
	@echo "✅ TTS system ready"

setup-ollama-model: ## Pull default Ollama model
	@echo "📥 Pulling Ollama model..."
	@if ! command -v ollama > /dev/null 2>&1; then \
		echo "❌ Ollama not installed. Run 'make install-ollama' first." && exit 1; \
	fi
	@. venv/bin/activate && PYTHONPATH=backend python scripts/setup_ollama.py || (echo "⚠️  Model pull failed. You can pull manually with: ollama pull llama3.1:8b" && exit 1)
	@echo "✅ Ollama model ready"

setup: check-system install-ollama ## Complete one-command setup
	@echo "🚀 Setting up audiobook system..."
	@python3 -m venv venv || (echo "❌ Failed to create venv" && exit 1)
	@. venv/bin/activate && pip install --upgrade pip
	@. venv/bin/activate && pip install -r backend/requirements.txt
	@. venv/bin/activate && pip install -r backend/requirements-dev.txt
	@$(MAKE) install-tts
	@mkdir -p data/books data/databases data/checkpoints logs
	@mkdir -p frontend/src/components frontend/src/store frontend/src/styles frontend/src/types
	@mkdir -p scripts
	@touch data/.gitkeep data/books/.gitkeep data/databases/.gitkeep data/checkpoints/.gitkeep
	@touch logs/.gitkeep
	@if ! command -v npm > /dev/null 2>&1; then \
		echo "⚠️  npm not found. Install Node.js to build React frontend."; \
		echo "   For now, you can use the backend API directly."; \
	else \
		echo "📦 Installing Node.js dependencies..."; \
		cd frontend && npm install || (echo "⚠️  Failed to install npm dependencies. You can install manually with 'cd frontend && npm install'" && exit 0); \
		echo "✅ Node.js dependencies installed"; \
	fi
	@if [ ! -f .env ]; then \
		echo "OLLAMA_BASE_URL=http://localhost:11434" > .env; \
		echo "OLLAMA_MODEL=llama3.1:8b" >> .env; \
		echo "TTS_ENGINE=coqui" >> .env; \
		echo "TTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2" >> .env; \
		echo "TTS_LANGUAGE=en" >> .env; \
		echo "TTS_SPEED=1.0" >> .env; \
		echo "WEB_HOST=127.0.0.1" >> .env; \
		echo "WEB_PORT=8000" >> .env; \
		echo "DEBUG=false" >> .env; \
		echo "DATA_DIR=./data" >> .env; \
		echo "BOOKS_DIR=./data/books" >> .env; \
		echo "AUDIO_DIR=./data/books" >> .env; \
		echo "DATABASE_PATH=./data/databases/audiobook.db" >> .env; \
		echo "SCRAPER_DELAY_SECONDS=2" >> .env; \
		echo "SCRAPER_USER_AGENT=Mozilla/5.0 (compatible; AudiobookBot/1.0)" >> .env; \
		echo "SCRAPER_RETRY_ATTEMPTS=3" >> .env; \
		echo "LOG_LEVEL=INFO" >> .env; \
		echo "LOG_DIR=./logs" >> .env; \
		echo "📝 Created .env file"; \
	fi
	@echo "✅ Setup complete! Activate venv with: source venv/bin/activate"
	@echo "💡 Optional: Run 'make setup-ollama-model' to pull the default LLM model"
	@echo "💡 Optional: Run 'make setup-tts-model' to check/download TTS models"

teardown: ## Complete cleanup to clean state
	@echo "🧹 Cleaning up..."
	@rm -rf venv || true
	@rm -rf frontend/node_modules frontend/dist || true
	@rm -rf data/books/* data/databases/* data/checkpoints/* logs/* || true
	@rm -rf .pytest_cache .mypy_cache htmlcov .coverage || true
	@rm -rf backend/.pytest_cache backend/.mypy_cache backend/htmlcov backend/.coverage || true
	@rm -rf backend/__pycache__ backend/src/**/__pycache__ backend/tests/**/__pycache__ || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + || true
	@echo "✅ Cleanup complete"

rebuild: teardown setup ## Teardown + setup (recovery)

install: ## Install dependencies only
	@echo "📦 Installing dependencies..."
	@. venv/bin/activate && pip install -r backend/requirements.txt
	@. venv/bin/activate && pip install -r backend/requirements-dev.txt
	@echo "✅ Dependencies installed"

dev: ## Run in development mode
	@echo "🔧 Starting development server..."
	@. venv/bin/activate && cd backend && python -m src.web.app --reload

test: ## Run all tests
	@echo "🧪 Running tests..."
	@. venv/bin/activate && cd backend && pytest tests/ -v

test-coverage: ## Run tests with coverage
	@echo "📊 Running tests with coverage..."
	@. venv/bin/activate && cd backend && pytest tests/ --cov=src --cov-report=html --cov-report=term

lint: ## Run all linters
	@echo "🔍 Running linters..."
	@. venv/bin/activate && cd backend && flake8 src tests
	@. venv/bin/activate && cd backend && pylint src
	@. venv/bin/activate && cd backend && mypy src

format: ## Format code
	@echo "✨ Formatting code..."
	@. venv/bin/activate && cd backend && black src tests
	@. venv/bin/activate && cd backend && isort src tests

format-check: ## Check formatting
	@echo "🔍 Checking code formatting..."
	@. venv/bin/activate && cd backend && black --check src tests
	@. venv/bin/activate && cd backend && isort --check src tests

run: ## Run application
	@echo "🎵 Starting audiobook web app..."
	@if [ ! -d "frontend/dist" ] || [ -z "$$(ls -A frontend/dist 2>/dev/null)" ]; then \
		echo "⚠️  React build not found. Building React app..."; \
		if command -v npm > /dev/null 2>&1; then \
			cd frontend && npm run build || (echo "❌ Failed to build React app. Run 'cd frontend && npm install' first." && exit 1); \
		else \
			echo "❌ npm not found. Install Node.js to build React frontend."; \
			echo "   Backend will run but frontend won't be available."; \
		fi; \
	fi
	@. venv/bin/activate && cd backend && python -m src.web.app

build-frontend: ## Build React frontend
	@echo "🔨 Building React frontend..."
	@if ! command -v npm > /dev/null 2>&1; then \
		echo "❌ npm not found. Please install Node.js." && exit 1; \
	fi
	@cd frontend && npm run build
	@echo "✅ Frontend built successfully"

dev-frontend: ## Run React dev server (for development)
	@echo "🔧 Starting React dev server..."
	@if ! command -v npm > /dev/null 2>&1; then \
		echo "❌ npm not found. Please install Node.js." && exit 1; \
	fi
	@cd frontend && npm run dev

clean: ## Remove build artifacts
	@echo "🧹 Cleaning build artifacts..."
	@rm -rf .pytest_cache .mypy_cache htmlcov .coverage
	@rm -rf backend/.pytest_cache backend/.mypy_cache backend/htmlcov backend/.coverage
	@rm -rf backend/__pycache__ backend/src/**/__pycache__ backend/tests/**/__pycache__
	@find . -type d -name "*.egg-info" -exec rm -rf {} + || true

