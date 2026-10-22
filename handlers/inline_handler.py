import asyncio
import hashlib
import html
from datetime import date

from aiogram import Router, Bot
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

import database as db
from utils import search_engine as engine
from utils.helpers import get_lang
from config import TOPIC_VIP_CLUB, GENRES

router = Router()

INLINE_PAGE = 20
_BOT_USERNAME = None


async def _bot_username(bot: Bot) -> str:
    """Bot username'i bir marta olinadi (avval har natija uchun alohida get_me() chaqirilardi)."""
    global _BOT_USERNAME
    if not _BOT_USERNAME:
        _BOT_USERNAME = (await bot.get_me()).username
    return _BOT_USERNAME


def _genre_name(topic_id) -> str:
    g = GENRES.get(topic_id)
    if isinstance(g, (tuple, list)):
        return str(g[0])
    return str(g) if g else ""


@router.inline_query()
async def inline_search(query: InlineQuery, bot: Bot):
    text = query.query.strip()
    user_id = query.from_user.id
    user = db.get_user(user_id)
    today = str(date.today())
    offset = int(query.offset) if (query.offset or "").isdigit() else 0
    next_offset = ""

    if not text:
        # Bo'sh qidiruv — trending kinolar
        movies = db.get_trending_movies(INLINE_PAGE)
    else:
        # Lotin/kirill, apostrof, ko'p so'zli, xatoga chidamli qidiruv + sahifalash (offset)
        res = await asyncio.to_thread(engine.search, text, INLINE_PAGE, offset)
        movies = res.rows
        if offset + INLINE_PAGE < res.total:
            next_offset = str(offset + INLINE_PAGE)

    uname = await _bot_username(bot)
    results = []
    for movie in movies:
        # VIP kinoni faqat MUDDATI TUGAMAGAN VIP userlar ko'radi (plan_until ham tekshiriladi).
        if movie["topic_id"] == TOPIC_VIP_CLUB:
            is_vip = (user and user["plan"] == "vip" and
                      user["plan_until"] and user["plan_until"] >= today)
            if not is_vip and not db.is_admin(user_id):
                continue

        title = html.escape(str(movie["title"]))
        code = html.escape(str(movie["code"]))
        deep = f"https://t.me/{uname}?start=movie_{movie['code']}"
        meta = [str(movie["year"])] if movie["year"] else []
        genre = _genre_name(movie["topic_id"])
        if genre:
            meta.append(genre)
        if movie["user_rating"]:
            meta.append(f"⭐{movie['user_rating']}")
        meta.append(f"📥 {movie['downloads']}")

        results.append(InlineQueryResultArticle(
            id=hashlib.md5(str(movie["code"]).encode()).hexdigest(),
            title=f"🎬 {movie['title']}",
            description=" • ".join(meta),
            input_message_content=InputTextMessageContent(
                message_text=(
                    f"🎬 <b>{title}</b>\n"
                    f"🔢 Kod: <code>{code}</code>\n\n"
                    f"▶️ Ko'rish uchun: {deep}"
                ),
                parse_mode="HTML"
            ),
        ))

    if not results and not offset:
        results.append(InlineQueryResultArticle(
            id="not_found",
            title="❌ Topilmadi",
            description="Boshqa nom yoki kod bilan qidiring",
            input_message_content=InputTextMessageContent(
                message_text=f"❌ <b>{html.escape(text)}</b> topilmadi.",
                parse_mode="HTML"
            )
        ))

    await query.answer(results, cache_time=30, is_personal=True, next_offset=next_offset)
