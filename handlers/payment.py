from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
import database as db
from config import (PRICE_PRO_1M, PRICE_PRO_3M, PRICE_VIP_3M,
                    PRICE_LIMIT_PACK, DB_GROUP_ID, TOPIC_PAYMENTS)
from utils.helpers import get_plan_until, get_lang
from utils.keyboards import plans_keyboard, back_main
from locales import t

router = Router()

async def send_invoice(bot, chat_id, title, description, payload, stars):
    await bot.send_invoice(
        chat_id=chat_id, title=title, description=description,
        payload=payload, currency="XTR",
        prices=[LabeledPrice(label=title, amount=stars)],
        provider_token="",
    )

@router.callback_query(F.data == "buy_pro_1m")
async def buy_pro_1m(cb: CallbackQuery):
    lang = get_lang(cb.from_user.id)
    await cb.answer()
    await send_invoice(cb.bot, cb.from_user.id,
        t("buy_pro_1m", lang), "30 kun, kuniga 10 ta kino.", "pro_1m", PRICE_PRO_1M)

@router.callback_query(F.data == "buy_pro_3m")
async def buy_pro_3m(cb: CallbackQuery):
    lang = get_lang(cb.from_user.id)
    await cb.answer()
    await send_invoice(cb.bot, cb.from_user.id,
        t("buy_pro_3m", lang), "90 kun, kuniga 10 ta kino.", "pro_3m", PRICE_PRO_3M)

@router.callback_query(F.data == "buy_vip_3m")
async def buy_vip_3m(cb: CallbackQuery):
    lang = get_lang(cb.from_user.id)
    await cb.answer()
    await send_invoice(cb.bot, cb.from_user.id,
        t("buy_vip_3m", lang), "90 kun, CHEKSIZ kino + VIP Club!", "vip_3m", PRICE_VIP_3M)

# Eski buy_vip_6m ham ishlashi uchun
@router.callback_query(F.data == "buy_vip_6m")
async def buy_vip_6m(cb: CallbackQuery):
    await buy_vip_3m(cb)

@router.callback_query(F.data == "buy_limit_pack")
async def buy_limit_pack(cb: CallbackQuery):
    lang = get_lang(cb.from_user.id)
    await cb.answer()
    await send_invoice(cb.bot, cb.from_user.id,
        t("buy_limit", lang),
        "+50 limit. Ishlatilganda tugaydi, kunlik limitga ta'sir qilmaydi.",
        "limit_pack", PRICE_LIMIT_PACK)

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment(message: Message, bot: Bot):
    user_id  = message.from_user.id
    payload  = message.successful_payment.invoice_payload
    stars    = message.successful_payment.total_amount
    lang     = get_lang(user_id)
    user     = db.get_user(user_id)

    plan_map = {
        "pro_1m": ("pro", 30,  1),
        "pro_3m": ("pro", 90,  3),
        "vip_3m": ("vip", 90,  3),
    }

    if payload in plan_map:
        plan, days, months = plan_map[payload]
        until = get_plan_until(user["plan_until"] if user else None, days)
        db.update_user_plan(user_id, plan, until, stars)
        if plan == "vip":
            await message.answer(
                t("payment_success_vip", lang, until=until), parse_mode="HTML")
        else:
            await message.answer(
                t("payment_success_pro", lang, months=months, until=until), parse_mode="HTML")

    elif payload == "limit_pack":
        db.add_bought_limit(user_id, 50, stars)
        await message.answer(t("payment_success_limit", lang), parse_mode="HTML")

    # Log
    try:
        await bot.send_message(
            DB_GROUP_ID,
            f"💰 Yangi to'lov!\n"
            f"👤 {message.from_user.full_name} (@{message.from_user.username})\n"
            f"📦 {payload} | ⭐ {stars}",
            message_thread_id=TOPIC_PAYMENTS
        )
    except: pass
