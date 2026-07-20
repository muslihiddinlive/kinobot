from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from config import (DB_GROUP_ID, TOPIC_ERRORS, TOPIC_USERS, REQUIRED_CHANNEL_URL,
                    GENRES, SUPERADMIN_ID, SUPERADMIN_GREETINGS, BOT_NAME, TOPIC_VIP_CLUB)
from utils.helpers import format_movie_card, get_plan_until, get_lang, format_limit_text, days_left
from utils.keyboards import (main_menu, extra_menu, back_main, search_menu, media_type_keyboard,
                              movies_list_keyboard, movie_card_keyboard, plans_keyboard,
                              limit_over_keyboard, episode_list_keyboard, language_keyboard)
from locales import t
from datetime import date

router = Router()

# ── Holatlar ──────────────────────────────────────────
class SearchState(StatesGroup):
    waiting = State()

class SearchByCodeState(StatesGroup):
    waiting = State()

class SearchByNameState(StatesGroup):
    waiting = State()

class RequestState(StatesGroup):
    waiting = State()

class CommentState(StatesGroup):
    waiting = State()


# ══════════════════════════════════════════════════════
#  MUHIM: State li message handlerlar BIRINCHI kelishi
#  kerak, chunki aiogram tartib bo'yicha tekshiradi.
#  catch_any_text (F.text filter) ENG OXIRIDA bo'ladi.
# ══════════════════════════════════════════════════════

# ── State li message handlerlar (BIRINCHI) ────────────

@router.message(SearchByCodeState.waiting)
async def process_search_by_code(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    query = message.text.strip().upper().lstrip("#")
    lang = get_lang(message.from_user.id)
    movie = db.get_movie_by_code(query)
    if movie:
        await _send_movie_by_code(message, bot, movie["code"])
        return
    db.log_search(message.from_user.id, query, False)
    await message.answer(
        t("search_not_found", lang, query=query),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔢 Qayta kod kiriting", callback_data="search_by_code")],
            [InlineKeyboardButton(text="🔤 Nom bo'yicha", callback_data="search_by_name")],
            [InlineKeyboardButton(text=t("home", lang), callback_data="back_main")],
        ]),
        parse_mode="HTML"
    )

@router.message(SearchByNameState.waiting)
async def process_search_by_name(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    query = message.text.strip()
    lang = get_lang(message.from_user.id)
    results = db.search_movies(query)
    if not results:
        db.log_search(message.from_user.id, query, False)
        await message.answer(
            t("search_not_found", lang, query=query),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔤 Qayta qidirish", callback_data="search_by_name")],
                [InlineKeyboardButton(text=t("menu_request", lang), callback_data="request_movie")],
                [InlineKeyboardButton(text=t("home", lang), callback_data="back_main")],
            ]),
            parse_mode="HTML"
        )
        return
    if len(results) == 1:
        await _send_movie_by_code(message, bot, results[0]["code"])
        return
    db.log_search(message.from_user.id, query, True)
    await message.answer(
        t("search_results", lang, query=query, count=len(results)),
        reply_markup=movies_list_keyboard(results, lang, back_cb="search"),
        parse_mode="HTML"
    )

@router.message(SearchState.waiting)
async def process_search(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    query = message.text.strip()
    lang = get_lang(message.from_user.id)
    movie = db.get_movie_by_code(query.upper().lstrip("#"))
    if movie:
        await _send_movie_by_code(message, bot, movie["code"])
        return
    results = db.search_movies(query)
    if not results:
        db.log_search(message.from_user.id, query, False)
        await message.answer(
            t("search_not_found", lang, query=query),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t("menu_search", lang), callback_data="search")],
                [InlineKeyboardButton(text=t("menu_request", lang), callback_data="request_movie")],
                [InlineKeyboardButton(text=t("home", lang), callback_data="back_main")],
            ]),
            parse_mode="HTML"
        )
        return
    if len(results) == 1:
        await _send_movie_by_code(message, bot, results[0]["code"])
        return
    db.log_search(message.from_user.id, query, True)
    await message.answer(
        t("search_results", lang, query=query, count=len(results)),
        reply_markup=movies_list_keyboard(results, lang, back_cb="search"),
        parse_mode="HTML"
    )

@router.message(CommentState.waiting)
async def save_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    lang = get_lang(message.from_user.id)
    if len(message.text) > 300:
        await message.answer(t("comment_too_long", lang))
        return
    db.add_rating(message.from_user.id, data["movie_id"], 0, message.text.strip())
    await message.answer(t("comment_saved", lang), reply_markup=back_main(lang))

@router.message(RequestState.waiting)
async def request_send(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    lang = get_lang(message.from_user.id)
    db.add_movie_request(message.from_user.id, message.text.strip())
    try:
        await bot.send_message(DB_GROUP_ID,
            f"📩 Kino so'rovi!\n"
            f"👤 {message.from_user.full_name} (@{message.from_user.username or 'yoq'})\n"
            f"📝 {message.text.strip()}",
            message_thread_id=TOPIC_USERS)
    except Exception:
        pass
    await message.answer(t("request_sent", lang), reply_markup=back_main(lang))


# ── Komandalar ────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user = message.from_user
    args = message.text.split()
    referred_by = None

    # Deep link: /start movie_CODE
    if len(args) > 1 and args[1].startswith("movie_"):
        code = args[1].replace("movie_", "")
        db.register_user(user.id, user.username or "", user.full_name)
        from middlewares.subscription import check_subscription
        channels = db.get_required_channels()
        if channels:
            not_sub = await check_subscription(bot, user.id)
            if not_sub:
                await state.update_data(pending_movie_code=code)
                from utils.keyboards import subscription_keyboard
                lang = db.get_user_lang(user.id)
                markup = subscription_keyboard(not_sub, lang, pending_code=code)
                await message.answer(t("subscribe_required", lang), reply_markup=markup)
                return
        await _send_movie_by_code(message, bot, code)
        return

    # Deep link: /start ref_ID
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referred_by = int(args[1].replace("ref_", ""))
            if referred_by == user.id:
                referred_by = None
        except Exception:
            pass

    existing = db.get_user(user.id)
    db.register_user(user.id, user.username or "", user.full_name, referred_by)

    if not existing and referred_by:
        referrer = db.get_user(referred_by)
        if referrer:
            db.add_referral_points(referred_by, 1)
            db.record_referral(referred_by, user.id)
            try:
                await bot.send_message(referred_by,
                    f"🎉 Yangi referal! +1 ball\n"
                    f"Jami: {float(referrer['referral_points'])+1:.0f} 🪙")
            except Exception:
                pass
        try:
            await bot.send_message(DB_GROUP_ID,
                f"👤 Yangi foydalanuvchi!\n"
                f"Ism: {user.full_name}\n"
                f"@{user.username or 'yoq'} | ID: {user.id}",
                message_thread_id=TOPIC_USERS)
        except Exception:
            pass

    lang = get_lang(user.id)
    greeting = _build_greeting(user)
    welcome = db.get_setting("welcome_text", "")
    text = f"{greeting}\n\n🎬 <b>{BOT_NAME}</b> ga xush kelibsiz!\n\nKino kodi yoki nomini yuboring 👇"
    if welcome:
        text = f"{greeting}\n\n{welcome}"
    await message.answer(text, reply_markup=main_menu(lang), parse_mode="HTML")


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    lang = get_lang(message.from_user.id)
    await message.answer("🎬 Asosiy menyu:", reply_markup=main_menu(lang))

@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    await state.set_state(SearchState.waiting)
    await message.answer(t("search_prompt", lang), reply_markup=search_menu(lang), parse_mode="HTML")

@router.message(Command("trending"))
async def cmd_trending(message: Message):
    lang = get_lang(message.from_user.id)
    await _show_trending_msg(message, lang)

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    lang = get_lang(message.from_user.id)
    user = db.get_user(message.from_user.id)
    await message.answer(
        _build_profile(user, lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("menu_plans", lang), callback_data="plans")],
            [InlineKeyboardButton(text=t("home", lang), callback_data="back_main")]
        ]),
        parse_mode="HTML"
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = get_lang(message.from_user.id)
    await message.answer(
        f"{t('help_title', lang)}\n\n{t('help_text', lang)}",
        reply_markup=back_main(lang), parse_mode="HTML"
    )

@router.message(Command("settings"))
async def cmd_settings(message: Message):
    await message.answer(t("language_title", "uz"), reply_markup=language_keyboard())

@router.message(Command("reward"))
async def cmd_reward(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    await state.set_state(SearchState.waiting)
    await message.answer(t("promo_prompt", lang), reply_markup=back_main(lang))


# ── Catch-all (ENG OXIRIDA — state li handlerlardan KEYIN) ──

@router.message(F.text & ~F.text.startswith("/"))
async def catch_any_text(message: Message, bot: Bot):
    """
    Har qanday matnni qidiruv sifatida qabul qiladi.
    State li handlerlar YUQORIDA bo'lgani uchun aiogram
    avval ularni tekshiradi — bu handler faqat state YO'Q
    bo'lganda ishlaydi. current_state tekshiruvi KERAK EMAS.
    """
    query = message.text.strip()
    if not query:
        return

    lang = get_lang(message.from_user.id)

    # 1) Avval kod sifatida tekshir
    clean_code = query.upper().lstrip("#")
    movie = db.get_movie_by_code(clean_code)
    if movie:
        await _send_movie_by_code(message, bot, movie["code"])
        return

    # 2) Nom/tag bo'yicha qidirish
    results = db.search_movies(query)
    if not results:
        db.log_search(message.from_user.id, query, False)
        await message.answer(
            t("search_not_found", lang, query=query),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔢 Kod orqali", callback_data="search_by_code")],
                [InlineKeyboardButton(text="🔤 Nom bo'yicha", callback_data="search_by_name")],
                [InlineKeyboardButton(text=t("menu_request", lang), callback_data="request_movie")],
                [InlineKeyboardButton(text=t("home", lang), callback_data="back_main")],
            ]),
            parse_mode="HTML"
        )
        return

    if len(results) == 1:
        await _send_movie_by_code(message, bot, results[0]["code"])
        return

    db.log_search(message.from_user.id, query, True)
    await message.answer(
        t("search_results", lang, query=query, count=len(results)),
        reply_markup=movies_list_keyboard(results, lang, back_cb="search"),
        parse_mode="HTML"
    )

@router.message(F.text.startswith("/"))
async def unknown_cmd(message: Message):
    lang = get_lang(message.from_user.id)
    if db.is_admin(message.from_user.id):
        await message.answer(
            "❓ Noto'g'ri buyruq.\n\nAdmin: /admin\nUser: /menu /search /profile /help",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👨‍💼 Admin Panel", callback_data="admin_panel_cmd")]
            ])
        )
    else:
        await message.answer(
            "❌ Mavjud: /menu /search /trending /profile /reward /help",
            reply_markup=main_menu(lang)
        )


# ══════════════════════════════════════════════════════
#  ICHKI FUNKSIYALAR
# ══════════════════════════════════════════════════════

def _build_greeting(user) -> str:
    if user.id == SUPERADMIN_ID:
        idx = db.get_greeting_index(user.id)
        title = SUPERADMIN_GREETINGS[idx]
        db.increment_greeting_index(user.id, len(SUPERADMIN_GREETINGS))
        return f"👑 Salom, <b>{title}</b>!"
    return f"👋 Salom, <b>{user.first_name}</b>!"


async def _send_movie_by_code(message: Message, bot: Bot, code: str, episode_num: int = 1):
    """Message dan kino yuborish"""
    user_id = message.from_user.id
    lang = get_lang(user_id)

    user = db.get_user(user_id)
    if not user:
        db.register_user(user_id, message.from_user.username or "", message.from_user.full_name)
        user = db.get_user(user_id)

    if user and user["is_banned"]:
        await message.answer(t("banned_message", lang))
        return

    limit = db.get_daily_limit(user)
    if limit <= 0:
        await message.answer(
            f"⛔ <b>{t('search_limit_over', lang)}</b>",
            reply_markup=limit_over_keyboard(lang), parse_mode="HTML"
        )
        return

    movie = db.get_movie_by_code(code.upper())
    if not movie:
        db.log_search(user_id, code, False)
        await message.answer(
            t("search_not_found", lang, query=code),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t("menu_search", lang), callback_data="search")],
                [InlineKeyboardButton(text=t("menu_request", lang), callback_data="request_movie")],
            ]),
            parse_mode="HTML"
        )
        return

    # VIP tekshirish
    today = str(date.today())
    if movie["topic_id"] == TOPIC_VIP_CLUB:
        is_vip = user["plan"] == "vip" and user["plan_until"] and user["plan_until"] >= today
        if not is_vip and not db.is_admin(user_id):
            await message.answer(
                "👑 <b>Bu kino faqat VIP a'zolar uchun!</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="👑 VIP olish", callback_data="buy_vip_3m")],
                    [InlineKeyboardButton(text=t("home", lang), callback_data="back_main")],
                ]),
                parse_mode="HTML"
            )
            return

    # Qism
    total_ep = int(movie.get("total_episodes") or 1)
    episode_num = max(1, min(episode_num, total_ep))
    if total_ep > 1:
        ep = db.get_episode(movie["id"], episode_num) or db.get_episode(movie["id"], 1)
        if not ep:
            await message.answer("❌ Qism topilmadi.")
            return
        msg_id = ep["message_id"]
        episode_num = ep["episode_num"]
    else:
        msg_id = movie["message_id"]

    # Yuborish
    try:
        await bot.copy_message(message.chat.id, DB_GROUP_ID, msg_id)
    except Exception as e:
        await message.answer("❌ Kino yuborishda xato. Qayta urining.")
        try:
            await bot.send_message(DB_GROUP_ID,
                f"⚠️ Forward xato: {e} | {code}", message_thread_id=TOPIC_ERRORS)
        except Exception:
            pass
        return

    db.use_one_limit(user_id)
    db.increment_downloads(movie["id"])
    db.log_search(user_id, code, True)

    user = db.get_user(user_id)
    new_limit = db.get_daily_limit(user)
    is_fav = db.is_favorite(user_id, movie["id"])
    is_adm = db.is_admin(user_id)
    card = format_movie_card(dict(movie), episode_num, lang)
    markup = movie_card_keyboard(
        movie["id"], movie["code"], lang, is_fav, is_adm,
        episode_num, total_ep, movie.get("topic_id")
    )
    await message.answer(card, reply_markup=markup, parse_mode="HTML")
    await message.answer(
        f"📥 <b>{int(movie['downloads'])+1}</b> marta  |  Qoldi: <b>{format_limit_text(new_limit)}</b>",
        parse_mode="HTML"
    )


async def _send_movie_from_cb(cb: CallbackQuery, bot: Bot, code: str, episode_num: int = 1):
    """Callback dan kino yuborish"""
    user_id = cb.from_user.id
    lang = get_lang(user_id)

    user = db.get_user(user_id)
    if not user:
        db.register_user(user_id, cb.from_user.username or "", cb.from_user.full_name)
        user = db.get_user(user_id)

    if user and user["is_banned"]:
        await cb.answer(t("banned_message", lang), show_alert=True)
        return

    limit = db.get_daily_limit(user)
    if limit <= 0:
        await cb.answer(t("search_limit_over", lang), show_alert=True)
        await cb.message.answer(
            f"⛔ {t('search_limit_over', lang)}",
            reply_markup=limit_over_keyboard(lang)
        )
        return

    movie = db.get_movie_by_code(code.upper())
    if not movie:
        await cb.answer(t("search_not_found", lang, query=code), show_alert=True)
        return

    today = str(date.today())
    if movie["topic_id"] == TOPIC_VIP_CLUB:
        is_vip = user["plan"] == "vip" and user["plan_until"] and user["plan_until"] >= today
        if not is_vip and not db.is_admin(user_id):
            await cb.answer("👑 VIP kerak!", show_alert=True)
            return

    total_ep = int(movie.get("total_episodes") or 1)
    episode_num = max(1, min(episode_num, total_ep))
    msg_id = movie["message_id"]
    if total_ep > 1:
        ep = db.get_episode(movie["id"], episode_num)
        if ep:
            msg_id = ep["message_id"]

    try:
        await bot.copy_message(cb.message.chat.id, DB_GROUP_ID, msg_id)
    except Exception:
        await cb.answer("❌ Xato yuz berdi", show_alert=True)
        return

    db.use_one_limit(user_id)
    db.increment_downloads(movie["id"])
    db.log_search(user_id, code, True)

    user = db.get_user(user_id)
    new_limit = db.get_daily_limit(user)
    is_fav = db.is_favorite(user_id, movie["id"])
    is_adm = db.is_admin(user_id)
    card = format_movie_card(dict(movie), episode_num, lang)
    markup = movie_card_keyboard(
        movie["id"], movie["code"], lang, is_fav, is_adm,
        episode_num, total_ep, movie.get("topic_id")
    )
    await cb.message.answer(card, reply_markup=markup, parse_mode="HTML")
    await cb.message.answer(
        f"📥 <b>{int(movie['downloads'])+1}</b> marta  |  Qoldi: <b>{format_limit_text(new_limit)}</b>",
        parse_mode="HTML"
    )
    await cb.answer()


# ══════════════════════════════════════════════════════
#  CALLBACK HANDLERLAR
# ══════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_panel_cmd")
async def admin_panel_from_btn(cb: CallbackQuery):
    if not db.is_admin(cb.from_user.id):
        return await cb.answer("❌")
    from utils.keyboards import admin_menu
    await cb.message.edit_text("👨‍💼 <b>Admin Panel</b>", reply_markup=admin_menu(), parse_mode="HTML")
    await cb.answer()

# ── Qidiruv ───────────────────────────────────────────

@router.callback_query(F.data == "search")
async def search_cb(cb: CallbackQuery, state: FSMContext):
    lang = get_lang(cb.from_user.id)
    await state.set_state(SearchState.waiting)
    await cb.message.edit_text(
        t("search_prompt", lang),
        reply_markup=search_menu(lang), parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data == "search_by_code")
async def search_by_code_cb(cb: CallbackQuery, state: FSMContext):
    lang = get_lang(cb.from_user.id)
    await state.set_state(SearchByCodeState.waiting)
    await cb.message.edit_text(
        "🔢 <b>Kod orqali qidirish</b>\n\n"
        "Kino kodini yuboring.\n"
        "<i>Masalan: 0042 | S001 | TROLL</i>",
        reply_markup=back_main(lang), parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data == "search_by_name")
async def search_by_name_cb(cb: CallbackQuery, state: FSMContext):
    lang = get_lang(cb.from_user.id)
    await state.set_state(SearchByNameState.waiting)
    await cb.message.edit_text(
        "🔤 <b>Nom bo'yicha qidirish</b>\n\n"
        "Kino nomini yoki #fishkasini yuboring.\n"
        "<i>Masalan: John Wick | #action | Uzbek</i>",
        reply_markup=back_main(lang), parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data.startswith("get_movie_"))
async def get_movie_cb(cb: CallbackQuery, bot: Bot):
    code = cb.data.replace("get_movie_", "")
    await _send_movie_from_cb(cb, bot, code)

# ── Obuna tekshirish ──────────────────────────────────

@router.callback_query(F.data.startswith("check_subscription"))
async def check_sub(cb: CallbackQuery, state: FSMContext, bot: Bot):
    from middlewares.subscription import check_subscription
    lang = get_lang(cb.from_user.id)

    # pending_code: "check_subscription:CODE" yoki state dan
    parts = cb.data.split(":", 1)
    pending_code = parts[1] if len(parts) > 1 else None
    if not pending_code:
        fsm_data = await state.get_data()
        pending_code = fsm_data.get("pending_movie_code")

    not_sub = await check_subscription(cb.bot, cb.from_user.id)
    if not_sub:
        await cb.answer(t("subscribe_fail", lang), show_alert=True)
        return

    await cb.answer(t("subscribe_success", lang), show_alert=True)
    await state.clear()

    if pending_code:
        await _send_movie_from_cb(cb, bot, pending_code)
    else:
        welcome = db.get_setting("welcome_text", f"🎬 <b>{BOT_NAME}</b>")
        try:
            await cb.message.edit_text(welcome, reply_markup=main_menu(lang), parse_mode="HTML")
        except Exception:
            await cb.message.answer(welcome, reply_markup=main_menu(lang), parse_mode="HTML")

# ── Back ──────────────────────────────────────────────

@router.callback_query(F.data == "back_main")
async def back_main_cb(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = get_lang(cb.from_user.id)
    welcome = db.get_setting("welcome_text", f"🎬 <b>{BOT_NAME}</b>")
    try:
        await cb.message.edit_text(welcome, reply_markup=main_menu(lang), parse_mode="HTML")
    except Exception:
        await cb.message.answer(welcome, reply_markup=main_menu(lang), parse_mode="HTML")
    await cb.answer()

# ── Qism navigatsiyasi ────────────────────────────────

@router.callback_query(F.data.startswith("ep_list_"))
async def ep_list(cb: CallbackQuery):
    movie_id = int(cb.data.replace("ep_list_", ""))
    episodes = db.get_episodes(movie_id)
    if not episodes:
        await cb.answer("Qismlar topilmadi", show_alert=True)
        return
    await cb.message.answer("📋 Qismni tanlang:", reply_markup=episode_list_keyboard(movie_id, episodes))
    await cb.answer()

@router.callback_query(F.data.startswith("ep_") & ~F.data.startswith("ep_list_"))
async def ep_navigate(cb: CallbackQuery, bot: Bot):
    parts = cb.data.replace("ep_", "").split("_")
    if len(parts) < 2:
        return await cb.answer()
    movie_id, ep_num = int(parts[0]), int(parts[1])
    conn = db.get_conn()
    row = conn.execute("SELECT code FROM movies WHERE id=?", (movie_id,)).fetchone()
    conn.close()
    if not row:
        return await cb.answer("Kino topilmadi", show_alert=True)
    await _send_movie_from_cb(cb, bot, row["code"], ep_num)

# ── Media tur ─────────────────────────────────────────

@router.callback_query(F.data == "browse_media")
async def browse_media(cb: CallbackQuery):
    lang = get_lang(cb.from_user.id)
    await cb.message.edit_text(t("choose_media_type", lang), reply_markup=media_type_keyboard(lang))
    await cb.answer()

@router.callback_query(F.data.startswith("media_"))
async def media_selected(cb: CallbackQuery):
    topic_id = int(cb.data.replace("media_", ""))
    lang = get_lang(cb.from_user.id)
    movies = db.get_movies_by_topic(topic_id, limit=20)
    if not movies:
        await cb.answer(t("no_movies_in_genre", lang), show_alert=True)
        return
    genre_name = GENRES.get(topic_id, ("🎬", ""))[0]
    await cb.message.edit_text(
        f"{genre_name} — {len(movies)} ta kino:",
        reply_markup=movies_list_keyboard(movies, lang),
        parse_mode="HTML"
    )
    await cb.answer()

# ── Tasodifiy ─────────────────────────────────────────

@router.callback_query(F.data == "random_movie")
async def random_movie_cb(cb: CallbackQuery, bot: Bot):
    lang = get_lang(cb.from_user.id)
    user = db.get_user(cb.from_user.id)
    if not user:
        db.register_user(cb.from_user.id, cb.from_user.username or "", cb.from_user.full_name)
        user = db.get_user(cb.from_user.id)
    if not user or db.get_daily_limit(user) <= 0:
        await cb.answer(t("search_limit_over", lang), show_alert=True)
        await cb.message.answer(f"⛔ {t('search_limit_over', lang)}", reply_markup=limit_over_keyboard(lang))
        return
    movie = db.get_random_movie()
    if not movie:
        await cb.answer("🎬 Hozircha kinolar yo'q", show_alert=True)
        return
    await cb.answer(f"🎲 {movie['title']}")
    await _send_movie_from_cb(cb, bot, movie["code"])

@router.callback_query(F.data.startswith("similar_"))
async def similar_cb(cb: CallbackQuery, bot: Bot):
    topic_id = int(cb.data.replace("similar_", ""))
    lang = get_lang(cb.from_user.id)
    movie = db.get_random_movie(topic_id)
    if not movie:
        await cb.answer(t("no_movies_in_genre", lang), show_alert=True)
        return
    await _send_movie_from_cb(cb, bot, movie["code"])

# ── Trending ──────────────────────────────────────────

@router.callback_query(F.data == "trending")
async def trending_cb(cb: CallbackQuery):
    lang = get_lang(cb.from_user.id)
    movies = db.get_trending_movies(10)
    if not movies:
        await cb.message.edit_text(t("trending_empty", lang), reply_markup=back_main(lang))
        await cb.answer()
        return
    text = f"{t('trending_title', lang)}\n\n"
    buttons = []
    for i, m in enumerate(movies, 1):
        ep_info = f" ({m.get('total_episodes',1)} qism)" if m.get('total_episodes', 1) > 1 else ""
        text += f"{i}. <b>{m['title']}</b>{ep_info} — 📥{m['downloads']}\n"
        buttons.append([InlineKeyboardButton(text=f"🎬 {m['title']}", callback_data=f"get_movie_{m['code']}")])
    buttons.append([InlineKeyboardButton(text=t("home", lang), callback_data="back_main")])
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await cb.answer()

async def _show_trending_msg(message, lang):
    movies = db.get_trending_movies(10)
    if not movies:
        await message.answer(t("trending_empty", lang), reply_markup=back_main(lang))
        return
    text = f"{t('trending_title', lang)}\n\n"
    buttons = []
    for i, m in enumerate(movies, 1):
        text += f"{i}. <b>{m['title']}</b> — 📥{m['downloads']}\n"
        buttons.append([InlineKeyboardButton(text=f"🎬 {m['title']}", callback_data=f"get_movie_{m['code']}")])
    buttons.append([InlineKeyboardButton(text=t("home", lang), callback_data="back_main")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")

# ── Reyting ───────────────────────────────────────────

@router.callback_query(F.data.startswith("dorat_"))
async def do_rate(cb: CallbackQuery):
    parts = cb.data.replace("dorat_", "").split("_")
    if len(parts) < 2:
        return await cb.answer()
    movie_id, rating = int(parts[0]), int(parts[1])
    db.add_rating(cb.from_user.id, movie_id, rating)
    await cb.answer(f"Bahoyingiz: {'⭐' * rating}", show_alert=True)

# ── Izoh ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("comment_"))
async def comment_cb(cb: CallbackQuery, state: FSMContext):
    movie_id = int(cb.data.replace("comment_", ""))
    lang = get_lang(cb.from_user.id)
    await state.set_state(CommentState.waiting)
    await state.update_data(movie_id=movie_id)
    await cb.message.answer(t("comment_prompt", lang), reply_markup=back_main(lang))
    await cb.answer()

# ── Sevimlilar ────────────────────────────────────────

@router.callback_query(F.data.startswith("fav_"))
async def add_fav(cb: CallbackQuery):
    movie_id = int(cb.data.replace("fav_", ""))
    lang = get_lang(cb.from_user.id)
    db.add_favorite(cb.from_user.id, movie_id)
    await cb.answer(t("favorite_added", lang), show_alert=True)

@router.callback_query(F.data.startswith("unfav_"))
async def rem_fav(cb: CallbackQuery):
    movie_id = int(cb.data.replace("unfav_", ""))
    lang = get_lang(cb.from_user.id)
    db.remove_favorite(cb.from_user.id, movie_id)
    await cb.answer(t("favorite_removed", lang), show_alert=True)

@router.callback_query(F.data == "favorites")
async def favorites_cb(cb: CallbackQuery):
    lang = get_lang(cb.from_user.id)
    favs = db.get_favorites(cb.from_user.id)
    if not favs:
        await cb.message.edit_text(
            f"{t('favorites_title', lang)}\n\n{t('favorites_empty', lang)}",
            reply_markup=back_main(lang), parse_mode="HTML"
        )
        await cb.answer()
        return
    buttons = [[InlineKeyboardButton(
        text=f"🎬 {m['title']}", callback_data=f"get_movie_{m['code']}"
    )] for m in favs]
    buttons.append([InlineKeyboardButton(text=t("home", lang), callback_data="back_main")])
    await cb.message.edit_text(
        f"{t('favorites_title', lang)} — {len(favs)} ta",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML"
    )
    await cb.answer()

# ── Profil ────────────────────────────────────────────

@router.callback_query(F.data == "profile")
async def profile_cb(cb: CallbackQuery):
    lang = get_lang(cb.from_user.id)
    user = db.get_user(cb.from_user.id)
    await cb.message.edit_text(
        _build_profile(user, lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("menu_plans", lang), callback_data="plans"),
             InlineKeyboardButton(text=t("menu_referral", lang), callback_data="referral")],
            [InlineKeyboardButton(text=t("home", lang), callback_data="back_main")],
        ]),
        parse_mode="HTML"
    )
    await cb.answer()

def _build_profile(user, lang):
    from utils.helpers import plan_badge
    today = str(date.today())
    uid = user["user_id"]
    if uid == SUPERADMIN_ID:
        badge = t("profile_superadmin_badge", lang)
    elif db.is_admin(uid):
        badge = t("profile_admin_badge", lang)
    else:
        plan = user["plan"]
        until = user["plan_until"]
        if until and until < today and plan not in ("free", "banned"):
            plan = "free"
        badge = plan_badge(plan, until, lang)

    limit = db.get_daily_limit(user)
    limit_str = format_limit_text(limit)
    d = days_left(user["plan_until"]) if user["plan_until"] else 0
    text = (
        f"{t('profile_title', lang)}\n\n"
        f"╭─────────────────────\n"
        f"├‣ 👋 {t('profile_name', lang)}:   {user['full_name']}\n"
        f"├‣ 🏷 {t('profile_plan', lang)}:   {badge}\n"
    )
    if d > 0 and not db.is_admin(uid):
        text += f"├‣ ⏳ Qoldi:   {d} kun\n"
    text += (
        f"├‣ 🎬 {t('profile_daily_limit', lang)}: {limit_str}\n"
        f"├‣ 🎟 {t('profile_bought_limit', lang)}: {user['bought_limit']} ta\n"
        f"├‣ 🪙 {t('profile_ref_points', lang)}: {float(user['referral_points']):.1f}\n"
        f"├‣ ⭐ {t('profile_stars', lang)}: {user['total_stars']}\n"
        f"├‣ 🌐 {t('profile_lang', lang)}: {user['lang'].upper()}\n"
        f"╰─────────────────────"
    )
    return text

# ── Qo'shimcha menyu ──────────────────────────────────

@router.callback_query(F.data == "extra_menu")
async def extra_menu_cb(cb: CallbackQuery):
    lang = get_lang(cb.from_user.id)
    await cb.message.edit_text("➕ <b>Qo'shimcha</b>", reply_markup=extra_menu(lang), parse_mode="HTML")
    await cb.answer()

# ── Til ───────────────────────────────────────────────

@router.callback_query(F.data == "set_language")
async def lang_cb(cb: CallbackQuery):
    lang = get_lang(cb.from_user.id)
    await cb.message.edit_text(t("language_title", lang), reply_markup=language_keyboard())
    await cb.answer()

@router.callback_query(F.data.startswith("lang_"))
async def change_lang(cb: CallbackQuery):
    new_lang = cb.data.replace("lang_", "")
    db.set_user_lang(cb.from_user.id, new_lang)
    await cb.message.edit_text(t("language_changed", new_lang), reply_markup=main_menu(new_lang))
    await cb.answer()

# ── Yordam ────────────────────────────────────────────

@router.callback_query(F.data == "help")
async def help_cb(cb: CallbackQuery):
    lang = get_lang(cb.from_user.id)
    await cb.message.edit_text(
        f"{t('help_title', lang)}\n\n{t('help_text', lang)}",
        reply_markup=back_main(lang), parse_mode="HTML"
    )
    await cb.answer()

# ── Kino so'rovi ──────────────────────────────────────

@router.callback_query(F.data == "request_movie")
async def request_cb(cb: CallbackQuery, state: FSMContext):
    lang = get_lang(cb.from_user.id)
    await state.set_state(RequestState.waiting)
    await cb.message.edit_text(t("request_prompt", lang), reply_markup=back_main(lang))
    await cb.answer()

@router.callback_query(F.data == "noop")
async def noop(cb: CallbackQuery):
    await cb.answer()
