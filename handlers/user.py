from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date, timedelta
import database as db
from config import REFERRAL_POINTS_FOR_PRO, LEADERBOARD_SIZE, SUPERADMIN_ID, DB_GROUP_ID, TOPIC_ADMIN_LOGS
from utils.helpers import get_plan_until, get_lang
from utils.keyboards import plans_keyboard, back_main
from locales import t

router = Router()

class PromoState(StatesGroup):
    waiting_code = State()

class AdminMsgState(StatesGroup):
    waiting_msg  = State()
    confirm      = State()

# ── Tariflar ──────────────────────────────────────────
@router.callback_query(F.data == "plans")
async def show_plans(cb: CallbackQuery):
    lang = get_lang(cb.from_user.id)
    free = db.get_setting("free_daily_limit", "5")
    plan_texts = {
        "uz": (
            f"{t('plans_title', lang)}\n\n"
            f"{t('plan_free', lang, limit=free)}\n\n"
            f"💎 <b>PRO 1 oy</b> — ⭐ 30 yulduz\n   └ Kuniga 10 ta kino\n\n"
            f"💎 <b>PRO 3 oy</b> — ⭐ 50 yulduz\n   └ Kuniga 10 ta kino\n\n"
            f"👑 <b>VIP 3 oy</b> — ⭐ 100 yulduz\n   └ Cheksiz kino + VIP Club!\n\n"
            f"🎟 <b>Limit +50</b> — ⭐ 50 yulduz\n   └ Ishlatilganda tugaydi"
        ),
        "ru": (
            f"💎 <b>Тарифы</b>\n\n"
            f"🆓 Бесплатно — {free} фильмов/день\n\n"
            f"💎 <b>PRO 1 месяц</b> — ⭐ 30 звёзд\n   └ 10 фильмов/день\n\n"
            f"💎 <b>PRO 3 месяца</b> — ⭐ 50 звёзд\n   └ 10 фильмов/день\n\n"
            f"👑 <b>VIP 3 месяца</b> — ⭐ 100 звёзд\n   └ Безлимит + VIP Club!\n\n"
            f"🎟 <b>Лимит +50</b> — ⭐ 50 звёзд\n   └ Расходуется при просмотре"
        ),
        "en": (
            f"💎 <b>Plans</b>\n\n"
            f"🆓 Free — {free} movies/day\n\n"
            f"💎 <b>PRO 1 month</b> — ⭐ 30 stars\n   └ 10 movies/day\n\n"
            f"💎 <b>PRO 3 months</b> — ⭐ 50 stars\n   └ 10 movies/day\n\n"
            f"👑 <b>VIP 3 months</b> — ⭐ 100 stars\n   └ Unlimited + VIP Club!\n\n"
            f"🎟 <b>Limit +50</b> — ⭐ 50 stars\n   └ Used when watching"
        ),
        "tr": (
            f"💎 <b>Planlar</b>\n\n"
            f"🆓 Ücretsiz — {free} film/gün\n\n"
            f"💎 <b>PRO 1 ay</b> — ⭐ 30 yıldız\n   └ 10 film/gün\n\n"
            f"💎 <b>PRO 3 ay</b> — ⭐ 50 yıldız\n   └ 10 film/gün\n\n"
            f"👑 <b>VIP 3 ay</b> — ⭐ 100 yıldız\n   └ Sınırsız + VIP Club!\n\n"
            f"🎟 <b>Limit +50</b> — ⭐ 50 yıldız\n   └ İzlerken azalır"
        ),
    }
    text = plan_texts.get(lang, plan_texts["uz"])
    await cb.message.edit_text(text, reply_markup=plans_keyboard(lang), parse_mode="HTML")
    await cb.answer()

# ── Promo kod ─────────────────────────────────────────
@router.callback_query(F.data == "promo")
async def promo_start(cb: CallbackQuery, state: FSMContext):
    lang = get_lang(cb.from_user.id)
    await state.set_state(PromoState.waiting_code)
    await cb.message.edit_text(
        t("promo_prompt", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("cancel", lang), callback_data="back_main")]
        ])
    )
    await cb.answer()

@router.message(PromoState.waiting_code)
async def process_promo(message: Message, state: FSMContext):
    await state.clear()
    code = message.text.strip().upper()
    user_id = message.from_user.id
    lang = get_lang(user_id)
    today = str(date.today())

    promo = db.get_promo(code)
    if not promo:
        await message.answer(t("promo_not_found", lang), reply_markup=back_main(lang)); return
    if promo["expires_at"] and promo["expires_at"] < today:
        await message.answer(t("promo_expired", lang), reply_markup=back_main(lang)); return
    if promo["used_count"] >= promo["max_uses"]:
        await message.answer(t("promo_used_up", lang), reply_markup=back_main(lang)); return
    if db.has_used_promo(user_id, code):
        await message.answer(t("promo_already_used", lang), reply_markup=back_main(lang)); return

    user = db.get_user(user_id)
    rtype = promo["reward_type"]
    rval  = promo["reward_value"]

    if rtype == "pro_days":
        until = get_plan_until(user["plan_until"], rval)
        db.update_user_plan(user_id, "pro", until, 0)
        db.use_promo(user_id, code)
        await message.answer(t("promo_success_pro", lang, days=rval, until=until), reply_markup=back_main(lang))
    elif rtype == "vip_days":
        until = get_plan_until(user["plan_until"], rval)
        db.update_user_plan(user_id, "vip", until, 0)
        db.use_promo(user_id, code)
        await message.answer(t("promo_success_vip", lang, days=rval, until=until), reply_markup=back_main(lang))
    elif rtype == "limit_pack":
        db.add_bought_limit(user_id, rval, 0)
        db.use_promo(user_id, code)
        await message.answer(t("promo_success_limit", lang, amount=rval), reply_markup=back_main(lang))
    elif rtype == "points":
        db.add_referral_points(user_id, rval)
        db.use_promo(user_id, code)
        await message.answer(t("promo_success_points", lang, points=rval), reply_markup=back_main(lang))

# ── Referal ───────────────────────────────────────────
@router.callback_query(F.data == "referral")
async def show_referral(cb: CallbackQuery):
    user_id = cb.from_user.id
    lang = get_lang(user_id)
    user = db.get_user(user_id)
    points = user["referral_points"] if user else 0
    needed = int(db.get_setting("referral_points_for_pro", str(REFERRAL_POINTS_FOR_PRO)))
    bot_info = await cb.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    text = (
        f"{t('referral_title', lang)}\n\n"
        f"{t('referral_link', lang)}\n<code>{link}</code>\n\n"
        f"{t('referral_points', lang, points=points)}\n"
        f"{t('referral_needed', lang, needed=needed)}\n\n"
        f"{t('referral_info', lang)}"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("referral_redeem", lang, needed=needed), callback_data="redeem_points")],
        [InlineKeyboardButton(text="📨 Adminga xabar", callback_data="send_admin_msg")],
        [InlineKeyboardButton(text=t("back", lang), callback_data="back_main")],
    ])
    await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data == "redeem_points")
async def redeem_points(cb: CallbackQuery):
    user_id = cb.from_user.id
    lang = get_lang(user_id)
    user = db.get_user(user_id)
    needed = int(db.get_setting("referral_points_for_pro", str(REFERRAL_POINTS_FOR_PRO)))
    points = float(user["referral_points"]) if user else 0

    if points < needed:
        await cb.answer(t("referral_not_enough", lang, points=int(points), needed=needed), show_alert=True); return

    until = get_plan_until(user["plan_until"], 30)
    db.redeem_referral_points(user_id, needed, until)
    await cb.message.edit_text(t("referral_success", lang, until=until), reply_markup=back_main(lang))
    await cb.answer()

# ── Adminga xabar (referal uchun) ─────────────────────
@router.callback_query(F.data == "send_admin_msg")
async def send_admin_msg_start(cb: CallbackQuery, state: FSMContext):
    lang = get_lang(cb.from_user.id)
    user = db.get_user(cb.from_user.id)
    today = str(date.today())
    points = float(user["referral_points"]) if user else 0

    # Bugun yuborgan-yubormagan tekshirish
    if user["last_admin_msg"] == today:
        # Kunlik limit oshdi — 0.5 ball kerak
        if points < 0.5:
            await cb.answer(t("send_to_admin_no_points", lang, points=points), show_alert=True); return
        await state.set_state(AdminMsgState.confirm)
        await cb.message.edit_text(
            t("send_to_admin_limit", lang, points=points),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t("confirm", lang), callback_data="admin_msg_pay")],
                [InlineKeyboardButton(text=t("cancel", lang), callback_data="back_main")],
            ])
        )
    else:
        await state.set_state(AdminMsgState.waiting_msg)
        await cb.message.edit_text(
            t("send_to_admin_prompt", lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t("cancel", lang), callback_data="back_main")]
            ])
        )
    await cb.answer()

@router.callback_query(F.data == "admin_msg_pay", AdminMsgState.confirm)
async def admin_msg_pay_confirm(cb: CallbackQuery, state: FSMContext):
    lang = get_lang(cb.from_user.id)
    await state.set_state(AdminMsgState.waiting_msg)
    await state.update_data(pay=True)
    await cb.message.edit_text(
        t("send_to_admin_prompt", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("cancel", lang), callback_data="back_main")]
        ])
    )
    await cb.answer()

@router.message(AdminMsgState.waiting_msg)
async def admin_msg_send(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    user_id = message.from_user.id
    lang = get_lang(user_id)
    today = str(date.today())

    # 0.5 ball kesish (agar kerak bo'lsa)
    if data.get("pay"):
        db.deduct_referral_points(user_id, 0.5)

    # Adminlarga yuborish (ma'qullash buttonlari bilan)
    approve_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("admin_approve_referral","uz"), callback_data=f"ref_approve_{user_id}"),
         InlineKeyboardButton(text=t("admin_decline_referral","uz"), callback_data=f"ref_decline_{user_id}")],
    ])

    sent = False
    # Superadminga
    try:
        await bot.send_message(SUPERADMIN_ID,
            f"📨 Foydalanuvchi xabari:\n"
            f"👤 {message.from_user.full_name} (@{message.from_user.username or "yoq"})\n"
            f"ID: {user_id}\n\n"
            f"💬 {message.text}",
            reply_markup=approve_markup)
        sent = True
    except: pass

    # Barcha adminlarga
    for adm in db.get_all_admins():
        if adm["can_broadcast"]:
            try:
                await bot.send_message(adm["user_id"],
                    f"📨 Foydalanuvchi xabari:\n👤 {message.from_user.full_name}\nID: {user_id}\n\n💬 {message.text}",
                    reply_markup=approve_markup)
            except: pass

    # Oxirgi yuborgan sanani yangilash
    db.update_last_admin_msg(user_id, today)
    await message.answer(t("send_to_admin_sent", lang), reply_markup=back_main(lang))

# ── Admin ma'qullash/rad etish ────────────────────────
@router.callback_query(F.data.startswith("ref_approve_"))
async def ref_approve(cb: CallbackQuery, bot: Bot):
    if not db.is_admin(cb.from_user.id):
        await cb.answer("❌ Ruxsat yo'q"); return
    uid = int(cb.data.replace("ref_approve_", ""))
    lang = get_lang(uid)
    db.add_referral_points(uid, 1)
    db.audit(cb.from_user.id, "ref_approve", str(uid))
    try: await bot.send_message(uid, t("referral_approved", lang))
    except: pass
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer("✅ Referal berildi", show_alert=True)

@router.callback_query(F.data.startswith("ref_decline_"))
async def ref_decline(cb: CallbackQuery, bot: Bot):
    if not db.is_admin(cb.from_user.id):
        await cb.answer("❌ Ruxsat yo'q"); return
    uid = int(cb.data.replace("ref_decline_", ""))
    lang = get_lang(uid)
    try: await bot.send_message(uid, t("referral_declined", lang))
    except: pass
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer("❌ Rad etildi", show_alert=True)

# ── Leaderboard ───────────────────────────────────────
@router.callback_query(F.data == "leaderboard")
async def show_leaderboard(cb: CallbackQuery):
    lang = get_lang(cb.from_user.id)
    rows = db.get_leaderboard(LEADERBOARD_SIZE)
    if not rows:
        await cb.answer("Hali ma'lumot yo'q!", show_alert=True); return
    medals = ["🥇","🥈","🥉"] + ["🏅"]*10
    text = f"{t('leaderboard_title', lang)}\n\n"
    for i, row in enumerate(rows):
        name = row["full_name"] or row["username"] or "Foydalanuvchi"
        badge = "👑 VIP" if row["plan"]=="vip" else ("💎 PRO" if row["plan"]=="pro" else "🆓")
        text += f"{medals[i]} {name} — {badge}\n"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_main(lang))
    await cb.answer()
