"""Foydalanuvchi faolligini (DAU/WAU/MAU) hisoblaydi: har foydalanuvchi uchun kuniga bitta DB yozuvi."""
import asyncio
import logging
from datetime import date

from aiogram import BaseMiddleware
from aiogram.types import Update

from utils import admin_data

log = logging.getLogger(__name__)


class ActivityMiddleware(BaseMiddleware):
    def __init__(self):
        self._seen: set = set()
        self._day = ""

    @staticmethod
    def _uid(upd: Update):
        for ev in (upd.message, upd.callback_query, upd.inline_query, upd.my_chat_member):
            u = getattr(ev, "from_user", None)
            if u and not u.is_bot:
                return u.id
        return None

    async def __call__(self, handler, event: Update, data):
        uid = self._uid(event)
        if uid:
            today = str(date.today())
            if self._day != today:
                self._seen.clear()
                self._day = today
            if uid not in self._seen:
                try:
                    res = await asyncio.to_thread(admin_data.touch_active, uid)
                    if res is not None:           # ro'yxatdan o'tmaganlar keyingi safar qayta uriniladi
                        self._seen.add(uid)
                except Exception as e:  # noqa: BLE001
                    log.debug("activity: %s", e)
        return await handler(event, data)
