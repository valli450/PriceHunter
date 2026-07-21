"""
Target Scraper
Собирает скидки с категорий электроники.
Target использует API (search/redsky) для загрузки товаров.
"""
import re
import json
from typing import List, Dict
from urllib.parse import urljoin, urlencode

import httpx
from bs4 import BeautifulSoup

from scraper.utils import make_deal_id, get_affiliate_url

STORE = "target"
BASE = "https://www.target.com"


def scrape_deals() -> List[Dict]:
    """
    Target отдаёт данные через RedSky API.
    Пробуем прямой запрос к API + fallback на парсинг HTML.
    """
    deals = []
    seen_ids = set()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    categories = [
        "https://www.target.com/c/electronics/-/N-5xtgr",      # All Electronics
        "https://www.target.com/c/tv-video/-/N-5xsxt",          # TVs
        "https://www.target.com/c/laptops/-/N-5xspf",           # Laptops
        "https://www.target.com/c/video-games/-/N-5xsxi",       # Gaming
        "https://www.target.com/c/headphones/-/N-55nt0",        # Headphones
        "https://www.target.com/c/clearance/-/N-5xtbw",         # Clearance
        "https://www.target.com/c/deals/-/N-54bxl",             # Deals
    ]
    
    with httpx.Client(headers=headers, follow_redirects=True, timeout=30) as client:
        for cat_url in categories:
            try:
                resp = client.get(cat_url)
                resp.raise_for_status()
            except Exception as e:
                print(f"  [Target] Failed: {cat_url}: {e}")
                continue
            
            soup = BeautifulSoup(resp.text, "lxml")
            
            # Target встраивает JSON-LD и __TGT_DATA__ в HTML
            _extract_from_html(soup, client, cat_url, deals, seen_ids)
    
    return deals


def _extract_from_html(soup, client, base_url, deals, seen_ids):
    """Извлекает товары из HTML страницы Target."""
    
    # Попытка 1: JSON-LD
    for script in soup.select("script[type='application/ld+json']"):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                _make_deal_from_ld(item, deals, seen_ids)
        except:
            pass
    
    # Попытка 2: Карточки товаров из HTML
    products = soup.select("[data-test='product-card'], [class*='product-card'], [class*='h-padding-a-tiny']")
    for card in products:
        _extract_card(card, deals, seen_ids)
    
    # Попытка 3: window.__TGT_DATA__
    for script in soup.find_all("script"):
        if script.string and "__TGT_DATA__" in script.string:
            try:
                match = re.search(r'window\.__TGT_DATA__\s*=\s*({.*?});', script.string, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    _find_products_in_tgt_data(data, deals, seen_ids)
            except:
                pass


def _make_deal_from_ld(item, deals, seen_ids):
    """Извлекает сделку из JSON-LD."""
    name = item.get("name", "")
    if not name:
        return
    
    url = item.get("url", "")
    if not url:
        return
    
    if not url.startswith("http"):
        url = urljoin(BASE, url)
    
    deal_id = make_deal_id(url)
    if deal_id in seen_ids:
        return
    
    offers = item.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    
    price = offers.get("price", 0)
    currency = offers.get("priceCurrency", "USD")
    
    # Target JSON-LD не всегда содержит original price
    # Пробуем найти highPrice / wasPrice
    orig = float(item.get("highPrice", item.get("price", 0)))
    curr = float(price)
    
    if curr >= orig or orig <= 0:
        # Возможно скидка не указана в JSON-LD
        return
    
    discount = round((orig - curr) / orig * 100, 1)
    img = item.get("image", "")
    
    deal = {
        "id": deal_id,
        "store": STORE,
        "title": name[:200],
        "url": url,
        "image_url": img if isinstance(img, str) else (img[0] if isinstance(img, list) else ""),
        "original_price": round(orig, 2),
        "current_price": round(curr, 2),
        "discount_pct": discount,
        "category": _categorize(name),
        "affiliate_url": url,  # Target нет прямого affiliate
    }
    seen_ids.add(deal_id)
    deals.append(deal)


def _extract_card(card, deals, seen_ids):
    """Извлекает данные из HTML карточки товара."""
    # Ссылка
    link = card.select_one("a[href*='/p/'], a[data-test='product-title']")
    if not link:
        return
    href = link.get("href", "")
    if not href:
        return
    
    url = urljoin(BASE, href)
    deal_id = make_deal_id(url)
    if deal_id in seen_ids:
        return
    
    # Название
    title_el = card.select_one("[data-test='product-title'], [class*='product-title'], h3, a[data-test]")
    title = title_el.get_text(strip=True) if title_el else ""
    if not title or len(title) < 5:
        return
    
    # Цены
    price_el = card.select_one("[data-test='current-price'], [class*='price'], [class*='sale-price']")
    was_el = card.select_one("[data-test='original-price'], [class*='was-price'], [class*='original'], del")
    
    if not price_el:
        return
    
    price_text = price_el.get_text()
    curr_match = re.search(r'\$?([\d,]+\.?\d*)', price_text)
    if not curr_match:
        return
    
    curr = float(curr_match.group(1).replace(",", ""))
    
    if was_el:
        was_text = was_el.get_text()
        orig_match = re.search(r'\$?([\d,]+\.?\d*)', was_text)
        orig = float(orig_match.group(1).replace(",", "")) if orig_match else 0
    else:
        orig = 0
    
    if curr <= 0 or (orig > 0 and curr >= orig):
        return
    
    if orig == 0:
        # Пробуем найти regular price в других элементах
        all_text = card.get_text()
        prices = re.findall(r'\$([\d,]+\.?\d*)', all_text)
        prices = [float(p.replace(",", "")) for p in prices if float(p.replace(",", "")) > 0]
        if len(prices) >= 2:
            orig = max(prices)
            curr = min(prices)
            if curr >= orig:
                return
        else:
            return
    
    discount = round((orig - curr) / orig * 100, 1)
    
    # Изображение
    img = card.select_one("img[src*='target'], img[data-src*='target']")
    img_url = img.get("src") or img.get("data-src", "") if img else ""
    
    deal = {
        "id": deal_id,
        "store": STORE,
        "title": title[:200],
        "url": url,
        "image_url": img_url,
        "original_price": round(orig, 2),
        "current_price": round(curr, 2),
        "discount_pct": discount,
        "category": _categorize(title),
        "affiliate_url": url,
    }
    seen_ids.add(deal_id)
    deals.append(deal)


def _find_products_in_tgt_data(data, deals, seen_ids):
    """Рекурсивно ищет продукты в Target __TGT_DATA__."""
    if isinstance(data, dict):
        # Ищем структуры с product data
        if "products" in data:
            for p in data["products"]:
                _make_deal_from_tgt_product(p, deals, seen_ids)
        
        for k, v in data.items():
            _find_products_in_tgt_data(v, deals, seen_ids)
    elif isinstance(data, list):
        for item in data:
            _find_products_in_tgt_data(item, deals, seen_ids)


def _make_deal_from_tgt_product(p, deals, seen_ids):
    if not isinstance(p, dict):
        return
    
    title = p.get("title", p.get("product_title", p.get("name", "")))
    if not title:
        return
    
    url = p.get("url", p.get("product_url", p.get("canonical_url", "")))
    if not url:
        return
    
    if not url.startswith("http"):
        url = urljoin(BASE, url)
    
    deal_id = make_deal_id(url)
    if deal_id in seen_ids:
        return
    
    # Цены
    price_data = p.get("price", p.get("offer_price", {}))
    if isinstance(price_data, str):
        price_data = {"current": price_data}
    
    curr = float(price_data.get("current_price", price_data.get("current", price_data.get("price", 0))))
    orig = float(price_data.get("original_price", price_data.get("list_price", price_data.get("was", 0))))
    
    if curr >= orig or orig <= 0 or curr <= 0:
        return
    
    discount = round((orig - curr) / orig * 100, 1)
    img = p.get("image", p.get("primary_image", p.get("thumbnail", "")))
    
    deal = {
        "id": deal_id,
        "store": STORE,
        "title": title[:200],
        "url": url,
        "image_url": img if isinstance(img, str) else (img[0] if isinstance(img, list) else ""),
        "original_price": round(orig, 2),
        "current_price": round(curr, 2),
        "discount_pct": discount,
        "category": _categorize(title),
        "affiliate_url": url,
    }
    seen_ids.add(deal_id)
    deals.append(deal)


def _categorize(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ["gpu", "graphics", "rtx", "radeon", "geforce"]):
        return "gpu"
    if any(w in t for w in ["laptop", "notebook", "macbook", "chromebook"]):
        return "laptop"
    if any(w in t for w in ["monitor", "display", "ultrawide"]):
        return "monitor"
    if any(w in t for w in ["tv", "oled", "qled", "television"]):
        return "tv"
    if any(w in t for w in ["ssd", "hard drive", "nvme", "storage"]):
        return "storage"
    if any(w in t for w in ["headphone", "earbuds", "airpods", "speaker"]):
        return "audio"
    if any(w in t for w in ["tablet", "ipad", "kindle"]):
        return "tablet"
    if any(w in t for w in ["phone", "iphone", "samsung", "pixel"]):
        return "phone"
    return "other"
