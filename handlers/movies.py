from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from config import DB_GROUP_ID, GENRES, TOPIC_ADMIN_LOGS, REQUIRED_CHANNEL_URL
from utils.helpers import format_movie_card, parse_tags, auto_code
from utils.keyboards import (admin_menu, channel_post_keyboard, add_movie_format_kb,
                              add_movie_rating_kb, episodes_type_kb, movie_status_kb,
                              after_movie_add_kb, thumbnail_kb, episode_list_keyboard)

router = Router()

def genre_keyboard():
    buttons = []
    items = list(GENRES.items())
    for i in range(0, len(items), 2):
        row = []
        for tid, (name, _) in items[i:i+2]:
            row.append(InlineKeyboardButton(text=name, callback_data=f"amovie_genre_{tid}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_movies")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

class AddMovieState(StatesGroup):
    genre        = State()
    title        = State()
    code_choice  = State()
    code_manual  = State()
    ep_type      = State()   # single | multi | ongoing
    ep_count     = State()   # ko'p qismli bo'lsa soni
    status       = State()
    year         = State()
    country      = State()
    language     = State()
    format_      = State()
    rating       = State()
    tags         = State()
    description  = State()
    media        = State()   # fayl(lar)
    # Kanalga yuborish
    ask_channel  = State()
    thumbnail    = State()

class AddEpisodeState(StatesGroup):
    movie_id     = State()
    media        = State()

class EditMovieState(StatesGroup):
    field        = State()
    value        = State()

class UpdateMediaState(StatesGroup):
    code         = State()
    media        = State()

# ── Kino menyu ────────────────────────────────────────
@router.callback_query(F.data == "adm_movies")
async def adm_movies_menu(cb: CallbackQuery):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="adm_add_movie")],
        [InlineKeyboardButton(text="📋 Ro'yxat", callback_data="adm_list_movies"),
         InlineKeyboardButton(text="🔄 Fayl yangilash", callback_data="adm_update_movie")],
        [InlineKeyboardButton(text="🔝 Trending", callback_data="adm_trending"),
         InlineKeyboardButton(text="🔍 Dublikat", callback_data="adm_duplicates")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")],
    ])
    await cb.message.edit_text("🎬 <b>Kino boshqaruv</b>", reply_markup=markup, parse_mode="HTML")
    await cb.answer()

# ── KINO QO'SHISH ─────────────────────────────────────
@router.callback_query(F.data == "adm_add_movie")
async def add_start(cb: CallbackQuery, state: FSMContext):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    await state.set_state(AddMovieState.genre)
    await cb.message.edit_text("🎬 <b>Yangi kino</b>\n\n1️⃣ Janrni tanlang:", reply_markup=genre_keyboard(), parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("amovie_genre_"), AddMovieState.genre)
async def add_genre(cb: CallbackQuery, state: FSMContext):
    tid = int(cb.data.replace("amovie_genre_", ""))
    await state.update_data(topic_id=tid, genre_name=GENRES[tid][0])
    await state.set_state(AddMovieState.title)
    await cb.message.edit_text(f"✅ Janr: <b>{GENRES[tid][0]}</b>\n\n2️⃣ Kino nomini kiriting:", parse_mode="HTML")
    await cb.answer()

@router.message(AddMovieState.title)
async def add_title(message: Message, state: FSMContext):
    title = message.text.strip()
    suggested = auto_code(title)
    await state.update_data(title=title)
    await state.set_state(AddMovieState.code_choice)
    await message.answer(
        f"3️⃣ <b>Kino kodi</b>\n\nTaklif: <code>{suggested}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ {suggested} — tasdiqlash", callback_data=f"code_auto_{suggested}")],
            [InlineKeyboardButton(text="✏️ O'zim kiritaman", callback_data="code_manual")],
        ]), parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("code_auto_"), AddMovieState.code_choice)
async def code_auto(cb: CallbackQuery, state: FSMContext):
    code = cb.data.replace("code_auto_", "")
    await state.update_data(code=code)
    await state.set_state(AddMovieState.ep_type)
    await cb.message.edit_text("4️⃣ Qism turi:", reply_markup=episodes_type_kb())
    await cb.answer()

@router.callback_query(F.data == "code_manual", AddMovieState.code_choice)
async def code_manual_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AddMovieState.code_manual)
    await cb.message.edit_text("Kino kodini kiriting:")
    await cb.answer()

@router.message(AddMovieState.code_manual)
async def code_manual_input(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    if db.get_movie_by_code(code):
        await message.answer(f"⚠️ <b>{code}</b> band! Boshqa kod kiriting:", parse_mode="HTML"); return
    await state.update_data(code=code)
    await state.set_state(AddMovieState.ep_type)
    await message.answer("4️⃣ Qism turi:", reply_markup=episodes_type_kb())

@router.callback_query(F.data == "ep_type_single", AddMovieState.ep_type)
async def ep_single(cb: CallbackQuery, state: FSMContext):
    await state.update_data(ep_type="single", total_episodes=1)
    await state.set_state(AddMovieState.year)
    await cb.message.edit_text(
        "5️⃣ Yilini kiriting yoki o'tkazib yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ O'tkazish", callback_data="year_skip")]
        ])
    )
    await cb.answer()

@router.callback_query(F.data == "ep_type_multi", AddMovieState.ep_type)
async def ep_multi(cb: CallbackQuery, state: FSMContext):
    await state.update_data(ep_type="multi", status="completed")
    await state.set_state(AddMovieState.ep_count)
    await cb.message.edit_text(
        "📺 <b>Ko'p qismli serial</b>\n\n"
        "Nechanchi qismdan boshlamoqchisiz?\n"
        "<i>Masalan: 1 — birinchi qismdan boshlash</i>\n"
        "<i>Masalan: 5 — 5-qismdan boshlash</i>",
        parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data == "ep_type_ongoing", AddMovieState.ep_type)
async def ep_ongoing(cb: CallbackQuery, state: FSMContext):
    await state.update_data(ep_type="ongoing", status="ongoing")
    await state.set_state(AddMovieState.ep_count)
    await cb.message.edit_text(
        "🔄 <b>Davom etmoqda</b>\n\n"
        "Nechanchi qismni qo'shmoqchisiz?\n"
        "<i>Masalan: 1 — birinchi qismdan boshlash</i>",
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(AddMovieState.ep_count)
async def ep_count_input(message: Message, state: FSMContext):
    try:
        ep_num = int(message.text.strip())
        if ep_num < 1:
            await message.answer("❌ Kamida 1 bo'lishi kerak!"); return
        data = await state.get_data()
        status = data.get("status", "completed")
        # Boshlang'ich qism raqami saqlanadi
        await state.update_data(start_ep=ep_num, total_episodes=ep_num, status=status)
        await state.set_state(AddMovieState.year)
        await message.answer(
            f"✅ {ep_num}-qismdan boshlanadi\n\n"
            f"5️⃣ Yilini kiriting yoki o'tkazib yuboring:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭ O'tkazish", callback_data="year_skip")]
            ])
        )
    except:
        await message.answer("❌ Raqam kiriting!")

@router.callback_query(F.data == "year_skip", AddMovieState.year)
async def year_skip(cb: CallbackQuery, state: FSMContext):
    await state.update_data(year="")
    await state.set_state(AddMovieState.country)
    await cb.message.edit_text(
        "6️⃣ Davlatini kiriting yoki o'tkazib yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ O'tkazish", callback_data="country_skip")]
        ])
    )
    await cb.answer()

@router.message(AddMovieState.year)
async def add_year(message: Message, state: FSMContext):
    await state.update_data(year=message.text.strip())
    await state.set_state(AddMovieState.country)
    await message.answer(
        "6️⃣ Davlatini kiriting yoki o'tkazib yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ O'tkazish", callback_data="country_skip")]
        ])
    )

@router.callback_query(F.data == "country_skip", AddMovieState.country)
async def country_skip(cb: CallbackQuery, state: FSMContext):
    await state.update_data(country="")
    await _ask_language(cb.message, state)
    await cb.answer()

@router.message(AddMovieState.country)
async def add_country(message: Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    await _ask_language(message, state)

async def _ask_language(message, state):
    await state.set_state(AddMovieState.language)
    await message.answer(
        "7️⃣ Tilini tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="mlang_O'zbek"),
             InlineKeyboardButton(text="🇷🇺 Rus", callback_data="mlang_Rus")],
            [InlineKeyboardButton(text="🇬🇧 Ingliz", callback_data="mlang_Ingliz"),
             InlineKeyboardButton(text="🇰🇷 Koreys", callback_data="mlang_Koreys")],
            [InlineKeyboardButton(text="🇹🇷 Turk", callback_data="mlang_Turk"),
             InlineKeyboardButton(text="🌐 Boshqa", callback_data="mlang_other")],
            [InlineKeyboardButton(text="⏭ O'tkazish", callback_data="mlang_skip")],
        ])
    )

@router.callback_query(F.data.startswith("mlang_"), AddMovieState.language)
async def add_lang_cb(cb: CallbackQuery, state: FSMContext):
    val = "" if cb.data in ("mlang_skip","mlang_other") else cb.data.replace("mlang_","")
    if cb.data == "mlang_other":
        await cb.message.edit_text("Tilni yozing:"); await cb.answer(); return
    await state.update_data(language=val)
    await state.set_state(AddMovieState.format_)
    await cb.message.edit_text("8️⃣ Sifatini tanlang:", reply_markup=add_movie_format_kb())
    await cb.answer()

@router.message(AddMovieState.language)
async def add_lang_text(message: Message, state: FSMContext):
    await state.update_data(language=message.text.strip())
    await state.set_state(AddMovieState.format_)
    await message.answer("8️⃣ Sifatini tanlang:", reply_markup=add_movie_format_kb())

@router.callback_query(F.data.startswith("afmt_"), AddMovieState.format_)
async def add_format(cb: CallbackQuery, state: FSMContext):
    val = "" if cb.data=="afmt_skip" else cb.data.replace("afmt_","")
    await state.update_data(format_=val)
    await state.set_state(AddMovieState.tags)
    await cb.message.edit_text(
        "9️⃣ Fishkalar kiriting:\n<i>Masalan: action drama romantik</i>\nYoki o'tkazib yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ O'tkazish", callback_data="tags_skip")]
        ]),
        parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data == "tags_skip", AddMovieState.tags)
async def tags_skip(cb: CallbackQuery, state: FSMContext):
    await state.update_data(tags="")
    await state.set_state(AddMovieState.description)
    await cb.message.edit_text(
        "🔟 Qisqacha ta'rif kiriting yoki o'tkazib yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ O'tkazish", callback_data="desc_skip")]
        ])
    )
    await cb.answer()

@router.message(AddMovieState.tags)
async def add_tags(message: Message, state: FSMContext):
    await state.update_data(tags=parse_tags(message.text.strip()))
    await state.set_state(AddMovieState.description)
    await message.answer(
        "🔟 Qisqacha ta'rif kiriting yoki o'tkazib yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ O'tkazish", callback_data="desc_skip")]
        ])
    )

@router.callback_query(F.data == "desc_skip", AddMovieState.description)
async def desc_skip(cb: CallbackQuery, state: FSMContext):
    await state.update_data(description="")
    await state.set_state(AddMovieState.media)
    data = await state.get_data()
    ep_info = f"\n📺 Qismlar: {data.get('total_episodes',1)} ta" if data.get('total_episodes',1) > 1 else ""
    await cb.message.edit_text(
        f"✅ <b>Ma'lumotlar tayyor!</b>\n\n"
        f"🎬 {data['title']} | <code>{data['code']}</code>{ep_info}\n\n"
        f"📎 Endi kino faylini yuboring:",
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(AddMovieState.description)
async def add_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AddMovieState.media)
    data = await state.get_data()
    await message.answer(
        f"✅ <b>Ma'lumotlar tayyor!</b>\n\n"
        f"🎬 {data['title']} | <code>{data['code']}</code>\n\n"
        f"📎 Endi kino faylini yuboring:",
        parse_mode="HTML"
    )

@router.message(AddMovieState.media, F.video | F.document | F.animation)
async def add_media(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    tid = data["topic_id"]
    caption = f"🎬 {data['title']}\n🔢 #{data['code']}"

    try:
        if message.video:
            sent = await bot.send_video(DB_GROUP_ID, message.video.file_id, caption=caption, message_thread_id=tid)
        elif message.document:
            sent = await bot.send_document(DB_GROUP_ID, message.document.file_id, caption=caption, message_thread_id=tid)
        else:
            sent = await bot.send_animation(DB_GROUP_ID, message.animation.file_id, caption=caption, message_thread_id=tid)

        total_ep = data.get("total_episodes", 1)
        status = data.get("status", "completed")
        if data.get("ep_type") == "ongoing": status = "ongoing"

        ep_type = data.get("ep_type", "single")
        db.add_movie(
            data["code"], data["title"], tid, sent.message_id,
            data.get("year",""), data.get("country",""), data.get("language",""),
            data.get("format_",""), "", data.get("description",""),
            data.get("tags",""), message.from_user.id, ep_type
        )
        # Status va qismlar sonini yangilash
        movie = db.get_movie_by_code(data["code"])
        db.update_movie(movie["id"], total_episodes=total_ep, status=status)

        # Qismni episodes ga qo'shish (start_ep dan boshlanadi)
        db.init_episodes()
        start_ep = data.get("start_ep", 1)
        db.add_episode(movie["id"], start_ep, sent.message_id, tid)
        db.update_movie(movie["id"], total_episodes=start_ep)
        db.audit(message.from_user.id, "add_movie", data["code"], data["title"])

        # Admin uchun kino kartasi
        bot_info = await bot.get_me()
        await state.update_data(movie_id=movie["id"], bot_username=bot_info.username)
        await state.set_state(AddMovieState.ask_channel)

        # Admin uchun preview
        card = format_movie_card(dict(movie), 1)
        await message.answer(
            f"✅ <b>Kino qo'shildi!</b>\n\n{card}",
            reply_markup=after_movie_add_kb(movie["id"]),
            parse_mode="HTML"
        )

        try:
            await bot.send_message(DB_GROUP_ID,
                f"✅ Yangi kino: {data['title']} | #{data['code']}",
                message_thread_id=TOPIC_ADMIN_LOGS)
        except: pass

    except Exception as e:
        await state.clear()
        await message.answer(f"❌ Xato: {e}")

# ── Kanalga yuborish ──────────────────────────────────
@router.callback_query(F.data.startswith("send_to_channel_"))
async def ask_thumbnail(cb: CallbackQuery, state: FSMContext):
    movie_id = int(cb.data.replace("send_to_channel_",""))
    await state.update_data(movie_id=movie_id)
    await state.set_state(AddMovieState.thumbnail)
    await cb.message.edit_text(
        "🖼 Thumbnail (muqova rasm) yuboring:\n\n"
        "<i>Rasm, GIF yoki video yuborishingiz mumkin.\n"
        "Kinoning o'zini yubormang!</i>",
        reply_markup=thumbnail_kb(),
        parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data == "no_thumbnail", AddMovieState.thumbnail)
async def send_channel_no_thumb(cb: CallbackQuery, state: FSMContext, bot: Bot):
    await _send_to_channel(cb.message, state, bot, None)
    await cb.answer()

@router.message(AddMovieState.thumbnail, F.photo | F.animation | F.video)
async def send_channel_with_thumb(message: Message, state: FSMContext, bot: Bot):
    if message.photo:
        thumb = message.photo[-1].file_id
        thumb_type = "photo"
    elif message.animation:
        thumb = message.animation.file_id
        thumb_type = "animation"
    else:
        thumb = message.video.file_id
        thumb_type = "video"
    await _send_to_channel(message, state, bot, (thumb_type, thumb))

async def _send_to_channel(message, state, bot, thumb):
    data = await state.get_data()
    await state.clear()
    movie_id = data.get("movie_id")
    movie = db.get_movie_by_code(
        db.get_conn().execute("SELECT code FROM movies WHERE id=?", (movie_id,)).fetchone()["code"]
    ) if movie_id else None

    if not movie:
        await message.answer("❌ Kino topilmadi."); return

    bot_info = await bot.get_me()
    card = format_movie_card(dict(movie), 1)
    markup = channel_post_keyboard(bot_info.username, movie["code"])

    channels = db.get_required_channels()
    if not channels:
        await message.answer("❌ Majburiy kanal yo'q! Avval kanal qo'shing."); return

    for ch in channels:
        try:
            if thumb:
                thumb_type, thumb_id = thumb
                if thumb_type == "photo":
                    await bot.send_photo(ch["channel_id"], thumb_id, caption=card,
                                         reply_markup=markup, parse_mode="HTML")
                elif thumb_type == "animation":
                    await bot.send_animation(ch["channel_id"], thumb_id, caption=card,
                                             reply_markup=markup, parse_mode="HTML")
                else:
                    await bot.send_video(ch["channel_id"], thumb_id, caption=card,
                                         reply_markup=markup, parse_mode="HTML")
            else:
                await bot.send_message(ch["channel_id"], card,
                                       reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            await message.answer(f"❌ {ch['channel_name']} ga yuborishda xato: {e}")

    await message.answer(
        f"✅ Kanal(lar)ga yuborildi!\n🎬 {movie['title']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Admin panel", callback_data="adm_movies")]
        ])
    )

# ── Qism qo'shish ─────────────────────────────────────
class AddEpisodeNumState(StatesGroup):
    num   = State()
    media = State()

@router.callback_query(F.data.startswith("add_ep_"))
async def add_episode_start(cb: CallbackQuery, state: FSMContext):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    movie_id = int(cb.data.replace("add_ep_",""))
    last_ep = db.get_last_episode_num(movie_id)
    conn = db.get_conn()
    movie = conn.execute("SELECT title FROM movies WHERE id=?", (movie_id,)).fetchone()
    conn.close()
    await state.update_data(movie_id=movie_id, last_ep=last_ep)
    await state.set_state(AddEpisodeNumState.num)
    await cb.message.answer(
        f"➕ <b>{movie['title']}</b>\n\n"
        f"Hozirda {last_ep} ta qism bor.\n"
        f"Nechanchi qismni qo'shmoqchisiz?\n"
        f"<i>Keyingisi: {last_ep+1}</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"✅ {last_ep+1}-qism (keyingisi)",
                callback_data=f"ep_num_auto_{last_ep+1}"
            )],
        ]),
        parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data.startswith("ep_num_auto_"), AddEpisodeNumState.num)
async def ep_num_auto(cb: CallbackQuery, state: FSMContext):
    ep_num = int(cb.data.replace("ep_num_auto_",""))
    data = await state.get_data()
    await state.update_data(next_ep=ep_num)
    await state.set_state(AddEpisodeState.media)
    conn = db.get_conn()
    movie = conn.execute("SELECT title FROM movies WHERE id=?", (data["movie_id"],)).fetchone()
    conn.close()
    await cb.message.edit_text(
        f"✅ {ep_num}-qism\n\n📎 Fayl yuboring:",
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(AddEpisodeNumState.num)
async def ep_num_manual(message: Message, state: FSMContext):
    try:
        ep_num = int(message.text.strip())
        if ep_num < 1:
            await message.answer("❌ Kamida 1 bo'lishi kerak!"); return
        data = await state.get_data()
        await state.update_data(next_ep=ep_num)
        await state.set_state(AddEpisodeState.media)
        conn = db.get_conn()
        movie = conn.execute("SELECT title FROM movies WHERE id=?", (data["movie_id"],)).fetchone()
        conn.close()
        await message.answer(
            f"✅ {ep_num}-qism\n\n📎 Fayl yuboring:",
            parse_mode="HTML"
        )
    except:
        await message.answer("❌ Raqam kiriting!")

@router.message(AddEpisodeState.media, F.video | F.document | F.animation)
async def add_episode_media(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    movie_id = data["movie_id"]
    ep_num = data["next_ep"]

    movie = db.get_conn().execute("SELECT * FROM movies WHERE id=?", (movie_id,)).fetchone()
    tid = movie["topic_id"]
    caption = f"🎬 {movie['title']} — {ep_num}-qism\n🔢 #{movie['code']}"

    try:
        if message.video:
            sent = await bot.send_video(DB_GROUP_ID, message.video.file_id, caption=caption, message_thread_id=tid)
        elif message.document:
            sent = await bot.send_document(DB_GROUP_ID, message.document.file_id, caption=caption, message_thread_id=tid)
        else:
            sent = await bot.send_animation(DB_GROUP_ID, message.animation.file_id, caption=caption, message_thread_id=tid)

        db.add_episode(movie_id, ep_num, sent.message_id, tid)
        total = db.get_episode_count(movie_id)
        db.audit(message.from_user.id, "add_episode", movie["code"], f"ep{ep_num}")

        await message.answer(
            f"✅ {ep_num}-qism qo'shildi!\n"
            f"🎬 {movie['title']} — jami {total} qism",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Yana qism qo'shish", callback_data=f"add_ep_{movie_id}")],
                [InlineKeyboardButton(text="🎬 Admin panel", callback_data="adm_movies")],
            ])
        )
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")

# ── Ro'yxat ───────────────────────────────────────────
@router.callback_query(F.data == "adm_list_movies")
async def list_movies(cb: CallbackQuery):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    movies = db.list_movies(limit=10)
    if not movies:
        await cb.answer("Hozircha kino yo'q!", show_alert=True); return
    text = "🎬 <b>Oxirgi 10 kino:</b>\n\n"
    for m in movies:
        _et = m.get('episode_type','single'); _ep = m.get('total_episodes',1); ep = f" ({_ep} qism, Serial)" if (_et in ('multi','ongoing') or m.get('status')=='ongoing' or _ep > 1) else " (Film)"
        text += f"• <code>{m['code']}</code> — {m['title']}{ep} | 📥{m['downloads']}\n"
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_movies")]
    ]))
    await cb.answer()

# ── O'chirish ─────────────────────────────────────────
@router.callback_query(F.data.startswith("delete_movie_"))
async def delete_confirm(cb: CallbackQuery):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    mid = int(cb.data.replace("delete_movie_",""))
    await cb.message.answer("⚠️ Kinoni o'chirishni tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ha", callback_data=f"confirm_del_{mid}"),
             InlineKeyboardButton(text="❌ Yo'q", callback_data="back_main")],
        ]))
    await cb.answer()

@router.callback_query(F.data.startswith("confirm_del_"))
async def delete_exec(cb: CallbackQuery, bot: Bot):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    mid = int(cb.data.replace("confirm_del_",""))
    movie_info = db.delete_movie(mid)
    db.audit(cb.from_user.id, "delete_movie", str(mid))

    # DB guruhidagi xabarni ham o'chirish
    if movie_info and movie_info.get("message_id"):
        try:
            await bot.delete_message(DB_GROUP_ID, movie_info["message_id"])
        except Exception:
            pass  # Allaqachon o'chirilgan yoki ruxsat yo'q

    await cb.message.edit_text("✅ Kino o'chirildi (DB dan ham).")
    await cb.answer()

# ── Tahrirlash ────────────────────────────────────────
@router.callback_query(F.data.startswith("edit_movie_"))
async def edit_movie(cb: CallbackQuery, state: FSMContext):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    mid = int(cb.data.replace("edit_movie_",""))
    await state.update_data(movie_id=mid)
    await state.set_state(EditMovieState.field)
    await cb.message.answer("✏️ Qaysi maydonni tahrirlaysiz?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Nom", callback_data="ef_title"),
             InlineKeyboardButton(text="📅 Yil", callback_data="ef_year")],
            [InlineKeyboardButton(text="🌍 Davlat", callback_data="ef_country"),
             InlineKeyboardButton(text="🗣 Til", callback_data="ef_language")],
            [InlineKeyboardButton(text="🏷 Fishkalar", callback_data="ef_tags"),
             InlineKeyboardButton(text="📝 Ta'rif", callback_data="ef_description")],
            [InlineKeyboardButton(text="📺 Qism soni", callback_data="ef_total_episodes"),
             InlineKeyboardButton(text="🔖 Holati", callback_data="ef_status_btn")],
            [InlineKeyboardButton(text="❌ Bekor", callback_data="back_main")],
        ]))
    await cb.answer()

@router.callback_query(F.data == "ef_status_btn", EditMovieState.field)
async def edit_status(cb: CallbackQuery, state: FSMContext):
    await state.update_data(field="status")
    await state.set_state(EditMovieState.value)
    await cb.message.edit_text("Yangi holatni tanlang:", reply_markup=movie_status_kb())
    await cb.answer()

@router.callback_query(F.data.startswith("mstatus_"), EditMovieState.value)
async def edit_status_val(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data(); await state.clear()
    val = cb.data.replace("mstatus_","")
    db.update_movie(data["movie_id"], status=val)
    await cb.message.edit_text(f"✅ Holati yangilandi!")
    await cb.answer()

@router.callback_query(F.data.startswith("ef_"), EditMovieState.field)
async def edit_field(cb: CallbackQuery, state: FSMContext):
    field = cb.data.replace("ef_","")
    await state.update_data(field=field)
    await state.set_state(EditMovieState.value)
    await cb.message.edit_text(f"Yangi {field} qiymatini yuboring:")
    await cb.answer()

@router.message(EditMovieState.value)
async def edit_value(message: Message, state: FSMContext):
    data = await state.get_data(); await state.clear()
    field = data["field"]
    val = message.text.strip()
    if field == "tags": val = parse_tags(val)
    elif field == "total_episodes":
        try: val = int(val)
        except: await message.answer("❌ Raqam kiriting"); return
    db.update_movie(data["movie_id"], **{field: val})
    db.audit(message.from_user.id, "edit_movie", str(data["movie_id"]), f"{field}={val}")
    await message.answer(f"✅ Yangilandi!", reply_markup=admin_menu())

# ── Trending ─────────────────────────────────────────
@router.callback_query(F.data == "adm_trending")
async def trending_manage(cb: CallbackQuery):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    await cb.message.edit_text(
        "🔝 <b>Trending boshqaruv</b>\n\n"
        "Trend qilish: kino kodini yuboring\n"
        "Bekor qilish: <code>-KOD</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_movies")]
        ])
    )
    await cb.answer()

# ── Kino yangilash ────────────────────────────────────
@router.callback_query(F.data == "adm_update_movie")
async def update_start(cb: CallbackQuery, state: FSMContext):
    if not db.is_admin(cb.from_user.id): return await cb.answer("❌")
    await state.set_state(UpdateMediaState.code)
    await cb.message.edit_text("🔄 Yangilamoqchi bo'lgan kino kodini yuboring:")
    await cb.answer()

@router.message(UpdateMediaState.code)
async def update_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    movie = db.get_movie_by_code(code)
    if not movie:
        await message.answer(f"❌ <b>{code}</b> topilmadi.", parse_mode="HTML"); return
    await state.update_data(movie_id=movie["id"], code=code, topic_id=movie["topic_id"])
    await state.set_state(UpdateMediaState.media)
    await message.answer(f"✅ <b>{movie['title']}</b>\n\nYangi fayl yuboring:", parse_mode="HTML")

@router.message(UpdateMediaState.media, F.video | F.document | F.animation)
async def update_media(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data(); await state.clear()
    movie = db.get_movie_by_code(data["code"])
    caption = f"🎬 {movie['title']}\n🔢 #{movie['code']}"
    try:
        if message.video:
            sent = await bot.send_video(DB_GROUP_ID, message.video.file_id, caption=caption, message_thread_id=data["topic_id"])
        elif message.document:
            sent = await bot.send_document(DB_GROUP_ID, message.document.file_id, caption=caption, message_thread_id=data["topic_id"])
        else:
            sent = await bot.send_animation(DB_GROUP_ID, message.animation.file_id, caption=caption, message_thread_id=data["topic_id"])
        db.update_movie(data["movie_id"], message_id=sent.message_id)
        db.audit(message.from_user.id, "update_movie", data["code"])
        await message.answer(f"✅ <b>{movie['title']}</b> yangilandi!", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")
