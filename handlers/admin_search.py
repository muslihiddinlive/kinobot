"""Admin: harfli (inline klaviatura) foydalanuvchi qidiruvi.

Admin harf tugmalarini bosadi, bot har bosishda xabarni tahrirlab, mos
foydalanuvchilarni real vaqtda tavsiya qiladi (ism, familiya, @username, bio, ID).
Qidiruv matni FSM ma'lumotida saqlanadi (callback_data'ga sig'masligi mumkin).
"""
import asyncio
import html

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from utils import admin_nav
from utils import search_engine as engine
from utils.keyboards import letter_search_keyboard, grid, user_button, page_nav, PAGE_SIZE

router = Router()
MAX_QUERY = 32
SUGGEST = 6


def _is_admin(uid: int) -> bool:
    return db.is_admin(uid)


async def _render(cb: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    q, layout = d.get("lq", ""), d.get("lq_lay", "lat")
    users = db.search_users(q, limit=SUGGEST) if q else []
    total = db.count_search_users(q) if q else 0
    admin_nav.set_back(cb.from_user.id, "lq_view")       # kartadan "Orqaga" shu ekranga qaytadi
    if q:
        info = f"Topildi: <b>{total}</b> ta" + ("" if total <= SUGGEST else f" (dastlabki {SUGGEST} ta ko'rsatilmoqda)")
    else:
        info = "Harflarni bosing: ism, familiya, @username yoki bio bo'yicha izlanadi."
    text = f"🔎 <b>Qidiruv:</b> <code>{html.escape(q) or '…'}</code>\n{info}"
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=letter_search_keyboard(layout, users, total))
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            raise


@router.callback_query(F.data == "lq_start")
async def lq_start(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id): return await cb.answer()
    await state.clear()
    await state.update_data(lq="", lq_lay="lat")
    await _render(cb, state)
    await cb.answer()


@router.callback_query(F.data == "lq_view")
async def lq_view(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id): return await cb.answer()
    await _render(cb, state)
    await cb.answer()


@router.callback_query(F.data.startswith("lq_l_"))
async def lq_layout(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id): return await cb.answer()
    lay = cb.data.replace("lq_l_", "")
    await state.update_data(lq_lay=lay if lay in ("lat", "cyr", "num") else "lat")
    await _render(cb, state)
    await cb.answer()


@router.callback_query(F.data.startswith("lq_k_"))
async def lq_key(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id): return await cb.answer()
    key = cb.data.replace("lq_k_", "", 1)
    d = await state.get_data()
    q = d.get("lq", "")
    if key == "BS": q = q[:-1]
    elif key == "CL": q = ""
    elif key == "SP": q = (q + " ") if q and not q.endswith(" ") else q
    elif len(q) < MAX_QUERY: q += key
    await state.update_data(lq=q)
    await _render(cb, state)
    await cb.answer()


# ── To'liq natijalar (sahifalab) ──
@router.callback_query(F.data.regexp(r"^lqr_\d+$"))
async def lq_results(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb.from_user.id): return await cb.answer()
    d = await state.get_data()
    q = d.get("lq", "")
    total = db.count_search_users(q) if q else 0
    pages = max(1, (total - 1) // PAGE_SIZE + 1)
    page = max(0, min(int(cb.data.replace("lqr_", "")), pages - 1))
    users = db.search_users(q, limit=PAGE_SIZE, offset=page * PAGE_SIZE) if q else []
    admin_nav.set_back(cb.from_user.id, f"lqr_{page}")
    rows = grid([user_button(u) for u in users])
    nav = page_nav(page, pages, "lqr_")
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔤 Klaviatura", callback_data="lq_view"),
                 InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_users")])
    text = f"🔎 <b>{html.escape(q) or '…'}</b>: {total} ta natija"
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            raise
    await cb.answer()


# ── Topilmagan so'rovlar (foydalanuvchilar nima qidirib, topa olmayapti) ──
@router.callback_query(F.data == "adm_missing")
async def adm_missing(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id): return await cb.answer()
    rows = await asyncio.to_thread(engine.missing_queries, 30, 20)
    watching = len(db.get_pending_watches())
    if rows:
        lines = [f"{i}. <b>{html.escape(q)}</b> — {n}× ({u} user)" for i, (q, n, u) in enumerate(rows, 1)]
        body = "\n".join(lines) + "\n\n<i>Shu kinolarni qo'shsangiz, 🔔 bosgan foydalanuvchilarga avtomatik xabar boradi.</i>"
    else:
        body = "Oxirgi 30 kunda topilmagan so'rov yo'q 🎉"
    text = f"🔎 <b>Topilmagan so'rovlar</b> (30 kun)\n\n{body}\n\n🔔 Kutayotganlar: {watching} ta"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Yangilash", callback_data="adm_missing"),
                                                InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")]])
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            raise
    await cb.answer()
