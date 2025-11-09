# Project Structure

> **Last Updated:** 2025-01-27  
> **Status:** Current

## Overview

The project is organized with clear separation between Python backend and TypeScript frontend code. This separation makes it easier to:
- Maintain language-specific tooling and dependencies
- Scale frontend and backend independently
- Onboard developers familiar with either stack
- Deploy components separately if needed

## Directory Structure

```
audiobook/
├── backend/                 # Python backend
│   ├── src/                # Python source code
│   │   ├── controllers/    # Business logic controllers
│   │   ├── data/           # Data persistence layer
│   │   ├── llm/           # LLM annotation modules
│   │   ├── models/         # Data models
│   │   ├── scraper/       # Web scraping modules
│   │   ├── services/       # Service layer (uses controllers)
│   │   ├── text_processing/ # Text processing pipeline
│   │   ├── tts/           # Text-to-speech engine
│   │   ├── utils/         # Utility functions
│   │   └── web/           # FastAPI backend
│   │       ├── app.py     # FastAPI application
│   │       ├── routes.py  # API routes
│   │       └── models/    # Request/response models
│   ├── tests/             # Test code (mirrors src/)
│   ├── requirements.txt   # Python production dependencies
│   ├── requirements-dev.txt # Python dev dependencies
│   ├── pytest.ini         # Test configuration
│   └── README.md          # Backend documentation
│
├── frontend/              # TypeScript/React frontend
│   ├── src/
│   │   ├── components/    # React components (.tsx)
│   │   ├── store/         # Zustand state stores (.ts)
│   │   ├── styles/        # CSS modules and global styles
│   │   ├── types/         # TypeScript type definitions
│   │   ├── App.tsx        # Main app component
│   │   └── main.tsx       # Entry point
│   ├── dist/              # Built frontend (generated, gitignored)
│   ├── package.json       # Node.js dependencies
│   ├── tsconfig.json      # TypeScript configuration
│   ├── vite.config.ts     # Vite build configuration
│   ├── index.html         # HTML entry point
│   └── README.md          # Frontend documentation
│
├── scripts/               # Utility scripts
├── data/                  # Runtime data (gitignored)
│   ├── books/            # Book data
│   ├── checkpoints/      # Checkpoint files
│   ├── metrics/          # Metrics reports
│   └── voices/           # Voice registry configs
├── logs/                  # Application logs (gitignored)
├── docs/                  # Documentation
│
├── Makefile              # Build automation
├── SETUP.md              # Setup instructions
├── README.md             # Main project documentation
└── .env                  # Environment variables (gitignored)
```

## Language Separation

### Python Backend (`backend/`)

All Python code lives in `backend/`:
- **Controllers**: `backend/src/controllers/` - Business logic operations
- **Data Layer**: `backend/src/data/` - Persistence (DataSynchronizer)
- **Models**: `backend/src/models/` - Data models with accessors
- **Scraper**: `backend/src/scraper/` - Web scraping logic
- **TTS**: `backend/src/tts/` - Text-to-speech engine (XTTS v2)
- **Text Processing**: `backend/src/text_processing/` - Text normalization, chunking, segmentation
- **Services**: `backend/src/services/` - Service layer (uses controllers)
- **Web API**: `backend/src/web/` - FastAPI application
- **Utils**: `backend/src/utils/` - Shared utilities
- **Tests**: `backend/tests/` - Test code (mirrors src/)

**Configuration Files:**
- `backend/requirements.txt` - Production dependencies
- `backend/requirements-dev.txt` - Development dependencies
- `backend/pytest.ini` - Test configuration
- `.env` (project root) - Environment variables

### TypeScript Frontend (`frontend/`)

All TypeScript/React code lives in `frontend/`:
- **Components**: `frontend/src/components/` - React components
- **State**: `frontend/src/store/` - Zustand stores
- **Styles**: `frontend/src/styles/` - CSS modules
- **Types**: `frontend/src/types/` - TypeScript definitions

**Configuration Files:**
- `frontend/package.json` - Node.js dependencies
- `frontend/tsconfig.json` - TypeScript configuration
- `frontend/vite.config.ts` - Build configuration

## Build Process

### Frontend Build

```bash
cd frontend
npm install      # Install dependencies
npm run build    # Build for production
```

Output goes to `frontend/dist/` where FastAPI serves it.

### Backend

```bash
source venv/bin/activate
pip install -r backend/requirements.txt
cd backend && python -m src.web.app
```

## Development Workflow

### Frontend Development

```bash
cd frontend
npm run dev      # Start Vite dev server (port 3000)
```

The dev server proxies `/api` and `/audio` to the FastAPI backend (port 8000).

### Backend Development

```bash
source venv/bin/activate
make dev         # Start FastAPI with auto-reload
```

### Full Stack Development

1. Terminal 1: `make dev` (FastAPI backend)
2. Terminal 2: `make dev-frontend` (React dev server)
3. Open `http://localhost:3000` (dev server) or `http://localhost:8000` (production build)

## Key Decisions

1. **Separate Directories**: Python and TypeScript code are completely separated
2. **Build Output**: Frontend builds to `frontend/dist/` which FastAPI serves
3. **Configuration**: Each language has its own config files in its directory
4. **Makefile**: Centralized build automation that handles both languages
5. **Controllers Pattern**: Business logic separated into single-responsibility controllers
6. **Models with Accessors**: Models contain data + computed properties
7. **Data Synchronizer**: Centralized persistence layer
