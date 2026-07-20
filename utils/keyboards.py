from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import GENRES, REQUIRED_CHANNEL_URL
from locales import t, LANG_BUTTONS

# ── Asosiy menyu (soddalashtirilgan) ──────────────────
def main_menu(lang="uz") -> InlineKeyboardMarkup:
    extra_texts = {
        "uz": "➕ Qo'shimcha", "ru": "➕ Дополнительно",
        "en": "➕ More", "tr": "➕ Daha fazla"
    }
    vip_texts = {
        "uz": "👑 VIP Club", "ru": "👑 VIP Клуб",
        "en": "👑 VIP Club", "tr": "👑 VIP Kulübü"
    }
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("menu_search",lang), callback_data="search"),
         InlineKeyboardButton(text=t("menu_trending",lang), callback_data="trending")],
        [InlineKeyboardButton(text=t("menu_random",lang), callback_data="random_movie"),
         InlineKeyboardButton(text=vip_texts.get(lang,"👑 VIP Club"), callback_data="vip_club")],
        [InlineKeyboardButton(text=t("menu_plans",lang), callback_data="plans"),
         InlineKeyboardButton(text=t("menu_profile",lang), callback_data="profile")],
        [InlineKeyboardButton(text=extra_texts.get(lang,"➕ Qo'shimcha"), callback_data="extra_menu")],
    ])

def extra_menu(lang="uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("menu_promo",lang), callback_data="promo"),
         InlineKeyboardButton(text=t("menu_referral",lang), callback_data="referral")],
        [InlineKeyboardButton(text=t("menu_favorites",lang), callback_data="favorites"),
         InlineKeyboardButton(text=t("menu_leaderboard",lang), callback_data="leaderboard")],
        [InlineKeyboardButton(text=t("menu_request",lang), callback_data="request_movie"),
         InlineKeyboardButton(text=t("menu_channel",lang), url=REQUIRED_CHANNEL_URL)],
        [InlineKeyboardButton(text=t("menu_language",lang), callback_data="set_language"),
         InlineKeyboardButton(text=t("menu_help",lang), callback_data="help")],
        [InlineKeyboardButton(text=t("back",lang), callback_data="back_main")],
    ])

def back_main(lang="uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("home",lang), callback_data="back_main")]
    ])

def search_menu(lang="uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔢 Kod orqali", callback_data="search_by_code"),
         InlineKeyboardButton(text="🔤 Nom bo'yicha", callback_data="search_by_name")],
        [InlineKeyboardButton(text="🎭 Tur bo'yicha", callback_data="browse_media"),
         InlineKeyboardButton(text="🎲 Tasodifiy", callback_data="random_movie")],
        [InlineKeyboardButton(text="📢 Kanaldan topish", url=REQUIRED_CHANNEL_URL)],
        [InlineKeyboardButton(text=t("home", lang), callback_data="back_main")],
    ])

def media_type_keyboard(lang="uz") -> InlineKeyboardMarkup:
    from config import (TOPIC_FILMLAR, TOPIC_SERIALLAR, TOPIC_DRAMALAR, TOPIC_MULTFILMLAR,
                        TOPIC_ANIMELAR, TOPIC_HUJJATLI, TOPIC_MINI_SERIAL, TOPIC_STANDUP,
                        TOPIC_KONSERT, TOPIC_BOLALAR, TOPIC_SPORT, TOPIC_KOMEDIYA,
                        TOPIC_TRILLER, TOPIC_ANIMATSION)
    rows = [
        [(t("media_film",lang), TOPIC_FILMLAR),        (t("media_serial",lang), TOPIC_SERIALLAR)],
        [(t("media_drama",lang), TOPIC_DRAMALAR),      (t("media_cartoon",lang), TOPIC_MULTFILMLAR)],
        [(t("media_anime",lang), TOPIC_ANIMELAR),      (t("media_documentary",lang), TOPIC_HUJJATLI)],
        [(t("media_miniserial",lang), TOPIC_MINI_SERIAL),(t("media_standup",lang), TOPIC_STANDUP)],
        [(t("media_concert",lang), TOPIC_KONSERT),     (t("media_kids",lang), TOPIC_BOLALAR)],
        [(t("media_sport",lang), TOPIC_SPORT),         (t("media_comedy",lang), TOPIC_KOMEDIYA)],
        [(t("media_thriller",lang), TOPIC_TRILLER),    ("🎮 Animatsion", TOPIC_ANIMATSION)],
    ]
    buttons = [[InlineKeyboardButton(text=n, callback_data=f"media_{tid}") for n,tid in row] for row in rows]
    buttons.append([InlineKeyboardButton(text=t("home",lang), callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def movies_list_keyboard(movies, lang="uz", back_cb="browse_media") -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(
        text=f"{'🔥' if m.get('is_trending') else '🎬'} {m['title']}",
        callback_data=f"get_movie_{m['code']}"
    )] for m in movies]
    buttons.append([
        InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_cb),
        InlineKeyboardButton(text=t("home",lang), callback_data="back_main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def movie_card_keyboard(movie_id, code, lang="uz", is_favorite=False,
                        is_admin=False, episode_num=1, total_episodes=1, topic_id=None):
    """Kino karta — navigatsiya + reyting"""
    buttons = []

    # Qism navigatsiyasi (faqat ko'p qismli bo'lsa)
    if total_episodes > 1:
        nav = []
        if episode_num > 1:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"ep_{movie_id}_{episode_num-1}"))
        nav.append(InlineKeyboardButton(
            text=f"📋 {episode_num}/{total_episodes}",
            callback_data=f"ep_list_{movie_id}"
        ))
        if episode_num < total_episodes:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"ep_{movie_id}_{episode_num+1}"))
        buttons.append(nav)

    # Reyting — 5 ta yulduz
    buttons.append([
        InlineKeyboardButton(text="⭐1", callback_data=f"dorat_{movie_id}_1"),
        InlineKeyboardButton(text="⭐2", callback_data=f"dorat_{movie_id}_2"),
        InlineKeyboardButton(text="⭐3", callback_data=f"dorat_{movie_id}_3"),
        InlineKeyboardButton(text="⭐4", callback_data=f"dorat_{movie_id}_4"),
        InlineKeyboardButton(text="⭐5", callback_data=f"dorat_{movie_id}_5"),
    ])

    # Sevimli + izoh
    fav_text = "💔 Olib tashlash" if is_favorite else "❤️ Sevimlilarga"
    fav_data = f"unfav_{movie_id}" if is_favorite else f"fav_{movie_id}"
    buttons.append([
        InlineKeyboardButton(text=fav_text, callback_data=fav_data),
        InlineKeyboardButton(text="💬 Izoh", callback_data=f"comment_{movie_id}"),
    ])

    # Kanal + bosh sahifa
    buttons.append([
        InlineKeyboardButton(text="📢 Kanalda ko'rish", url=REQUIRED_CHANNEL_URL),
        InlineKeyboardButton(text=t("home",lang), callback_data="back_main"),
    ])

    if is_admin:
        buttons.insert(0, [
            InlineKeyboardButton(text="✏️ Tahrir", callback_data=f"edit_movie_{movie_id}"),
            InlineKeyboardButton(text="➕ Qism qo'sh", callback_data=f"add_ep_{movie_id}"),
            InlineKeyboardButton(text="🗑 O'chir", callback_data=f"delete_movie_{movie_id}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def episode_list_keyboard(movie_id, episodes, current=1) -> InlineKeyboardMarkup:
    """Qismlar ro'yxati"""
    buttons = []
    row = []
    for ep in episodes:
        num = ep["episode_num"]
        mark = "▶️" if num == current else ""
        row.append(InlineKeyboardButton(
            text=f"{mark}{num}",
            callback_data=f"ep_{movie_id}_{num}"
        ))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def plans_keyboard(lang="uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 PRO 1 oy — ⭐30", callback_data="buy_pro_1m")],
        [InlineKeyboardButton(text="💎 PRO 3 oy — ⭐50", callback_data="buy_pro_3m")],
        [InlineKeyboardButton(text="👑 VIP 3 oy — ⭐100", callback_data="buy_vip_3m")],
        [InlineKeyboardButton(text="🎟 Limit +50 — ⭐50", callback_data="buy_limit_pack")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main")],
    ])

def limit_over_keyboard(lang="uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 PRO olish", callback_data="plans"),
         InlineKeyboardButton(text="🎟 Limit +50", callback_data="buy_limit_pack")],
        [InlineKeyboardButton(text="🤝 Referal bilan bepul", callback_data="referral")],
        [InlineKeyboardButton(text=t("home",lang), callback_data="back_main")],
    ])

def language_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=name, callback_data=f"lang_{code}")] for name,code in LANG_BUTTONS]
    buttons.append([InlineKeyboardButton(text=t("home",lang), callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def channel_post_keyboard(bot_username, code) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Ko'rish", url=f"https://t.me/{bot_username}?start=movie_{code}")]
    ])

def subscription_keyboard(channels, lang="uz", pending_code=None) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=f"📢 {ch['channel_name']}", url=ch["invite_link"])] for ch in channels]
    cb = f"check_subscription:{pending_code}" if pending_code else "check_subscription"
    buttons.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data=cb)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kinolar", callback_data="adm_movies"),
         InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="adm_users"),
         InlineKeyboardButton(text="👨‍💼 Adminlar", callback_data="adm_admins")],
        [InlineKeyboardButton(text="📢 Kanallar", callback_data="adm_channels"),
         InlineKeyboardButton(text="🎁 Promo", callback_data="adm_promos")],
        [InlineKeyboardButton(text="📣 Reklama", callback_data="adm_broadcast"),
         InlineKeyboardButton(text="🔔 Xabar", callback_data="adm_notify")],
        [InlineKeyboardButton(text="📩 So'rovlar", callback_data="adm_requests"),
         InlineKeyboardButton(text="🏷 Fishkalar", callback_data="adm_tags")],
        [InlineKeyboardButton(text="📤 Eksport", callback_data="adm_export"),
         InlineKeyboardButton(text="🔍 Dublikat", callback_data="adm_duplicates")],
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="adm_settings"),
         InlineKeyboardButton(text="📋 Audit", callback_data="adm_audit")],
    ])

def users_page_keyboard(users, page, total, lang="uz") -> InlineKeyboardMarkup:
    buttons = []
    for u in users:
        badge = "👑" if u["plan"]=="vip" else ("💎" if u["plan"]=="pro" else ("🚫" if u["is_banned"] else "🆓"))
        name = (u["full_name"] or u["username"] or str(u["user_id"]))[:22]
        buttons.append([InlineKeyboardButton(text=f"{badge} {name}", callback_data=f"adm_user_{u['user_id']}")])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="◀️", callback_data=f"users_page_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{(total-1)//10+1}", callback_data="noop"))
    if (page+1)*10 < total: nav.append(InlineKeyboardButton(text="▶️", callback_data=f"users_page_{page+1}"))
    if nav: buttons.append(nav)
    buttons.append([
        InlineKeyboardButton(text="🔍 Qidirish", callback_data="adm_user_lookup"),
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def user_actions_keyboard(user_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Plan", callback_data=f"give_plan_{user_id}"),
         InlineKeyboardButton(text="➕ Limit", callback_data=f"give_limit_{user_id}"),
         InlineKeyboardButton(text="🪙 Ball", callback_data=f"give_points_{user_id}")],
        [InlineKeyboardButton(text="📨 Xabar", callback_data=f"msg_user_{user_id}"),
         InlineKeyboardButton(text="🚫 Ban", callback_data=f"ban_{user_id}"),
         InlineKeyboardButton(text="✅ Unban", callback_data=f"unban_{user_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_users")],
    ])

def channels_keyboard(channels) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        buttons.append([
            InlineKeyboardButton(text=f"📢 {ch['channel_name']}", url=ch["invite_link"]),
            InlineKeyboardButton(text="🗑", callback_data=f"del_ch_{ch['channel_id']}"),
        ])
    buttons.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="adm_add_ch")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def add_movie_format_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="HD", callback_data="afmt_HD"),
         InlineKeyboardButton(text="Full HD", callback_data="afmt_FullHD"),
         InlineKeyboardButton(text="4K", callback_data="afmt_4K"),
         InlineKeyboardButton(text="CAM", callback_data="afmt_CAM")],
        [InlineKeyboardButton(text="TS 1080p", callback_data="afmt_TS1080p"),
         InlineKeyboardButton(text="WEB-DL", callback_data="afmt_WEBDL")],
        [InlineKeyboardButton(text="⏭ O'tkazish", callback_data="afmt_skip")],
    ])

def add_movie_rating_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{i}⭐", callback_data=f"arat_{i}") for i in range(1,6)],
        [InlineKeyboardButton(text="⏭ O'tkazish", callback_data="arat_skip")],
    ])

def episodes_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 1 qismli film", callback_data="ep_type_single")],
        [InlineKeyboardButton(text="📺 Ko'p qismli serial", callback_data="ep_type_multi")],
        [InlineKeyboardButton(text="🔄 Davom etmoqda (hali tugamagan)", callback_data="ep_type_ongoing")],
    ])

def movie_status_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tugallangan", callback_data="mstatus_completed")],
        [InlineKeyboardButton(text="🔄 Davom etmoqda", callback_data="mstatus_ongoing")],
        [InlineKeyboardButton(text="📢 Tez kunda", callback_data="mstatus_announced")],
    ])

def after_movie_add_kb(movie_id) -> InlineKeyboardMarkup:
    """Kino qo'shilgandan keyin"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga yuborish", callback_data=f"send_to_channel_{movie_id}"),
         InlineKeyboardButton(text="⏭ O'tkazish", callback_data="adm_movies")],
    ])

def thumbnail_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Thumbnail siz yuborish", callback_data="no_thumbnail")],
    ])
