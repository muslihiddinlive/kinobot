from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from config import SUPERADMIN_ID, DB_GROUP_ID, TOPIC_ADMIN_LOGS
from utils.keyboards import admin_menu, users_page_keyboard, user_actions_keyboard, channels_keyboard
from utils.helpers import get_plan_until

router = Router()

def is_admin(uid): return db.is_admin(uid)

class AdminState(StatesGroup):
    add_admin_id   = State()
    add_admin_role = State()
    remove_admin   = State()
    user_lookup    = State()
    give_plan_type = State()
    give_limit_amt = State()
    give_pts_amt   = State()
    msg_user_text  = State()
    broadcast_collecting = State()
    notify_msg     = State()
    ch_id          = State()
    ch_name        = State()
    ch_link        = State()
    promo_code     = State()
    promo_type     = State()
    promo_value    = State()
    promo_uses     = State()
    promo_expires  = State()
    del_promo      = State()
    sett_value     = State()

# ── /admin ────────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id): return
    await message.answer("👨‍💼 <b>Admin Panel</b>", reply_markup=admin_menu(), parse_mode="HTML")

@router.callback_query(F.data == "adm_back")
async def adm_back(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return await cb.answer()
    await state.clear()
    await cb.message.edit_text("👨‍💼 <b>Admin Panel</b>", reply_markup=admin_menu(), parse_mode="HTML")
    await cb.answer()

# ── Dashboard/Statistika ──────────────────────────────
@router.callback_query(F.data == "adm_stats")
async def adm_stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return await cb.answer()
    s = db.get_stats()
    text = (
        f"📊 <b>Dashboard</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{s['total']}</b>\n"
        f"🆕 Bugun: <b>{s['new_today']}</b>\n"
        f"💎 PRO: <b>{s['pro']}</b>  |  👑 VIP: <b>{s['vip']}</b>  |  🚫 Ban: <b>{s['banned']}</b>\n"
        f"⭐ Jami yulduz: <b>{s['total_stars']}</b>\n\n"
        f"🎬 Kinolar: <b>{s['total_movies']}</b>\n"
        f"📥 Jami yuklash: <b>{s['total_downloads']}</b>\n\n"
        f"🔝 <b>Top 5 kino:</b>\n"
    )
    for i, m in enumerate(s["top_movies"], 1):
        text += f"  {i}. {m['title']} — {m['downloads']} ta\n"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="adm_stats"),
         InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")]
    ]))
    await cb.answer()

# ── Foydalanuvchilar ──────────────────────────────────
@router.callback_query(F.data == "adm_users")
async def adm_users(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return await cb.answer()
    await _show_users_page(cb.message, 0)
    await cb.answer()

@router.callback_query(F.data.startswith("users_page_"))
async def users_page_cb(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return await cb.answer()
    page = int(cb.data.replace("users_page_",""))
    await _show_users_page(cb.message, page)
    await cb.answer()

async def _show_users_page(message, page):
    total = db.get_users_count()
    users = db.get_users_page(offset=page*10, limit=10)
    text = f"👥 <b>Foydalanuvchilar</b> — jami {total} ta\n\nTanlang:"
    try:
        await message.edit_text(text, reply_markup=users_page_keyboard(users, page, total), parse_mode="HTML")
    except:
        await message.answer(text, reply_markup=users_page_keyboard(users, page, total), parse_mode="HTML")

# User qidirish
@router.callback_query(F.data == "adm_user_lookup")
async def user_lookup_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return await cb.answer()
    await state.set_state(AdminState.user_lookup)
    await cb.message.edit_text(
        "🔍 User ID yoki @username yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_users")]
        ])
    )
    await cb.answer()

@router.message(AdminState.user_lookup)
async def user_lookup(message: Message, state: FSMContext):
    await state.clear()
    q = message.text.strip()
    user = db.get_user_by_username(q) if q.startswith("@") else db.get_user(int(q)) if q.isdigit() else None
    if not user:
        await message.answer("❌ Topilmadi.", reply_markup=admin_menu()); return
    await _show_user_detail(message, user, send=True)

@router.callback_query(F.data.startswith("adm_user_"))
async def user_detail(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return await cb.answer()
    uid = int(cb.data.replace("adm_user_",""))
    user = db.get_user(uid)
    if not user:
        await cb.answer("Topilmadi", show_alert=True); return
    await _show_user_detail(cb.message, user, send=False)
    await cb.answer()

async def _show_user_detail(message, user, send=False):
    from utils.helpers import plan_badge, days_left
    from datetime import date
    today = str(date.today())
    plan = user["plan"]; until = user["plan_until"]
    if until and until < today and plan not in ("free","banned"): plan = "free"
    badge = plan_badge(plan, until)
    days = days_left(until) if until else 0

    text = (
        f"👤 <b>Foydalanuvchi</b>\n\n"
        f"🆔 <code>{user['user_id']}</code>\n"
        f"👋 {user['full_name']}\n"
        f"📱 @{user['username'] or 'yoq'}\n"
        f"🏷 Plan: {badge}"
    )
    if days > 0: text += f" ({days} kun)"
    text += (
        f"\n🎬 Limit: +{user['bought_limit']}\n"
        f"🪙 Ball: {float(user['referral_points']):.1f}\n"
        f"⭐ Yulduz: {user['total_stars']}\n"
        f"🌐 Til: {user['lang'].upper()}\n"
        f"🚫 Ban: {'Ha' if user['is_banned'] else 'Yoq'}\n"
        f"📅 Qo'shilgan: {user['joined_at']}\n"
    )
    markup = user_actions_keyboard(user["user_id"])
    if send:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        await message.edit_text(text, reply_markup=markup, parse_mode="HTML")

# ── Tezkor amallar ────────────────────────────────────
@router.callback_query(F.data.startswith("ban_"))
async def ban_cb(cb: CallbackQuery, bot: Bot):
    if not is_admin(cb.from_user.id): return await cb.answer()
    uid = int(cb.data.replace("ban_",""))
    db.ban_user(uid); db.audit(cb.from_user.id,"ban",str(uid))
    try: await bot.send_message(uid, "🚫 Siz botdan bloklangiz.")
    except: pass
    await cb.answer("✅ Ban qilindi", show_alert=True)
    user = db.get_user(uid)
    await _show_user_detail(cb.message, user)

@router.callback_query(F.data.startswith("unban_"))
async def unban_cb(cb: CallbackQuery, bot: Bot):
    if not is_admin(cb.from_user.id): return await cb.answer()
    uid = int(cb.data.replace("unban_",""))
    db.unban_user(uid); db.audit(cb.from_user.id,"unban",str(uid))
    try: await bot.send_message(uid, "✅ Bloklash olib tashlandi!")
    except: pass
    await cb.answer("✅ Unban qilindi", show_alert=True)
    user = db.get_user(uid)
    await _show_user_detail(cb.message, user)

@router.callback_query(F.data.startswith("give_plan_"))
async def give_plan_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return await cb.answer()
    uid = int(cb.data.replace("give_plan_",""))
    await state.update_data(uid=uid)
    await state.set_state(AdminState.give_plan_type)
    await cb.message.answer("Plan turini tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 PRO 1 oy", callback_data="gp_pro_30"),
             InlineKeyboardButton(text="💎 PRO 3 oy", callback_data="gp_pro_90")],
            [InlineKeyboardButton(text="👑 VIP 3 oy", callback_data="gp_vip_90")],
        ]))
    await cb.answer()

@router.callback_query(F.data.startswith("gp_"), AdminState.give_plan_type)
async def give_plan_exec(cb: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data(); await state.clear()
    parts = cb.data.replace("gp_","").split("_")
    plan, days = parts[0], int(parts[1])
    user = db.get_user(data["uid"])
    until = get_plan_until(user["plan_until"] if user else None, days)
    db.update_user_plan(data["uid"], plan, until, 0)
    db.audit(cb.from_user.id, "give_plan", str(data["uid"]), f"{plan} {until}")
    badge = "💎 PRO" if plan=="pro" else "👑 VIP"
    try: await bot.send_message(data["uid"], f"🎁 {badge} aktivlashtirildi!\nMuddati: {until}")
    except: pass
    await cb.answer(f"✅ {badge} berildi", show_alert=True)
    await cb.message.edit_text("👨‍💼 <b>Admin Panel</b>", reply_markup=admin_menu(), parse_mode="HTML")

@router.callback_query(F.data.startswith("give_limit_"))
async def give_limit_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return await cb.answer()
    uid = int(cb.data.replace("give_limit_",""))
    await state.update_data(uid=uid)
    await state.set_state(AdminState.give_limit_amt)
    await cb.message.answer("Necha limit? (raqam):")
    await cb.answer()

@router.message(AdminState.give_limit_amt)
async def give_limit_exec(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data(); await state.clear()
    try:
        amount = int(message.text.strip())
        db.add_bought_limit(data["uid"], amount, 0)
        db.audit(message.from_user.id, "give_limit", str(data["uid"]), str(amount))
        try: await bot.send_message(data["uid"], f"🎁 +{amount} limit berildi!")
        except: pass
        await message.answer(f"✅ +{amount} limit berildi.", reply_markup=admin_menu())
    except: await message.answer("❌ Raqam kiriting", reply_markup=admin_menu())

@router.callback_query(F.data.startswith("give_points_"))
async def give_points_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return await cb.answer()
    uid = int(cb.data.replace("give_points_",""))
    await state.update_data(uid=uid)
    await state.set_state(AdminState.give_pts_amt)
    await cb.message.answer("Necha ball? (raqam):")
    await cb.answer()

@router.message(AdminState.give_pts_amt)
async def give_points_exec(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data(); await state.clear()
    try:
        pts = float(message.text.strip())
        db.add_referral_points(data["uid"], pts)
        db.audit(message.from_user.id, "give_points", str(data["uid"]), str(pts))
        try: await bot.send_message(data["uid"], f"🪙 +{pts} ball berildi!")
        except: pass
        await message.answer(f"✅ +{pts} ball berildi.", reply_markup=admin_menu())
    except: await message.answer("❌ Raqam kiriting", reply_markup=admin_menu())

@router.callback_query(F.data.startswith("msg_user_"))
async def msg_user_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return await cb.answer()
    uid = int(cb.data.replace("msg_user_",""))
    await state.update_data(uid=uid)
    await state.set_state(AdminState.msg_user_text)
    await cb.message.answer(f"📨 {uid} ga yubormoqchi bo'lgan xabarni yozing:")
    await cb.answer()

@router.message(AdminState.msg_user_text)
async def msg_user_send(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data(); await state.clear()
    try:
        await bot.copy_message(data["uid"], message.chat.id, message.message_id)
        await message.answer("✅ Xabar yuborildi.", reply_markup=admin_menu())
    except Exception as e:
        await message.answer(f"❌ Xato: {e}", reply_markup=admin_menu())

# ── Adminlar ──────────────────────────────────────────
@router.callback_query(F.data == "adm_admins")
async def adm_admins(cb: CallbackQuery):
    if cb.from_user.id != SUPERADMIN_ID: return await cb.answer("❌ Faqat superadmin")
    admins = db.get_all_admins()
    text = "👨‍💼 <b>Adminlar</b>\n\n"
    for a in admins:
        text += f"• {a['full_name']} (@{a['username']}) — {a['role']}\n"
    if not admins: text += "Qo'shimcha admin yo'q.\n"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qo'shish", callback_data="adm_add_admin"),
         InlineKeyboardButton(text="➖ O'chirish", callback_data="adm_remove_admin")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")],
    ]))
    await cb.answer()

@router.callback_query(F.data == "adm_add_admin")
async def add_admin_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != SUPERADMIN_ID: return await cb.answer("❌")
    await state.set_state(AdminState.add_admin_id)
    await cb.message.edit_text("Yangi admin Telegram ID sini yuboring:")
    await cb.answer()

@router.message(AdminState.add_admin_id)
async def add_admin_id(message: Message, state: FSMContext):
    try:
        await state.update_data(uid=int(message.text.strip()))
        await state.set_state(AdminState.add_admin_role)
        await message.answer("Rolini tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Moderator", callback_data="role_moderator")],
            [InlineKeyboardButton(text="👨‍💼 Admin (to'liq)", callback_data="role_admin")],
        ]))
    except: await message.answer("❌ Noto'g'ri ID")

@router.callback_query(F.data.startswith("role_"), AdminState.add_admin_role)
async def add_admin_role(cb: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data(); await state.clear()
    role = cb.data.replace("role_","")
    uid = data["uid"]
    can_ban = can_broadcast = 1 if role=="admin" else 0
    try:
        chat = await bot.get_chat(uid)
        un, fn = chat.username or "", chat.full_name or str(uid)
    except:
        un, fn = "", str(uid)
    db.add_admin(uid, un, fn, role, 1, 1, can_ban, can_broadcast, cb.from_user.id)
    db.audit(cb.from_user.id, "add_admin", str(uid), role)
    try: await bot.send_message(uid, f"✅ Siz {role} sifatida qo'shildingiz!\n/admin")
    except: pass
    await cb.answer("✅ Admin qo'shildi", show_alert=True)
    await cb.message.edit_text("👨‍💼 <b>Admin Panel</b>", reply_markup=admin_menu(), parse_mode="HTML")

@router.callback_query(F.data == "adm_remove_admin")
async def remove_admin_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != SUPERADMIN_ID: return await cb.answer("❌")
    await state.set_state(AdminState.remove_admin)
    await cb.message.edit_text("O'chirmoqchi bo'lgan admin ID sini yuboring:")
    await cb.answer()

@router.message(AdminState.remove_admin)
async def remove_admin_exec(message: Message, state: FSMContext):
    await state.clear()
    try:
        db.remove_admin(int(message.text.strip()))
        db.audit(message.from_user.id, "remove_admin", message.text.strip())
        await message.answer("✅ Admin o'chirildi.", reply_markup=admin_menu())
    except: await message.answer("❌ Noto'g'ri ID", reply_markup=admin_menu())

# ── Kanallar ─────────────────────────────────────────
@router.callback_query(F.data == "adm_channels")
async def adm_channels(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return await cb.answer()
    chs = db.get_required_channels()
    text = "📢 <b>Majburiy kanallar</b>\n\nO'chirish uchun 🗑 bosing:"
    if not chs: text = "📢 <b>Majburiy kanallar</b>\n\nHozircha kanal yo'q."
    await cb.message.edit_text(text, reply_markup=channels_keyboard(chs), parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("del_ch_"))
async def del_ch(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return await cb.answer("❌")
    ch_id = cb.data.replace("del_ch_","")
    db.remove_required_channel(ch_id)
    db.audit(cb.from_user.id, "remove_channel", ch_id)
    chs = db.get_required_channels()
    text = "📢 <b>Majburiy kanallar</b>\n\nO'chirish uchun 🗑 bosing:"
    if not chs: text = "📢 <b>Majburiy kanallar</b>\n\nHozircha kanal yo'q."
    await cb.message.edit_text(text, reply_markup=channels_keyboard(chs), parse_mode="HTML")
    await cb.answer("✅ Kanal o'chirildi", show_alert=True)

@router.callback_query(F.data == "adm_add_ch")
async def add_ch_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return await cb.answer()
    await state.set_state(AdminState.ch_id)
    await cb.message.edit_text(
        "Kanal ID sini yuboring:\n<i>Masalan: @kanalnom yoki -100xxxxxxxxx</i>",
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(AdminState.ch_id)
async def ch_id(message: Message, state: FSMContext):
    await state.update_data(ch_id=message.text.strip())
    await state.set_state(AdminState.ch_name)
    await message.answer("Kanal nomi:")

@router.message(AdminState.ch_name)
async def ch_name(message: Message, state: FSMContext):
    await state.update_data(ch_name=message.text.strip())
    await state.set_state(AdminState.ch_link)
    await message.answer("Kanal invite linki (https://t.me/...):")

@router.message(AdminState.ch_link)
async def ch_link(message: Message, state: FSMContext):
    data = await state.get_data(); await state.clear()
    db.add_required_channel(data["ch_id"], data["ch_name"], message.text.strip())
    db.audit(message.from_user.id, "add_channel", data["ch_id"])
    await message.answer(f"✅ Kanal qo'shildi: {data['ch_name']}", reply_markup=admin_menu())

# ── Promo ─────────────────────────────────────────────
@router.callback_query(F.data == "adm_promos")
async def adm_promos(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return await cb.answer()
    promos = db.list_promos()
    text = "🎁 <b>Promo Kodlar</b>\n\n"
    for p in promos[:10]:
        text += f"• <code>{p['code']}</code> — {p['reward_type']}:{p['reward_value']} | {p['used_count']}/{p['max_uses']}\n"
    if not promos: text += "Hozircha yo'q.\n"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi", callback_data="adm_create_promo"),
         InlineKeyboardButton(text="🗑 O'chirish", callback_data="adm_del_promo")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")],
    ]))
    await cb.answer()

@router.callback_query(F.data == "adm_create_promo")
async def create_promo_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return await cb.answer()
    await state.set_state(AdminState.promo_code)
    await cb.message.edit_text("Promo kod nomi (masalan: YOQOLGAN24):")
    await cb.answer()

@router.message(AdminState.promo_code)
async def promo_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip().upper())
    await state.set_state(AdminState.promo_type)
    await message.answer("Promo turi:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 PRO kun", callback_data="pt_pro_days"),
         InlineKeyboardButton(text="👑 VIP kun", callback_data="pt_vip_days")],
        [InlineKeyboardButton(text="🎟 Limit", callback_data="pt_limit_pack"),
         InlineKeyboardButton(text="🪙 Ball", callback_data="pt_points")],
    ]))

@router.callback_query(F.data.startswith("pt_"), AdminState.promo_type)
async def promo_type(cb: CallbackQuery, state: FSMContext):
    await state.update_data(rtype=cb.data.replace("pt_",""))
    await state.set_state(AdminState.promo_value)
    await cb.message.edit_text("Qiymat (raqam):"); await cb.answer()

@router.message(AdminState.promo_value)
async def promo_value(message: Message, state: FSMContext):
    try:
        await state.update_data(rvalue=int(message.text.strip()))
        await state.set_state(AdminState.promo_uses)
        await message.answer("Max necha marta ishlatiladi?")
    except: await message.answer("❌ Raqam kiriting")

@router.message(AdminState.promo_uses)
async def promo_uses(message: Message, state: FSMContext):
    try:
        await state.update_data(uses=int(message.text.strip()))
        await state.set_state(AdminState.promo_expires)
        await message.answer("Tugash sanasi (YYYY-MM-DD) yoki 'yoq':")
    except: await message.answer("❌ Raqam kiriting")

@router.message(AdminState.promo_expires)
async def promo_expires(message: Message, state: FSMContext):
    exp = None if message.text.strip().lower() in ("yoq","yo'q","-") else message.text.strip()
    data = await state.get_data(); await state.clear()
    db.create_promo(data["code"], data["rtype"], data["rvalue"], data["uses"], exp)
    db.audit(message.from_user.id, "create_promo", data["code"])
    await message.answer(
        f"✅ Promo yaratildi!\nKod: <code>{data['code']}</code>\n"
        f"Tur: {data['rtype']} | Qiymat: {data['rvalue']}\n"
        f"Max: {data['uses']} ta | Tugaydi: {exp or 'cheksiz'}",
        parse_mode="HTML", reply_markup=admin_menu()
    )

@router.callback_query(F.data == "adm_del_promo")
async def del_promo_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return await cb.answer()
    await state.set_state(AdminState.del_promo)
    await cb.message.edit_text("O'chirmoqchi bo'lgan promo kodni yuboring:")
    await cb.answer()

@router.message(AdminState.del_promo)
async def del_promo_exec(message: Message, state: FSMContext):
    await state.clear()
    db.delete_promo(message.text.strip().upper())
    await message.answer("✅ Promo o'chirildi.", reply_markup=admin_menu())

# ── Broadcast ─────────────────────────────────────────
@router.callback_query(F.data == "adm_notify")
async def adm_notify_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return await cb.answer()
    await state.set_state(AdminState.notify_msg)
    await cb.message.edit_text("🔔 Adminlarga yuboriladigan xabar:")
    await cb.answer()

@router.message(AdminState.notify_msg)
async def adm_notify_send(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    from config import ADMIN_IDS
    targets = list(set(ADMIN_IDS + [a["user_id"] for a in db.get_all_admins()]))
    sent = 0
    for aid in targets:
        try: await bot.copy_message(aid, message.chat.id, message.message_id); sent += 1
        except: pass
    await message.answer(f"✅ {sent} ta adminga yuborildi.", reply_markup=admin_menu())

# ── So'rovlar ─────────────────────────────────────────
@router.callback_query(F.data == "adm_requests")
async def adm_requests(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return await cb.answer()
    reqs = db.get_pending_requests(10)
    if not reqs:
        await cb.answer("Hozircha so'rov yo'q!", show_alert=True); return
    text = "📩 <b>Kino so'rovlari</b>\n\n"
    for r in reqs:
        text += f"👤 @{r['username'] or r['user_id']}: {r['request']}\n\n"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")]
    ]))
    await cb.answer()

# ── Fishkalar ─────────────────────────────────────────
@router.callback_query(F.data == "adm_tags")
async def adm_tags(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return await cb.answer()
    tags = db.get_popular_tags(15)
    text = "🏷 <b>Top fishkalar</b>\n\n"
    for tag, count in tags:
        text += f"• {tag} — {count} ta\n"
    if not tags: text += "Hozircha ma'lumot yo'q.\n"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")]
    ]))
    await cb.answer()

# ── Audit ─────────────────────────────────────────────
@router.callback_query(F.data == "adm_audit")
async def adm_audit(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return await cb.answer()
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY done_at DESC LIMIT 20").fetchall()
    conn.close()
    text = "📋 <b>Audit Log</b> (oxirgi 20)\n\n"
    for r in rows:
        text += f"• {r['done_at'][:16]} | {r['action']} | {r['target']}\n"
    if not rows: text += "Hozircha yo'q.\n"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")]
    ]))
    await cb.answer()

# ── Sozlamalar ────────────────────────────────────────
@router.callback_query(F.data == "adm_settings")
async def adm_settings(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return await cb.answer()
    free  = db.get_setting("free_daily_limit","5")
    pro   = db.get_setting("pro_daily_limit","10")
    maint = db.get_setting("maintenance_mode","0")
    await cb.message.edit_text("⚙️ <b>Sozlamalar</b>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🆓 Free limit: {free}/kun", callback_data="sett_free_daily_limit")],
            [InlineKeyboardButton(text=f"💎 PRO limit: {pro}/kun", callback_data="sett_pro_daily_limit")],
            [InlineKeyboardButton(text="💬 Xush kelibsiz xabar", callback_data="sett_welcome_text")],
            [InlineKeyboardButton(
                text="🔧 Texnik rejim: " + ("✅ Yoqilgan" if maint=="1" else "❌ Ochirilgan"),
                callback_data="sett_toggle_maint")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")],
        ]))
    await cb.answer()

@router.callback_query(F.data == "sett_toggle_maint")
async def toggle_maint(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return await cb.answer()
    cur = db.get_setting("maintenance_mode","0")
    db.set_setting("maintenance_mode","0" if cur=="1" else "1")
    status = "o'chirildi" if cur=="1" else "yoqildi"
    await cb.answer(f"Texnik rejim {status}", show_alert=True)
    await adm_settings(cb)

@router.callback_query(F.data.startswith("sett_"))
async def sett_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id): return await cb.answer()
    key = cb.data.replace("sett_","")
    if key == "toggle_maint": return
    await state.update_data(sett_key=key)
    await state.set_state(AdminState.sett_value)
    labels = {"free_daily_limit": "Free kunlik limit", "pro_daily_limit": "PRO kunlik limit",
              "welcome_text": "Xush kelibsiz matni"}
    await cb.message.edit_text(f"Yangi {labels.get(key, key)} qiymatini yuboring:")
    await cb.answer()

@router.message(AdminState.sett_value)
async def sett_value(message: Message, state: FSMContext):
    data = await state.get_data(); await state.clear()
    db.set_setting(data["sett_key"], message.text.strip())
    db.audit(message.from_user.id, "setting", data["sett_key"], message.text.strip())
    await message.answer("✅ Sozlama saqlandi.", reply_markup=admin_menu())
