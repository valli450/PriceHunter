"""
PriceHunter — Telegram Bot.
Отправляет уведомления о горячих скидках подписчикам.
"""
import os
import sys
import asyncio
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_USERNAME = "PriceHunterBot"  # Замени на своё имя после создания бота


def send_deal_notifications(deals: List[Dict], subscribers: List[Dict]):
    """
    Отправляет уведомления о скидках подписчикам.
    Можно вызвать как из планировщика, так и вручную.
    """
    if not TELEGRAM_BOT_TOKEN:
        print("[Telegram] No TELEGRAM_BOT_TOKEN configured")
        return
    
    import httpx
    
    for subscriber in subscribers:
        chat_id = subscriber.get("chat_id")
        if not chat_id:
            continue
        
        min_discount = subscriber.get("min_discount", 30)
        
        for deal in deals:
            if deal["discount_pct"] < min_discount:
                continue
            if deal.get("store") == "amazon":
                continue
            
            # Проверяем фильтры подписчика
            if subscriber.get("store") and deal["store"] != subscriber["store"]:
                continue
            if subscriber.get("category") and deal.get("category") != subscriber["category"]:
                continue
            
            # Не шлём повторно
            from backend.database import was_sent, mark_sent
            if was_sent(deal["id"], chat_id):
                continue
            
            # Форматируем сообщение
            msg = _format_deal_telegram(deal)
            
            try:
                resp = httpx.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": msg,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": False,
                    },
                    timeout=10,
                )
                if resp.status_code == 200:
                    mark_sent(deal["id"], chat_id)
                    print(f"[Telegram] Sent to {chat_id}: {deal['title'][:40]}...")
                else:
                    print(f"[Telegram] Error sending to {chat_id}: {resp.text}")
            except Exception as e:
                print(f"[Telegram] Send error: {e}")


def _format_deal_telegram(deal: Dict) -> str:
    """Форматирует скидку для Telegram сообщения."""
    emoji = "🔥" if deal["discount_pct"] >= 50 else "💰" if deal["discount_pct"] >= 30 else "💸"
    store_emojis = {"bestbuy": "🔵", "walmart": "🛒", "target": "🎯"}
    store_emoji = store_emojis.get(deal["store"], "🏪")
    
    title = deal["title"][:100]
    store_name = deal["store"].title()
    category = deal.get("category", "").title()
    url = deal.get("affiliate_url") or deal["url"]
    
    msg = (
        f"{emoji} *{title}*\n\n"
        f"~~${deal['original_price']:.2f}~~ → *${deal['current_price']:.2f}*\n"
        f"Скидка: *-{deal['discount_pct']:.0f}%*\n\n"
        f"{store_emoji} {store_name}\n"
        f"📂 {category}\n\n"
        f"[🛒 Открыть]({url})"
    )
    return msg


async def run_bot_polling():
    """Запускает polling-режим бота (для обработки команд)."""
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
    
    if not TELEGRAM_BOT_TOKEN:
        print("[Telegram] No token configured")
        return
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        await update.message.reply_text(
            f"👋 Привет! Я PriceHunter — бот для отслеживания скидок 50%+ на технику.\n\n"
            f"📌 *Команды:*\n"
            f"/subscribe — подписаться на уведомления\n"
            f"/hot — топ скидок прямо сейчас\n"
            f"/stores — список магазинов\n\n"
            f"🔥 Слежу за: Best Buy, Walmart, Target\n"
            f"Каждые 6 часов проверяю новые скидки",
            parse_mode="Markdown",
        )
    
    async def hot(update: Update, context: ContextTypes.DEFAULT_TYPE):
        from backend.database import get_hot_deals
        deals = get_hot_deals(limit=10, min_discount=30)
        
        if not deals:
            await update.message.reply_text("😴 Сейчас нет горячих скидок. Попробуй позже.")
            return
        
        msg = "🔥 *Горячие скидки прямо сейчас:*\n\n"
        for i, d in enumerate(deals[:5], 1):
            msg += f"{i}. *{d['title'][:60]}*\n"
            msg += f"   ${d['original_price']:.0f} → ${d['current_price']:.0f} (-{d['discount_pct']:.0f}%) — {d['store'].title()}\n\n"
        msg += f"[🌐 Открыть сайт PriceHunter](https://pricehunter.fly.dev/api/deals/hot)"
        
        await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("hot", hot))
    
    print("[Telegram] Starting bot polling...")
    await application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    asyncio.run(run_bot_polling())
