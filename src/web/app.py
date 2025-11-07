"""FastAPI web application."""

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from src.utils.config import get_settings
from src.web.database import init_db
from src.web.routes import router

app = FastAPI(title="Audiobook System", version="0.1.0")
settings = get_settings()

# Initialize database
init_db()

# CORS middleware for development (React dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="")

# Mount audio files from data directory
app.mount("/audio", StaticFiles(directory="data/books"), name="audio")

# Serve React build in production
dist_path = Path("web/dist")
if dist_path.exists():
    # Mount static assets (JS, CSS, etc.)
    app.mount("/assets", StaticFiles(directory="web/dist/assets"), name="assets")
    
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
else:
    # Development mode - serve a message
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve development message."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Audiobook Player - Development</title>
        </head>
        <body>
            <h1>Audiobook Player</h1>
            <p>React build not found. Run 'npm run build' to build the React app, or use 'npm run dev' for development.</p>
            <p>For development, start the React dev server with 'npm run dev' (runs on port 3000).</p>
        </body>
        </html>
        """


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.web.app:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=settings.debug,
    )

