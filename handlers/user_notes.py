"""Foydalanuvchiga eslatma va teglar (admin ichki yozuvlari) + teg bo'yicha ro'yxat."""
import html

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from config import SUPERADMIN_ID
from utils import admin_data as ad, admin_nav
from utils.keyboards import grid, page_nav, user_button, PAGE_SIZE

router = Router()
_TAGLIST: dict = {}      # admin_id -> [teglar] (tugma indekslari uchun)
_FILTER: dict = {}       # admin_id -> [teglar] (ro'yxat filtri)


class NoteState(StatesGroup):
    waiting = State()


class TagState(StatesGroup):
    waiting = State()


def B(text, cb):
    return InlineKeyboardButton(text=text, callback_data=cb)


async def _edit(cb: CallbackQuery, text: str, rows):
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            raise


def _ts(s: str) -> str:
    return f"{s[8:10]}.{s[5:7]} {s[11:16]}" if s and len(s) >= 16 else (s or "")


# ── Eslatmalar ──
async def _show_notes(cb: CallbackQuery, uid: int):
    u = db.get_user(uid)
    notes = ad.get_notes(uid, 6)
    name = html.escape((u["full_name"] if u else "") or str(uid))
    lines = [f"📝 <b>Eslatmalar</b> — {name}", ""]
    for n in notes:
        lines.append(f"<b>#{n['id']}</b> <code>{_ts(n['created_at'])}</code> · {html.escape(ad.person_name(n['admin_id']))}\n{html.escape(n['note'])}\n")
    if not notes:
        lines.append("Hozircha eslatma yo'q.")
    dels = [B(f"🗑 #{n['id']}", f"un_del_{n['id']}") for n in notes]
    rows = [[B("➕ Eslatma qo'shish", f"un_add_{uid}")]] + grid(dels, per_row=3, long_len=12) + [[B("🔙 Orqaga", f"adm_user_{uid}")]]
    await _edit(cb, "\n".join(lines), rows)


@router.callback_query(F.data.regexp(r"^un_list_\d+$"))
async def un_list(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_notes(cb, int(cb.data.replace("un_list_", "")))
    await cb.answer()


@router.callback_query(F.data.regexp(r"^un_add_\d+$"))
async def un_add(cb: CallbackQuery, state: FSMContext):
    uid = int(cb.data.replace("un_add_", ""))
    await state.set_state(NoteState.waiting)
    await state.update_data(note_uid=uid)
    await _edit(cb, "📝 Eslatma matnini yuboring (500 belgigacha). Faqat adminlar ko'radi.", [[B("❌ Bekor", f"un_list_{uid}")]])
    await cb.answer()


@router.message(NoteState.waiting)
async def un_save(message: Message, state: FSMContext):
    d = await state.get_data()
    await state.clear()
    uid = d.get("note_uid")
    text = (message.text or "").strip()
    if not uid or not text:
        return await message.answer("❌ Matn yuboring.")
    ad.add_note(uid, message.from_user.id, text)
    db.audit(message.from_user.id, "note_add", str(uid), text[:40])
    await message.answer("✅ Eslatma saqlandi.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [B("📝 Eslatmalar", f"un_list_{uid}"), B("👤 Karta", f"adm_user_{uid}")]]))


@router.callback_query(F.data.regexp(r"^un_del_\d+$"))
async def un_del(cb: CallbackQuery):
    n = ad.get_note(int(cb.data.replace("un_del_", "")))
    if not n:
        return await cb.answer("Topilmadi", show_alert=True)
    if n["admin_id"] != cb.from_user.id and cb.from_user.id != SUPERADMIN_ID:
        return await cb.answer("Faqat muallif yoki superadmin o'chira oladi", show_alert=True)
    ad.delete_note(n["id"])
    db.audit(cb.from_user.id, "note_del", str(n["user_id"]), f"#{n['id']}")
    await _show_notes(cb, n["user_id"])
    await cb.answer("O'chirildi")


# ── Teglar ──
def _tag_options(admin_id: int) -> list:
    opts = list(ad.PRESET_TAGS)
    opts += [t for t, _ in ad.all_tags() if t not in opts]
    _TAGLIST[admin_id] = opts[:16]
    return _TAGLIST[admin_id]


async def _show_tags(cb: CallbackQuery, uid: int):
    have = set(ad.get_tags(uid))
    opts = _tag_options(cb.from_user.id)
    btns = [B(f"{'✅' if t in have else '◻️'} {t}"[:30], f"un_tg_{uid}_{i}") for i, t in enumerate(opts)]
    rows = grid(btns, long_len=18) + [[B("➕ Boshqa teg", f"un_newtag_{uid}")], [B("🔙 Orqaga", f"adm_user_{uid}")]]
    await _edit(cb, "🏷 <b>Teglar</b>\n\nBosib qo'shing/olib tashlang:", rows)


@router.callback_query(F.data.regexp(r"^un_tags_\d+$"))
async def un_tags(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_tags(cb, int(cb.data.replace("un_tags_", "")))
    await cb.answer()


@router.callback_query(F.data.regexp(r"^un_tg_\d+_\d+$"))
async def un_toggle(cb: CallbackQuery):
    _, _, uid, idx = cb.data.split("_")
    opts = _TAGLIST.get(cb.from_user.id, [])
    if int(idx) >= len(opts):
        return await cb.answer("Eskirgan, qayta oching", show_alert=True)
    added = ad.toggle_tag(int(uid), opts[int(idx)], cb.from_user.id)
    db.audit(cb.from_user.id, "tag_add" if added else "tag_del", uid, opts[int(idx)])
    await _show_tags(cb, int(uid))
    await cb.answer("Qo'shildi" if added else "Olib tashlandi")


@router.callback_query(F.data.regexp(r"^un_newtag_\d+$"))
async def un_newtag(cb: CallbackQuery, state: FSMContext):
    uid = int(cb.data.replace("un_newtag_", ""))
    await state.set_state(TagState.waiting)
    await state.update_data(tag_uid=uid)
    await _edit(cb, "🏷 Yangi teg nomini yuboring (24 belgigacha):", [[B("❌ Bekor", f"un_tags_{uid}")]])
    await cb.answer()


@router.message(TagState.waiting)
async def un_newtag_save(message: Message, state: FSMContext):
    d = await state.get_data()
    await state.clear()
    uid, tag = d.get("tag_uid"), (message.text or "").strip()[:24]
    if not uid or not tag:
        return await message.answer("❌ Teg nomini yuboring.")
    if tag not in ad.get_tags(uid):
        ad.toggle_tag(uid, tag, message.from_user.id)
        db.audit(message.from_user.id, "tag_add", str(uid), tag)
    await message.answer(f"✅ Teg qo'shildi: {html.escape(tag)}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [B("🏷 Teglar", f"un_tags_{uid}"), B("👤 Karta", f"adm_user_{uid}")]]))


# ── Teg bo'yicha ro'yxat ──
@router.callback_query(F.data == "ut_tags")
async def ut_tags(cb: CallbackQuery):
    tags = ad.all_tags()
    _FILTER[cb.from_user.id] = [t for t, _ in tags]
    if not tags:
        await _edit(cb, "🏷 Hozircha teg yo'q. Foydalanuvchi kartasidan teg qo'shing.", [[B("🔙 Orqaga", "adm_users")]])
        return await cb.answer()
    btns = [B(f"{t} ({c})"[:30], f"ut_f_{i}") for i, (t, c) in enumerate(tags)]
    await _edit(cb, "🏷 <b>Teg bo'yicha foydalanuvchilar</b>", grid(btns, long_len=18) + [[B("🔙 Orqaga", "adm_users")]])
    await cb.answer()


async def _tag_users(cb: CallbackQuery, idx: int, page: int):
    tags = _FILTER.get(cb.from_user.id, [])
    if idx >= len(tags):
        return await cb.answer("Eskirgan, qayta oching", show_alert=True)
    tag = tags[idx]
    total = ad.count_users_with_tag(tag)
    pages = max(1, (total - 1) // PAGE_SIZE + 1)
    page = max(0, min(page, pages - 1))
    users = ad.users_with_tag(tag, page * PAGE_SIZE, PAGE_SIZE)
    admin_nav.set_back(cb.from_user.id, f"ut_l_{idx}_{page}")
    rows = grid([user_button(u) for u in users])
    nav = page_nav(page, pages, f"ut_l_{idx}_")
    if nav: rows.append(nav)
    rows.append([B("🏷 Teglar", "ut_tags"), B("🔙 Orqaga", "adm_users")])
    await _edit(cb, f"🏷 <b>{html.escape(tag)}</b> — {total} ta", rows)


@router.callback_query(F.data.regexp(r"^ut_f_\d+$"))
async def ut_first(cb: CallbackQuery):
    await _tag_users(cb, int(cb.data.replace("ut_f_", "")), 0)
    await cb.answer()


@router.callback_query(F.data.regexp(r"^ut_l_\d+_\d+$"))
async def ut_list(cb: CallbackQuery):
    _, _, idx, page = cb.data.split("_")
    await _tag_users(cb, int(idx), int(page))
    await cb.answer()
