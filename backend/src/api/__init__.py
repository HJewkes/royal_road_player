"""API routes module."""

from src.api.routes import app
from src.api.requests import (
    AddFictionRequest,
    BackfillResult,
    BackfillTitlesRequest,
    ChunkRequest,
    DownloadRequest,
    ExportRequest,
    FictionInfo,
    FictionPreview,
    GenerateRequest,
    NormalizeRequest,
    SeriesBookInfo,
    ValidateRequest,
)

__all__ = [
    'app',
    # Request models
    'AddFictionRequest',
    'BackfillResult',
    'BackfillTitlesRequest',
    'ChunkRequest',
    'DownloadRequest',
    'ExportRequest',
    'FictionInfo',
    'FictionPreview',
    'GenerateRequest',
    'NormalizeRequest',
    'SeriesBookInfo',
    'ValidateRequest',
]

