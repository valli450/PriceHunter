"""
PriceHunter — Scraper Engine (async, Playwright-based).
"""
import asyncio
from typing import List, Dict
from datetime import datetime

from scraper.playwright_scraper import scrape_all_stores as _async_scrape
from scraper.utils import format_deal_message


def scrape_all_stores() -> List[Dict]:
    """Синхронная обёртка над async scraper."""
    return asyncio.run(_async_scrape())
