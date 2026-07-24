"""
PriceHunter — Playwright Scraper v7.
Stores: Best Buy, Target, Amazon, Macy's (+ Walmart via httpx).
"""
import re, json, asyncio
from typing import List, Dict
from datetime import datetime
from urllib.parse import quote

from scraper.utils import make_deal_id, get_affiliate_url

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


async def scrape_all_stores() -> List[Dict]:
    """Scrape all stores."""
    from playwright.async_api import async_playwright
    all_deals = []

    # ─── Playwright stores ───
    async with async_playwright() as pw:
        for name, fn in [
            ("walmart", _scrape_walmart),
            ("target", _scrape_target),
            ("bestbuy", _scrape_bestbuy),
            ("macys", _scrape_macys),
            ("homedepot", _scrape_homedepot),
            ("costco", _scrape_costco),
            ("lowes", _scrape_lowes),
        ]:
            print(f"[{datetime.now().isoformat()}] Scraping {name}...")
            try:
                browser = await pw.chromium.launch(headless=True,
                    args=["--disable-blink-features=AutomationControlled"])
                context = await browser.new_context(
                    user_agent=UA, viewport={"width": 1280, "height": 800},
                    locale="en-US")
                await context.add_init_script(
                    "Object.defineProperty(navigator,'webdriver',{get:()=>false})")
                d = await fn(context)
                print(f"  -> {len(d)} deals")
                all_deals.extend(d)
                await browser.close()
            except Exception as e:
                print(f"  -> Error: {e}")
        await browser.close()

    all_deals.sort(key=lambda d: d["discount_pct"], reverse=True)

    # Flip Score v2 — multi-factor scoring
    HIGH_DEMAND = ["apple", "lego", "airpods", "ipad", "macbook", "nintendo", 
                   "playstation", "xbox", "kitchenaid", "milwaukee", "dewalt",
                   "samsung", "sony", "bose", "dyson", "ninja", "yeti", "tvs"]
    # Category multipliers for resale
    CAT_MULT = {"laptop":1.35, "tv":1.3, "gpu":1.4, "gaming":1.45, "audio":1.3,
                "tools":1.35, "toys":1.4, "tablet":1.35, "phone":1.3, "home":1.2}
    
    for d in all_deals:
        title = d["title"].lower()
        cat = d.get("category", "other")
        dp = d["discount_pct"]
        cp = d["current_price"]
        
        # Brand score (0-3)
        brand_score = sum(1 for kw in HIGH_DEMAND if kw in title)
        brand_score = min(brand_score, 3)
        
        # Discount score (0-3)
        if dp >= 70: disc_score = 3
        elif dp >= 50: disc_score = 2
        elif dp >= 30: disc_score = 1
        else: disc_score = 0
        
        # Profit potential score (0-3)
        profit_est = cp * (CAT_MULT.get(cat, 1.25) - 1)
        if profit_est >= 100: prof_score = 3
        elif profit_est >= 40: prof_score = 2
        elif profit_est >= 15: prof_score = 1
        else: prof_score = 0
        
        total = brand_score + disc_score + prof_score
        # Flip Score 1-100
        score_num = int((total + 1) * 11.1)  # 0-9 → 11-100
        score_num = max(1, min(100, score_num))
        if total >= 8: score, s30, label = score_num, 60, "🔥 Insane"
        elif total >= 6: score, s30, label = score_num, 45, "⚡ Gold"
        elif total >= 4: score, s30, label = score_num, 30, "👍 Good"
        elif total >= 2: score, s30, label = score_num, 15, "🆗 Okay"
        else: score, s30, label = score_num, 8, "🤷 Meh"
        
        cat_m = CAT_MULT.get(cat, 1.25)
        hot_mult = 1.4 if brand_score >= 2 else 1.0
        multiplier = max(cat_m, 1.25) * (1 + (hot_mult - 1) * 0.3)
        
        d["avg_resale"] = round(cp * multiplier, 2)
        d["min_resale"] = round(cp * (multiplier - 0.12), 2)
        d["max_resale"] = round(cp * (multiplier + 0.18), 2)
        d["profit_est"] = round(cp * (multiplier - 1), 2)
        d["roi_pct"] = round((multiplier - 1) * 100, 1)
        d["sold_30d"] = s30
        d["flip_score"] = score

    print(f"  Total: {len(all_deals)} deals")
    return all_deals


# ═══════════════════════════════════════════════════════════════════
#  BEST BUY — search-based
# ═══════════════════════════════════════════════════════════════════

BB_SEARCHES = [
    "laptop+sale", "tv+sale", "headphone+sale",
    "ipad+sale", "monitor+sale", "robot+vacuum+sale",
]

async def _scrape_bestbuy(context) -> List[Dict]:
    page = await context.new_page()
    deals = []
    seen_titles = set()

    for q in BB_SEARCHES:
        url = f"https://www.bestbuy.com/site/searchpage.jsp?id=pcat17071&st={q}"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(4000)
        except:
            continue

        items = await page.evaluate("""() => {
            const results = [];
            const seenUrls = new Set();
            // Find product containers by their title element
            const skuTitles = document.querySelectorAll('.sku-title');
            skuTitles.forEach(sku => {
                const link = sku.querySelector('a');
                const href = link ? link.href : '';
                if (!href || seenUrls.has(href)) return;
                seenUrls.add(href);
                
                const title = (sku.innerText || sku.textContent || '').trim();
                if (!title || title.length < 10) return;
                
                // Find prices from the product card container
                const container = sku.closest('[class*="product"], [data-testid*="product"], .list-item');
                const text = container ? container.innerText : document.body.innerText;
                const dollars = [...text.matchAll(/\\$(\\d+(?:\\.\\d{2})?)/g)].map(m => parseFloat(m[1])).filter(v => v > 1 && v < 10000);
                if (dollars.length >= 2) {
                    results.push({ title: title.substring(0,150), url: href, prices: [...new Set(dollars)].sort((a,b)=>a-b) });
                }
            });
            return results;
        }""")

        for p in items:
            key = p['title'][:40]
            if key in seen_titles: continue
            seen_titles.add(key)
            prices = p['prices']
            if len(prices) < 2: continue
            was, now = max(prices), min(prices)
            if was <= now or was - now < 5: continue
            pct = round((was - now) / was * 100, 1)
            if pct < 15: continue
            url = p.get('url', url) or f"https://www.bestbuy.com/site/search?q={quote(p['title'][:40])}"
            deals.append({
                "id": make_deal_id(url + str(was)),
                "store": "bestbuy",
                "title": p['title'],
                "url": url,
                "image_url": "",
                "original_price": round(was, 2),
                "current_price": round(now, 2),
                "discount_pct": pct,
                "category": _cat(p['title']),
                "affiliate_url": get_affiliate_url("bestbuy", url),
            })

    await page.close()
    return deals


# ═══════════════════════════════════════════════════════════════════
#  TARGET — парсит строки вида "$X.XXreg $Y.YY"
# ═══════════════════════════════════════════════════════════════════

TARGET_SEARCHES = [
    "clearance+laptops", "clearance+electronics", "clearance+tvs",
    "clearance+lego", "clearance+toys", "clearance+apple",
    "clearance+headphones", "clearance+gaming", "clearance+kitchen",
    "clearance+home", "clearance+tools", "clearance+monitor",
    "clearance+tablet", "clearance+outdoor",
]

async def _scrape_target(context) -> List[Dict]:
    page = await context.new_page()
    all_deals = []
    seen_titles = set()

    for search in TARGET_SEARCHES:
        url = f"https://www.target.com/s?searchTerm={search}"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
        except:
            continue

        # First pass: collect product links from HTML
        product_links = await page.evaluate("""() => {
            const links = {};
            document.querySelectorAll('a[href*="/p/"]').forEach(a => {
                const title = (a.innerText || a.textContent || '').trim();
                if (title && title.length > 10) links[title.substring(0, 40)] = a.href;
                // Also check aria-label
                const aria = a.getAttribute('aria-label');
                if (aria && aria.length > 10) links[aria.substring(0, 40)] = a.href;
            });
            // Also check data-test attributes
            document.querySelectorAll('[data-test="product-title"], [data-test*="title"]').forEach(el => {
                const title = (el.innerText || el.textContent || '').trim();
                if (title && title.length > 10) {
                    const link = el.closest('a') || el.querySelector('a');
                    if (link && link.href) links[title.substring(0, 40)] = link.href;
                }
            });
            return links;
        }""")

        products = await page.evaluate("""() => {
            const lines = document.body.innerText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
            const results = [];
            const seen = new Set();
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                if (line.match(/^(Sale|Sponsored|Add to|Shipping|Sold|Ships|Pickup|Shop)/i)) continue;
                if (line.match(/^\\d+\\+? result/)) continue;
                if (!line.includes('reg')) continue;
                const m = line.match(/\$([0-9,]+(?:\.[0-9]{2})?)\s*reg\s*\$([0-9,]+(?:\.[0-9]{2})?)/);
                if (!m) continue;
                const parseDollar = (s) => parseFloat(s.replace(/,/g, ''));
                const curr = parseDollar(m[1]);
                const orig = parseDollar(m[2]);
                if (orig <= curr || orig - curr < 3 || curr < 3) continue;
                let title = '';
                for (let j = i + 1; j < Math.min(i + 5, lines.length); j++) {
                    const l = lines[j];
                    if (l.length < 5 || l.startsWith('$') || l.match(/^(Sale|Sponsored|Add to|Shipping|reg|Sold|Ships)/i)) continue;
                    if (l.match(/^\\d+\\+? result/)) continue;
                    title = l; break;
                }
                if (!title || title.length < 5 || seen.has(title)) continue;
                seen.add(title);
                results.push({ title: title.substring(0, 150), curr, orig });
            }
            return results;
        }""")

        for p in products:
            key = p['title'][:40]
            if key in seen_titles: continue
            seen_titles.add(key)
            pct = round((p['orig'] - p['curr']) / p['orig'] * 100, 1)
            if pct < 15 or pct > 95: continue
            # Match to product link
            url = product_links.get(p['title'][:40]) or product_links.get(p['title'][:30]) or ""
            if not url:
                # Try matching by first 3 words
                words = p['title'].split()[:3]
                for tkey, turl in product_links.items():
                    if all(w.lower() in tkey.lower() for w in words):
                        url = turl; break
            if not url:
                url = "https://www.target.com/s?searchTerm=" + p['title'][:30].replace(' ', '+')
            all_deals.append({
                "id": make_deal_id(url),
                "store": "target",
                "title": p['title'],
                "url": url,
                "image_url": "",
                "original_price": round(p['orig'], 2),
                "current_price": round(p['curr'], 2),
                "discount_pct": pct,
                "category": _cat(p['title']),
                "affiliate_url": url,
            })

    await page.close()
    return all_deals


# ═══════════════════════════════════════════════════════════════════
#  AMAZON — search-based
# ═══════════════════════════════════════════════════════════════════

AMAZON_SEARCHES = [
    "deals+of+the+day", "under+$50+deals",
    "laptop+deals", "headphone+deals",
    "lego+deals", "tool+deals",
]

async def _scrape_amazon(context) -> List[Dict]:
    page = await context.new_page()
    deals = []
    seen_ids = set()

    for search in AMAZON_SEARCHES:
        url = f"https://www.amazon.com/s?k={search}&ref=nb_sb_noss"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(4000)
        except:
            continue

        items = await page.evaluate("""() => {
            const results = [];
            const cards = document.querySelectorAll('[data-component-type="s-search-result"]');
            cards.forEach(card => {
                const asin = card.getAttribute('data-asin') || '';
                if (!asin || asin.length < 10) return;
                const titleEl = card.querySelector('h2 a, [class*="title"] a');
                const title = titleEl ? (titleEl.innerText || titleEl.textContent || '').trim() : '';
                if (!title || title.length < 10) return;
                const link = titleEl ? titleEl.href : '';
                if (!link) return;
                const whole = card.querySelector('.a-price .a-price-whole');
                const fraction = card.querySelector('.a-price .a-price-fraction');
                const base = card.querySelector('.a-text-price span[aria-hidden="true"]');
                let curr = 0, orig = 0;
                if (whole) {
                    curr = parseFloat((whole.innerText + '.' + (fraction ? fraction.innerText : '00')).replace(/[^0-9.]/g, ''));
                }
                if (base) {
                    const bText = base.innerText.replace(/[^0-9.]/g, '');
                    orig = parseFloat(bText);
                }
                if (curr === 0 || orig === 0) {
                    const dollars = [...(card.innerText||'').matchAll(/\\$(\\d+(?:\\.\\d{2})?)/g)].map(m => parseFloat(m[1])).filter(v => v > 1 && v < 10000);
                    if (dollars.length >= 2) {
                        const sorted = [...new Set(dollars)].sort((a,b)=>a-b);
                        if (curr === 0) curr = sorted[0];
                        if (orig === 0) orig = sorted[sorted.length - 1];
                    }
                }
                if (curr > 0 && orig > 0 && orig > curr) {
                    results.push({ title: title.substring(0, 150), url: link, asin, curr, orig });
                }
            });
            return results;
        }""")

        for p in items:
            if p['asin'] in seen_ids: continue
            seen_ids.add(p['asin'])
            if p['orig'] <= p['curr'] or p['orig'] - p['curr'] < 3: continue
            pct = round((p['orig'] - p['curr']) / p['orig'] * 100, 1)
            if pct < 15 or pct > 95: continue
            deals.append({
                "id": make_deal_id(p['asin']),
                "store": "amazon",
                "title": p['title'],
                "url": url,
                "image_url": "",
                "original_price": round(p['orig'], 2),
                "current_price": round(p['curr'], 2),
                "discount_pct": pct,
                "category": _cat(p['title']),
                "affiliate_url": get_affiliate_url("amazon", p.get('url', url)),
            })

    await page.close()
    return deals


# ═══════════════════════════════════════════════════════════════════
#  MACY'S — search-based
# ═══════════════════════════════════════════════════════════════════

MACYS_SEARCHES = [
    "clearance", "sale",
    "clearance+home", "sale+shoes",
]

async def _scrape_macys(context) -> List[Dict]:
    page = await context.new_page()
    deals = []
    seen_titles = set()

    for search in MACYS_SEARCHES:
        url = f"https://www.macys.com/shop/search?keyword={search}"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(4000)
        except:
            continue

        items = await page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            const body = document.body.innerText;
            const lines = document.body.innerText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                if (!line.match(/[Ww]as|orig|reg|now/i)) continue;
                const dollars = [...line.matchAll(/\\$(\\d+(?:\\.\\d{2})?)/g)].map(m => parseFloat(m[1])).filter(v => v > 1 && v < 10000);
                if (dollars.length < 2) continue;
                let title = '';
                for (let j = i + 1; j < Math.min(i + 5, lines.length); j++) {
                    const l = lines[j];
                    if (l.length > 10 && !l.includes('$') && !l.match(/^(Sale|Was|reg|now|Free|Shipping|Item|Color|Size)/i) && !l.match(/^\\d/)) {
                        title = l; break;
                    }
                }
                if (!title || title.length < 5 || seen.has(title)) {
                    // Try going backwards
                    for (let j = i - 1; j >= Math.max(0, i - 3); j--) {
                        const l = lines[j];
                        if (l.length > 10 && !l.includes('$') && !l.match(/^(Sale|Was|reg)/i)) {
                            title = l; break;
                        }
                    }
                }
                if (!title || title.length < 5 || seen.has(title)) continue;
                seen.add(title);
                const sorted = [...new Set(dollars)].sort((a,b)=>a-b);
                results.push({ title: title.substring(0, 150), curr: sorted[0], orig: sorted[sorted.length-1], url: 'https://www.macys.com/shop/search?keyword=' + encodeURIComponent(title.substring(0, 30)) });
            }
            return results;
        }""")

        for p in items:
            key = p['title'][:40]
            if key in seen_titles: continue
            seen_titles.add(key)
            if p['orig'] <= p['curr'] or p['orig'] - p['curr'] < 3: continue
            pct = round((p['orig'] - p['curr']) / p['orig'] * 100, 1)
            if pct < 15 or pct > 95: continue
            deals.append({
                "id": make_deal_id(p.get('url', url)),
                "store": "macys",
                "title": p['title'],
                "url": url,
                "image_url": "",
                "original_price": round(p['orig'], 2),
                "current_price": round(p['curr'], 2),
                "discount_pct": pct,
                "category": _cat(p['title']),
                "affiliate_url": url,
            })

    await page.close()
    return deals


# ═══════════════════════════════════════════════════════════════════
#  WALMART — httpx + BeautifulSoup
# ═══════════════════════════════════════════════════════════════════

WALMART_URLS = [
    "https://www.walmart.com/browse/electronics/3944",
    "https://www.walmart.com/browse/electronics/tvs/3944_1060825",
    "https://www.walmart.com/browse/electronics/laptops/3944_3951",
    "https://www.walmart.com/browse/electronics/headphones/3944_133276",
    "https://www.walmart.com/browse/toys/lego/4171_1224954",
    "https://www.walmart.com/browse/home/kitchen/4044_1085430",
]

async def _scrape_walmart(context) -> List[Dict]:
    """Walmart via Playwright — browse category pages."""
    page = await context.new_page()
    deals = []
    seen_titles = set()

    for cat_url in WALMART_URLS:
        try:
            await page.goto(cat_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(5000)
        except:
            continue

        # First pass: collect product links from HTML
        product_links = await page.evaluate("""() => {
            const links = {};
            // Find product links in the page
            document.querySelectorAll('a[href*="/ip/"], a[href*="/seo/"]').forEach(a => {
                const href = a.href || '';
                if (!href) return;
                const titleEl = a.querySelector('[data-testid="product-title"], [class*="title"], span[class*="Truncate"]');
                const title = titleEl ? (titleEl.innerText || titleEl.textContent || '').trim() : (a.innerText || a.textContent || '').trim();
                if (!title || title.length < 10) return;
                links[title.substring(0, 50)] = href;
            });
            // Also try aria-label
            document.querySelectorAll('[data-testid="item-card"], [class*="product"]').forEach(card => {
                const link = card.querySelector('a[href*="/ip/"], a[href*="/seo/"]');
                if (!link) return;
                const href = link.href || '';
                if (!href) return;
                const titleEl = card.querySelector('[data-testid="product-title"], [class*="title"], span[class*="Truncate"]');
                const title = titleEl ? (titleEl.innerText || titleEl.textContent || '').trim() : '';
                if (!title || title.length < 10) return;
                links[title.substring(0, 50)] = href;
            });
            return links;
        }""")

        # Second pass: extract prices and match to links
        items = await page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            const body = document.body.innerText;
            const lines = body.split('\\n').map(l => l.trim()).filter(l => l.length > 0);

            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                if (!line.match(/[Ww]as|reg|sale|now|save/i)) continue;
                const dollars = [...line.matchAll(/\\$(\\d+(?:\.\\d{2})?)/g)].map(m => parseFloat(m[1].replace(/,/g,''))).filter(v => v > 1 && v < 10000);
                if (dollars.length < 2) continue;

                let title = '';
                for (let j = i + 1; j < Math.min(i + 5, lines.length); j++) {
                    const l = lines[j];
                    if (l.length < 10 || l.includes('$')) continue;
                    if (l.match(/^(Sale|Was|Now|Free|Shipping|Item|Color|Size|Qty|Save|Rollback|Pickup|Sold|Available|Top rated|Not yet reviewed)/i)) continue;
                    if (l.match(/^\\d+\\+?/)) continue;
                    title = l; break;
                }
                if (!title || title.length < 8 || seen.has(title)) continue;
                // Must look like a product name (has uppercase words, not just generic text)
                if (!title.match(/[A-Z][a-z]{2,}/)) continue;
                if (title.match(/^(Available|Top rated|Not yet|Customer|Rating|Review|Free|Save|Shop|Browse|Category)/i)) continue;
                seen.add(title);

                const sorted = [...new Set(dollars)].sort((a,b)=>a-b);
                const curr = sorted[0];
                const orig = sorted[sorted.length - 1];
                if (orig <= curr || orig - curr < 3) continue;
                
                results.push({ title: title.substring(0, 150), curr, orig });
            }
            return results;
        }""")

        for p in items:
            key = p['title'][:40]
            if key in seen_titles: continue
            seen_titles.add(key)
            pct = round((p['orig'] - p['curr']) / p['orig'] * 100, 1)
            if pct < 15 or pct > 95: continue
            # Try to find a real product link
            url = product_links.get(p['title'][:50]) or product_links.get(p['title'][:40]) or ""
            if not url:
                # Try matching by first few words
                prefix = p['title'].split(' ')[:3]
                if prefix:
                    for tkey, turl in product_links.items():
                        if all(w.lower() in tkey.lower() for w in prefix):
                            url = turl
                            break
            if not url:
                url = "https://www.walmart.com/search?q=" + p['title'][:40].replace(' ', '+')
            
            deals.append({
                "id": make_deal_id(url),
                "store": "walmart",
                "title": p['title'],
                "url": url,
                "image_url": "",
                "original_price": round(p['orig'], 2),
                "current_price": round(p['curr'], 2),
                "discount_pct": pct,
                "category": _cat(p['title']),
                "affiliate_url": get_affiliate_url("walmart", url),
            })

    await page.close()
    return deals


# ═══════════════════════════════════════════════════════════════════
#  CATEGORIZER
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
#  COSTCO — search-based clearance
# ═══════════════════════════════════════════════════════════════════

async def _scrape_costco(context) -> List[Dict]:
    page = await context.new_page()
    deals = []
    seen_titles = set()

    for q in ["clearance", "sale", "deals", "clearance+electronics", "clearance+home"]:
        url = f"https://www.costco.com/{q}.html"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=12000)
            await page.wait_for_timeout(3000)
        except:
            continue

        items = await page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            const lines = document.body.innerText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                const dollars = [...line.matchAll(/\\$(\\d+(?:\\.\\d{2})?)/g)].map(m => parseFloat(m[1])).filter(v => v > 1 && v < 10000);
                if (dollars.length < 2) continue;
                let title = '';
                for (let j = i + 1; j < Math.min(i + 4, lines.length); j++) {
                    const l = lines[j];
                    if (l.length > 10 && !l.includes('$') && !l.match(/^(Sale|Was|Now|Free|Shipping|Item|Save|Price|Delivered)/i)) {
                        title = l; break;
                    }
                }
                if (!title || title.length < 5 || seen.has(title)) continue;
                seen.add(title);
                const sorted = [...new Set(dollars)].sort((a,b)=>a-b);
                results.push({ title: title.substring(0, 150), curr: sorted[0], orig: sorted[sorted.length-1] });
            }
            return results;
        }""")

        for p in items:
            key = p['title'][:40]
            if key in seen_titles: continue
            seen_titles.add(key)
            pct = round((p['orig'] - p['curr']) / p['orig'] * 100, 1)
            if pct < 15 or pct > 95: continue
            url = "https://www.costco.com/search?q=" + p['title'][:30].replace(' ', '+')
            deals.append({
                "id": make_deal_id(url), "store": "costco", "title": p['title'],
                "url": url, "image_url": "", "original_price": round(p['orig'], 2),
                "current_price": round(p['curr'], 2), "discount_pct": pct,
                "category": _cat(p['title']), "affiliate_url": url,
            })

    await page.close()
    return deals


# ═══════════════════════════════════════════════════════════════════
#  HOME DEPOT — search-based
# ═══════════════════════════════════════════════════════════════════

async def _scrape_homedepot(context) -> List[Dict]:
    page = await context.new_page()
    deals = []
    seen_titles = set()

    for q in ["clearance", "special-buys", "deals", "clearance+power+tools"]:
        url = f"https://www.homedepot.com/b/{q}/N-5yc1v"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=12000)
            await page.wait_for_timeout(3000)
        except:
            continue

        items = await page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            const lines = document.body.innerText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                if (!line.match(/[Ww]as|reg|sale|now|save/i)) continue;
                const dollars = [...line.matchAll(/\\$(\\d+(?:\\.\\d{2})?)/g)].map(m => parseFloat(m[1])).filter(v => v > 1 && v < 10000);
                if (dollars.length < 2) continue;
                let title = '';
                for (let j = i + 1; j < Math.min(i + 4, lines.length); j++) {
                    const l = lines[j];
                    if (l.length > 10 && !l.includes('$') && !l.match(/^(Sale|Was|Now|Free|Shipping|Item|Save|Model|SKU|Compare)/i)) {
                        title = l; break;
                    }
                }
                if (!title || title.length < 5 || seen.has(title)) continue;
                seen.add(title);
                const sorted = [...new Set(dollars)].sort((a,b)=>a-b);
                if (sorted[0] < sorted[sorted.length-1]) {
                    results.push({ title: title.substring(0, 150), curr: sorted[0], orig: sorted[sorted.length-1] });
                }
            }
            return results;
        }""")

        for p in items:
            key = p['title'][:40]
            if key in seen_titles: continue
            seen_titles.add(key)
            pct = round((p['orig'] - p['curr']) / p['orig'] * 100, 1)
            if pct < 15 or pct > 95: continue
            url = "https://www.homedepot.com/s/" + p['title'][:30].replace(' ', '%20')
            deals.append({
                "id": make_deal_id(url), "store": "homedepot", "title": p['title'],
                "url": url, "image_url": "", "original_price": round(p['orig'], 2),
                "current_price": round(p['curr'], 2), "discount_pct": pct,
                "category": _cat(p['title']), "affiliate_url": url,
            })

    await page.close()
    return deals


# ═══════════════════════════════════════════════════════════════════
#  LOWE'S — search-based
# ═══════════════════════════════════════════════════════════════════

async def _scrape_lowes(context) -> List[Dict]:
    page = await context.new_page()
    deals = []
    seen_titles = set()

    for q in ["clearance", "deals", "sale", "clearance+tools", "clearance+appliances"]:
        url = f"https://www.lowes.com/search?searchTerm={q}"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=12000)
            await page.wait_for_timeout(3000)
        except:
            continue

        items = await page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            const lines = document.body.innerText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                if (!line.match(/[Ww]as|reg|sale|now/i)) continue;
                const dollars = [...line.matchAll(/\\$(\\d+(?:\\.\\d{2})?)/g)].map(m => parseFloat(m[1])).filter(v => v > 1 && v < 10000);
                if (dollars.length < 2) continue;
                let title = '';
                for (let j = i + 1; j < Math.min(i + 4, lines.length); j++) {
                    const l = lines[j];
                    if (l.length > 10 && !l.includes('$') && !l.match(/^(Sale|Was|Now|Free|Shipping|Item|Compare|Save|Model)/i)) {
                        title = l; break;
                    }
                }
                if (!title || title.length < 5 || seen.has(title)) continue;
                seen.add(title);
                const sorted = [...new Set(dollars)].sort((a,b)=>a-b);
                if (sorted[0] < sorted[sorted.length-1]) {
                    results.push({ title: title.substring(0, 150), curr: sorted[0], orig: sorted[sorted.length-1] });
                }
            }
            return results;
        }""")

        for p in items:
            key = p['title'][:40]
            if key in seen_titles: continue
            seen_titles.add(key)
            pct = round((p['orig'] - p['curr']) / p['orig'] * 100, 1)
            if pct < 15 or pct > 95: continue
            url = "https://www.lowes.com/search?searchTerm=" + p['title'][:30].replace(' ', '+')
            deals.append({
                "id": make_deal_id(url), "store": "lowes", "title": p['title'],
                "url": url, "image_url": "", "original_price": round(p['orig'], 2),
                "current_price": round(p['curr'], 2), "discount_pct": pct,
                "category": _cat(p['title']), "affiliate_url": url,
            })

    await page.close()
    return deals

def _cat(t: str) -> str:
    t = t.lower()
    if any(w in t for w in ["gpu","graphics","rtx","radeon","geforce"]): return "gpu"
    if any(w in t for w in ["laptop","notebook","macbook","chromebook"]): return "laptop"
    if any(w in t for w in ["monitor","display","ultrawide"]): return "monitor"
    if any(w in t for w in ["tv","oled","qled","television"]): return "tv"
    if any(w in t for w in ["ssd","nvme","solid state","hard drive"]): return "storage"
    if any(w in t for w in ["headphone","earbuds","airpods","speaker","soundbar","wh-","wf-"]): return "audio"
    if any(w in t for w in ["tablet","ipad","kindle"]): return "tablet"
    if any(w in t for w in ["phone","iphone","samsung","pixel"]): return "phone"
    if any(w in t for w in ["nintendo","playstation","xbox","switch","dual sense","ps5","xbox series","game pass"]): return "gaming"
    if any(w in t for w in ["mouse","keyboard","webcam","camera","router"]): return "peripherals"
    if any(w in t for w in ["lego","nerf","hot wheels","action figure","toy"]): return "toys"
    if any(w in t for w in ["milwaukee","dewalt","makita","craftsman","drill","saw","tool","socket","wrench"]): return "tools"
    if any(w in t for w in ["kitchenaid","vitamix","dyson","instant pot","ninja","nespresso","mixer","blender","vacuum","coffee"]): return "home"
    if any(w in t for w in ["uppababy","nuna","chicco","stroller","car seat","baby","kids","diaper"]): return "baby"
    if any(w in t for w in ["yeti","weber","solo stove","coleman","grill","cooler","camping","outdoor","fire pit"]): return "outdoor"
    if any(w in t for w in ["electronics","computer","printer","scanner"]): return "electronics"
    if any(w in t for w in ["shoe","sneaker","boot","sandals","heel","loafer"]): return "fashion"
    if any(w in t for w in ["fragrance","cologne","perfume","candle","diffuser"]): return "beauty"
    if any(w in t for w in ["handbag","backpack","luggage","wallet","purse"]): return "accessories"
    return "other"
