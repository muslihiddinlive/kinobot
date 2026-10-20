"""Foydalanuvchi ismi/username/bio ni asta-sekin yangilaydi (bio bo'yicha qidiruv uchun).

Bot API'da bio faqat getChat(user_id) orqali olinadi, shuning uchun fon vazifasi
har `every` soniyada `batch` ta foydalanuvchini tekshiradi (flood'dan saqlanish uchun
sekin). Tekshirilgan foydalanuvchi 14 kundan keyin yana yangilanadi.
"""
import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

import database as db

log = logging.getLogger(__name__)


async def profile_sync_loop(bot: Bot, every: int = 300, batch: int = 50, delay: float = 0.5):
    await asyncio.sleep(90)
    while True:
        try:
            for uid in await asyncio.to_thread(db.get_users_needing_bio, batch):
                try:
                    ch = await bot.get_chat(uid)
                    name = " ".join(p for p in (ch.first_name, ch.last_name) if p)
                    await asyncio.to_thread(db.set_user_profile, uid, name, ch.username or "", getattr(ch, "bio", None) or "")
                except (TelegramBadRequest, TelegramForbiddenError):
                    await asyncio.to_thread(db.mark_bio_checked, uid)   # chat topilmadi/bloklagan
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after + 1)
                except Exception as e:  # noqa: BLE001
                    log.debug("profile_sync %s: %s", uid, e)
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.error("profile_sync_loop: %s", e)
        await asyncio.sleep(every)
