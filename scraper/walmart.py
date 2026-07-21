"""
Walmart Scraper
Собирает скидки с категорий электроники.
Использует Playwright для JS-рендеринга.
"""
import re
from typing import List, Dict
from urllib.parse import urljoin

from scraper.utils import make_deal_id, get_affiliate_url

STORE = "walmart"
BASE = "https://www.walmart.com"


def scrape_deals() -> List[Dict]:
    """
    Использует httpx для парсинга Walmart страниц.
    Walmart отдаёт JSON-данные в HTML (initial state).
    """
    deals = []
    
    categories = [
        "https://www.walmart.com/browse/electronics/3944",                    # Все электроника
        "https://www.walmart.com/browse/electronics/video-game-consoles/3944_2638154",  # Gaming
        "https://www.walmart.com/browse/electronics/tvs/3944_1060825",        # TVs
        "https://www.walmart.com/browse/electronics/laptops/3944_3951",       # Laptops
        "https://www.walmart.com/browse/electronics/headphones/3944_133276",  # Headphones
        "https://www.walmart.com/browse/electronics/cell-phones/3944_1078524", # Phones
        "https://www.walmart.com/browse/electronics/shop-all-computers/3944_3951_7177397", # All Computers
    ]
    
    import httpx
    from bs4 import BeautifulSoup
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    seen_ids = set()
    
    with httpx.Client(headers=headers, follow_redirects=True, timeout=30) as client:
        for cat_url in categories:
            try:
                resp = client.get(cat_url)
                resp.raise_for_status()
            except Exception as e:
                print(f"  [Walmart] Failed: {cat_url}: {e}")
                continue
            
            soup = BeautifulSoup(resp.text, "lxml")
            
            # Walmart embeds product data in script tags (__WML_REDUX_INITIAL_STATE__)
            # Или в JSON-LD
            products = []
            
            # Попытка 1: JSON-LD
            for script in soup.select("script[type='application/ld+json']"):
                try:
                    data = json.loads(script.string)
                    items = data if isinstance(data, list) else [data]
                    products.extend(items)
                except: pass
            
            # Попытка 2: карточки товаров
            if not products:
                cards = soup.select("[data-testid='item-card'], [class*='product'], div[class*='Grid-col']")
                for card in cards:
                    _extract_walmart_card(card, client, cat_url, deals, seen_ids)
            
            # Попытка 3: поиск по атрибутам
            if not deals:
                for script in soup.find_all("script"):
                    if script.string and "window.__WML_REDUX_INITIAL_STATE__" in script.string:
                        try:
                            # Извлекаем JSON объект
                            match = re.search(r'window\.__WML_REDUX_INITIAL_STATE__\s*=\s*({.*?});', script.string, re.DOTALL)
                            if match:
                                state = json.loads(match.group(1))
                                # Рекурсивно ищем продукты
                                _find_products_in_state(state, deals, seen_ids)
                        except: pass
    
    return deals


def _extract_walmart_card(card, client, base_url, deals, seen_ids):
    """Извлекает данные из HTML-карточки товара Walmart."""
    import json
    from bs4 import BeautifulSoup
    
    # Ссылка
    link = card.select_one("a[href*='/ip/'], a[href*='/seo/']")
    if not link:
        return
    
    href = link.get("href", "")
    if not href.startswith("http"):
        href = urljoin(BASE, href)
    
    deal_id = make_deal_id(href)
    if deal_id in seen_ids:
        return
    
    # Название
    title_el = card.select_one("[data-testid='product-title'], [class*='title'], span[class*='Truncate']")
    if not title_el:
        return
    title = title_el.get_text(strip=True)
    
    # Цены
    price_el = card.select_one("[data-testid='price'], [itemprop='price'], [class*='price']")
    if not price_el:
        return
    
    text = price_el.get_text()
    prices = re.findall(r'\$?([\d,]+\.?\d*)', text)
    prices = [float(p.replace(",", "")) for p in prices if float(p.replace(",", "")) > 0]
    
    if len(prices) < 2:
        # Проверим was-price / strike-through
        was_el = card.select_one("[class*='was'], [class*='strike'], s, del")
        if was_el:
            was_text = was_el.get_text()
            was_match = re.search(r'\$?([\d,]+\.?\d*)', was_text)
            if was_match and prices:
                orig = float(was_match.group(1).replace(",", ""))
                curr = prices[0]
            else:
                return
        else:
            return
    else:
        orig = max(prices)
        curr = min(prices)
    
    if curr >= orig or orig <= 0 or curr <= 0:
        return
    
    discount = round((orig - curr) / orig * 100, 1)
    
    # Изображение
    img = card.select_one("img[src*='walmartimages'], img[data-src*='walmartimages']")
    img_url = img.get("src") or img.get("data-src", "") if img else ""
    
    deal = {
        "id": deal_id,
        "store": STORE,
        "title": title[:200],
        "url": href,
        "image_url": img_url,
        "original_price": round(orig, 2),
        "current_price": round(curr, 2),
        "discount_pct": discount,
        "category": _categorize(title),
        "affiliate_url": get_affiliate_url(STORE, href),
    }
    seen_ids.add(deal_id)
    deals.append(deal)


def _find_products_in_state(state, deals, seen_ids):
    """Рекурсивно ищет товары в JSON initial state."""
    import json as _json
    
    if isinstance(state, dict):
        # Проверяем ключи продуктов
        if any(k in state for k in ["name", "title", "price"]):
            if "name" in state and "price" in state:
                price_info = state.get("price", {})
                _make_deal_from_state(state, price_info, deals, seen_ids)
        
        for k, v in state.items():
            if isinstance(v, (dict, list)):
                _find_products_in_state(v, deals, seen_ids)
    elif isinstance(state, list):
        for item in state:
            _find_products_in_state(item, deals, seen_ids)


def _make_deal_from_state(product, price_info, deals, seen_ids):
    title = product.get("name", "")
    if not title or len(title) < 5:
        return
    
    url = product.get("productUrl", product.get("canonicalUrl", ""))
    if not url:
        return
    
    # ID
    deal_id = make_deal_id(url)
    if deal_id in seen_ids:
        return
    
    orig = float(price_info.get("wasPrice", price_info.get("listPrice", price_info.get("maxPrice", 0))) or 0)
    curr = float(price_info.get("price", price_info.get("minPrice", price_info.get("salePrice", 0))) or 0)
    
    if curr >= orig or orig <= 0 or curr <= 0:
        return
    
    discount = round((orig - curr) / orig * 100, 1)
    img_url = product.get("image", product.get("thumbnailUrl", ""))
    
    deal = {
        "id": deal_id,
        "store": STORE,
        "title": title[:200],
        "url": url if url.startswith("http") else urljoin(BASE, url),
        "image_url": img_url,
        "original_price": round(orig, 2),
        "current_price": round(curr, 2),
        "discount_pct": discount,
        "category": _categorize(title),
        "affiliate_url": get_affiliate_url(STORE, url),
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


try:
    import json as _js
except ImportError:
    import simplejson as _js
