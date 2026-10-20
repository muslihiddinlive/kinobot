"""Guruhlarda superadmin/adminlarning har bir xabariga bot reaksiya bosadi.

Sozlamalar DB `settings` jadvalida: react_super, react_admin, react_channel
(emoji; bo'sh = o'chiq). Superadmin panelidagi "⚡ Reaksiyalar" bo'limidan
o'zgartiriladi. Eslatma: bot guruhdagi xabarlarni ko'rishi kerak (admin qiling
yoki BotFather'da privacy mode'ni o'chiring); kanalda bot admin bo'lishi shart.
"""
import asyncio
import logging
import time

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, ReactionTypeEmoji

import database as db
from config import SUPERADMIN_ID, ADMIN_IDS

log = logging.getLogger(__name__)
_tasks: set = set()

# Telegram bepul reaksiyalar ro'yxatidan tanlanganlar
EMOJIS = ["👍", "❤", "🔥", "🥰", "👏", "🎉", "🤩", "💯", "⚡", "🏆", "🫡", "🙏"]


class _Cache:
    ttl = 45

    def __init__(self):
        self.t = 0.0
        self.cfg: dict[str, str] = {}
        self.admins: set[int] = set()

    def get(self):
        if time.time() - self.t > self.ttl:
            self.cfg = {k: db.get_setting(k, "") for k in ("react_super", "react_admin", "react_channel")}
            conn = db.get_conn()
            rows = conn.execute("SELECT user_id FROM admins").fetchall()
            conn.close()
            self.admins = {r["user_id"] for r in rows} | set(ADMIN_IDS)
            self.t = time.time()
        return self


cache = _Cache()


def invalidate():
    cache.t = 0.0


async def react(bot: Bot, chat_id: int, message_id: int, emoji: str):
    try:
        await bot.set_message_reaction(chat_id=chat_id, message_id=message_id,
                                       reaction=[ReactionTypeEmoji(emoji=emoji)])
    except Exception as e:  # noqa: BLE001  (reaksiya muhim emas: xatoni yutamiz)
        log.debug("Reaksiya qo'yilmadi (%s): %s", chat_id, e)


def fire(bot: Bot, chat_id: int, message_id: int, emoji: str):
    t = asyncio.create_task(react(bot, chat_id, message_id, emoji))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


class ReactionMiddleware(BaseMiddleware):
    """dp.message.outer_middleware sifatida ulanadi; hech qanday handlerni to'sib qo'ymaydi."""

    async def __call__(self, handler, event: Message, data):
        try:
            if event.chat.type in ("group", "supergroup") and event.from_user and not event.from_user.is_bot:
                c = cache.get()
                uid = event.from_user.id
                if SUPERADMIN_ID and uid == SUPERADMIN_ID:
                    emoji = c.cfg.get("react_super", "")
                elif uid in c.admins:
                    emoji = c.cfg.get("react_admin", "")
                else:
                    emoji = ""
                if emoji:
                    fire(data["bot"], event.chat.id, event.message_id, emoji)
        except Exception as e:  # noqa: BLE001
            log.debug("ReactionMiddleware: %s", e)
        return await handler(event, data)
