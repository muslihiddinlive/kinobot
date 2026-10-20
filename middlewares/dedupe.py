"""Webhook uchun takroriy update'lardan himoya.

Render uyg'onayotganda yoki javob sekin bo'lganda Telegram bir xil update'ni
qayta yuborishi mumkin. Bu middleware oxirgi update_id'larni eslab qoladi va
takrorlanganini o'tkazib yuboradi (limit/ball ikki marta yechilmasligi uchun).
"""
import logging
from collections import OrderedDict

from aiogram import BaseMiddleware
from aiogram.types import Update

log = logging.getLogger(__name__)


class DedupeMiddleware(BaseMiddleware):
    def __init__(self, size: int = 5000):
        self._seen: OrderedDict[int, None] = OrderedDict()
        self._size = size

    async def __call__(self, handler, event: Update, data):
        uid = event.update_id
        if uid in self._seen:
            log.info("Takroriy update o'tkazib yuborildi: %s", uid)
            return None
        self._seen[uid] = None
        while len(self._seen) > self._size:
            self._seen.popitem(last=False)
        return await handler(event, data)
