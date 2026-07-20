from aiogram import Router, F, Bot
from aiogram.types import (Message, CallbackQuery, InlineKeyboardMarkup,
                            InlineKeyboardButton, BufferedInputFile)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
import json
from datetime import datetime
from utils.export import export_users_csv, export_payments_csv, export_movies_csv
from utils.helpers import get_lang

router = Router()

class TargetedState(StatesGroup):
    collecting = State()
    target     = State()

class ScheduledState(StatesGroup):
    collecting = State()
    target     = State()
    time_input = State()

class UserSearchState(StatesGroup):
    query = State()

# ── Broadcast menyu ───────────────────────────────────
@router.callback_query(F.data == "adm_broadcast")
async def broadcast_menu(cb: CallbackQuery):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📣 Hammaga", callback_data="bc_all")],
        [InlineKeyboardButton(text="🎯 Maqsadli reklama", callback_data="bc_targeted")],
        [InlineKeyboardButton(text="📅 Rejalashtirilgan", callback_data="bc_scheduled")],
        [InlineKeyboardButton(text="👤 Muayyan userlarga", callback_data="bc_specific")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")],
    ])
    await cb.message.edit_text("📣 <b>Reklama</b>\n\nTurini tanlang:", reply_markup=markup, parse_mode="HTML")
    await cb.answer()

# ── Maqsad tanlash klaviaturasi ───────────────────────
def target_keyboard(scheduled=False) -> InlineKeyboardMarkup:
    prefix = "scht_" if scheduled else "bct_"
    back = "bc_scheduled" if scheduled else "bc_targeted"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Hammaga", callback_data=f"{prefix}all")],
        [InlineKeyboardButton(text="👑 Faqat VIP", callback_data=f"{prefix}vip"),
         InlineKeyboardButton(text="💎 PRO + VIP", callback_data=f"{prefix}pro")],
        [InlineKeyboardButton(text="🆓 Faqat Free", callback_data=f"{prefix}free")],
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data=f"{prefix}lang_uz"),
         InlineKeyboardButton(text="🇷🇺 Ruscha", callback_data=f"{prefix}lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data=f"{prefix}lang_en"),
         InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data=f"{prefix}lang_tr")],
        [InlineKeyboardButton(text="👨‍💼 Adminlar", callback_data=f"{prefix}admins")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=back)],
    ])

# ── Xabar to'plash ────────────────────────────────────
async def _start_collecting(message_or_cb, state, target_type, is_cb=True):
    await state.update_data(msgs=[], target_type=target_type)

    target_names = {
        "all": "Hammaga", "vip": "VIP", "pro": "PRO+VIP",
        "free": "Free", "admins": "Adminlar",
        "lang_uz": "O'zbekcha", "lang_ru": "Ruscha",
        "lang_en": "English", "lang_tr": "Türkçe",
    }
    name = target_names.get(target_type, target_type)
    text = (
        f"📣 <b>Reklama</b> → <b>{name}</b>\n\n"
        "Xabarlarni yuboring (rasm, video, matn, havola — hammasi).\n"
        "Hammasi bitta xabarga birlashtiriladi.\n\n"
        "Tayyor bo'lgach ✅ tugmasini bosing:"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yuborish!", callback_data="bc_send_now")],
        [InlineKeyboardButton(text="🗑 Tozalash", callback_data="bc_clear")],
        [InlineKeyboardButton(text="❌ Bekor", callback_data="adm_broadcast")],
    ])
    if is_cb:
        await message_or_cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await message_or_cb.answer()
    else:
        await message_or_cb.answer(text, reply_markup=markup, parse_mode="HTML")

# ── Hammaga ───────────────────────────────────────────
@router.callback_query(F.data == "bc_all")
async def bc_all(cb: CallbackQuery, state: FSMContext):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    await state.set_state(TargetedState.collecting)
    await _start_collecting(cb, state, "all")

# ── Maqsadli ─────────────────────────────────────────
@router.callback_query(F.data == "bc_targeted")
async def bc_targeted(cb: CallbackQuery, state: FSMContext):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    await state.set_state(TargetedState.target)
    await cb.message.edit_text("🎯 Kimga yuborilsin?", reply_markup=target_keyboard())
    await cb.answer()

@router.callback_query(F.data.startswith("bct_"), TargetedState.target)
async def bc_target_selected(cb: CallbackQuery, state: FSMContext):
    target = cb.data.replace("bct_","")
    await state.set_state(TargetedState.collecting)
    await _start_collecting(cb, state, target)

# ── Xabar qo'shish ────────────────────────────────────
@router.message(TargetedState.collecting)
async def bc_collect(message: Message, state: FSMContext):
    data = await state.get_data()
    msgs = data.get("msgs", [])
    msgs.append({"chat_id": message.chat.id, "message_id": message.message_id})
    await state.update_data(msgs=msgs)

    target_name = data.get("target_type","all")
    await message.answer(
        f"✅ {len(msgs)} ta xabar qo'shildi.\n"
        f"🎯 Maqsad: {target_name}\n\n"
        "Yana xabar yuboring yoki ✅ Yuborish bosing:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Yuborish!", callback_data="bc_send_now")],
            [InlineKeyboardButton(text="🗑 Tozalash", callback_data="bc_clear")],
            [InlineKeyboardButton(text="❌ Bekor", callback_data="adm_broadcast")],
        ])
    )

@router.callback_query(F.data == "bc_clear")
async def bc_clear(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.update_data(msgs=[])
    await cb.answer("🗑 Xabarlar tozalandi", show_alert=True)

# ── Yuborish ──────────────────────────────────────────
@router.callback_query(F.data == "bc_send_now")
async def bc_send_now(cb: CallbackQuery, state: FSMContext, bot: Bot):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    data = await state.get_data()
    await state.clear()
    msgs = data.get("msgs", [])
    target_type = data.get("target_type", "all")

    if not msgs:
        await cb.answer("❌ Xabar yo'q!", show_alert=True); return

    # Maqsadlarni aniqlash
    if target_type.startswith("specific_"):
        uid = int(target_type.replace("specific_",""))
        users = [uid]
        chats = []
    elif target_type == "admins":
        from config import ADMIN_IDS, SUPERADMIN_ID
        users = list(set(ADMIN_IDS + [SUPERADMIN_ID] + [a["user_id"] for a in db.get_all_admins()]))
        chats = []
    elif target_type.startswith("lang_"):
        users = db.get_users_by_lang(target_type.replace("lang_",""))
        chats = []
    else:
        users = db.get_users_by_plan(target_type)
        chats = db.get_bot_chats(exclude_db=True)

    all_targets = list(users) + [c["chat_id"] for c in chats]
    sent = failed = 0
    status_msg = await cb.message.answer(f"📤 Yuborilmoqda... ({len(all_targets)} ta)")

    for target in all_targets:
        try:
            for m in msgs:
                await bot.copy_message(target, m["chat_id"], m["message_id"])
            sent += 1
        except: failed += 1

    db.audit(cb.from_user.id, "broadcast", target_type, f"{sent} yuborildi")
    await status_msg.edit_text(
        f"✅ Yuborildi: {sent}\n❌ Xato: {failed}\n🎯 Maqsad: {target_type}"
    )
    await cb.answer()

# ── Rejalashtirilgan ──────────────────────────────────
@router.callback_query(F.data == "bc_scheduled")
async def bc_scheduled_menu(cb: CallbackQuery, state: FSMContext):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    await state.set_state(ScheduledState.collecting)
    await state.update_data(msgs=[], target_type="all")
    await cb.message.edit_text(
        "📅 <b>Rejalashtirilgan reklama</b>\n\nXabarlarni yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Keyingi qadam", callback_data="sched_next")],
            [InlineKeyboardButton(text="❌ Bekor", callback_data="adm_broadcast")],
        ]),
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(ScheduledState.collecting)
async def sched_collect(message: Message, state: FSMContext):
    data = await state.get_data()
    msgs = data.get("msgs", [])
    msgs.append({"chat_id": message.chat.id, "message_id": message.message_id})
    await state.update_data(msgs=msgs)
    await message.answer(
        f"✅ {len(msgs)} ta xabar. Yana qo'shing yoki keyingi bosing.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Keyingi", callback_data="sched_next")],
        ])
    )

@router.callback_query(F.data == "sched_next", ScheduledState.collecting)
async def sched_next(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ScheduledState.target)
    await cb.message.edit_text(
        "🎯 Kimga yuborilsin?",
        reply_markup=target_keyboard(scheduled=True)
    )
    await cb.answer()

@router.callback_query(F.data.startswith("scht_"), ScheduledState.target)
async def sched_target(cb: CallbackQuery, state: FSMContext):
    target = cb.data.replace("scht_","")
    await state.update_data(target_type=target)
    await state.set_state(ScheduledState.time_input)
    now = datetime.now()
    await cb.message.edit_text(
        f"⏰ <b>Yuborish vaqtini kiriting</b>\n\n"
        f"Format: <code>YYYY-MM-DD HH:MM</code>\n"
        f"Hozirgi vaqt: <code>{now.strftime('%Y-%m-%d %H:%M')}</code>\n\n"
        f"Misol: <code>{now.strftime('%Y-%m-%d')} 20:00</code>",
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(ScheduledState.time_input)
async def sched_time(message: Message, state: FSMContext):
    try:
        send_at = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
        now = datetime.now()

        # Vaqt o'tgan bo'lsa qayta so'rash
        if send_at <= now:
            await message.answer(
                f"❌ <b>Vaqt o'tib ketgan!</b>\n\n"
                f"Hozir: <code>{now.strftime('%Y-%m-%d %H:%M')}</code>\n"
                f"Siz kiritdingiz: <code>{send_at.strftime('%Y-%m-%d %H:%M')}</code>\n\n"
                f"Kelajakdagi vaqtni kiriting:",
                parse_mode="HTML"
            ); return

        data = await state.get_data()
        await state.clear()

        db.add_scheduled_broadcast(
            message.from_user.id,
            json.dumps(data["msgs"]),
            data.get("target_type","all"),
            send_at.strftime("%Y-%m-%d %H:%M:00")
        )
        db.audit(message.from_user.id, "scheduled_broadcast",
                 data.get("target_type","all"), send_at.strftime("%Y-%m-%d %H:%M"))

        await message.answer(
            f"✅ <b>Rejalashtirildi!</b>\n\n"
            f"📅 Vaqt: <code>{send_at.strftime('%Y-%m-%d %H:%M')}</code>\n"
            f"🎯 Maqsad: {data.get('target_type','all')}\n"
            f"📨 {len(data['msgs'])} ta xabar",
            parse_mode="HTML"
        )

    except ValueError:
        await message.answer(
            f"❌ <b>Noto'g'ri format!</b>\n\n"
            f"To'g'ri format: <code>YYYY-MM-DD HH:MM</code>\n"
            f"Misol: <code>{datetime.now().strftime('%Y-%m-%d')} 20:00</code>",
            parse_mode="HTML"
        )

# ── Muayyan userlarga ─────────────────────────────────
@router.callback_query(F.data == "bc_specific")
async def bc_specific_menu(cb: CallbackQuery, state: FSMContext):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    await state.set_state(UserSearchState.query)
    await cb.message.edit_text(
        "👤 <b>Muayyan userlarga yuborish</b>\n\n"
        "User qidirish uchun isim yoki username yuboring:\n"
        "<i>Masalan: leo → 'leonardo012' topiladi</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_broadcast")]
        ]),
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(UserSearchState.query)
async def user_search(message: Message, state: FSMContext):
    await state.clear()
    query = message.text.strip().lower()

    conn = db.get_conn()
    rows = conn.execute('''
        SELECT user_id, username, full_name FROM users
        WHERE lower(username) LIKE ? OR lower(full_name) LIKE ?
        LIMIT 10
    ''', (f"%{query}%", f"%{query}%")).fetchall()
    conn.close()

    if not rows:
        await message.answer(
            f"❌ <b>{query}</b> bo'yicha hech kim topilmadi.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Qayta qidirish", callback_data="bc_specific")],
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_broadcast")],
            ])
        ); return

    text = f"🔍 <b>'{query}'</b> bo'yicha {len(rows)} ta natija:\n\n"
    buttons = []
    for u in rows:
        name = u["full_name"] or "Nomsiz"
        uname = f"@{u['username']}" if u["username"] else ""

        # Qayerdan topilganini aniqlash
        found_in = []
        if u["username"] and query in u["username"].lower():
            found_in.append(f"username: {uname}")
        if u["full_name"] and query in u["full_name"].lower():
            found_in.append(f"ism: {name}")
        found_str = " | ".join(found_in)

        text += f"👤 <b>{name}</b> {uname}\n🆔 <code>{u['user_id']}</code> | {found_str}\n\n"
        buttons.append([InlineKeyboardButton(
            text=f"📨 {name} ({u['user_id']})",
            callback_data=f"send_specific_{u['user_id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔍 Qayta qidirish", callback_data="bc_specific")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_broadcast")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")

@router.callback_query(F.data.startswith("send_specific_"))
async def send_specific_start(cb: CallbackQuery, state: FSMContext):
    uid = int(cb.data.replace("send_specific_",""))
    user = db.get_user(uid)
    name = user["full_name"] if user else str(uid)
    await state.set_state(TargetedState.collecting)
    await state.update_data(msgs=[], target_type=f"specific_{uid}")
    await cb.message.edit_text(
        f"📨 <b>{name}</b> ga yubormoqchi bo'lgan xabarlarni yuboring:\n\n"
        "Tayyor bo'lgach ✅ bosing:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Yuborish!", callback_data="bc_send_now")],
            [InlineKeyboardButton(text="❌ Bekor", callback_data="adm_broadcast")],
        ]),
        parse_mode="HTML"
    )
    await cb.answer()

# ── Eksport ───────────────────────────────────────────
@router.callback_query(F.data == "adm_export")
async def adm_export_menu(cb: CallbackQuery):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Foydalanuvchilar (CSV)", callback_data="exp_users")],
        [InlineKeyboardButton(text="💰 To'lovlar (CSV)", callback_data="exp_payments")],
        [InlineKeyboardButton(text="🎬 Kinolar (CSV)", callback_data="exp_movies")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")],
    ])
    await cb.message.edit_text(
        "📤 <b>Eksport</b>\n\nNimani yuklab olmoqchisiz?",
        reply_markup=markup, parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data == "exp_users")
async def exp_users(cb: CallbackQuery, bot: Bot):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    await cb.answer("⏳ Tayyorlanmoqda...")
    data = export_users_csv()
    file = BufferedInputFile(data, filename=f"users_{datetime.now().strftime('%Y%m%d')}.csv")
    await bot.send_document(cb.from_user.id, file, caption="👥 Foydalanuvchilar ro'yxati")
    db.audit(cb.from_user.id, "export_users")

@router.callback_query(F.data == "exp_payments")
async def exp_payments(cb: CallbackQuery, bot: Bot):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    await cb.answer("⏳ Tayyorlanmoqda...")
    data = export_payments_csv()
    file = BufferedInputFile(data, filename=f"payments_{datetime.now().strftime('%Y%m%d')}.csv")
    await bot.send_document(cb.from_user.id, file, caption="💰 To'lovlar tarixi")
    db.audit(cb.from_user.id, "export_payments")

@router.callback_query(F.data == "exp_movies")
async def exp_movies(cb: CallbackQuery, bot: Bot):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    await cb.answer("⏳ Tayyorlanmoqda...")
    data = export_movies_csv()
    file = BufferedInputFile(data, filename=f"movies_{datetime.now().strftime('%Y%m%d')}.csv")
    await bot.send_document(cb.from_user.id, file, caption="🎬 Kinolar ro'yxati")
    db.audit(cb.from_user.id, "export_movies")

# ── Dublikat ──────────────────────────────────────────
@router.callback_query(F.data == "adm_duplicates")
async def adm_duplicates(cb: CallbackQuery):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    conn = db.get_conn()
    rows = conn.execute('''
        SELECT title, COUNT(*) as cnt, GROUP_CONCAT(code, ', ') as codes
        FROM movies GROUP BY lower(title) HAVING cnt > 1
    ''').fetchall()
    conn.close()

    if not rows:
        await cb.message.edit_text(
            "✅ Dublikat kino topilmadi!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_movies")]
            ])
        )
        await cb.answer(); return

    text = f"⚠️ <b>Dublikat kinolar ({len(rows)} ta):</b>\n\n"
    for r in rows:
        text += f"• <b>{r['title']}</b>\n  Kodlar: {r['codes']}\n\n"

    await cb.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_movies")]
        ])
    )
    await cb.answer()
