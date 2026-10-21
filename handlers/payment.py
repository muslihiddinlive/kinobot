from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import database as db
from config import (PRICE_PRO_1M, PRICE_PRO_3M, PRICE_VIP_3M,
                    PRICE_LIMIT_PACK, DB_GROUP_ID, TOPIC_PAYMENTS)
from utils.helpers import get_plan_until, get_lang
from utils.keyboards import plans_keyboard, back_main
from utils.keyboards import sbtn
from locales import t

router = Router()

# MUHIM: Stars orqali avtomatik to'lov (send_invoice) OLIB TASHLANDI.
# Endi har bir "sotib olish" bosilganda — admin guruhiga so'rov boradi,
# admin "✅ Tasdiqlash" bosgandan keyingina tarif/limit foydalanuvchiga
# beriladi. Bu — to'lov avtomatik hisobga tushmasligi xavfidan saqlaydi.

PLAN_TITLES = {
    "pro_1m":     ("💎 PRO — 1 oy",   PRICE_PRO_1M),
    "pro_3m":     ("💎 PRO — 3 oy",   PRICE_PRO_3M),
    "vip_3m":     ("👑 VIP — 3 oy",   PRICE_VIP_3M),
    "limit_pack": ("➕ +50 limit",    PRICE_LIMIT_PACK),
}

async def _request_purchase(cb: CallbackQuery, payload: str):
    lang = get_lang(cb.from_user.id)
    title, stars = PLAN_TITLES[payload]
    await cb.answer()
    await cb.message.answer(
        f"📨 <b>So'rovingiz qabul qilindi!</b>\n\n"
        f"{title} — ⭐ {stars}\n\n"
        f"Admin tez orada ko'rib chiqib, tasdiqlaydi. Iltimos, kuting.",
        parse_mode="HTML", reply_markup=back_main(lang)
    )
    try:
        await cb.bot.send_message(
            DB_GROUP_ID,
            f"🛒 <b>Yangi so'rov!</b>\n"
            f"👤 {cb.from_user.full_name} (@{cb.from_user.username or '—'})\n"
            f"🆔 <code>{cb.from_user.id}</code>\n"
            f"📦 {title} — ⭐ {stars}",
            message_thread_id=TOPIC_PAYMENTS,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                sbtn("✅ Tasdiqlash", "success", callback_data=f"approve_pay:{cb.from_user.id}:{payload}"),
                sbtn("❌ Rad etish", "danger", callback_data=f"decline_pay:{cb.from_user.id}:{payload}"),
            ]])
        )
    except Exception:
        pass

@router.callback_query(F.data == "buy_pro_1m")
async def buy_pro_1m(cb: CallbackQuery):
    await _request_purchase(cb, "pro_1m")

@router.callback_query(F.data == "buy_pro_3m")
async def buy_pro_3m(cb: CallbackQuery):
    await _request_purchase(cb, "pro_3m")

@router.callback_query(F.data == "buy_vip_3m")
async def buy_vip_3m(cb: CallbackQuery):
    await _request_purchase(cb, "vip_3m")

# Eski buy_vip_6m ham ishlashi uchun
@router.callback_query(F.data == "buy_vip_6m")
async def buy_vip_6m(cb: CallbackQuery):
    await buy_vip_3m(cb)

@router.callback_query(F.data == "buy_limit_pack")
async def buy_limit_pack(cb: CallbackQuery):
    await _request_purchase(cb, "limit_pack")


def _grant(user_id: int, payload: str, stars: int):
    """Tarif yoki limitni foydalanuvchiga beradi. (xabar_matni, lang) qaytaradi."""
    lang = get_lang(user_id)
    user = db.get_user(user_id)
    plan_map = {
        "pro_1m": ("pro", 30, 1),
        "pro_3m": ("pro", 90, 3),
        "vip_3m": ("vip", 90, 3),
    }
    if payload in plan_map:
        plan, days, months = plan_map[payload]
        until = get_plan_until(user["plan_until"] if user else None, days)
        db.update_user_plan(user_id, plan, until, stars)
        if plan == "vip":
            return t("payment_success_vip", lang, until=until), lang
        return t("payment_success_pro", lang, months=months, until=until), lang
    elif payload == "limit_pack":
        db.add_bought_limit(user_id, 50, stars)
        return t("payment_success_limit", lang), lang
    return "✅ So'rovingiz tasdiqlandi.", lang


@router.callback_query(F.data.startswith("approve_pay:"))
async def approve_pay(cb: CallbackQuery, bot: Bot):
    if not db.is_admin(cb.from_user.id):
        return await cb.answer("⛔ Sizda ruxsat yo'q", show_alert=True)

    # --- FIX (kritik): ikki marta bosilishdan himoya ---
    # Ilgari bu yerda faqat matn (edit_text) o'zgartirilardi, tugmalar
    # (reply_markup) esa xabarda qolib ketardi. Natijada admin ikki marta
    # bossa (yoki tarmoq sekinligida ikki marta yuborilsa) _grant()
    # ikki marta chaqirilib, foydalanuvchiga tarif/limit IKKI MARTA
    # berilishi mumkin edi. Endi: 1) allaqachon tasdiqlangan/rad etilgan
    # xabar matnida belgi bo'lsa — darhol to'xtaymiz; 2) muvaffaqiyatli
    # ishlov berilgach, tugmalarni butunlay olib tashlaymiz.
    current_text = cb.message.html_text or ""
    if "✅ <b>Tasdiqlandi</b>" in current_text or "❌ <b>Rad etildi</b>" in current_text:
        return await cb.answer("Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)

    _, user_id_s, payload = cb.data.split(":", 2)
    user_id = int(user_id_s)
    title, stars = PLAN_TITLES.get(payload, (payload, 0))
    msg, lang = _grant(user_id, payload, stars)
    try:
        await bot.send_message(user_id, msg, parse_mode="HTML")
    except Exception:
        pass
    try:
        await bot.send_message(
            DB_GROUP_ID,
            f"💰 To'lov tasdiqlandi!\n👤 <code>{user_id}</code>\n📦 {title} | ⭐ {stars}\n"
            f"✅ Tasdiqladi: @{cb.from_user.username or cb.from_user.id}",
            message_thread_id=TOPIC_PAYMENTS, parse_mode="HTML"
        )
    except Exception:
        pass
    try:
        await cb.message.edit_text(
            current_text + f"\n\n✅ <b>Tasdiqlandi</b> (@{cb.from_user.username or cb.from_user.id})",
            parse_mode="HTML",
            reply_markup=None,  # --- FIX: tugmalarni olib tashlaymiz, qayta bosilmasin ---
        )
    except Exception:
        pass
    await cb.answer("✅ Tasdiqlandi")


@router.callback_query(F.data.startswith("decline_pay:"))
async def decline_pay(cb: CallbackQuery, bot: Bot):
    if not db.is_admin(cb.from_user.id):
        return await cb.answer("⛔ Sizda ruxsat yo'q", show_alert=True)

    # --- FIX (kritik): xuddi shu ikki-marta-bosish himoyasi ---
    current_text = cb.message.html_text or ""
    if "✅ <b>Tasdiqlandi</b>" in current_text or "❌ <b>Rad etildi</b>" in current_text:
        return await cb.answer("Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)

    _, user_id_s, payload = cb.data.split(":", 2)
    user_id = int(user_id_s)
    try:
        await bot.send_message(
            user_id, "❌ So'rovingiz rad etildi. Savollar bo'lsa, admin bilan bog'laning."
        )
    except Exception:
        pass
    try:
        await cb.message.edit_text(
            current_text + f"\n\n❌ <b>Rad etildi</b> (@{cb.from_user.username or cb.from_user.id})",
            parse_mode="HTML",
            reply_markup=None,  # --- FIX: tugmalarni olib tashlaymiz ---
        )
    except Exception:
        pass
    await cb.answer("❌ Rad etildi")
