# ============================================================================
# Audiobook Makefile
# ============================================================================
# This project uses these virtual environments:
#
#   venv (Python 3.14+)
#     - General dependencies (FastAPI, web scraping, text processing)
#     - Used for: linting, formatting
#
#   venv311 (Python 3.11)
#     - TTS dependencies (Coqui TTS requires Python 3.9-3.11)
#     - Includes all general dependencies + TTS libraries
#     - Used for: running the server on the Mac
#
#   venv-cu128 (Python 3.12, Linux + NVIDIA)
#     - TTS on CUDA 12.8, plus the MCP server (make setup-cuda)
#
# The server, tests and MCP server run on the venv that scripts/venv.sh picks:
# $AUDIOBOOK_VENV, else venv-cu128, else venv311.
# ============================================================================

.PHONY: help setup setup-cuda check-cuda install-timer uninstall-timer teardown rebuild dev dev-bg kill-dev test lint format clean frontend-setup frontend-dev frontend-build dev-all

# Default target
help:
	@echo "Audiobook - Available commands:"
	@echo ""
	@echo "  Setup:"
	@echo "    make check-system   - Check system requirements (Python 3.11, Node.js)"
	@echo "    make setup          - Create venvs and install dependencies"
	@echo "    make setup-cuda     - Create venv-cu128 (Linux CUDA) with uv"
	@echo "    make check-cuda     - Smoke-import torch/TTS on CUDA in gpu-jobs.slice"
	@echo "    make install-timer  - Link and enable the systemd autopull timer (Linux)"
	@echo "    make uninstall-timer - Disable and unlink the systemd autopull timer"
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
	./venv311/bin/pip install -r backend/requirements.txt -r backend/requirements-tts.txt -r mcp_server/requirements.txt
	@echo "✅ Setup complete!"
	@echo "  - venv (Python 3.14+): General dependencies"
	@echo "  - venv311 (Python 3.11): TTS dependencies (used by server)"

# Linux CUDA venv: uv fetches Python 3.12 itself, so no system python is needed
# best-match: the cu128 index also carries old copies of PyPI packages (requests)
setup-cuda:
	@command -v uv > /dev/null || (echo "❌ uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh" && exit 1)
	@if [ -d "venv-cu128" ]; then echo "⚠️  venv-cu128 already exists, skipping creation"; else uv venv --python 3.12 venv-cu128; fi
	cd backend && uv pip install --python ../venv-cu128/bin/python --index-strategy unsafe-best-match -r requirements-cu128.txt
	@echo "✅ venv-cu128 ready. Check it with: make check-cuda"

# GPU work on this host runs in gpu-jobs.slice, which freezes during a stream
check-cuda:
	systemd-run --user --slice=gpu-jobs.slice --wait --pipe --quiet --same-dir \
		--setenv=AUDIOBOOK_VENV="$(AUDIOBOOK_VENV)" \
		bash scripts/venv.sh scripts/check_cuda.py

# Unattended autopull on Linux: link the units from deploy/systemd into the user
# manager. Refuses without the env file, since autopull publishes by default.
AUTOPULL_ENV := $(HOME)/.config/audiobook/autopull.env
SYSTEMD_UNITS := $(CURDIR)/deploy/systemd

install-timer:
	@test -f "$(AUTOPULL_ENV)" || (echo "❌ $(AUTOPULL_ENV) not found. Start from deploy/systemd/autopull.env.example" && exit 1)
	systemctl --user link "$(SYSTEMD_UNITS)/audiobook-autopull.service" \
		"$(SYSTEMD_UNITS)/audiobook-autopull-failed.service" "$(SYSTEMD_UNITS)/audiobook-autopull.timer"
	systemctl --user daemon-reload
	systemctl --user enable --now audiobook-autopull.timer
	@echo "✅ Timer enabled. Check it with: systemctl --user list-timers audiobook-autopull.timer"

# disable also removes the symlinks that link created
uninstall-timer:
	-systemctl --user disable --now audiobook-autopull.timer
	-systemctl --user disable audiobook-autopull.service audiobook-autopull-failed.service
	systemctl --user daemon-reload
	@echo "✅ Timer removed"

# Run development server on the resolved venv (TTS needs venv311 or venv-cu128)
dev:
	@echo "Starting development server..."
	cd backend && bash ../scripts/venv.sh main.py

# Run in background
dev-bg:
	@echo "Starting development server in background..."
	cd backend && bash ../scripts/venv.sh main.py &

# Kill dev servers
kill-dev:
	@echo "Stopping development servers..."
	-pkill -f "python main.py" || true
	-pkill -f "vite" || true
	-pkill -f "npm run dev" || true
	@echo "✅ Servers stopped"

# Run tests on the resolved venv (they need no TTS, but every venv has pytest)
test:
	cd backend && bash ../scripts/venv.sh -m pytest tests/ -v

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
	@echo "Starting backend and frontend dev servers..."
	@echo "📡 Backend: http://localhost:8000"
	@echo "🌐 Frontend: http://localhost:5173"
	@echo "🛑 Press Ctrl+C to stop both servers"
	@trap 'pkill -f "python main.py" 2>/dev/null; pkill -f "vite" 2>/dev/null; exit' EXIT INT TERM; \
	(cd backend && bash ../scripts/venv.sh main.py > /tmp/backend.log 2>&1) & \
	(cd frontend && npm run dev > /tmp/frontend.log 2>&1) & \
	wait

