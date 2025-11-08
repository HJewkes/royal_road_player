"""Scraper module."""

from src.scraper.royal_road_client import RoyalRoadClient
from src.scraper.html_processor import HTMLProcessor
from src.scraper.royal_road_controller import RoyalRoadController

__all__ = [
    'RoyalRoadClient',
    'HTMLProcessor',
    'RoyalRoadController',
]

