"""Superadmin paneli: chatlar, bot nomidan yozish, faollik reytingi, reaksiyalar, DB backup.

Faqat config.SUPERADMIN_ID uchun. Callback prefiksi: `sa_`.
"""
import html
import logging

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from config import SUPERADMIN_ID
from middlewares import reactions as rx
from utils import tg_backup
from utils.keyboards import grid, page_nav, PAGE_SIZE, sbtn

log = logging.getLogger(__name__)
router = Router()


def is_super(uid: int) -> bool:
    return bool(SUPERADMIN_ID) and uid == SUPERADMIN_ID


class SaState(StatesGroup):
    say_text = State()


def B(text, cb):
    return InlineKeyboardButton(text=text, callback_data=cb)


async def _deny(cb: CallbackQuery) -> bool:
    if not is_super(cb.from_user.id):
        await cb.answer("Faqat superadmin uchun", show_alert=True)
        return True
    return False


async def _edit(cb: CallbackQuery, text: str, rows):
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            raise


# ── Bosh menyu ──
@router.callback_query(F.data == "sa_menu")
async def sa_menu(cb: CallbackQuery, state: FSMContext):
    if await _deny(cb): return
    await state.clear()
    from utils import pin
    rows = grid([B("📡 Chatlar", "sa_chats_0"), B("🏆 Reyting", "sa_rank_7"),
                 B("🛡 Ruxsatlar", "sa_perm"), B("🩺 Salomatlik", "sa_health"),
                 B("⚡ Reaksiyalar", "sa_react"), B("💾 Backup", "sa_backup"),
                 B("📤 Hisobot", "sa_report"), B("🔐 PIN", "sa_pin"),
                 B("📤 Eksport", "adm_export"), B("📋 Audit", "adm_audit")])
    rows.append([B("🔙 Orqaga", "adm_back")])
    warn = "" if pin.enabled() else "\n\n⚠️ <i>PIN o'rnatilmagan: 🔐 PIN bo'limidan o'rnatish tavsiya etiladi.</i>"
    await _edit(cb, "👑 <b>Superadmin panel</b>" + warn, rows)
    await cb.answer()


# ── Bot a'zo bo'lgan kanal/guruhlar ──
def _chat_icon(c) -> str:
    base = "📢" if c["chat_type"] == "channel" else "👥"
    return base + ("👑" if (c["status"] or "") in ("administrator", "creator") else "")


@router.callback_query(F.data.regexp(r"^sa_chats_\d+$"))
async def sa_chats(cb: CallbackQuery):
    if await _deny(cb): return
    total = db.count_bot_chats()
    pages = max(1, (total - 1) // PAGE_SIZE + 1)
    page = max(0, min(int(cb.data.replace("sa_chats_", "")), pages - 1))
    chats = db.get_bot_chats_page(offset=page * PAGE_SIZE, limit=PAGE_SIZE)
    if not chats:
        await _edit(cb, "📡 <b>Chatlar</b>\n\nHozircha yo'q. Botni guruh yoki kanalga qo'shsangiz, shu yerda avtomatik paydo bo'ladi.",
                    [[B("🔙 Orqaga", "sa_menu")]])
        return await cb.answer()
    btns = []
    for c in chats:
        title = c["title"] or str(c["chat_id"])
        title = title if len(title) <= 20 else title[:19] + "…"
        btns.append(B(f"{_chat_icon(c)} {title}", f"sa_chat_{c['chat_id']}_{page}"))
    rows = grid(btns)
    nav = page_nav(page, pages, "sa_chats_")
    if nav: rows.append(nav)
    rows.append([B("🔙 Orqaga", "sa_menu")])
    await _edit(cb, f"📡 <b>Bot a'zo bo'lgan chatlar</b> — {total} ta\n👑 = bot admin, 📢 = kanal, 👥 = guruh", rows)
    await cb.answer()


@router.callback_query(F.data.regexp(r"^sa_chat_-?\d+_\d+$"))
async def sa_chat(cb: CallbackQuery, bot: Bot):
    if await _deny(cb): return
    _, _, cid, page = cb.data.split("_")
    cid, page = int(cid), int(page)
    c = db.get_bot_chat(cid)
    if not c:
        return await cb.answer("Chat topilmadi", show_alert=True)
    lines = [f"{_chat_icon(c)} <b>{html.escape(c['title'] or '—')}</b>", f"🆔 <code>{cid}</code>",
             f"Turi: {c['chat_type']} | Holat: {c['status'] or 'member'}"]
    try:
        ch = await bot.get_chat(cid)
        if ch.username: lines.append(f"🔗 @{ch.username}")
        lines.append(f"👥 A'zolar: {await bot.get_chat_member_count(cid)}")
        me = await bot.get_chat_member(cid, bot.id)
        if me.status == "administrator":
            rights = [n for n, ok in (("xabar yozish", getattr(me, "can_post_messages", True)),
                                      ("o'chirish", me.can_delete_messages), ("pin", getattr(me, "can_pin_messages", False)),
                                      ("ban", me.can_restrict_members)) if ok]
            lines.append("🛡 Huquqlar: " + (", ".join(rights) or "—"))
    except TelegramAPIError as e:
        lines.append(f"⚠️ Jonli ma'lumot olinmadi: {html.escape(str(e)[:80])}")
    rows = [[B("✍️ Bot nomidan yozish", f"sa_say_{cid}_{page}")],
            [B("🚪 Chatdan chiqish", f"sa_leave_{cid}_{page}")],
            [B("🔙 Orqaga", f"sa_chats_{page}")]]
    await _edit(cb, "\n".join(lines), rows)
    await cb.answer()


# ── Bot nomidan yozish ──
@router.callback_query(F.data.regexp(r"^sa_say_-?\d+_\d+$"))
async def sa_say(cb: CallbackQuery, state: FSMContext):
    if await _deny(cb): return
    _, _, cid, page = cb.data.split("_")
    await state.set_state(SaState.say_text)
    await state.update_data(sa_target=int(cid), sa_page=int(page))
    await _edit(cb, "✍️ Shu chatga <b>bot nomidan</b> yuboriladigan xabarni yuboring (matn, rasm, video, fayl...).",
                [[B("❌ Bekor qilish", f"sa_chat_{cid}_{page}")]])
    await cb.answer()


@router.message(SaState.say_text)
async def sa_say_msg(message: Message, state: FSMContext):
    if not is_super(message.from_user.id): return
    d = await state.get_data()
    c = db.get_bot_chat(d["sa_target"])
    await state.update_data(sa_src=message.message_id)
    await state.set_state(None)
    await message.reply(f"Shu xabar <b>{html.escape((c['title'] if c else '') or d['sa_target'].__str__())}</b> ga bot nomidan yuborilsinmi?",
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            sbtn("✅ Yuborish", "success", callback_data="sa_sayY"), B("❌ Bekor", f"sa_chat_{d['sa_target']}_{d['sa_page']}")]]))


@router.callback_query(F.data == "sa_sayY")
async def sa_say_send(cb: CallbackQuery, state: FSMContext, bot: Bot):
    if await _deny(cb): return
    d = await state.get_data()
    if "sa_target" not in d or "sa_src" not in d:
        return await cb.answer("Eskirgan so'rov", show_alert=True)
    try:
        await bot.copy_message(chat_id=d["sa_target"], from_chat_id=cb.message.chat.id, message_id=d["sa_src"])
    except TelegramAPIError as e:
        await cb.answer(f"❌ {str(e)[:150]}", show_alert=True)
        return
    db.audit(cb.from_user.id, "say_as_bot", str(d["sa_target"]))
    page = d.get("sa_page", 0)
    await state.clear()
    await _edit(cb, "✅ Yuborildi.", [[B("✍️ Yana yozish", f"sa_say_{d['sa_target']}_{page}"),
                                      B("🔙 Chat", f"sa_chat_{d['sa_target']}_{page}")]])
    await cb.answer()


# ── Chatdan chiqish ──
@router.callback_query(F.data.regexp(r"^sa_leave_-?\d+_\d+$"))
async def sa_leave(cb: CallbackQuery):
    if await _deny(cb): return
    _, _, cid, page = cb.data.split("_")
    await _edit(cb, "🚪 Bot shu chatdan chiqsinmi?",
                [[sbtn("✅ Ha, chiqish", "danger", callback_data=f"sa_leaveY_{cid}"), B("❌ Yo'q", f"sa_chat_{cid}_{page}")]])
    await cb.answer()


@router.callback_query(F.data.regexp(r"^sa_leaveY_-?\d+$"))
async def sa_leave_do(cb: CallbackQuery, bot: Bot):
    if await _deny(cb): return
    cid = int(cb.data.replace("sa_leaveY_", ""))
    c = db.get_bot_chat(cid)
    try:
        await bot.leave_chat(cid)
    except TelegramAPIError as e:
        return await cb.answer(f"❌ {str(e)[:150]}", show_alert=True)
    if c: db.save_bot_chat(cid, c["chat_type"], c["title"] or "", "left")
    db.audit(cb.from_user.id, "leave_chat", str(cid))
    await _edit(cb, "🚪 Chatdan chiqildi.", [[B("🔙 Chatlar", "sa_chats_0")]])
    await cb.answer()


# ── Faollik reytingi ──
@router.callback_query(F.data.regexp(r"^sa_rank_\d+$"))
async def sa_rank(cb: CallbackQuery):
    if await _deny(cb): return
    days = int(cb.data.replace("sa_rank_", ""))
    top = db.get_activity_ranking(days, 10)
    medals = ["🥇", "🥈", "🥉"] + [f"{i}." for i in range(4, 11)]
    title = {7: "oxirgi 7 kun", 30: "oxirgi 30 kun", 0: "butun vaqt"}.get(days, f"{days} kun")
    if top:
        lines = [f"{medals[i]} <b>{html.escape(u['full_name'] or u['username'] or str(u['user_id']))}</b> — "
                 f"🔎{u['searches']} ⭐{u['rated']} ❤️{u['favs']} = <b>{u['searches'] + u['rated'] * 3 + u['favs'] * 2}</b>"
                 for i, u in enumerate(top)]
        body = "\n".join(lines) + "\n\n<i>Ball: qidiruv ×1, baho ×3, sevimli ×2</i>"
    else:
        body = "Bu davrda faollik yo'q."
    mark = lambda d, t: f"✅ {t}" if d == days else t
    await _edit(cb, f"🏆 <b>Faollik reytingi</b> ({title})\n\n{body}",
                [[B(mark(7, "7 kun"), "sa_rank_7"), B(mark(30, "30 kun"), "sa_rank_30"), B(mark(0, "Hammasi"), "sa_rank_0")],
                 [B("🔙 Orqaga", "sa_menu")]])
    await cb.answer()


# ── Reaksiyalar ──
_TARGETS = {"super": ("👑 Superadmin xabari", "react_super"),
            "admin": ("🛡 Adminlar xabari", "react_admin"),
            "channel": ("📢 Kanal postlari", "react_channel")}


@router.callback_query(F.data == "sa_react")
async def sa_react(cb: CallbackQuery):
    if await _deny(cb): return
    btns = [B(f"{label}: {db.get_setting(key, '') or '🚫'}", f"sa_rt_{t}") for t, (label, key) in _TARGETS.items()]
    rows = grid(btns)
    rows.append([B("🔙 Orqaga", "sa_menu")])
    await _edit(cb, "⚡ <b>Avto-reaksiyalar</b>\n\nBot guruhdagi superadmin/adminlarning har bir xabariga, "
                    "kanaldagi har bir postga tanlangan emoji bosadi.\n\n"
                    "<i>Guruhda bot xabarlarni ko'rishi kerak (admin qiling yoki privacy mode'ni o'chiring), "
                    "kanalda bot admin bo'lishi shart.</i>", rows)
    await cb.answer()


@router.callback_query(F.data.regexp(r"^sa_rt_(super|admin|channel)$"))
async def sa_react_pick(cb: CallbackQuery):
    if await _deny(cb): return
    t = cb.data.replace("sa_rt_", "")
    emojis = [B(e, f"sa_re_{t}_{i}") for i, e in enumerate(rx.EMOJIS)]
    rows = [emojis[i:i + 4] for i in range(0, len(emojis), 4)]       # faqat emoji: qisqa, 4 tadan
    rows.append([B("🚫 O'chirish", f"sa_re_{t}_x")])
    rows.append([B("🔙 Orqaga", "sa_react")])
    await _edit(cb, f"{_TARGETS[t][0]}: qaysi emoji bosilsin?", rows)
    await cb.answer()


@router.callback_query(F.data.regexp(r"^sa_re_(super|admin|channel)_(\d+|x)$"))
async def sa_react_set(cb: CallbackQuery):
    if await _deny(cb): return
    _, _, t, idx = cb.data.split("_")
    emoji = "" if idx == "x" else rx.EMOJIS[int(idx)]
    db.set_setting(_TARGETS[t][1], emoji)
    rx.invalidate()
    db.audit(cb.from_user.id, "set_reaction", f"{t}={emoji or 'off'}")
    await sa_react(cb)


@router.channel_post()
async def on_channel_post(message: Message, bot: Bot):
    emoji = rx.cache.get().cfg.get("react_channel", "")
    if emoji:
        await rx.react(bot, message.chat.id, message.message_id, emoji)


# ── DB backup ──
@router.callback_query(F.data == "sa_backup")
async def sa_backup(cb: CallbackQuery):
    if await _deny(cb): return
    await _edit(cb, tg_backup.status_text(),
                [[sbtn("💾 Hozir backup", "primary", callback_data="sa_backup_now"), B("🔄 Yangilash", "sa_backup")],
                 [B("🔙 Orqaga", "sa_menu")]])
    await cb.answer()


@router.callback_query(F.data == "sa_backup_now")
async def sa_backup_now(cb: CallbackQuery, bot: Bot):
    if await _deny(cb): return
    await cb.answer("⏳ Backup olinmoqda...")
    r = await tg_backup.backup_now(bot, force=True)
    db.audit(cb.from_user.id, "backup_now", "ok" if r.get("ok") else str(r.get("error"))[:80])
    note = "✅ Backup yuborildi." if r.get("ok") else f"❌ Xato: {html.escape(str(r.get('error'))[:150])}"
    await _edit(cb, note + "\n\n" + tg_backup.status_text(),
                [[B("💾 Yana backup", "sa_backup_now"), B("🔄 Yangilash", "sa_backup")],
                 [B("🔙 Orqaga", "sa_menu")]])
