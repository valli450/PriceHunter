"""
PriceHunter — Scraper Utilities.
"""
import re
import hashlib
from typing import Dict


def make_deal_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def get_affiliate_url(store: str, url: str) -> str:
    """Добавляет affiliate tracking параметры к URL."""
    from dotenv import dotenv_values
    config = dotenv_values()
    
    if store == "bestbuy":
        aid = config.get("BESTBUY_AFFILIATE_ID", "")
        if aid:
            sep = "&" if "?" in url else "?"
            return f"{url}{sep}affiliateId={aid}"
    elif store == "walmart":
        aid = config.get("WALMART_AFFILIATE_ID", "")
        if aid:
            sep = "&" if "?" in url else "?"
            return f"{url}{sep}veh=aff&wmlspartner={aid}"
    elif store == "amazon":
        tag = config.get("AMAZON_ASSOCIATE_TAG", "")
        if tag:
            sep = "&" if "?" in url else "?"
            return f"{url}{sep}tag={tag}"
    return url


def format_deal_message(deal: Dict) -> str:
    """Форматирует сделку для Telegram / уведомления."""
    emoji = "🔥" if deal["discount_pct"] >= 50 else "💰" if deal["discount_pct"] >= 30 else "💸"
    store_emojis = {"bestbuy": "🔵", "walmart": "🛒", "target": "🎯", "amazon": "📦"}
    store_emoji = store_emojis.get(deal["store"], "🏪")
    
    msg = (
        f"{emoji} {store_emoji} *{deal['title'][:80]}*\n"
        f"~~${deal['original_price']:.2f}~~ → *${deal['current_price']:.2f}* "
        f"(-{deal['discount_pct']:.0f}%)\n"
        f"  Магазин: {deal['store'].title()}\n"
        f"  [Открыть]({deal.get('affiliate_url', deal['url'])})"
    )
    return msg
