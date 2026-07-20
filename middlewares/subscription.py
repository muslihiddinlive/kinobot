from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
import database as db
from utils.keyboards import subscription_keyboard
from locales import t
import logging

logger = logging.getLogger(__name__)

async def check_subscription(bot, user_id: int) -> list:
    """Obuna bo'lmagan kanallar ro'yxatini qaytaradi"""
    channels = db.get_required_channels()
    not_subscribed = []

    for ch in channels:
        try:
            member = await bot.get_chat_member(
                chat_id=ch["channel_id"],
                user_id=user_id
            )
            if member.status in ("left", "kicked", "banned"):
                not_subscribed.append(dict(ch))
        except TelegramForbiddenError:
            # Bot kanalda admin emas — kanaldan o'tkazib yuboramiz
            logger.warning(f"Bot kanalda admin emas: {ch['channel_id']}")
        except TelegramBadRequest as e:
            # Noto'g'ri kanal ID
            logger.warning(f"Kanal topilmadi: {ch['channel_id']} — {e}")
        except Exception as e:
            logger.error(f"Kanal tekshirishda xato {ch['channel_id']}: {e}")

    return not_subscribed

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        from config import ADMIN_IDS, SUPERADMIN_ID

        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        bot = data.get("bot")
        user_id = event.from_user.id

        # Admin va superadmin tekshiruvsiz o'tadi
        if user_id in ADMIN_IDS or user_id == SUPERADMIN_ID or db.is_admin(user_id):
            return await handler(event, data)

        # Bu callbacklar obunasiz ishlashi kerak
        if isinstance(event, CallbackQuery):
            cb_data = event.data or ""
            if cb_data == "back_main" or cb_data.startswith("check_subscription"):
                return await handler(event, data)

        # /start movie_CODE va /start ref_ID — deeplink xabarlarini middleware
        # o'tkazib yuboradi. movie_ uchun handler o'zi obunani tekshiradi;
        # ref_ (referal) uchun esa obuna talab qilinmasligi kerak — aks holda
        # obunasiz foydalanuvchi referal sifatida ro'yxatga olinmay qoladi.
        if isinstance(event, Message) and event.text:
            parts = event.text.split()
            if parts[0] == "/start" and len(parts) > 1 and (
                parts[1].startswith("movie_") or parts[1].startswith("ref_")
            ):
                return await handler(event, data)

        # DB da kanallar bor-yo'qligini tekshir
        channels = db.get_required_channels()
        if not channels:
            # Kanal yo'q — tekshiruvsiz o'tkazamiz
            return await handler(event, data)

        not_sub = await check_subscription(bot, user_id)
        if not_sub:
            lang = db.get_user_lang(user_id)
            # Agar deeplink kodi bor bo'lsa — subscription tugmasiga ham yuboramiz
            pending_code = None
            if isinstance(event, Message) and event.text:
                parts = event.text.split()
                if len(parts) > 1 and parts[1].startswith("movie_"):
                    pending_code = parts[1].replace("movie_", "")
            markup = subscription_keyboard(not_sub, lang, pending_code=pending_code)
            text = t("subscribe_required", lang)
            if isinstance(event, Message):
                await event.answer(text, reply_markup=markup)
            elif isinstance(event, CallbackQuery):
                try:
                    await event.message.edit_text(text, reply_markup=markup)
                except Exception:
                    await event.answer(text, show_alert=True)
                await event.answer()
            return  # Handler ga o'tmaymiz

        return await handler(event, data)
