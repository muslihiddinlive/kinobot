from aiogram import Router, Bot
from aiogram.types import (InlineQuery, InlineQueryResultArticle,
                            InputTextMessageContent, InlineQueryResultCachedVideo,
                            InlineQueryResultCachedDocument)
import database as db
from utils.helpers import format_movie_info, get_lang
from config import TOPIC_VIP_CLUB
import hashlib

router = Router()

@router.inline_query()
async def inline_search(query: InlineQuery, bot: Bot):
    text = query.query.strip()
    user_id = query.from_user.id
    lang = get_lang(user_id)
    user = db.get_user(user_id)
    results = []

    if not text:
        # Bo'sh qidiruv — trending kinolar
        movies = db.get_trending_movies(10)
    else:
        movies = db.search_movies(text)

    for movie in movies[:15]:
        # VIP kinoni faqat VIP userlar ko'radi
        if movie["topic_id"] == TOPIC_VIP_CLUB:
            if not user or user["plan"] != "vip":
                continue

        info = format_movie_info(dict(movie), lang, show_tags=False)
        bot_info = await bot.get_me()
        deep = f"https://t.me/{bot_info.username}?start=movie_{movie['code']}"

        # Kino ma'lumoti — article sifatida
        result = InlineQueryResultArticle(
            id=hashlib.md5(movie["code"].encode()).hexdigest(),
            title=f"🎬 {movie['title']}",
            description=f"📥 {movie['downloads']} | 🔢 {movie['code']}",
            input_message_content=InputTextMessageContent(
                message_text=(
                    f"🎬 <b>{movie['title']}</b>\n"
                    f"🔢 Kod: <code>{movie['code']}</code>\n\n"
                    f"▶️ Ko'rish uchun: {deep}"
                ),
                parse_mode="HTML"
            ),
            thumbnail_url=None,
        )
        results.append(result)

    if not results:
        results.append(InlineQueryResultArticle(
            id="not_found",
            title="❌ Topilmadi",
            description="Boshqa nom yoki kod bilan qidiring",
            input_message_content=InputTextMessageContent(
                message_text=f"❌ <b>{text}</b> topilmadi.",
                parse_mode="HTML"
            )
        ))

    await query.answer(results, cache_time=30, is_personal=True)
