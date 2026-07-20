from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import database as db
from config import TOPIC_VIP_CLUB, DB_GROUP_ID
from utils.helpers import format_movie_info, get_lang
from utils.keyboards import back_main, plans_keyboard
from locales import t

router = Router()

@router.callback_query(F.data == "vip_club")
async def vip_club_menu(cb: CallbackQuery, bot: Bot):
    user_id = cb.from_user.id
    lang = get_lang(user_id)
    user = db.get_user(user_id)

    # VIP tekshirish
    from datetime import date
    today = str(date.today())
    is_vip = (user and user["plan"] == "vip" and
              user["plan_until"] and user["plan_until"] >= today)
    is_adm = db.is_admin(user_id)

    if not is_vip and not is_adm:
        await cb.message.edit_text(
            "👑 <b>VIP Club</b>\n\n"
            "🔒 Bu bo'lim faqat VIP a'zolar uchun!\n\n"
            "VIP olish uchun:\n"
            "⭐ 100 yulduz → 6 oylik cheksiz kino + VIP Club kirish",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👑 VIP olish — ⭐100", callback_data="buy_vip_3m")],
                [InlineKeyboardButton(text=t("back", lang), callback_data="back_main")],
            ]),
            parse_mode="HTML"
        )
        await cb.answer()
        return

    # VIP kinolar ro'yxati
    movies = db.get_vip_movies(limit=20)
    text = "👑 <b>VIP Club</b>\n\n"

    if not movies:
        text += "Hozircha VIP kino yo'q. Tez orada qo'shiladi!"
        await cb.message.edit_text(text, reply_markup=back_main(lang), parse_mode="HTML")
        await cb.answer()
        return

    text += f"🎬 {len(movies)} ta maxsus kino mavjud:\n\n"
    for m in movies:
        text += f"• <code>{m['code']}</code> — {m['title']}\n"

    buttons = [[InlineKeyboardButton(
        text=f"🎬 {m['title']}", callback_data=f"get_movie_{m['code']}"
    )] for m in movies]
    buttons.append([InlineKeyboardButton(text=t("back", lang), callback_data="back_main")])

    await cb.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await cb.answer()
