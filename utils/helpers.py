from datetime import date, timedelta
from config import GENRES

def get_plan_until(current_until, days):
    today = str(date.today())
    base = current_until if current_until and current_until >= today else today
    return str(date.fromisoformat(base) + timedelta(days=days))

def plan_badge(plan, until, lang="uz"):
    today = str(date.today())
    if plan == "vip" and until and until >= today: return "👑 VIP"
    if plan == "pro" and until and until >= today: return "💎 PRO"
    if plan == "banned": return "🚫 Ban"
    return "🆓 Free"

def is_plan_active(plan, until):
    return plan in ("pro","vip") and until and until >= str(date.today())

def status_emoji(status: str) -> str:
    return {"completed": "✅ Tugallangan", "ongoing": "🔄 Davom etmoqda", "announced": "📢 Tez kunda"}.get(status, "✅")

def format_movie_card(movie, episode_num=1, lang="uz") -> str:
    """Chiroyli kino kartochkasi — hashtagsiz"""
    genre_name = GENRES.get(movie.get("topic_id"), ("🎬 Kino",""))[0]
    ur = float(movie.get("user_rating") or 0)
    rc = int(movie.get("rating_count") or 0)
    total_ep = int(movie.get("total_episodes") or 1)
    status = status_emoji(movie.get("status","completed"))
    stars = "★" * int(round(ur)) + "☆" * (5 - int(round(ur))) if ur > 0 else "☆☆☆☆☆"

    # Til bayrog'i
    lang_flags = {
        "o'zbek": "🇺🇿", "uzbek": "🇺🇿", "uz": "🇺🇿",
        "rus": "🇷🇺", "russian": "🇷🇺", "ru": "🇷🇺",
        "ingliz": "🇬🇧", "english": "🇬🇧", "en": "🇬🇧",
        "turk": "🇹🇷", "turkish": "🇹🇷",
        "koreys": "🇰🇷", "korean": "🇰🇷",
    }
    movie_lang = movie.get("language","") or ""
    flag = lang_flags.get(movie_lang.lower(), "🌐")

    # Qism ma'lumoti
    ep_type = movie.get("episode_type", "single")
    is_serial = ep_type in ("multi", "ongoing") or movie.get("status") == "ongoing" or total_ep > 1
    if not is_serial and total_ep == 1:
        ep_text = "1 ta (Film)"
    elif movie.get("status") == "ongoing":
        ep_text = f"{total_ep} ta qism (Davom etmoqda)"
    else:
        ep_text = f"{total_ep} ta qism (Serial)"

    lines = [
        f"🎬  <b>{movie['title']}</b>",
        f"{flag}  {movie_lang} tili ✅" if movie_lang else "",
        "╭─────────────────────",
        f"├‣  🔢  Kod:       <code>{movie['code']}</code>",
        f"├‣  🎭  Janr:      {genre_name}",
        f"├‣  📺  Qism:      {ep_text}",
    ]
    if total_ep > 1:
        lines.append(f"├‣  📍  Joriy:     {episode_num}/{total_ep} qism")
    lines.append(f"├‣  🔖  Holati:    {status}")
    if movie.get("year"):
        lines.append(f"├‣  📅  Yil:       {movie['year']}")
    if movie.get("country"):
        lines.append(f"├‣  🌍  Davlat:    {movie['country']}")
    if movie.get("format"):
        lines.append(f"├‣  🎞  Sifat:     {movie['format']}")
    if ur > 0:
        lines.append(f"├‣  ⭐  Reyting:   {stars} {ur:.1f}/5  ({rc} ovoz)")
    lines.append("╰─────────────────────")
    if movie.get("description"):
        lines.append(f"\n📝  <i>{movie['description']}</i>")
    lines.append(f"\n📥  <b>{movie.get('downloads',0)}</b> marta tomosha qilindi")
    return "\n".join([l for l in lines if l != ""])

def format_movie_info(movie, lang="uz", show_tags=False):
    """Orqaga moslik uchun"""
    return format_movie_card(movie, lang=lang)

def parse_tags(tags_str):
    if not tags_str: return ""
    tags = [f"#{t.strip().lower().lstrip('#')}" for t in tags_str.replace(","," ").split() if t.strip()]
    return " ".join(tags)

def deep_link(bot_username, code):
    return f"https://t.me/{bot_username}?start=movie_{code}"

def get_lang(user_id):
    import database as db
    return db.get_user_lang(user_id)

def auto_code(title: str) -> str:
    import re, database as db
    base = re.sub(r'[^a-zA-Z0-9]', '', title.upper())[:6]
    if not base: base = "FILM"
    code = base
    i = 1
    while db.get_movie_by_code(code):
        code = f"{base}{i}"
        i += 1
    return code

def format_limit_text(limit: int) -> str:
    if limit >= 999999: return "♾️ Cheksiz"
    return f"{limit} ta"

def days_left(until: str) -> int:
    if not until: return 0
    try:
        delta = date.fromisoformat(until) - date.today()
        return max(0, delta.days)
    except: return 0
