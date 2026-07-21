"""
PriceHunter — ядро базы данных.
Использует Supabase (PostgreSQL) с fallback на SQLite для локальной разработки.
"""
import os
import json
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

USE_SUPABASE = os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")

if USE_SUPABASE:
    from supabase import create_client, Client

    supabase: Client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_KEY"),
    )
else:
    import sqlite3
    from pathlib import Path

    DB_PATH = Path(__file__).parent / "pricehunter.db"

    def get_conn():
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init_db():
        conn = get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS deals (
                id TEXT PRIMARY KEY,
                store TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                image_url TEXT,
                original_price REAL NOT NULL,
                current_price REAL NOT NULL,
                discount_pct REAL NOT NULL,
                category TEXT DEFAULT 'electronics',
                currency TEXT DEFAULT 'USD',
                affiliate_url TEXT,
                avg_resale REAL DEFAULT 0,
                min_resale REAL DEFAULT 0,
                max_resale REAL DEFAULT 0,
                sold_30d INTEGER DEFAULT 0,
                profit_est REAL DEFAULT 0,
                roi_pct REAL DEFAULT 0,
                flip_score TEXT DEFAULT 'B',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                store TEXT,
                category TEXT,
                min_discount REAL DEFAULT 30,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS sent_alerts (
                deal_id TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                sent_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (deal_id, chat_id)
            );
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_id TEXT NOT NULL,
                price REAL NOT NULL,
                recorded_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_price_history_deal ON price_history(deal_id);
        """)
        conn.commit()
        conn.close()

    init_db()


# ─── Общий API ────────────────────────────────────────────────────────

def save_deal(deal: dict) -> bool:
    """Сохраняет или обновляет сделку. Возвращает True если это НОВЫЙ deal (upsert)."""
    deal_id = deal["id"]
    now = datetime.now(timezone.utc).isoformat()

    if USE_SUPABASE:
        existing = supabase.table("deals").select("id").eq("id", deal_id).execute()
        is_new = len(existing.data) == 0
        data = {**deal, "updated_at": now}
        if is_new:
            data["created_at"] = now
        supabase.table("deals").upsert(data).execute()
        return is_new
    else:
        conn = get_conn()
        existing = conn.execute("SELECT id FROM deals WHERE id = ?", (deal_id,)).fetchone()
        is_new = existing is None
        if is_new:
            conn.execute("""
                INSERT INTO deals (id, store, title, url, image_url, original_price, current_price, discount_pct, category, affiliate_url, avg_resale, min_resale, max_resale, sold_30d, profit_est, roi_pct, flip_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (deal_id, deal["store"], deal["title"], deal["url"], deal.get("image_url"),
                  deal["original_price"], deal["current_price"], deal["discount_pct"],
                  deal.get("category", "electronics"), deal.get("affiliate_url"),
                  deal.get("avg_resale", 0), deal.get("min_resale", 0), deal.get("max_resale", 0),
                  deal.get("sold_30d", 0), deal.get("profit_est", 0), deal.get("roi_pct", 0),
                  deal.get("flip_score", "B")))
        else:
            conn.execute("""
                UPDATE deals SET current_price=?, discount_pct=?, updated_at=?, affiliate_url=?,
                avg_resale=?, min_resale=?, max_resale=?, sold_30d=?, profit_est=?, roi_pct=?, flip_score=?
                WHERE id=?
            """, (deal["current_price"], deal["discount_pct"], now, deal.get("affiliate_url"),
                  deal.get("avg_resale", 0), deal.get("min_resale", 0), deal.get("max_resale", 0),
                  deal.get("sold_30d", 0), deal.get("profit_est", 0), deal.get("roi_pct", 0),
                  deal.get("flip_score", "B"), deal_id))
        conn.commit()
        conn.close()
        return is_new


def save_price_snapshot(deal_id: str, price: float):
    """Сохраняет снимок цены в историю."""
    if USE_SUPABASE:
        supabase.table("price_history").insert({"deal_id": deal_id, "price": price}).execute()
    else:
        conn = get_conn()
        conn.execute("INSERT INTO price_history (deal_id, price) VALUES (?, ?)", (deal_id, price))
        conn.commit()
        conn.close()


def get_price_history(deal_id: str, days: int = 30) -> list:
    """Возвращает историю цен для сделки."""
    if USE_SUPABASE:
        from datetime import datetime, timezone, timedelta
        since = datetime.now(timezone.utc) - timedelta(days=days)
        return supabase.table("price_history").select("price,recorded_at").eq("deal_id", deal_id).gte("recorded_at", since.isoformat()).order("recorded_at").execute().data
    else:
        conn = get_conn()
        rows = conn.execute(
            "SELECT price, recorded_at FROM price_history WHERE deal_id = ? AND recorded_at >= datetime('now', ? || ' days') ORDER BY recorded_at",
            (deal_id, f"-{days}")
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


def get_hot_deals(limit: int = 50, min_discount: float = 30, store: Optional[str] = None):
    """Возвращает сделки с минимальной скидкой."""
    if USE_SUPABASE:
        query = supabase.table("deals").select("*").gte("discount_pct", min_discount).order("discount_pct", desc=True).limit(limit)
        if store:
            query = query.eq("store", store)
        return query.execute().data
    else:
        conn = get_conn()
        sql = "SELECT * FROM deals WHERE discount_pct >= ? ORDER BY discount_pct DESC LIMIT ?"
        params = [min_discount, limit]
        if store:
            sql = "SELECT * FROM deals WHERE discount_pct >= ? AND store = ? ORDER BY discount_pct DESC LIMIT ?"
            params = [min_discount, store, limit]
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]


def get_subscribers():
    """Все активные подписки."""
    if USE_SUPABASE:
        return supabase.table("alerts").select("*").eq("active", True).execute().data
    else:
        conn = get_conn()
        rows = conn.execute("SELECT * FROM alerts WHERE active = 1").fetchall()
        conn.close()
        return [dict(r) for r in rows]


def add_subscriber(chat_id: str, store: Optional[str], category: Optional[str], min_discount: float = 30):
    if USE_SUPABASE:
        supabase.table("alerts").upsert({
            "chat_id": chat_id, "store": store, "category": category, "min_discount": min_discount
        }).execute()
    else:
        conn = get_conn()
        conn.execute("""
            INSERT INTO alerts (chat_id, store, category, min_discount)
            VALUES (?, ?, ?, ?)
        """, (chat_id, store, category, min_discount))
        conn.commit()
        conn.close()


def was_sent(deal_id: str, chat_id: str) -> bool:
    if USE_SUPABASE:
        return len(supabase.table("sent_alerts").select("deal_id").eq("deal_id", deal_id).eq("chat_id", chat_id).execute().data) > 0
    else:
        conn = get_conn()
        row = conn.execute("SELECT 1 FROM sent_alerts WHERE deal_id = ? AND chat_id = ?", (deal_id, chat_id)).fetchone()
        conn.close()
        return row is not None


def mark_sent(deal_id: str, chat_id: str):
    if USE_SUPABASE:
        supabase.table("sent_alerts").upsert({"deal_id": deal_id, "chat_id": chat_id}).execute()
    else:
        conn = get_conn()
        conn.execute("INSERT OR IGNORE INTO sent_alerts (deal_id, chat_id) VALUES (?, ?)", (deal_id, chat_id))
        conn.commit()
        conn.close()
