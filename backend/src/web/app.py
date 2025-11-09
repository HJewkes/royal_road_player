"""FastAPI web application."""

import os
import asyncio
import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.utils.config import get_settings
from src.web.routes import router
from src.services.job_queue import get_queue
from src.data.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - start/stop background services."""
    # Startup: Initialize database
    init_db()
    print("✅ Database initialized")
    
    # Startup: Start background processor
    queue = get_queue()
    queue.start_background_processor(interval_seconds=1.0)
    print("✅ Background job processor started (logs: logs/queue_processor.log)")
    
    yield
    
    # Shutdown: Stop background processor
    if queue._processor_task and not queue._processor_task.done():
        queue._processor_task.cancel()
        try:
            await queue._processor_task
        except asyncio.CancelledError:
            pass
        print("✅ Background job processor stopped")


app = FastAPI(title="Audiobook System", version="0.1.0", lifespan=lifespan)

# CORS middleware for development (React dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="")

# Get project root (backend/../)
project_root = Path(__file__).parent.parent.parent.parent

# Mount audio files from data directory (relative to project root)
app.mount("/audio", StaticFiles(directory=str(project_root / "data" / "books")), name="audio")

# Determine if we're in development mode
# Check environment variable first (overrides .env file), then settings.debug, then dist existence
DEV_SERVER_URL = "http://localhost:3000"
dist_path = project_root / "frontend" / "dist"
debug_env = os.getenv("DEBUG", "").lower() in ("true", "1", "yes")
is_development = debug_env or settings.debug or not dist_path.exists()

if is_development:
    # Development mode - redirect to frontend dev server
    @app.get("/")
    async def root():
        """Redirect to frontend dev server in development mode."""
        return RedirectResponse(url=DEV_SERVER_URL, status_code=307)
    
    # Also redirect all non-API routes to dev server in development
    @app.get("/{full_path:path}")
    async def redirect_to_dev(full_path: str, request: Request):
        """Redirect non-API routes to frontend dev server in development."""
        # Don't redirect API or audio routes
        if full_path.startswith("api/") or full_path.startswith("audio/"):
            return {"detail": "Not found"}
        
        # Redirect to dev server, preserving the path
        return RedirectResponse(url=f"{DEV_SERVER_URL}/{full_path}", status_code=307)
else:
    # Production mode - serve React build
    if dist_path.exists():
        # Mount static assets (JS, CSS, etc.)
        app.mount("/assets", StaticFiles(directory=str(dist_path / "assets")), name="assets")
        
        # Serve index.html for all non-API routes (SPA routing)
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str, request: Request):
            """Serve React app for all non-API routes."""
            # Don't serve React for API routes
            if full_path.startswith("api/") or full_path.startswith("audio/"):
                return {"detail": "Not found"}
            
            # Serve index.html for all other routes
            index_path = dist_path / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            else:
                return HTMLResponse("""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Audiobook Player</title>
                </head>
                <body>
                    <h1>Audiobook Player</h1>
                    <p>React build not found. Please run 'npm run build' to build the React app.</p>
                </body>
                </html>
                """)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "src.web.app:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=settings.debug,
    )

