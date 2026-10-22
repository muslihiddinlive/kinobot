"""'Kino qo'shilganda xabar bering': topilmagan so'rov egalariga yangi kino qo'shilganda xabar yuboradi."""
import asyncio
import html
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from utils import search_engine as engine

log = logging.getLogger(__name__)
_tasks: set = set()

_TXT = {
    "uz": "🎉 Siz so'ragan kino qo'shildi!\n\n🎬 <b>{title}</b>",
    "ru": "🎉 Фильм, который вы искали, добавлен!\n\n🎬 <b>{title}</b>",
    "en": "🎉 The movie you were looking for has been added!\n\n🎬 <b>{title}</b>",
    "tr": "🎉 Aradığınız film eklendi!\n\n🎬 <b>{title}</b>",
}
_BTN = {"uz": "▶️ Ko'rish", "ru": "▶️ Смотреть", "en": "▶️ Watch", "tr": "▶️ İzle"}


async def notify_watchers(bot: Bot, code: str) -> int:
    movie = db.get_movie_by_code(code)
    if not movie:
        return 0
    sent = 0
    for w in await asyncio.to_thread(db.get_pending_watches):
        try:
            if not engine.matches_watch(movie, w["query"]):
                continue
            lang = db.get_user_lang(w["user_id"])
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text=_BTN.get(lang, _BTN["uz"]), callback_data=f"get_movie_{movie['code']}")]])
            text = _TXT.get(lang, _TXT["uz"]).format(title=html.escape(str(movie["title"])))
            try:
                await bot.send_message(w["user_id"], text, parse_mode="HTML", reply_markup=kb)
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
                await bot.send_message(w["user_id"], text, parse_mode="HTML", reply_markup=kb)
            sent += 1
        except Exception as e:  # noqa: BLE001  (foydalanuvchi botni bloklagan bo'lishi mumkin)
            log.debug("watch xabari yuborilmadi (%s): %s", w["user_id"], e)
        finally:
            db.mark_watch_notified(w["id"])
        await asyncio.sleep(0.05)
    return sent


def fire_notify(bot: Bot, code: str) -> None:
    """Orqa fonda ishga tushiradi (admin kino qo'shish oqimini kutdirmaydi)."""
    t = asyncio.create_task(notify_watchers(bot, code))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
