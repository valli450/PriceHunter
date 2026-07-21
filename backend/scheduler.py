"""
PriceHunter — Scheduler.
Периодически запускает скрапер и отправляет уведомления.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apscheduler.schedulers.background import BackgroundScheduler
from backend.database import save_deal, get_hot_deals, get_subscribers, was_sent, mark_sent
from scraper import scrape_all_stores
from scraper.utils import format_deal_message

scheduler = BackgroundScheduler()


def scrape_and_notify():
    """Запускает скрапер, сохраняет сделки, отправляет уведомления."""
    print(f"[Scheduler] Running scrape...")
    
    deals = scrape_all_stores()
    if not deals:
        print(f"[Scheduler] No deals found")
        return
    
    new_deals = []
    for deal in deals:
        if save_deal(deal):
            new_deals.append(deal)
    
    print(f"[Scheduler] Saved {len(new_deals)} new deals (total {len(deals)})")
    
    # Отправляем уведомления подписчикам о новых скидках 50%+
    hot_new = [d for d in new_deals if d["discount_pct"] >= 50]
    if not hot_new:
        print(f"[Scheduler] No hot new deals to notify about")
        return
    
    subscribers = get_subscribers()
    if not subscribers:
        print(f"[Scheduler] No subscribers to notify")
        return
    
    from scraper import format_deal_message
    
    # Пробуем отправить через Telegram бота
    try:
        from backend.telegram_bot import send_deal_notifications
        send_deal_notifications(hot_new, subscribers)
    except ImportError:
        print(f"[Scheduler] Telegram bot not available, skipping notifications")
    except Exception as e:
        print(f"[Scheduler] Telegram notification error: {e}")


def start_scheduler():
    """Запускает планировщик задач."""
    # Скрапим сразу при старте
    scheduler.add_job(scrape_and_notify, 'interval', hours=6, id='scrape_deals', next_run_time=None)
    
    # Также каждые 6 часов (в 00:00, 06:00, 12:00, 18:00)
    scheduler.add_job(scrape_and_notify, 'cron', hour='0,6,12,18', id='scrape_deals_cron')
    
    scheduler.start()
    print(f"[Scheduler] Started. Next scrape soon...")


if __name__ == "__main__":
    scrape_and_notify()
