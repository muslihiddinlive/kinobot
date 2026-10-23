"""Superadmin vositalari: ruxsatlar muharriri (RBAC), salomatlik paneli, PIN, avto-hisobot sozlamalari."""
import asyncio
import html
import logging
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, Chat, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from config import SUPERADMIN_ID
from middlewares.guard import redispatch
from utils import admin_data as ad, health, perms, pin, reports, tg_backup
from utils.keyboards import grid, page_nav, sbtn
from handlers import audit_view

log = logging.getLogger(__name__)
router = Router()


def B(text, cb):
    return InlineKeyboardButton(text=text, callback_data=cb)


def is_super(uid: int) -> bool:
    return bool(SUPERADMIN_ID) and uid == SUPERADMIN_ID


async def _edit(cb: CallbackQuery, text: str, rows):
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def _try_delete(message: Message):
    try:
        await message.delete()
    except TelegramAPIError:
        pass


# ═════════ Ruxsatlar muharriri (RBAC) ═════════
SHORT = {"stats": "Statistika", "audit": "Audit", "users": "Userlar", "ban": "Ban", "grant": "Reja berish", "message": "Xabar",
         "movies": "Kinolar", "broadcast": "Reklama", "channels": "Kanallar", "promo": "Promo", "payments": "To'lovlar",
         "export": "Eksport", "settings": "Sozlamalar"}


def _preset_name(p: set) -> str:
    for _, (label, s) in perms.PRESETS.items():
        if p == s:
            return label
    return f"✏️ Maxsus ({len(p)}/{len(perms.PERMS)})"


@router.callback_query(F.data == "sa_perm")
async def sa_perm(cb: CallbackQuery):
    conn = db.get_conn()
    admins = conn.execute("SELECT * FROM admins ORDER BY added_at").fetchall()
    conn.close()
    btns = [B(f"{(a['full_name'] or a['username'] or a['user_id'])!s:.12} · {_preset_name(perms.effective_perms(a))[:2]}", f"sa_pa_{a['user_id']}") for a in admins]
    body = ("Adminlardan birini tanlang.\n\n" if admins else "Hozircha qo'shilgan admin yo'q (<b>Adminlar</b> bo'limidan qo'shing).\n\n")
    body += "<i>ADMIN_IDS (env) dagilar to'liq huquqli, bu yerda tahrirlanmaydi.</i>"
    await _edit(cb, "🛡 <b>Admin ruxsatlari</b>\n\n" + body, grid(btns) + [[B("🔙 Orqaga", "sa_menu")]])
    await cb.answer()


async def _perm_card(cb: CallbackQuery, uid: int):
    a = db.get_admin(uid)
    if not a:
        return await cb.answer("Admin topilmadi", show_alert=True)
    cur = perms.effective_perms(a)
    btns = [B(f"{'✅' if k in cur else '❌'} {SHORT[k]}", f"sa_pt_{uid}_{k}") for k in perms.PERMS]
    pre = [B(label, f"sa_pp_{uid}_{key}") for key, (label, _) in perms.PRESETS.items()]
    rows = grid(btns) + [pre, [B("📋 Faoliyati", f"sa_pl_{uid}"), B("🔙 Orqaga", "sa_perm")]]
    await _edit(cb, f"🛡 <b>{html.escape(str(a['full_name'] or a['username'] or uid))}</b>\n"
                    f"Rol: {a['role']} · {_preset_name(cur)}\n\nBosib ruxsatni yoqing/o'chiring:", rows)


@router.callback_query(F.data.regexp(r"^sa_pa_\d+$"))
async def sa_pa(cb: CallbackQuery):
    await _perm_card(cb, int(cb.data.replace("sa_pa_", "")))
    await cb.answer()


@router.callback_query(F.data.regexp(r"^sa_pt_\d+_[a-z]+$"))
async def sa_pt(cb: CallbackQuery):
    _, _, uid, key = cb.data.split("_")
    uid = int(uid)
    a = db.get_admin(uid)
    if not a or key not in perms.PERMS:
        return await cb.answer("Topilmadi", show_alert=True)
    cur = perms.effective_perms(a)
    cur.symmetric_difference_update({key})
    ad.set_admin_perms(uid, cur)
    db.audit(cb.from_user.id, "set_perms", str(uid), f"{key}={'on' if key in cur else 'off'}")
    await _perm_card(cb, uid)
    await cb.answer()


@router.callback_query(F.data.regexp(r"^sa_pp_\d+_[a-z]+$"))
async def sa_pp(cb: CallbackQuery):
    _, _, uid, key = cb.data.split("_")
    if key not in perms.PRESETS or not db.get_admin(int(uid)):
        return await cb.answer("Topilmadi", show_alert=True)
    ad.set_admin_perms(int(uid), perms.PRESETS[key][1])
    db.audit(cb.from_user.id, "set_perms", uid, f"preset={key}")
    await _perm_card(cb, int(uid))
    await cb.answer("Qo'llandi")


@router.callback_query(F.data.regexp(r"^sa_pl_\d+$"))
async def sa_pl(cb: CallbackQuery):
    audit_view.set_filter(cb.from_user.id, admin_id=int(cb.data.replace("sa_pl_", "")))
    await audit_view.show(cb, 0)
    await cb.answer()


# ═════════ Salomatlik paneli ═════════
async def _health_text(bot: Bot) -> str:
    lag = await health.loop_lag_ms()
    dbi = await asyncio.to_thread(health.db_info)
    warns = []
    lines = ["🩺 <b>Salomatlik</b>", "",
             f"⏱ Uptime: <b>{health.uptime_text()}</b> · RAM: <b>{health.rss_mb():.0f} MB</b> · loop: {lag:.0f} ms",
             f"🧩 {health.versions()}"]
    if lag > 200:
        warns.append("event loop sekin (>200 ms): og'ir sinxron kod bor")
    try:
        wh = await bot.get_webhook_info()
        host = (wh.url or "").split("/wh/")[0].replace("https://", "") or "— (polling)"
        lines.append(f"🌐 Webhook: <code>{html.escape(host)}</code> · navbatda: <b>{wh.pending_update_count}</b>")
        if wh.pending_update_count > 50:
            warns.append(f"navbatda {wh.pending_update_count} ta update: bot sekin javob beryapti")
        if wh.last_error_message:
            when = wh.last_error_date.strftime("%d.%m %H:%M") if wh.last_error_date else "?"
            lines.append(f"⚠️ Oxirgi webhook xatosi ({when}): <code>{html.escape(wh.last_error_message[:120])}</code>")
            if wh.last_error_date and (datetime.now(wh.last_error_date.tzinfo) - wh.last_error_date).total_seconds() < 3600:
                warns.append("soʻnggi soatda webhook xatosi bo'lgan")
    except Exception as e:  # noqa: BLE001
        lines.append(f"🌐 Webhook ma'lumoti olinmadi: {html.escape(str(e)[:80])}")
    c = dbi["counts"]
    lines.append(f"🗄 DB: <b>{dbi['size_mb']:.1f} MB</b> (WAL {dbi['wal_mb']:.1f}) · users {c['users']} · kino {c['movies']} · qidiruv log {c['search_logs']}")
    if dbi["size_mb"] > 50:
        warns.append("DB 50 MB dan katta: Telegram backup (gzip 20 MB limit) uchun tashqi DBga o'tishni o'ylang")
    st = tg_backup._state
    lines.append(f"💾 Backup: {st['last_ok'] or 'hali yo`q'} · 📌 {'✅' if st['pinned'] else ('❌' if st['pinned'] is False else '—')}"
                 + (f" · ⚠️ {html.escape(str(st['last_error'])[:60])}" if st["last_error"] else ""))
    if not tg_backup.BACKUP_ENABLED:
        warns.append("DB backup o'chiq (BACKUP_CHAT_ID yo'q)")
    elif st["pinned"] is False:
        warns.append("backup xabari pin qilinmagan: tiklash ishlamaydi")
    tasks = health.tasks_status()
    if tasks:
        lines.append("🔁 Fon vazifalari: " + " ".join(f"{ok}{n.replace('_loop', '')}" for n, ok in tasks))
        if any(ok == "❌" for _, ok in tasks):
            warns.append("fon vazifasi to'xtagan: botni qayta ishga tushiring")
    e24 = ad.count_errors(24)
    lines.append(f"🚨 Xatolar (24 soat): <b>{e24}</b>")
    if e24 >= 20:
        warns.append(f"24 soatda {e24} ta xato")
    if warns:
        lines += ["", "⚠️ <b>Diqqat:</b>"] + [f"• {w}" for w in warns]
    else:
        lines += ["", "✅ Hammasi joyida"]
    return "\n".join(lines)


@router.callback_query(F.data == "sa_health")
async def sa_health(cb: CallbackQuery, bot: Bot):
    await cb.answer("⏳")
    text = await _health_text(bot)
    await _edit(cb, text, [[B("🔄 Yangilash", "sa_health"), B("🚨 Xatolar", "sa_err_0")], [B("🔙 Orqaga", "sa_menu")]])


@router.callback_query(F.data.regexp(r"^sa_err_\d+$"))
async def sa_err(cb: CallbackQuery):
    per = 4
    total = ad.count_errors()
    pages = max(1, (total - 1) // per + 1)
    page = max(0, min(int(cb.data.replace("sa_err_", "")), pages - 1))
    rows = ad.get_errors(per, page * per)
    lines = [f"🚨 <b>Xatolar</b> — {total} ta", ""]
    for r in rows:
        lines.append(f"<code>{r['at'][5:16]}</code> · {html.escape(r['kind'] or '')}"
                     + (f" · upd {r['update_id']}" if r["update_id"] else "") + f"\n<code>{html.escape((r['message'] or '')[:220])}</code>\n")
    if not rows:
        lines.append("Xato yo'q 🎉")
    kb = []
    nav = page_nav(page, pages, "sa_err_")
    if nav: kb.append(nav)
    kb.append([sbtn("🧹 Tozalash", "danger", callback_data="sa_errclr"), B("🔙 Orqaga", "sa_health")])
    await _edit(cb, "\n".join(lines), kb)
    await cb.answer()


@router.callback_query(F.data == "sa_errclr")
async def sa_errclr(cb: CallbackQuery):
    ad.clear_errors()
    db.audit(cb.from_user.id, "errors_clear")
    await _edit(cb, "🧹 Xatolar logi tozalandi.", [[B("🔙 Salomatlik", "sa_health")]])
    await cb.answer()


# ═════════ PIN ═════════
def _pin_text() -> str:
    on = pin.enabled()
    return ("🔐 <b>Superadmin PIN</b>\n\n" + (f"Holat: ✅ yoqilgan · sessiya {pin.ttl_minutes()} daqiqa\n" if on else "Holat: ❌ o'rnatilmagan\n")
            + "\nPIN superadmin panelini va adminlarni boshqarishni himoyalaydi. 4-8 raqam. "
              "5 marta xato kiritilsa 10 daqiqaga bloklanadi.\n"
              "<i>PIN esdan chiqsa: serverda <code>SA_PIN_DISABLE=1</code> o'rnating, kirib, yangisini qo'ying.</i>")


def _pin_kb():
    rows = [[B("🔐 PIN o'rnatish" if not pin.enabled() else "🔁 PINni almashtirish", "sa_pin_set")]]
    if pin.enabled():
        cur = pin.ttl_minutes()
        rows.append([B(("✅ " if cur == m else "") + f"{m} daq", f"sa_pin_ttl_{m}") for m in (5, 15, 60)])
        rows.append([B("🔒 Hozir qulflash", "sa_pin_lock"), sbtn("🚫 O'chirish", "danger", callback_data="sa_pin_off")])
    rows.append([B("🔙 Orqaga", "sa_menu")])
    return rows


@router.callback_query(F.data == "sa_pin")
async def sa_pin(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await _edit(cb, _pin_text(), _pin_kb())
    await cb.answer()


@router.callback_query(F.data.regexp(r"^sa_pin_ttl_\d+$"))
async def sa_pin_ttl(cb: CallbackQuery):
    db.set_setting(pin.TTL_KEY, cb.data.replace("sa_pin_ttl_", ""))
    await _edit(cb, _pin_text(), _pin_kb())
    await cb.answer("Saqlandi")


@router.callback_query(F.data == "sa_pin_lock")
async def sa_pin_lock(cb: CallbackQuery):
    pin.lock(cb.from_user.id)
    await _edit(cb, "🔒 Qulflandi. Keyingi superadmin amalida PIN so'raladi.", [[B("🔙 Admin menyu", "adm_back")]])
    await cb.answer()


@router.callback_query(F.data == "sa_pin_off")
async def sa_pin_off(cb: CallbackQuery):
    pin.disable()
    db.audit(cb.from_user.id, "pin_off")
    await _edit(cb, _pin_text(), _pin_kb())
    await cb.answer("PIN o'chirildi")


@router.callback_query(F.data == "sa_pin_set")
async def sa_pin_set(cb: CallbackQuery, state: FSMContext):
    await state.set_state(pin.PinState.new)
    await state.update_data(pin_msg=cb.message.message_id, pin_chat=cb.message.chat.id)
    await _edit(cb, "🔐 Yangi PIN yuboring (4-8 raqam). Xabar darhol o'chiriladi.", [[B("❌ Bekor", "sa_pin")]])
    await cb.answer()


@router.message(pin.PinState.new)
async def pin_new(message: Message, state: FSMContext, bot: Bot):
    if not is_super(message.from_user.id):
        return
    text = (message.text or "").strip()
    await _try_delete(message)
    d = await state.get_data()
    if not pin.valid_format(text):
        await bot.edit_message_text("❌ PIN 4-8 raqamdan iborat bo'lsin. Qayta yuboring:", chat_id=d["pin_chat"], message_id=d["pin_msg"],
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[B("❌ Bekor", "sa_pin")]]))
        return
    await state.update_data(pin_candidate=text)
    await state.set_state(pin.PinState.confirm_new)
    await bot.edit_message_text("🔐 PINni takrorlang:", chat_id=d["pin_chat"], message_id=d["pin_msg"],
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[B("❌ Bekor", "sa_pin")]]))


@router.message(pin.PinState.confirm_new)
async def pin_confirm(message: Message, state: FSMContext, bot: Bot):
    if not is_super(message.from_user.id):
        return
    text = (message.text or "").strip()
    await _try_delete(message)
    d = await state.get_data()
    if text != d.get("pin_candidate"):
        await state.set_state(pin.PinState.new)
        await bot.edit_message_text("❌ PIN mos kelmadi. Yangi PINni qaytadan yuboring:", chat_id=d["pin_chat"], message_id=d["pin_msg"],
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[B("❌ Bekor", "sa_pin")]]))
        return
    pin.set_pin(text)
    pin.unlock(message.from_user.id)
    db.audit(message.from_user.id, "pin_set")
    await state.clear()
    await bot.edit_message_text(_pin_text(), chat_id=d["pin_chat"], message_id=d["pin_msg"], parse_mode="HTML",
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=_pin_kb()))


@router.message(pin.PinState.waiting)
async def pin_enter(message: Message, state: FSMContext, bot: Bot):
    if not is_super(message.from_user.id):
        return
    text = (message.text or "").strip()
    await _try_delete(message)
    d = await state.get_data()
    res, info = pin.attempt(message.from_user.id, text)
    if res == "ok":
        await state.clear()
        ret = d.get("pin_return") or "sa_menu"
        msg = Message(message_id=d["pin_msg"], date=datetime.now(), chat=Chat(id=d["pin_chat"], type="private"), text="x")
        fake = CallbackQuery(id="pin", from_user=message.from_user, chat_instance="pin", data=ret, message=msg)
        await redispatch(bot, fake, ret)
    elif res == "locked":
        await state.clear()
        await bot.edit_message_text(f"🔒 Juda ko'p xato urinish. {max(1, info // 60)} daqiqadan keyin qayta urinib ko'ring.",
                                    chat_id=d["pin_chat"], message_id=d["pin_msg"],
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[B("🔙 Admin menyu", "adm_back")]]))
    else:
        await bot.edit_message_text(f"🔐 <b>PIN kiriting</b>\n\n❌ Noto'g'ri PIN. Qolgan urinish: {info}", parse_mode="HTML",
                                    chat_id=d["pin_chat"], message_id=d["pin_msg"],
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[B("❌ Bekor", "adm_back")]]))


# ═════════ Avto-hisobot sozlamalari ═════════
def _rep_text() -> str:
    on = lambda k: "✅ yoqilgan" if db.get_setting(k, "0") == "1" else "❌ o'chiq"
    return ("📤 <b>Avto-hisobot (XLSX, diagrammalar bilan)</b>\n\n"
            f"Kunlik (7 kunlik ma'lumot): {on('report_daily')}\n"
            f"Haftalik, dushanba (30 kunlik): {on('report_weekly')}\n"
            f"⏰ Yuborish vaqti: <b>{int(db.get_setting('report_hour', '9') or 9):02d}:00</b> (UTC+{reports.TZ_OFFSET})\n\n"
            "Hisobot sizning shaxsiy chatingizga yuboriladi.")


def _rep_kb():
    cur = int(db.get_setting("report_hour", "9") or 9)
    hours = [B(("✅ " if cur == h else "") + f"{h:02d}:00", f"sa_rep_h_{h}") for h in (6, 8, 9, 12, 18, 21)]
    return [[B(("✅ " if db.get_setting("report_daily", "0") == "1" else "") + "Kunlik", "sa_rep_t_daily"),
             B(("✅ " if db.get_setting("report_weekly", "0") == "1" else "") + "Haftalik", "sa_rep_t_weekly")],
            hours[:3], hours[3:],
            [B("📤 Hozir (7 kun)", "sa_rep_now_7"), B("📤 Hozir (30 kun)", "sa_rep_now_30")],
            [B("🔙 Orqaga", "sa_menu")]]


@router.callback_query(F.data == "sa_report")
async def sa_report(cb: CallbackQuery):
    await _edit(cb, _rep_text(), _rep_kb())
    await cb.answer()


@router.callback_query(F.data.regexp(r"^sa_rep_t_(daily|weekly)$"))
async def sa_rep_toggle(cb: CallbackQuery):
    key = "report_" + cb.data.rsplit("_", 1)[-1]
    new = "0" if db.get_setting(key, "0") == "1" else "1"
    db.set_setting(key, new)
    db.audit(cb.from_user.id, "report_cfg", key, new)
    await _edit(cb, _rep_text(), _rep_kb())
    await cb.answer()


@router.callback_query(F.data.regexp(r"^sa_rep_h_\d+$"))
async def sa_rep_hour(cb: CallbackQuery):
    db.set_setting("report_hour", cb.data.rsplit("_", 1)[-1])
    await _edit(cb, _rep_text(), _rep_kb())
    await cb.answer("Saqlandi")


@router.callback_query(F.data.regexp(r"^sa_rep_now_\d+$"))
async def sa_rep_now(cb: CallbackQuery, bot: Bot):
    days = int(cb.data.rsplit("_", 1)[-1])
    await cb.answer("⏳ Hisobot tayyorlanmoqda...")
    await reports.send_report(bot, days, chat_id=cb.from_user.id)
    db.audit(cb.from_user.id, "report", f"{days}k")
