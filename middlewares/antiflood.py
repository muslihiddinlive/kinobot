from aiogram import BaseMiddleware
from aiogram.types import Message
from datetime import datetime
from collections import defaultdict

user_times = defaultdict(list)

class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self, rate=3, per=5):
        self.rate = rate  # max xabar soni
        self.per = per    # sekund ichida

    async def __call__(self, handler, event, data):
        from config import SUPERADMIN_ID, ADMIN_IDS
        if isinstance(event, Message):
            uid = event.from_user.id
            # --- FIX: /admin panel orqali qo'shilgan (faqat DB'da saqlanadigan)
            # adminlar bu yerda tekshirilmasdi — ular ham oddiy foydalanuvchi
            # kabi flood-limitga tushib qolardi (masalan bir nechta kino/qismni
            # ketma-ket tez qo'shayotganda). Endi db.is_admin() qo'shildi.
            import database as db
            if uid in ADMIN_IDS or uid == SUPERADMIN_ID or db.is_admin(uid):
                return await handler(event, data)
            now = datetime.now().timestamp()
            times = [t for t in user_times[uid] if now - t < self.per]
            times.append(now)
            user_times[uid] = times
            if len(times) > self.rate:
                await event.answer("⚠️ Juda tez! Biroz kuting.")
                return
        return await handler(event, data)
