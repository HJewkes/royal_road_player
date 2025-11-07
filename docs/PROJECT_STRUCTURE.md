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
│   │   ├── scraper/        # Web scraping modules
│   │   ├── tts/            # Text-to-speech engine
│   │   ├── llm/            # LLM annotation modules
│   │   ├── services/       # Business logic services
│   │   ├── utils/          # Utility functions
│   │   └── web/            # FastAPI backend
│   │       ├── app.py      # FastAPI application
│   │       ├── routes.py   # API routes
│   │       ├── database.py # Database setup
│   │       ├── jobs.py     # Background job management
│   │       └── models.py   # Data models
│   ├── tests/              # Test code (mirrors src/)
│   ├── requirements.txt    # Python production dependencies
│   ├── requirements-dev.txt # Python dev dependencies
│   ├── pytest.ini          # Test configuration
│   └── README.md           # Backend documentation
│
├── frontend/               # TypeScript/React frontend
│   ├── src/
│   │   ├── components/     # React components (.tsx)
│   │   ├── store/          # Zustand state stores (.ts)
│   │   ├── styles/         # CSS modules and global styles
│   │   ├── types/          # TypeScript type definitions
│   │   ├── App.tsx         # Main app component
│   │   └── main.tsx        # Entry point
│   ├── dist/               # Built frontend (generated, gitignored)
│   ├── package.json        # Node.js dependencies
│   ├── tsconfig.json       # TypeScript configuration
│   ├── vite.config.ts      # Vite build configuration
│   ├── index.html          # HTML entry point
│   └── README.md           # Frontend documentation
│
├── scripts/                 # Utility scripts
├── data/                    # Runtime data (gitignored)
├── logs/                    # Application logs (gitignored)
├── docs/                    # Documentation
│
├── Makefile                # Build automation
└── .env                    # Environment variables
```

## Language Separation

### Python Backend (`backend/`)

All Python code lives in `backend/`:
- **Source Code**: `backend/src/` - All Python modules
  - **Scraper**: `backend/src/scraper/` - Web scraping logic
  - **TTS**: `backend/src/tts/` - Text-to-speech engine
  - **Services**: `backend/src/services/` - Business logic layer
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
- `frontend/.eslintrc.cjs` - ESLint configuration

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

## Migration Notes

This structure was migrated from a mixed structure where TypeScript files were in `src/` alongside Python files. The migration:
- Moved all `.tsx`, `.ts`, `.css` files to `frontend/src/`
- Moved `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html` to `frontend/`
- Updated `vite.config.ts` to build to `dist/` (within frontend/)
- Updated `Makefile` to run npm commands from `frontend/`
- Updated `.gitignore` to ignore `frontend/node_modules/`
- Updated documentation to reflect new structure

