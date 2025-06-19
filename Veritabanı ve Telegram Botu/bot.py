import asyncio
from telegram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import os

from db import get_latest_violations

load_dotenv()
bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))

async def send_violations():
    violations = get_latest_violations()
    for row in violations:
        violation_id, name, chat_id, violation_type, timestamp = row

        if chat_id:
            await bot.send_message(
                chat_id=chat_id,
                text=f"🚨 Güvenlik Uyarısı!\n{name} adlı kişide eksik ekipman tespit edildi: {violation_type}\n⏰ {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        admin_chat_id = os.getenv("ADMIN_CHAT_ID")
        if admin_chat_id:
            await bot.send_message(
                chat_id=admin_chat_id,
                text=f"📢 Yönetici Bildirimi:\n{name} adlı işçide eksik ekipman: {violation_type}\nTarih: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        # Notified olarak işaretle
        #from db import mark_as_notified
        #mark_as_notified(violation_id)

import asyncio

async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_violations, 'interval', seconds=10)
    scheduler.start()
    print("✅ Bot aktif! Kontroller başlatıldı...")

    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError, SystemExit):
        print("⛔ Bot kapatılıyor...")
        scheduler.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Tekrarlı KeyboardInterrupt mesajını bastırmak için
        pass

