"""
Best Buy Scraper
Собирает скидки с Deal of the Day, Weekly Deals и категорий электроники.
"""
import re
from typing import List, Dict
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from scraper.utils import make_deal_id, get_affiliate_url

STORE = "bestbuy"
BASE = "https://www.bestbuy.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _parse_price(text: str) -> float:
    """Извлекает число из '$1,234.56'"""
    cleaned = re.sub(r'[^0-9.]', '', text)
    return float(cleaned) if cleaned else 0.0


def scrape_deals() -> List[Dict]:
    deals = []
    
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        # 1. Deal of the Day + Top Deals
        _scrape_page(client, "https://www.bestbuy.com/site/electronics/deals", deals)
        
        # 2. Категории электроники (GPU, ноутбуки, мониторы)
        categories = [
            "https://www.bestbuy.com/site/computer-cards-components/video-graphics-cards/abcat0507002.c?id=abcat0507002",  # GPU
            "https://www.bestbuy.com/site/laptop-computers/all-laptops/pc_category_68449_4421106_c?id=pcat17071",          # Laptops
            "https://www.bestbuy.com/site/monitors/all-monitors/pc_category_1428960_4421106_c?id=pcat1428960",            # Monitors
            "https://www.bestbuy.com/site/tvs/all-tvs/pc_category_3425893_4421106_c?id=pcat3425893",                      # TVs
        ]
        for url in categories:
            _scrape_page(client, url, deals)
    
    return deals


def _scrape_page(client: httpx.Client, url: str, deals: List[Dict]):
    try:
        resp = client.get(url)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [BestBuy] Failed to fetch {url}: {e}")
        return
    
    soup = BeautifulSoup(resp.text, "lxml")
    
    # Best Buy использует data-атрибуты для SKU-информации
    # Ищем плитки товаров (разные селекторы для разных страниц)
    products = []
    
    # Селектор 1: deal pages (sku-list)
    products.extend(soup.select("[class*='sku-item'], [class*='list-item'], article[class*='product']"))
    
    # Селектор 2: category pages
    if not products:
        products.extend(soup.select("[class*='product']"))
    
    # Селектор 3: data-component="product"
    if not products:
        products.extend(soup.select("[data-component='product']"))
    
    seen = set()
    for product in products:
        # Название
        title_el = product.select_one("[class*='title'], h4, [class*='heading'], a[class*='name']")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        
        # Ссылка
        link_el = title_el if title_el.name == "a" else product.select_one("a[href*='/site/']")
        if not link_el or not link_el.get("href"):
            continue
        href = link_el["href"]
        product_url = urljoin(BASE, href) if not href.startswith("http") else href
        
        # ID
        deal_id = make_deal_id(product_url)
        if deal_id in seen:
            continue
        seen.add(deal_id)
        
        # Цены
        # Текущая цена
        price_el = product.select_one("[class*='priceView'], [class*='price'], [data-testid='price'], span[class*='price']")
        if not price_el:
            continue
        
        # Ищем ценник — Best Buy часто использует структуру с "was" и "now"
        text = price_el.get_text()
        
        # Пробуем найти оригинальную цену (was/sale/reg)
        orig_match = re.search(r'(?:was|reg|sale|originally|was\$|compareat)[:\s]*\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
        current_match = re.search(r'(?:now|price|sale|current|your price)[:\s]*\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
        
        if not orig_match:
            # Если нет "was", ищем две цены рядом
            prices = re.findall(r'\$([\d,]+\.?\d*)', text)
            if len(prices) >= 2:
                orig = max(float(p.replace(",", "")) for p in prices[:3])
                curr = min(float(p.replace(",", "")) for p in prices[:3])
            elif len(prices) == 1:
                orig_match = None
                current_match = None
                # Если только одна цена, проверяем есть ли зачёркнутая цена рядом
                strike = product.select_one("del, s, [class*='strike'], [class*='was']")
                if strike:
                    strike_text = strike.get_text()
                    sp = re.search(r'\$([\d,]+\.?\d*)', strike_text)
                    if sp:
                        orig = float(sp.group(1).replace(",", ""))
                        curr = float(prices[0].replace(",", ""))
                    else:
                        continue
                else:
                    continue
            else:
                continue
        else:
            orig = float(orig_match.group(1).replace(",", ""))
            if current_match:
                curr = float(current_match.group(1).replace(",", ""))
            else:
                # Если нет "now", берём самую низкую цену из текста
                prices = re.findall(r'\$([\d,]+\.?\d*)', text)
                curr = min(float(p.replace(",", "")) for p in prices) if prices else orig
        
        if orig <= 0 or curr <= 0 or curr >= orig:
            continue
        
        discount = round((orig - curr) / orig * 100, 1)
        
        # Изображение
        img_el = product.select_one("img[src*='images'], img[data-src*='images']")
        img_url = img_el.get("src") or img_el.get("data-src", "") if img_el else ""
        
        deal = {
            "id": deal_id,
            "store": STORE,
            "title": title[:200],
            "url": product_url,
            "image_url": img_url,
            "original_price": round(orig, 2),
            "current_price": round(curr, 2),
            "discount_pct": discount,
            "category": _categorize(title),
            "affiliate_url": get_affiliate_url(STORE, product_url),
        }
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
