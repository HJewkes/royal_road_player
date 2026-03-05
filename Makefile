# ============================================================================
# Audiobook Makefile
# ============================================================================
# This project uses TWO virtual environments:
#
#   venv (Python 3.14+)
#     - General dependencies (FastAPI, web scraping, text processing)
#     - Used for: tests, linting, formatting
#
#   venv311 (Python 3.11)
#     - TTS dependencies (Coqui TTS requires Python 3.9-3.11)
#     - Includes all general dependencies + TTS libraries
#     - Used for: running the server (make dev, make dev-bg, make dev-all)
#
# The server MUST use venv311 to have TTS functionality available.
# ============================================================================

.PHONY: help setup teardown rebuild dev dev-bg kill-dev test lint format clean frontend-setup frontend-dev frontend-build dev-all

# Default target
help:
	@echo "Audiobook - Available commands:"
	@echo ""
	@echo "  Setup:"
	@echo "    make check-system   - Check system requirements (Python 3.11, Node.js)"
	@echo "    make setup          - Create venvs and install dependencies"
	@echo "    make teardown       - Clean everything for fresh start"
	@echo "    make rebuild        - teardown + setup"
	@echo ""
	@echo "  Development:"
	@echo "    make dev            - Run backend server"
	@echo "    make dev-bg         - Run backend server in background"
	@echo "    make kill-dev       - Stop all dev servers"
	@echo "    make dev-all        - Run both backend and frontend"
	@echo ""
	@echo "  Frontend:"
	@echo "    make frontend-setup - Install frontend dependencies"
	@echo "    make frontend-dev   - Run frontend dev server"
	@echo "    make frontend-build - Build frontend for production"
	@echo ""
	@echo "  Code Quality:"
	@echo "    make test           - Run tests"
	@echo "    make lint           - Run linters"
	@echo "    make format         - Format code"
	@echo "    make clean          - Remove build artifacts"
	@echo ""

# Check system requirements
check-system:
	@echo "Checking system requirements..."
	@which python3.11 > /dev/null || (echo "❌ Python 3.11 not found. Install with: brew install python@3.11" && exit 1)
	@which python3 > /dev/null || (echo "❌ Python 3 not found" && exit 1)
	@which node > /dev/null || (echo "❌ Node.js not found" && exit 1)
	@echo "✅ System requirements met"

# Setup virtual environment and install dependencies
setup: check-system
	@echo "Creating virtual environments..."
	@echo "Creating venv (Python 3) for general dependencies..."
	@if [ -d "venv" ]; then echo "⚠️  venv already exists, skipping creation"; else python3 -m venv venv; fi
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r backend/requirements.txt
	@echo "Creating venv311 (Python 3.11) for TTS dependencies..."
	@if [ -d "venv311" ]; then echo "⚠️  venv311 already exists, skipping creation"; else python3.11 -m venv venv311; fi
	./venv311/bin/pip install --upgrade pip
	./venv311/bin/pip install -r backend/requirements.txt -r backend/requirements-tts.txt
	@echo "✅ Setup complete!"
	@echo "  - venv (Python 3.14+): General dependencies"
	@echo "  - venv311 (Python 3.11): TTS dependencies (used by server)"

# Run development server (uses venv311 for TTS support)
dev:
	@if [ ! -d "venv311" ]; then echo "❌ venv311 not found. Run 'make setup' first." && exit 1; fi
	@echo "Starting development server (using venv311 for TTS support)..."
	cd backend && ../venv311/bin/python main.py

# Run in background
dev-bg:
	@if [ ! -d "venv311" ]; then echo "❌ venv311 not found. Run 'make setup' first." && exit 1; fi
	@echo "Starting development server in background (using venv311)..."
	cd backend && ../venv311/bin/python main.py &

# Kill dev servers
kill-dev:
	@echo "Stopping development servers..."
	-pkill -f "python main.py" || true
	-pkill -f "vite" || true
	-pkill -f "npm run dev" || true
	@echo "✅ Servers stopped"

# Run tests (uses venv - doesn't need TTS)
test:
	@if [ ! -d "venv" ]; then echo "❌ venv not found. Run 'make setup' first." && exit 1; fi
	cd backend && ../venv/bin/pytest tests/ -v

# Run linters (uses venv - doesn't need TTS)
lint:
	@if [ ! -d "venv" ]; then echo "❌ venv not found. Run 'make setup' first." && exit 1; fi
	cd backend && ../venv/bin/python -m mypy src/
	cd backend && ../venv/bin/python -m pylint src/

# Format code (uses venv - doesn't need TTS)
format:
	@if [ ! -d "venv" ]; then echo "❌ venv not found. Run 'make setup' first." && exit 1; fi
	cd backend && ../venv/bin/python -m black src/ tests/
	cd backend && ../venv/bin/python -m isort src/ tests/

# Clean build artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleaned!"

# Frontend commands
frontend-setup:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

# Teardown - clean everything for fresh start
teardown:
	@echo "🧹 Cleaning up..."
	rm -rf venv venv311 || true
	rm -rf frontend/node_modules frontend/dist || true
	rm -rf data/cache || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Rebuild - teardown + setup
rebuild: teardown setup

# Run both backend and frontend dev servers
dev-all:
	@if [ ! -d "venv311" ]; then echo "❌ venv311 not found. Run 'make setup' first." && exit 1; fi
	@echo "Starting backend and frontend dev servers..."
	@echo "📡 Backend: http://localhost:8000 (using venv311 for TTS)"
	@echo "🌐 Frontend: http://localhost:5173"
	@echo "🛑 Press Ctrl+C to stop both servers"
	@trap 'pkill -f "python main.py" 2>/dev/null; pkill -f "vite" 2>/dev/null; exit' EXIT INT TERM; \
	(cd backend && ../venv311/bin/python main.py > /tmp/backend.log 2>&1) & \
	(cd frontend && npm run dev > /tmp/frontend.log 2>&1) & \
	wait

