"""Audit 2.0: sahifalash, filtr (admin/amal), admin ismi bilan."""
import html

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from utils import admin_data as ad
from utils.keyboards import grid, page_nav

router = Router()
PAGE = 8
_F: dict = {}        # admin_id -> {"a": admin_id|None, "t": action|None}
_ACTS: dict = {}     # admin_id -> [action, ...] (au_t_<idx> uchun)


def set_filter(viewer_id: int, admin_id=None, action=None) -> None:
    _F[viewer_id] = {"a": admin_id, "t": action}


def _ts(done_at: str) -> str:
    # 2026-10-22 14:32:10 -> 22.10 14:32
    try:
        return f"{done_at[8:10]}.{done_at[5:7]} {done_at[11:16]}"
    except Exception:  # noqa: BLE001
        return done_at or ""


async def _edit(cb, text, rows):
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def show(cb: CallbackQuery, page: int = 0):
    f = _F.get(cb.from_user.id, {})
    a, t = f.get("a"), f.get("t")
    total = ad.audit_count(a, t)
    pages = max(1, (total - 1) // PAGE + 1)
    page = max(0, min(page, pages - 1))
    rows = ad.audit_page(page * PAGE, PAGE, a, t)
    lines = [f"📋 <b>Audit</b> — {total} ta yozuv"]
    if a or t:
        lines.append("🔎 Filtr: " + " · ".join(x for x in ((f"👤 {html.escape(ad.person_name(a))}" if a else ""), (f"🏷 {html.escape(t)}" if t else "")) if x))
    lines.append("")
    for r in rows:
        tgt = html.escape(str(r["target"] or ""))[:18]
        det = html.escape(str(r["detail"] or ""))[:24]
        lines.append(f"<code>{_ts(r['done_at'])}</code> · <b>{html.escape(ad.person_name(r['admin_id']))}</b> · {html.escape(r['action'])}"
                     + (f" · {tgt}" if tgt else "") + (f" · {det}" if det else ""))
    if not rows:
        lines.append("Yozuv yo'q.")
    kb = []
    nav = page_nav(page, pages, "au_p_")
    if nav: kb.append(nav)
    kb.append([InlineKeyboardButton(text="🔎 Filtr", callback_data="au_f")] +
              ([InlineKeyboardButton(text="♻️ Tozalash", callback_data="au_c")] if (a or t) else []))
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")])
    await _edit(cb, "\n".join(lines), kb)


@router.callback_query(F.data == "adm_audit")
async def adm_audit(cb: CallbackQuery):
    _F.pop(cb.from_user.id, None)
    await show(cb, 0)
    await cb.answer()


@router.callback_query(F.data.regexp(r"^au_p_\d+$"))
async def au_page(cb: CallbackQuery):
    await show(cb, int(cb.data.replace("au_p_", "")))
    await cb.answer()


@router.callback_query(F.data == "au_c")
async def au_clear(cb: CallbackQuery):
    _F.pop(cb.from_user.id, None)
    await show(cb, 0)
    await cb.answer()


@router.callback_query(F.data == "au_f")
async def au_filter(cb: CallbackQuery):
    await _edit(cb, "🔎 <b>Audit filtri</b>", [
        [InlineKeyboardButton(text="👤 Admin bo'yicha", callback_data="au_a"),
         InlineKeyboardButton(text="🏷 Amal bo'yicha", callback_data="au_t")],
        [InlineKeyboardButton(text="♻️ Tozalash", callback_data="au_c")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="au_p_0")]])
    await cb.answer()


@router.callback_query(F.data == "au_a")
async def au_admins(cb: CallbackQuery):
    btns = [InlineKeyboardButton(text=f"{ad.person_name(r['admin_id'])[:14]} ({r['c']})", callback_data=f"au_a_{r['admin_id']}")
            for r in ad.audit_admins()]
    rows = grid(btns) + [[InlineKeyboardButton(text="🔙 Orqaga", callback_data="au_f")]]
    await _edit(cb, "👤 Qaysi admin?", rows)
    await cb.answer()


@router.callback_query(F.data.regexp(r"^au_a_-?\d+$"))
async def au_pick_admin(cb: CallbackQuery):
    f = _F.setdefault(cb.from_user.id, {"a": None, "t": None})
    f["a"] = int(cb.data.replace("au_a_", ""))
    await show(cb, 0)
    await cb.answer()


@router.callback_query(F.data == "au_t")
async def au_actions(cb: CallbackQuery):
    acts = ad.audit_actions()
    _ACTS[cb.from_user.id] = [r["action"] for r in acts]
    btns = [InlineKeyboardButton(text=f"{r['action'][:14]} ({r['c']})", callback_data=f"au_t_{i}") for i, r in enumerate(acts)]
    rows = grid(btns) + [[InlineKeyboardButton(text="🔙 Orqaga", callback_data="au_f")]]
    await _edit(cb, "🏷 Qaysi amal?", rows)
    await cb.answer()


@router.callback_query(F.data.regexp(r"^au_t_\d+$"))
async def au_pick_action(cb: CallbackQuery):
    acts = _ACTS.get(cb.from_user.id, [])
    i = int(cb.data.replace("au_t_", ""))
    if i >= len(acts):
        return await cb.answer("Eskirgan, qayta oching", show_alert=True)
    f = _F.setdefault(cb.from_user.id, {"a": None, "t": None})
    f["t"] = acts[i]
    await show(cb, 0)
    await cb.answer()
