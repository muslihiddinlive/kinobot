"""Hashtag (teg) ro'yxati: tugmani bosganda inline qidiruv shu teg bilan ochiladi (@bot #teg)."""
import asyncio
import html

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from locales import t
from utils import search_engine as engine
from utils.helpers import get_lang
from utils.keyboards import grid

router = Router()

_T = {
    "title": {"uz": "🏷 <b>Hashtaglar</b>\n\nTegni bosing: inline qidiruv ochiladi va shu teg bo'yicha kinolar chiqadi.\nYoki istalgan chatda yozing: <code>@{bot} #teg</code>",
              "ru": "🏷 <b>Хэштеги</b>\n\nНажмите на тег: откроется inline-поиск по нему.\nИли напишите в любом чате: <code>@{bot} #тег</code>",
              "en": "🏷 <b>Hashtags</b>\n\nTap a tag to open inline search for it.\nOr type in any chat: <code>@{bot} #tag</code>",
              "tr": "🏷 <b>Etiketler</b>\n\nBir etikete dokunun: inline arama açılır.\nYa da herhangi bir sohbette yazın: <code>@{bot} #etiket</code>"},
    "empty": {"uz": "🏷 Hozircha hashtag yo'q.", "ru": "🏷 Хэштегов пока нет.", "en": "🏷 No hashtags yet.", "tr": "🏷 Henüz etiket yok."},
}
_bot_username = [None]


def _s(key, lang, **kw):
    return _T[key].get(lang, _T[key]["uz"]).format(**kw)


async def tags_view(bot, lang: str):
    """(matn, klaviatura)"""
    if not _bot_username[0]:
        _bot_username[0] = (await bot.get_me()).username
    tags = await asyncio.to_thread(engine.top_tags, 24)
    home = [InlineKeyboardButton(text=t("home", lang), callback_data="back_main")]
    if not tags:
        return _s("empty", lang), InlineKeyboardMarkup(inline_keyboard=[home])
    btns = [InlineKeyboardButton(text=f"{tag} ({n})", switch_inline_query_current_chat=tag) for tag, n in tags]
    return _s("title", lang, bot=html.escape(_bot_username[0])), InlineKeyboardMarkup(inline_keyboard=grid(btns, long_len=16) + [home])


@router.message(Command("tags"))
async def cmd_tags(message: Message, bot):
    text, kb = await tags_view(bot, get_lang(message.from_user.id))
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "tags_browse")
async def tags_browse(cb: CallbackQuery, bot):
    text, kb = await tags_view(bot, get_lang(cb.from_user.id))
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()
