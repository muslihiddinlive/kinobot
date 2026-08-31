from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
import database as db
from locales import t

class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        from config import SUPERADMIN_ID, ADMIN_IDS
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id
        # --- FIX: ilgari faqat statik ADMIN_IDS/SUPERADMIN_ID tekshirilardi.
        # /admin panel orqali qo'shilgan (faqat DB'dagi admins jadvalida
        # saqlanadigan) adminlar bu tekshiruvdan o'tolmasdi va texnik
        # rejimda oddiy foydalanuvchi kabi bloklanib qolardi. Endi
        # db.is_admin() orqali (SubscriptionMiddleware bilan bir xil
        # mantiq) DB'dagi adminlar ham hisobga olinadi.
        if user_id and (user_id in ADMIN_IDS or user_id == SUPERADMIN_ID or db.is_admin(user_id)):
            return await handler(event, data)
        if db.get_setting("maintenance_mode","0") == "1":
            lang = db.get_user_lang(user_id) if user_id else "uz"
            msg = db.get_setting("maintenance_text", t("maintenance", lang))
            if isinstance(event, Message): await event.answer(msg)
            elif isinstance(event, CallbackQuery): await event.answer(msg, show_alert=True)
            return
        return await handler(event, data)
