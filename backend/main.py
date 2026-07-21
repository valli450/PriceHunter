"""
PriceHunter — FastAPI Server v3.
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from dotenv import load_dotenv

from backend.database import get_hot_deals

load_dotenv()

app = FastAPI(title="PriceHunter", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ─── PWA ────────────────────────────────────────────────────────

@app.get("/manifest.json")
def manifest():
    with open(os.path.join(os.path.dirname(__file__), "manifest.json")) as f:
        return Response(f.read(), media_type="application/json")

@app.get("/sw.js")
def sw():
    return Response("self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(clients.claim()));self.addEventListener('fetch',e=>e.respondWith(fetch(e.request).catch(()=>new Response('Offline',{status:503}))));", media_type="application/javascript")

@app.get("/api/icon")
def icon(size: int = 192):
    return Response(f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 512 512"><rect width="512" height="512" rx="100" fill="#1a1210"/><circle cx="256" cy="200" r="120" fill="none" stroke="#ff6b35" stroke-width="24"/><circle cx="256" cy="200" r="50" fill="#ff6b35"/><path d="M256 320 L160 440 L352 440 Z" fill="#ff6b35"/><text x="256" y="480" text-anchor="middle" font-size="36" fill="#ff6b35" font-weight="bold">PH</text></svg>""", media_type="image/svg+xml")

# ─── API ────────────────────────────────────────────────────────

@app.get("/")
def root():
    return RedirectResponse(url="/api/deals/hot")

@app.get("/api/deals")
def list_deals(min_discount: float = 10, store: str = None, limit: int = 100):
    return get_hot_deals(limit=limit, min_discount=min_discount, store=store)

@app.on_event("startup")
def startup():
    """Seed DB if empty."""
    import json, os
    from backend.database import init_db, get_conn, save_deal
    init_db()
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
    conn.close()
    if count == 0:
        seed = os.path.join(os.path.dirname(__file__), "..", "seed.json")
        if os.path.exists(seed):
            with open(seed) as f:
                for d in json.load(f):
                    save_deal(d)
            print(f"Seeded DB from seed.json")
        else:
            print(f"Seed file not found at {seed}")


@app.get("/api/deals/hot", response_class=HTMLResponse)
def hot_deals_html(min_discount: float = 0, store: str = None):
    deals = get_hot_deals(limit=200, min_discount=min_discount, store=store)
    return render_page(deals)


@app.get("/api/competition")
def competition(q: str = ""):
    """Сколько конкурентов продают этот товар на eBay?"""
    import httpx
    try:
        url = f"https://www.ebay.com/sch/i.html?_nkw={__import__('urllib.parse').quote(q[:80])}&_sop=15&LH_Complete=1&LH_Sold=1"
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, follow_redirects=True)
        if r.status_code == 200:
            import re
            # Try to extract count from "Results" text
            m = re.search(r'([0-9,]+)\s*Results', r.text)
            if m:
                count = int(m.group(1).replace(",", ""))
            else:
                count = r.text.count('class="s-item"')
            badge = "🟢 Low" if count < 20 else "🟡 Medium" if count < 100 else "🔴 High"
            return {"count": count, "badge": badge, "label": f"{badge} ({count} active listings)"}
        return {"count": 0, "badge": "⚪ Unknown", "label": "⚪ No data"}
    except:
        return {"count": 0, "badge": "⚪ Unknown", "label": "⚪ No data"}

@app.get("/api/compare")
def compare(q: str = ""):
    """Найти этот товар в других магазинах."""
    if not q:
        return []
    deals = get_hot_deals(limit=500, min_discount=0)
    words = q.lower().split()[:5]
    matches = []
    store_icons = {"target":"🎯","walmart":"🛒","amazon":"📦","costco":"🏬","homedepot":"🧰","lowes":"🪴"}
    for d in deals:
        title = d["title"].lower()
        score = sum(1 for w in words if w in title)
        if score >= 2 and len(words) >= 3:
            matches.append({"store": d["store"], "price": d["current_price"], "orig": d["original_price"],
                            "dp": d["discount_pct"], "profit": d.get("profit_est", 0),
                            "roi": d.get("roi_pct", 0), "title": d["title"][:60],
                            "icon": store_icons.get(d["store"], "🏪"),
                            "url": d.get("affiliate_url", d.get("url", ""))})
    return sorted(matches, key=lambda x: x["price"])[:5]


@app.get("/api/barcode")
def barcode(upc: str = ""):
    if not upc or len(upc) < 3:
        return {"found": False, "deals": []}
    deals = get_hot_deals(limit=500, min_discount=0)
    matches = [d for d in deals if upc in d["title"] or upc[-4:] in d["title"]]
    return {"found": len(matches) > 0, "deals": matches[:5]}


@app.get("/api/deals/{deal_id}/history")
def deal_history(deal_id: str, days: int = 30):
    from backend.database import get_price_history
    return get_price_history(deal_id, days)


@app.post("/api/alerts")
def create_alert(chat_id: str = None, keyword: str = None, target_price: float = None, min_discount: float = 30):
    """Создаёт алерт: уведомить когда товар с keyword < target_price."""
    from backend.database import get_conn
    conn = get_conn()
    conn.execute("INSERT INTO alerts (chat_id, store, category, min_discount) VALUES (?, ?, ?, ?)",
                 (chat_id or "7547453615", keyword, "alert", min_discount))
    conn.commit()
    conn.close()
    return {"status": "ok", "alert": f"🔔 When {keyword} < ${target_price:.0f}"}


@app.get("/api/alerts/check")
def check_alerts():
    """Проверяет алерты и отправляет уведомления."""
    from backend.database import get_conn, get_hot_deals
    from scraper.utils import format_deal_message
    from backend.telegram_bot import send_deal_notifications
    conn = get_conn()
    alerts = conn.execute("SELECT * FROM alerts WHERE active = 1 AND store IS NOT NULL").fetchall()
    if not alerts:
        return {"checked": 0, "matches": 0}
    deals = get_hot_deals(limit=500, min_discount=0)
    matches = []
    for a in alerts:
        kw = a["store"].lower() if a["store"] else ""
        for d in deals:
            if kw and kw in d["title"].lower():
                if not a.get("category") or d.get("category") == a["category"]:
                    matches.append(d)
    if matches:
        from backend.database import get_subscribers
        subs = get_subscribers()
        if subs:
            send_deal_notifications(matches, subs)
    conn.close()
    return {"checked": len(alerts), "matches": len(matches)}


@app.get("/api/stats")
def stats():
    deals = get_hot_deals(limit=10000, min_discount=0)
    total = len(deals)
    by_store, by_cat = {}, {}
    for d in deals:
        by_store[d["store"]] = by_store.get(d["store"], 0) + 1
        by_cat[d.get("category", "other")] = by_cat.get(d.get("category", "other"), 0) + 1
    avg_d = round(sum(d["discount_pct"] for d in deals) / total, 1) if total else 0
    total_profit = round(sum(d.get("profit_est", 0) for d in deals), 2)
    return {"total_deals": total, "by_store": by_store, "by_category": by_cat,
            "avg_discount": avg_d, "total_profit_potential": total_profit}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    deals = get_hot_deals(limit=10000, min_discount=0)
    total = len(deals)
    by_store, by_cat = {}, {}
    for d in deals:
        by_store[d["store"]] = by_store.get(d["store"], 0) + 1
        by_cat[d.get("category", "other")] = by_cat.get(d.get("category", "other"), 0) + 1
    avg_d = round(sum(d["discount_pct"] for d in deals) / total, 1) if total else 0
    total_profit = round(sum(d.get("profit_est", 0) for d in deals), 2)
    top10 = sorted(deals, key=lambda d: d.get("profit_est", 0), reverse=True)[:10]
    
    # Build trend tiles, sell-through rows, heatmap
    store_icons = {"bestbuy":"🔵","walmart":"🛒","target":"🎯","amazon":"📦"}
    store_colors = {"target":"#e0443d","walmart":"#ffc120","amazon":"#ff9900","bestbuy":"#0046be"}
    cat_items = sorted(by_cat.items(), key=lambda x: -x[1])[:10]
    cat_roi, cat_sold, hm = {}, {}, {}
    for d in deals:
        k, r, s, st = d.get("category","other"), d.get("roi_pct",0), d.get("sold_30d",0), d["store"]
        cat_roi[k] = cat_roi.get(k,0) + r; cat_sold[k] = cat_sold.get(k,0) + s; hm[(st,k)] = hm.get((st,k),0) + r
    for k in cat_roi: cat_roi[k] = round(cat_roi[k]/by_cat.get(k,1), 1)
    for k in cat_sold: cat_sold[k] = round(cat_sold[k]/by_cat.get(k,1), 1)
    for k in hm: hm[k] = round(hm[k]/max(1,by_store.get(k[0],1)), 1)
    
    trend_tiles = "".join(
        f'<div style="background:#1a1210;border:1px solid #2a1e1e;border-radius:6px;padding:6px;text-align:center">'
        f'<div style="color:{"#2ed573" if cat_roi.get(c,0)>=35 else "#ffd93d" if cat_roi.get(c,0)>=25 else "#e57373" if cat_roi.get(c,0)>=15 else "#636e72"};font-weight:700">{cat_roi.get(c,0):.0f}%</div>'
        f'<div style="color:#7a6a62;font-size:.85em">{n}</div>'
        f'<div style="color:#5a4a42;font-size:.8em">{c[:5]+"." if len(c)>5 else c}</div></div>'
        for c,n in cat_items)
    sell_rows = "".join(
        f'<tr><td>{c}</td><td style="color:#ffd93d">{cat_sold.get(c,0):.0f}</td><td>{30/max(1,cat_sold.get(c,0)):.0f}d</td><td>{"⚡Fast" if cat_sold.get(c,0)>=40 else "👍Normal" if cat_sold.get(c,0)>=20 else "🐢Slow"}</td></tr>'
        for c,_ in cat_items[:8])
    store_list = sorted(by_store.items(), key=lambda x: -x[1])
    hm_header = "".join(f'<td style="text-align:center;font-size:.9em">{store_icons.get(s,"🏪")}</td>' for s,_ in store_list)
    hm_body = "".join(
        f'<tr><td style="color:#b09880">{c[:5]}</td>'
        + "".join(f'<td style="text-align:center;background:{"#2ed573" if hm.get((s,c),0)>=35 else "#ffd93d" if hm.get((s,c),0)>=25 else "#e57373" if hm.get((s,c),0)>0 else "#1a1210"};color:#0c0a0a;font-weight:600;border-radius:3px">{hm.get((s,c),0):.0f}%</td>' for s,_ in store_list)
        + '</tr>'
        for c,_ in cat_items[:6])
    
    store_colors = {"target":"#e0443d","walmart":"#ffc120","amazon":"#ff9900","bestbuy":"#0046be"}
    cat_colors = ["#ff6b35","#ffd93d","#2ed573","#00d2d3","#a29bfe","#fd79a8","#e17055","#6c5ce7","#00b894","#fdcb6e","#e84393","#636e72"]
    
    # Trend radar + sell-through + heatmap data
    cat_roi, cat_sold, hm = {}, {}, {}
    for d in deals:
        k, r, s, st = d.get("category","other"), d.get("roi_pct",0), d.get("sold_30d",0), d["store"]
        cat_roi[k] = cat_roi.get(k,0) + r
        cat_sold[k] = cat_sold.get(k,0) + s
        hm[(st,k)] = hm.get((st,k),0) + r
    for k in cat_roi: cat_roi[k] = round(cat_roi[k]/by_cat.get(k,1), 1)
    for k in cat_sold: cat_sold[k] = round(cat_sold[k]/by_cat.get(k,1), 1)
    for k in hm: hm[k] = round(hm[k]/max(1,by_store.get(k[0],1)), 1)
    
    # Pie chart
    store_data = [(s, c, store_icons.get(s,"🏪"), store_colors.get(s,"#888")) for s, c in sorted(by_store.items(), key=lambda x: -x[1])]
    total_s = sum(c for _,c,_,_ in store_data)
    pie_slices = ""
    ang = 0
    for store, count, icon, color in store_data:
        pct = count / total_s if total_s else 0
        deg = pct * 360
        if deg > 0.5:
            large = 1 if deg > 180 else 0
            x1 = 50 + 40 * __import__('math').cos(__import__('math').radians(ang))
            y1 = 50 + 40 * __import__('math').sin(__import__('math').radians(ang))
            x2 = 50 + 40 * __import__('math').cos(__import__('math').radians(ang + deg))
            y2 = 50 + 40 * __import__('math').sin(__import__('math').radians(ang + deg))
            pie_slices += f'<path d="M50 50 L{x1:.1f} {y1:.1f} A40 40 0 {large} 1 {x2:.1f} {y2:.1f} Z" fill="{color}"/>'
            ang += deg
    
    # Bar chart
    cat_items = sorted(by_cat.items(), key=lambda x: -x[1])[:10]
    max_cat = max(c[1] for c in cat_items) if cat_items else 1
    bars = ""
    for i, (cat, cnt) in enumerate(cat_items):
        h = max(8, cnt / max_cat * 80)
        bar_color = cat_colors[i % len(cat_colors)]
        label = cat[:6] + "…" if len(cat) > 6 else cat
        bars += f'<rect x="{20 + i*36}" y="{90 - h}" width="28" height="{h}" rx="3" fill="{bar_color}"/>'
        bars += f'<text x="{20 + i*36 + 14}" y="104" text-anchor="middle" font-size="8" fill="#7a6a62">{cnt}</text>'
        bars += f'<text x="{20 + i*36 + 14}" y="112" text-anchor="middle" font-size="6" fill="#5a4a42">{label}</text>'
    
    # Top 10 table
    top_rows = ""
    for i, d in enumerate(top10):
        si = store_icons.get(d["store"], "🏪")
        top_rows += f'<tr><td style="color:#7a6a62;font-size:.75em">{i+1}</td><td>{si}</td><td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.8em">{d["title"][:60]}</td><td style="color:#ffd93d;font-weight:600">${d.get("profit_est",0):.0f}</td><td style="color:#00d2d3">+{d.get("roi_pct",0):.0f}%</td></tr>'
    
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PriceHunter Dashboard</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0c0a0a;color:#ece5e0;padding:16px}}
h1{{font-size:1.3em;color:#ff6b35;margin-bottom:16px}}
h2{{font-size:1em;color:#b09880;margin:20px 0 10px}}
.g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-bottom:16px}}
.c{{background:#141111;border:1px solid #2a1e1e;border-radius:12px;padding:14px}}
.c .v{{font-size:1.5em;font-weight:700;color:#ffd93d}}
.c .l{{font-size:.78em;color:#7a6a62;margin-top:4px}}
.chart{{background:#141111;border:1px solid #2a1e1e;border-radius:12px;padding:14px;margin-bottom:16px;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:.82em}}
td{{padding:6px 8px;border-bottom:1px solid #1a1210}}
tr:hover{{background:#1a1210}}
.f{{text-align:center;padding:20px;color:#2a1e1e;font-size:.72em}}
a{{color:#ff6b35;text-decoration:none}}
</style></head><body>
<h1>📊 PriceHunter Dashboard</h1>
<div class="g">
<div class="c"><div class="v">{total}</div><div class="l">🎯 Total Deals</div></div>
<div class="c"><div class="v">${total_profit:.0f}</div><div class="l">💰 Profit Potential</div></div>
<div class="c"><div class="v">{len(by_store)}</div><div class="l">🏪 Stores</div></div>
<div class="c"><div class="v">{avg_d}%</div><div class="l">📉 Avg Discount</div></div>
</div>
<div class="g">
{''.join(f'<div class="c"><div class="v" style="color:{color}">{count}</div><div class="l">{icon} {store.title()}</div></div>' for store, count, icon, color in store_data)}
</div>
<div class="chart">
<h2>📈 Deals by Category</h2>
<svg width="400" height="120" viewBox="0 0 400 120" style="width:100%;max-width:400px">{bars}</svg>
</div>
<div class="chart">
<h2>🧩 Stores Distribution</h2>
<svg width="200" height="120" viewBox="0 0 200 120" style="width:100%;max-width:200px">
{pie_slices}
<text x="50" y="55" text-anchor="middle" font-size="8" fill="#ece5e0" font-weight="700">{total} deals</text>
</svg>
</div>
<div class="chart">
<h2>📈 Trend Radar</h2>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(80px,1fr));gap:4px;font-size:.68em">{trend_tiles}</div>
</div>
<div class="chart">
<h2>⏱ Sell-Through Rate</h2>
<table style="font-size:.76em">
<tr style="color:#7a6a62"><td>Category</td><td>Sold/mo</td><td>Days</td><td>Speed</td></tr>
{sell_rows}
</table>
</div>
<div class="chart">
<h2>🗺️ Margin Heatmap</h2>
<table style="font-size:.7em;width:100%">
<tr style="color:#7a6a62"><td>Cat.</td>{hm_header}</tr>
{hm_body}
</table>
</div>
<div class="chart">
<h2>🏆 Top 10 by Profit</h2>
<table>{top_rows}</table>
</div>
<div class="f"><a href="/api/deals/hot">← Back to deals</a></div>
</body></html>"""

# ─── CSS ────────────────────────────────────────────────────────

_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0c0a0a;color:#ece5e0;-webkit-font-smoothing:antialiased}
.hd{position:sticky;top:0;z-index:100;background:linear-gradient(135deg,#0c0a0a,#1a1210);padding:14px 16px 10px;border-bottom:1px solid #2a1e1e}
.hd h1{font-size:1.3em;color:#ff6b35;display:inline}
.sr{display:flex;gap:6px;padding:7px 16px;background:#0c0a0a;border-bottom:1px solid #2a1e1e;font-size:.78em;color:#7a6a62;overflow-x:auto;white-space:nowrap;align-items:center}
.sr .pf strong{color:#ffd93d}
.sr .zl{cursor:pointer;color:#7a6a62;font-size:.7em}
.sr .zl:hover{color:#ff6b35}
.nv{display:flex;gap:6px;padding:8px 16px;background:#0c0a0a;border-bottom:1px solid #2a1e1e;flex-wrap:wrap}
.nv-s{display:flex;gap:6px;align-items:center;margin-left:auto}
#sq{background:#1a1210;border:1px solid #3a2820;color:#b09880;padding:4px 10px;border-radius:14px;font-size:.72em;outline:none;width:100px}
#sq:focus{width:160px;border-color:#ff6b35;color:#ece5e0}
#so{background:#1a1210;border:1px solid #3a2820;color:#b09880;padding:4px 8px;border-radius:14px;font-size:.7em;outline:none;cursor:pointer}
.wl-btn{cursor:pointer;font-size:.8em;margin-left:auto;opacity:.4;transition:opacity .2s;padding:2px 4px}
.wl-btn.on{opacity:1}
.wl-btn:hover{opacity:.8}
.th{position:sticky;top:0;z-index:100}
.nb{background:#1a1210;border:1px solid #3a2820;color:#b09880;padding:5px 14px;border-radius:14px;font-size:.75em;cursor:pointer;flex-shrink:0;font-weight:600}
.nb.on{background:#ff6b35;color:#0c0a0a;border-color:#ff6b35}
.nb-dd{background:#1a1210;border:1px solid #3a2820;color:#b09880;padding:5px 14px;border-radius:14px;font-size:.75em;cursor:pointer;flex-shrink:0;position:relative}
.dd{display:none;position:absolute;top:100%;left:0;margin-top:6px;background:#141111;border:1px solid #3a2820;border-radius:12px;padding:8px;z-index:200;min-width:240px;box-shadow:0 8px 30px rgba(0,0,0,.8)}
.dd.s{display:grid;grid-template-columns:1fr 1fr;gap:4px}
.dd-it{background:#1a1210;border:1px solid #2a1e1e;border-radius:8px;padding:6px 8px;font-size:.72em;cursor:pointer;color:#b09880;white-space:nowrap}
.dd-it.on{background:#ff6b35;color:#0c0a0a;border-color:#ff6b35;font-weight:600}
.gr{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:10px;padding:10px 14px 80px}
.dc{background:#141111;border-radius:12px;padding:12px;border:1px solid #2a1e1e;cursor:pointer;transition:border .15s}
.dc:hover{border-color:#ff6b35}
.dc-h{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.dc-si{font-size:.72em;color:#7a6a62}
.dc-sc{font-size:.65em;font-weight:700;padding:1px 7px;border-radius:3px;color:#0c0a0a}
.dc-t{font-size:.88em;line-height:1.3;font-weight:500;margin-bottom:6px;color:#ece5e0}
.dc-p{display:flex;align-items:center;gap:5px;font-size:1em;flex-wrap:wrap}
.dc-b{color:#ffd93d;font-weight:700;font-size:1.1em}
.dc-ar{color:#4a3a32}
.dc-g{color:#2ed573;font-weight:700;font-size:1.1em}
.dc-r{color:#6a5a52;font-size:.78em}
.dc-d{padding:1px 6px;border-radius:3px;font-size:.75em;font-weight:600;color:#fff;margin-left:auto}
.dc-pr{display:flex;align-items:center;gap:8px;font-size:.82em;margin-top:4px}
.dc-pv{color:#ffd93d;font-weight:700;font-size:1em}
.dc-ro{color:#00d2d3;font-weight:600}
.dc-so{color:#6a5a52}
.ov{display:none;position:fixed;inset:0;z-index:200;background:rgba(0,0,0,.8);animation:fade .2s}
.ov.s{display:block}
.mo{position:fixed;bottom:0;left:0;right:0;z-index:201;background:#141111;border-radius:16px 16px 0 0;padding:20px 18px 24px;max-height:88vh;overflow-y:auto;animation:up .25s;border-top:1px solid #3a2820}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes up{from{transform:translateY(100%)}to{transform:translateY(0)}}
.mh{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px}
.mh h2{font-size:1em;font-weight:600;flex:1;color:#ece5e0;line-height:1.3}
.mcx{background:none;border:none;color:#7a6a62;font-size:1.2em;cursor:pointer;padding:4px}
.msi{font-size:.72em;color:#7a6a62;margin-bottom:4px}
.mpb{display:flex;gap:10px;align-items:center;margin:6px 0}
.mpb .mvn{font-size:1.2em;font-weight:700;color:#ffd93d}
.mpb .mvr{font-size:.85em;color:#00d2d3;font-weight:600}
.mpr{display:flex;gap:8px;font-size:.8em;color:#7a6a62;margin-bottom:6px;flex-wrap:wrap}
.mpr span strong{color:#ece5e0}
.mstats{display:flex;gap:10px;font-size:.78em;margin:6px 0 10px;flex-wrap:wrap}
.mstats span{background:#1a1210;padding:4px 10px;border-radius:6px;color:#b09880}
.mbtn{display:block;background:linear-gradient(90deg,#ff6b35,#ff8a50);color:#0c0a0a;text-align:center;padding:10px;border-radius:8px;font-weight:700;font-size:.9em;text-decoration:none;margin-bottom:8px}
.mplat{margin:8px 0 4px;font-size:.8em;color:#7a6a62}
.mpcard{background:#1a1210;border:1px solid #2a1e1e;border-radius:8px;padding:8px 10px;margin:4px 0;display:flex;justify-content:space-between;align-items:center}
.mpcard.best{border-color:#ffd93d;background:#1e1411}
.mpnm{font-size:.78em;font-weight:600;color:#ece5e0;min-width:80px}
.mppr{font-size:.82em;color:#ffd93d;font-weight:600;text-align:right}
.mpfee{font-size:.65em;color:#7a6a62}
.bestbadge{font-size:.6em;background:#ffd93d;color:#0c0a0a;padding:1px 5px;border-radius:3px;font-weight:700;margin-left:6px}
.mplink{font-size:.7em;color:#7a6a62;text-decoration:none;margin-left:auto;padding-left:8px}
.mplink:hover{color:#ffd93d}
.ft{text-align:center;padding:12px;color:#2a1e1e;font-size:.72em}
@media(max-width:480px){.gr{grid-template-columns:1fr}}
"""

_JS = r"""
var MI = MODAL_DATA_PLACEHOLDER;
document.querySelectorAll('.dc').forEach(function(el,i){el.addEventListener('click',function(e){openM(i);});});
function openM(i){
  var d=MI[i];
  document.getElementById('ov').classList.add('s');
  var h='<div class="mh"><span class="msi">'+d.si+' '+d.store+'</span><span class="mcx" onclick="closeM()">x</span></div>'+
    '<h2>'+d.title+(d.stars||'')+'</h2>'+
    '<div class="mpb"><span class="mvn">$'+d.cp.toFixed(0)+'</span><span class="mvr">$'+d.avg_r.toFixed(0)+'</span></div>'+
    '<div class="mpr"><span>Buy: <strong>$'+d.cp.toFixed(0)+'</strong></span><span>Sell: <strong>$'+d.avg_r.toFixed(0)+'</strong> ($'+d.min_r.toFixed(0)+'-$'+d.max_r.toFixed(0)+')</span></div>'+
    '<div class="mpb"><span class="mvn">+$'+d.profit.toFixed(0)+'</span><span class="mvr">ROI '+d.roi.toFixed(0)+'%</span></div>'+
    '<div class="mstats"><span>Sold: '+d.sold+'/30d</span><span style="background:'+d.fc+';color:#161210;font-weight:600">'+d.score+' '+d.fl+'</span><span style="background:#e8835a;color:#fff">-'+d.dp.toFixed(0)+'%</span></div>'+
    '<a href="'+d.buy_url+'" class="mbtn" target="_blank">Buy for $'+d.cp.toFixed(0)+'</a>'+
    '<div class="mplat">Resale prices by platform:</div>';
  var pk=['eBay','FB Marketplace','OfferUp','Craigslist'];
  var bestName=d.best[0];
  for(var qi=0;qi<pk.length;qi++){
    var p=d.plat[pk[qi]];
    h+='<div class="mpcard'+(pk[qi]===bestName?' best':'')+'"><span class="mpnm">'+pk[qi]+'</span>'+
      '<span><span class="mppr">$'+p.price.toFixed(0)+'</span>'+(p.fee_pct>0?' <span class="mpfee">-'+p.fee_pct+'%</span>':'')+'</span>'+
      (pk[qi]===bestName?'<span class="bestbadge">BEST</span>':'')+
      '<a class="mplink" href="'+(d.sell_urls[pk[qi]]||d.sell_urls.eBay)+'" target="_blank">></a></div>';
  }
  h+='<div id="phc" style="margin-top:8px;height:50px"></div>';
  h+='<div style="margin-top:10px;padding-top:10px;border-top:1px solid #2a1e1e">';
  h+='<div style="font-size:.78em;color:#b09880;margin-bottom:6px">💰 Net Profit Calculator</div>';
  h+='<div style="display:flex;gap:6px;flex-wrap:wrap;font-size:.78em">';
  h+='<input id="pc_sale" placeholder="Sale $" value="'+d.avg_r.toFixed(0)+'" style="width:70px;background:#1a1210;border:1px solid #3a2820;color:#ece5e0;padding:4px 8px;border-radius:6px;outline:none">';
  h+='<select id="pc_plat" style="background:#1a1210;border:1px solid #3a2820;color:#ece5e0;padding:4px 6px;border-radius:6px;outline:none;font-size:.9em"><option value="0.135">eBay 13.5%</option><option value="0.15">Amazon 15%</option><option value="0.10">Mercari 10%</option><option value="0">FB Mkt 0%</option><option value="0">OfferUp 0%</option></select>';
  h+='<input id="pc_ship" placeholder="Ship $" value="0" style="width:60px;background:#1a1210;border:1px solid #3a2820;color:#ece5e0;padding:4px 8px;border-radius:6px;outline:none">';
  h+='<select id="pc_state" style="background:#1a1210;border:1px solid #3a2820;color:#ece5e0;padding:4px 6px;border-radius:6px;outline:none;font-size:.9em"><option value="0">State tax</option><option value="0">— No tax —</option><option value="0.1025">CA 10.25%</option><option value="0.10">WA 10%</option><option value="0.0975">TN 9.75%</option><option value="0.095">LA 9.5%</option><option value="0.0925">AR 9.25%</option><option value="0.09">NY 9%</option><option value="0.0875">IL 8.75%</option><option value="0.08">TX 8%</option><option value="0.0725">FL 7.25%</option><option value="0.07">NJ 7%</option><option value="0.065">MA 6.5%</option><option value="0.06">PA 6%</option><option value="0.0475">MI 4.75%</option><option value="0.04">HI 4%</option><option value="0">OR 0%</option><option value="0">NH 0%</option><option value="0">DE 0%</option><option value="0">MT 0%</option></select>';
  h+='</div><div id="pc_result" style="margin-top:6px;font-size:.82em;color:#2ed573;font-weight:600"></div></div>';
  document.getElementById('mo').innerHTML=h;
  // Fetch price history and render sparkline
  var xhr=new XMLHttpRequest();
  xhr.open('GET','/api/deals/'+d.id+'/history?days=30',true);
  xhr.onload=function(){
    if(xhr.status!==200)return;
    var data=JSON.parse(xhr.responseText);
    if(!data||data.length<2)return;
    var prices=data.map(function(p){return p.price;});
    var min=Math.min.apply(null,prices),max=Math.max.apply(null,prices);
    var range=max-min||1;
    var w=200,h2=40;
    var pts=prices.map(function(p,i){return (i/(prices.length-1)*w).toFixed(0)+','+(h2-((p-min)/range)*(h2-4)-2).toFixed(0);}).join(' ');
    var color=prices[prices.length-1]<prices[0]?'#2ed573':'#e8835a';
    var svg='<svg width="'+w+'" height="'+h2+'" viewBox="0 0 '+w+' '+h2+'" style="width:100%;max-width:200px"><polyline fill="none" stroke="'+color+'" stroke-width="2" points="'+pts+'"/><text x="0" y="10" fill="#7a6a62" font-size="9">$'+min.toFixed(0)+'</text><text x="'+(w-30)+'" y="10" fill="#7a6a62" font-size="9">$'+max.toFixed(0)+'</text></svg>';
    document.getElementById('phc').innerHTML=svg;
    // ML Predictor: price drop probability
    if(prices.length>=4){
      var recent=prices.slice(-4);
      var drops=0;
      for(var pi=1;pi<recent.length;pi++){if(recent[pi]<recent[pi-1]){drops++;}}
      var prob=Math.round((drops/(recent.length-1))*100);
      var direction=drops>=3?'📉 Likely to drop further ('+prob+'%)':'📈 Stable or rising ('+prob+'% stability)';
      document.getElementById('phc').innerHTML+=direction;
    }
  };
  xhr.send();
  // Profit calculator
  setTimeout(function(){
    var inputs=document.querySelectorAll('#pc_sale,#pc_plat,#pc_ship,#pc_tax,#pc_state');
    function calc(){
      var sale=parseFloat(document.getElementById('pc_sale').value)||0;
      var fee=parseFloat(document.getElementById('pc_plat').value)||0;
      var ship=parseFloat(document.getElementById('pc_ship').value)||0;
      var stateTax=parseFloat(document.getElementById('pc_state').value)||0;
      var tax=(parseFloat(document.getElementById('pc_tax').value)||0)+(sale*stateTax);
      var cost=d.cp;
      var net=sale-sale*fee-ship-tax-cost;
      var el=document.getElementById('pc_result');
      el.innerHTML='Buy $'+cost.toFixed(0)+' → Net <strong>$'+net.toFixed(0)+'</strong> (ROI '+((net/cost)*100).toFixed(0)+'%)';
      el.style.color=net>0?'#2ed573':'#e57373';
    }
    inputs.forEach(function(el){el.addEventListener('input',calc);});
    calc();
  },100);
}
function closeM(){document.getElementById('ov').classList.remove('s');document.getElementById('mo').innerHTML='';}
function filterCards(){
  var wl=JSON.parse(localStorage.getItem('ph_wl')||'{}');
  var q=document.getElementById('sq').value.toLowerCase();
  var store=document.querySelector('.nb.on[data-store]');
  var cat=document.querySelector('.nb.on[data-c]');
  var sort=document.getElementById('so').value;
  var cards=Array.from(document.querySelectorAll('.dc'));
  cards.forEach(function(c){
    var show=true;
    if(store){show=show&&c.getAttribute('data-store')===store.getAttribute('data-store');}
    if(cat&&cat.getAttribute('data-c')!=='all'){
      if(cat.getAttribute('data-c')==='hot'){show=show&&c.getAttribute('data-hot')==='true';}
      else if(cat.getAttribute('data-c')==='goldmine'){show=show&&parseFloat(c.getAttribute('data-profit'))>=30&&parseInt(c.getAttribute('data-score'))>=65;}
      else if(cat.getAttribute('data-c')==='scalper'){show=show&&parseFloat(c.getAttribute('data-profit'))>=40&&parseInt(c.getAttribute('data-score'))>=80;}
      else if(cat.getAttribute('data-c')==='watchlist'){show=show&&wl[c.getAttribute('data-id')];}
      else{show=show&&c.getAttribute('data-c')===cat.getAttribute('data-c');}
    }
    if(q&&!c.querySelector('.dc-t').innerText.toLowerCase().includes(q)){show=false;}
    c.style.display=show?'':'none';
    // Update watchlist btn state
    var btn=c.querySelector('.wl-btn');
    if(btn){btn.classList.toggle('on',!!wl[c.getAttribute('data-id')]);}
  });
  if(sort==='profit'){cards.sort(function(a,b){return parseFloat(b.getAttribute('data-profit'))-parseFloat(a.getAttribute('data-profit'));});}
  else if(sort==='roi'){cards.sort(function(a,b){return parseFloat(b.getAttribute('data-roi'))-parseFloat(a.getAttribute('data-roi'));});}
  else if(sort==='discount'){cards.sort(function(a,b){return parseFloat(b.getAttribute('data-dp'))-parseFloat(a.getAttribute('data-dp'));});}
  else if(sort==='newest'){cards.sort(function(a,b){return b.getAttribute('data-date')<a.getAttribute('data-date')?-1:1;});}
  var gr=document.getElementById('gr');
  cards.forEach(function(c){gr.appendChild(c);});
}
document.getElementById('nv').onclick=function(e){
  var b=e.target.closest('.nb');if(!b)return;
  document.querySelectorAll('.nb').forEach(function(x){x.classList.remove('on');});
  b.classList.add('on');document.getElementById('dd').classList.remove('s');
  filterCards();
};
document.getElementById('sq').oninput=filterCards;
document.getElementById('so').onchange=filterCards;
document.getElementById('ddBtn').onclick=function(e){e.stopPropagation();document.getElementById('dd').classList.toggle('s');};
document.getElementById('dd').onclick=function(e){
  var it=e.target.closest('.dd-it');if(!it)return;
  document.querySelectorAll('.dd-it').forEach(function(x){x.classList.remove('on');});
  it.classList.add('on');document.querySelectorAll('.nb').forEach(function(x){x.classList.remove('on');});
  document.getElementById('dd').classList.remove('s');
  var cat=it.getAttribute('data-c');
  document.querySelectorAll('.dc').forEach(function(c){c.style.display=c.getAttribute('data-c')===cat?'':'none';});
};
document.addEventListener('click',function(e){if(!e.target.closest('.nb-dd'))document.getElementById('dd').classList.remove('s');});
if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js');
var MA_STORES=[
  {name:"Target Sharon",icon:"T",zip:"02067",city:"Sharon",dist:1.8,region:"Sharon"},
  {name:"Walmart Mansfield",icon:"W",zip:"02048",city:"Mansfield",dist:4.2,region:"Sharon"},
  {name:"Home Depot Stoughton",icon:"H",zip:"02072",city:"Stoughton",dist:5.5,region:"Sharon"},
  {name:"Best Buy Braintree",icon:"B",zip:"02184",city:"Braintree",dist:8.1,region:"Sharon"},
  {name:"Target Boston",icon:"T",zip:"02111",city:"Boston",dist:16,region:"Boston"},
  {name:"Walmart Somerville",icon:"W",zip:"02145",city:"Somerville",dist:18,region:"Boston"},
  {name:"Best Buy Cambridge",icon:"B",zip:"02142",city:"Cambridge",dist:17,region:"Boston"},
  {name:"Home Depot Brighton",icon:"H",zip:"02135",city:"Brighton",dist:18,region:"Boston"},
  {name:"Walmart Framingham",icon:"W",zip:"01701",city:"Framingham",dist:14,region:"MetroWest"},
  {name:"Target Natick",icon:"T",zip:"01760",city:"Natick",dist:15,region:"MetroWest"},
  {name:"Walmart Worcester",icon:"W",zip:"01605",city:"Worcester",dist:32,region:"Worcester"},
  {name:"Target Springfield",icon:"T",zip:"01109",city:"Springfield",dist:55,region:"Springfield"},
  {name:"Walmart Danvers",icon:"W",zip:"01923",city:"Danvers",dist:26,region:"NorthShore"},
];
function openStores(){
  var h='<div class="mh"><span class="msi">Stores in Massachusetts</span><span class="mcx" onclick="closeM()">x</span></div>';
  h+='<div style="font-size:.72em;color:#7a6a62;margin-bottom:8px">Nearest to 02067:</div>';
  MA_STORES.sort(function(a,b){return a.dist-b.dist;});
  var rg={};for(var ri=0;ri<MA_STORES.length;ri++){var s=MA_STORES[ri];if(!rg[s.region])rg[s.region]=[];rg[s.region].push(s);}
  var rn=Object.keys(rg);
  for(var ri=0;ri<rn.length;ri++){
    h+='<div style="font-size:.78em;color:#ff6b35;font-weight:600;margin:8px 0 4px">'+rn[ri]+'</div>';
    for(var si=0;si<rg[rn[ri]].length;si++){var s=rg[rn[ri]][si];
      h+='<div class="mpcard"><span class="mpnm">'+s.icon+' '+s.name+'</span><span style="font-size:.72em;color:#7a6a62">'+s.city+' '+s.dist+'mi</span></div>';
    }
  }
  document.getElementById('mo').innerHTML=h;
  document.getElementById('ov').classList.add('s');
}
"""


# ─── RENDER ─────────────────────────────────────────────────────

def render_page(deals):
    CATS = {"all":"🔥 All","hot":"⭐ Top Demand","toys":"🧱 LEGO","gaming":"🎮 Gaming","tools":"🔧 Tools","home":"🏠 Home","audio":"🎧 Audio","storage":"💾 Storage","outdoor":"🌿 Outdoor","baby":"👶 Baby","gpu":"🎮 GPU","laptop":"💻 Laptops","tv":"📺 TVs","monitor":"🖥️ Monitors","phone":"📱 Phones","tablet":"📱 Tablets","other":"📦 Other"}
    STORE_ICONS = {"bestbuy":"🔵","walmart":"🛒","target":"🎯","amazon":"📦","homedepot":"🧰","lowes":"🪴","costco":"🏬","kohls":"🏪","bhphoto":"📷","newegg":"🖥️","microcenter":"💻","dicks":"🏕️"}
    FLIP_COLORS = {"S":"#ff6b35","A":"#ffd93d","B":"#ff4757","C":"#636e72"}
    FLIP_LABELS = {"S":"Instant","A":"Fast","B":"Ok","C":"Risky"}
    HIGH_DEMAND = ["lego","airpods","ipad","apple","macbook","nintendo","playstation","xbox","kitchenaid","milwaukee","dewalt","samsung ssd","ninja","instant pot","yeti","weber","solo stove"]

    def is_hot(t): return any(kw in t.lower() for kw in HIGH_DEMAND)
    def plat_price(base, pct): return round(base * pct, 2)

    cards, modal_items = "", []
    cat_counts = {"hot": 0, "goldmine": 0, "scalper": 0}
    from datetime import datetime
    now = datetime.utcnow().strftime("%b %d %H:%M UTC")
    # Bundle detection
    bundle_p = __import__("re").compile(r"(\d+)\s*(pack|pair|count|set|roll|bundle|lot|kit)", __import__("re").I)

    for d in deals:
        m = bundle_p.search(d["title"])
        units = int(m.group(1)) if m else 1
        is_bundle = units > 1
        profit = d.get("profit_est", 0)
        score = d.get("flip_score", "C")
        is_goldmine = profit >= 30 and score in ("S", "A")
        c = d.get("category", "other")
        cat_counts[c] = cat_counts.get(c, 0) + 1
        hot = is_hot(d["title"])
        if hot: cat_counts["hot"] += 1
        profit = d.get("profit_est", 0)
        score = d.get("flip_score", "C")
        is_goldmine = profit >= 30 and score in ("S", "A")
        if is_goldmine: cat_counts["goldmine"] += 1
        roi_pct = d.get("roi_pct", 0)
        is_scalper = profit >= 40 and score_num >= 80 if isinstance(score, int) else False
        if is_scalper: cat_counts["scalper"] += 1

        store, title = d["store"], d["title"][:120]
        dp, cp = d["discount_pct"], d["current_price"]
        profit, roi = d.get("profit_est", 0), d.get("roi_pct", 0)
        avg_r, min_r, max_r = d.get("avg_resale", 0), d.get("min_resale", 0), d.get("max_resale", 0)
        sold, score = d.get("sold_30d", 0), d.get("flip_score", "B")
        buy_url = d.get("affiliate_url") or d["url"]
        si, fc = STORE_ICONS.get(store, "🏪"), FLIP_COLORS.get(score, "#888")
        fl = FLIP_LABELS.get(score, "")
        idx = len(modal_items)

        plat = {"eBay":{"price":avg_r,"fee_pct":13.5,"net":round(avg_r*0.865,2)},"FB Marketplace":{"price":plat_price(avg_r,0.92),"fee_pct":0,"net":plat_price(avg_r,0.92)},"OfferUp":{"price":plat_price(avg_r,0.9),"fee_pct":0,"net":plat_price(avg_r,0.9)},"Craigslist":{"price":plat_price(avg_r,0.85),"fee_pct":0,"net":plat_price(avg_r,0.85)}}
        best = max(plat.items(), key=lambda x: x[1]["net"])

        sell_urls = {"eBay": f"https://www.ebay.com/sch/i.html?_nkw={title[:60].replace(chr(32),'+')}&_sop=15"}
        sell_urls["FB Marketplace"] = f"https://www.facebook.com/marketplace/search/?q={title[:60].replace(chr(32),'%20')}"
        sell_urls["OfferUp"] = f"https://offerup.com/search?q={title[:60].replace(chr(32),'%20')}"
        sell_urls["Craigslist"] = f"https://{store[:2]}.craigslist.org/search/sss?query={title[:60].replace(chr(32),'+')}"

        modal_items.append({"id":d["id"],"title":d["title"][:120],"store":store,"cp":cp,"op":d["original_price"],"avg_r":avg_r,"min_r":min_r,"max_r":max_r,"profit":profit,"roi":roi,"sold":sold,"score":score,"dp":dp,"buy_url":buy_url,"si":si,"fc":fc,"fl":fl,"plat":plat,"best":best,"sell_urls":sell_urls,"stars":("⭐" if hot else "")})

        cards += f"""<div class="dc" data-c="{c}" data-store="{store}" data-hot="{str(hot).lower()}" data-profit="{profit}" data-roi="{roi}" data-dp="{dp}" data-id="{d['id']}" data-score="{score}" data-date="{now}">
  <div class="dc-h"><span class="dc-si">{si} {store.title()}</span><span class="dc-sc" style="background:{fc}">{score} {fl}</span><span class="wl-btn" onclick="event.stopPropagation();toggleWl(this)">🔖</span></div>
  <div class="dc-t">{title}{' ⭐' if hot else ''}{' 📦' if is_bundle and units > 1 else ''}</div>
  <div class="dc-p">
    <span class="dc-b">${cp:.0f}</span><span class="dc-ar">→</span><span class="dc-g">${avg_r:.0f}</span><span class="dc-r">($${min_r:.0f}-$${max_r:.0f}){' $'+str(round(avg_r/units,1))+'/ea' if is_bundle and units > 1 else ''}</span>
    <span class="dc-d" style="background:{'#e57373' if dp>=50 else '#e8835a' if dp>=30 else '#555'}">-{dp:.0f}%</span>
  </div>
  <div class="dc-pr">
    <span class="dc-pv">+${profit:.0f}</span><span class="dc-ro">ROI {roi:.0f}%</span><span class="dc-so">📊 {sold}/30d</span>
  </div>
</div>"""

    modal_json = json.dumps(modal_items)
    total_profit = sum(d.get("profit_est", 0) for d in deals)

    dd_items = ""
    for key, label in CATS.items():
        if key in ("all", "hot"): continue
        n = cat_counts.get(key, 0)
        if n > 0:
            dd_items += f'<div class="dd-it" data-c="{key}">{label} <span class="ct">{n}</span></div>'

    tabs = f'<button class="nb on" data-c="all">🔥 All <span class="ct">{len(deals)}</span></button>'
    if cat_counts.get("hot", 0) > 0:
        tabs += f'<button class="nb" data-c="hot">⭐ Top&nbsp;Demand <span class="ct">{cat_counts["hot"]}</span></button>'
    if cat_counts.get("goldmine", 0) > 0:
        tabs += f'<button class="nb" data-c="goldmine">💎 Goldmine <span class="ct">{cat_counts["goldmine"]}</span></button>'
    if cat_counts.get("scalper", 0) > 0:
        tabs += f'<button class="nb" data-c="scalper">🎯 Scalper <span class="ct">{cat_counts["scalper"]}</span></button>'
    tabs += f'<button class="nb" data-c="watchlist">🔖 Saved</button>'
    tabs += f'<a href="/dashboard" class="nb-dd" style="text-decoration:none">📊 Dash</a>'
    # Store tabs
    store_counts = {}
    for d in deals:
        s = d["store"]
        store_counts[s] = store_counts.get(s, 0) + 1
    store_icons = {"bestbuy":"🔵","walmart":"🛒","target":"🎯","amazon":"📦"}
    for s in ["target","walmart","amazon","bestbuy"]:
        if store_counts.get(s, 0) > 0:
            tabs += f'<button class="nb" data-store="{s}">{store_icons.get(s,"🏪")} {s.title()} <span class="ct">{store_counts[s]}</span></button>'
    tabs += f'<button class="nb-dd" id="ddBtn">📂 Categories ▾</button>'
    tabs += f'<div class="dd" id="dd">{dd_items}</div>'
    tabs += f'<div class="nv-s"><input id="sq" placeholder="🔍 Search" spellcheck="false"><button class="nb" id="bcBtn" onclick="openBarcode()" style="font-size:.8em;padding:3px 8px">📷</button><select id="so"><option value="">Sort</option><option value="discount">% Off</option><option value="profit">💰 Profit</option><option value="roi">📈 ROI</option><option value="newest">🆕 Newest</option></select></div>'

    js_final = _JS.replace("MODAL_DATA_PLACEHOLDER", modal_json)

    return f"""<!DOCTYPE html><html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0c0a0a">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/api/icon?size=192">
<title>PriceHunter</title>
<style>{_CSS}</style>
</head><body>
<div class="th"><div class="hd"><h1>🏷️ PriceHunter</h1></div>
<div class="sr">
<span>🎯 Deals: <strong>{len(deals)}</strong></span>
<span class="pf">💰 Profit: <strong>+${total_profit:.0f}</strong></span>
<span>🏪 {len(set(d['store'] for d in deals))} stores</span>
<span class="zl" id="zipBtn" onclick="openStores()">📍 02067</span>
<span>🔄 {now}</span>
</div>
<nav class="nv" id="nv">{tabs}</nav></div>
<div class="gr" id="gr">{cards}</div>
<div class="ov" id="ov" onclick="closeM()"></div>
<div class="mo" id="mo"></div>
<div class="ft">Tap a card for resale analytics</div>
<script>{js_final}</script>
</body></html>"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
