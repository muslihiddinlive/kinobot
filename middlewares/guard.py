"""Admin panel qo'riqchisi (callback_query uchun outer middleware):
  1) ruxsat tekshiruvi (RBAC)   2) superadmin PIN   3) xavfli amallarga tasdiq.
Hamma admin tugmalari shu yerdan o'tadi, shuning uchun alohida handlerlarga tegmasdan ruxsatlar majburlanadi."""
import logging
import secrets
import time

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Update

import database as db
from utils import perms, pin
from utils.keyboards import sbtn

log = logging.getLogger(__name__)

_PENDING: dict = {}          # token -> {uid, data, exp}
_ALLOW: dict = {}            # (uid, data) -> exp   (tasdiqlangan callback bir marta o'tadi)
_COUNTER = [10 ** 12]
_DP: list = [None]           # Dispatcher havolasi (middleware data'sida 'dispatcher' kaliti yo'q)


def set_dispatcher(dp) -> None:
    _DP[0] = dp


def _gc():
    now = time.time()
    for k in [k for k, v in _PENDING.items() if v["exp"] < now]:
        _PENDING.pop(k, None)
    for k in [k for k, v in _ALLOW.items() if v < now]:
        _ALLOW.pop(k, None)


async def _safe_edit(event: CallbackQuery, text: str, rows):
    try:
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def redispatch(bot, event: CallbackQuery, data_str: str, dp=None, message=None):
    """Asl callback'ni (tasdiqdan/PINdan keyin) xuddi foydalanuvchi bosgandek qayta yuboradi.
    message — asl xabar (tasdiq alohida xabarda so'ralgani uchun handler asl xabar ustida ishlaydi)."""
    dp = dp or _DP[0]
    _COUNTER[0] += 1
    cq = CallbackQuery(id=event.id, from_user=event.from_user, chat_instance=event.chat_instance,
                       data=data_str, message=message or event.message)
    await dp.feed_update(bot, Update(update_id=_COUNTER[0], callback_query=cq))


class GuardMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: CallbackQuery, data):
        d = event.data or ""
        uid = event.from_user.id

        # Tasdiqlash tugmalari (cf_ok_<token> / cf_no_<token>)
        if d.startswith("cf_"):
            return await self._on_confirm(event, data)

        perm = perms.required_perm(d)
        if perm is None:
            return await handler(event, data)

        if not perms.has_perm(uid, perm):
            label = "faqat superadmin" if perm == "super" else perms.PERMS.get(perm, perm)
            await event.answer(f"⛔ Ruxsat yo'q: {label}", show_alert=True)
            return None

        if perms.needs_pin(d) and pin.enabled() and not pin.unlocked(uid):
            return await self._ask_pin(event, data, d)

        text = perms.confirm_text(d)
        if text and _ALLOW.pop((uid, d), 0) < time.time():
            return await self._ask_confirm(event, d, text)
        return await handler(event, data)

    # ── PIN ──
    async def _ask_pin(self, event: CallbackQuery, data, orig: str):
        state = data.get("state")
        if state is None:
            await event.answer("🔐 PIN kerak", show_alert=True)
            return None
        await state.set_state(pin.PinState.waiting)
        await state.update_data(pin_return=orig, pin_msg=event.message.message_id, pin_chat=event.message.chat.id)
        await _safe_edit(event, "🔐 <b>PIN kiriting</b>\n\nXabar yuborilgach darhol o'chiriladi.",
                         [[InlineKeyboardButton(text="❌ Bekor", callback_data="adm_back")]])
        await event.answer()
        return None

    # ── Tasdiq ──
    # Tasdiq ALOHIDA xabarda so'raladi: asl xabar (masalan, to'lov so'rovi matni) o'zgarmaydi,
    # chunki ba'zi handlerlar (to'lovni tasdiqlash) asl xabar matniga tayanadi.
    async def _ask_confirm(self, event: CallbackQuery, orig: str, text: str):
        _gc()
        token = secrets.token_hex(4)
        _PENDING[token] = {"uid": event.from_user.id, "data": orig, "msg": event.message, "exp": time.time() + 180}
        await event.message.answer(
            f"⚠️ <b>Tasdiqlang</b>\n\n{text}\n\nDavom etamizmi?", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                sbtn("✅ Ha, davom etish", "danger", callback_data=f"cf_ok_{token}"),
                InlineKeyboardButton(text="❌ Bekor", callback_data=f"cf_no_{token}")]]))
        await event.answer()
        return None

    async def _on_confirm(self, event: CallbackQuery, data):
        d = event.data
        token = d.rsplit("_", 1)[-1]
        p = _PENDING.pop(token, None)
        if not p or p["uid"] != event.from_user.id or p["exp"] < time.time():
            await event.answer("Eskirgan so'rov. Amalni qaytadan boshlang.", show_alert=True)
            return None
        try:
            await event.message.delete()                      # tasdiq xabarini olib tashlaymiz
        except Exception:  # noqa: BLE001
            pass
        if d.startswith("cf_no_"):
            await event.answer("Bekor qilindi")
            return None
        _ALLOW[(p["uid"], p["data"])] = time.time() + 30
        await redispatch(data["bot"], event, p["data"], message=p["msg"])
        return None
