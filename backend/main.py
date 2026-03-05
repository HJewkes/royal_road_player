"""Audiobook V2 - Main entry point."""

import uvicorn

from src.api.routes import app
from src.config import get_settings

# Export app for uvicorn
__all__ = ["app"]


def main():
    """Run the application."""
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()

