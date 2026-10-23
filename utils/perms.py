"""Ruxsatlar (RBAC): har admin uchun alohida ruxsatlar, callback -> ruxsat xaritasi, xavfli amallar ro'yxati."""
import re

import database as db
from config import SUPERADMIN_ID, ADMIN_IDS

PERMS = {
    "stats":     "📊 Statistika",
    "audit":     "📋 Audit",
    "users":     "👥 Foydalanuvchilar",
    "ban":       "🚫 Ban/Unban",
    "grant":     "🎁 Reja/limit/ball",
    "message":   "📨 Xabar yuborish",
    "movies":    "🎬 Kinolar",
    "broadcast": "📣 Reklama",
    "channels":  "📢 Kanallar",
    "promo":     "🎟 Promo",
    "payments":  "💳 To'lovlar",
    "export":    "📤 Eksport",
    "settings":  "⚙️ Sozlamalar",
}
PRESETS = {
    "full":      ("👑 To'liq admin", set(PERMS)),
    "moderator": ("🛠 Moderator", {"stats", "users", "movies", "message"}),
    "viewer":    ("👁 Kuzatuvchi", {"stats", "users"}),
}

# (regex, ruxsat). Birinchi mos kelgan ishlaydi. "super" = faqat superadmin.
_RULES = [(re.compile(p), perm) for p, perm in [
    (r"^(adm_admins|adm_add_admin|adm_remove_admin)$|^role_|^sa_", "super"),
    (r"^dash_rep_", "export"),
    (r"^(adm_stats|adm_missing)$|^dash_", "stats"),
    (r"^adm_audit$|^au_", "audit"),
    (r"^(adm_users|adm_user_lookup)$|^users_page_|^adm_user_\d+$|^lqr?_|^un_|^ut_", "users"),
    (r"^(ban|unban)_\d+$", "ban"),
    (r"^(give_plan|give_limit|give_points)_|^gp_", "grant"),
    (r"^msg_user_|^adm_notify$", "message"),
    (r"^(adm_movies|adm_add_movie|adm_list_movies|adm_trending|adm_update_movie|adm_tags|adm_duplicates)$"
     r"|^(amovie_genre|code_auto|add_ep|ep_num_auto|send_to_channel|delete_movie|confirm_del|edit_movie|mlang|afmt|mstatus|ef)_"
     r"|^(code_manual|ep_type_single|ep_type_multi|ep_type_ongoing|year_skip|country_skip|tags_skip|desc_skip|no_thumbnail|ef_status_btn)$",
     "movies"),
    (r"^(adm_broadcast|bc_all|bc_targeted|bc_clear|bc_send_now|bc_scheduled|bc_specific|sched_next)$|^(bct|scht|send_specific)_", "broadcast"),
    (r"^(adm_channels|adm_add_ch)$|^del_ch_", "channels"),
    (r"^(adm_promos|adm_create_promo|adm_del_promo)$|^pt_", "promo"),
    (r"^approve_pay:|^decline_pay:|^ref_approve_|^ref_decline_|^adm_requests$", "payments"),
    (r"^(adm_export|exp_users|exp_payments|exp_movies)$", "export"),
    (r"^adm_settings$|^sett_", "settings"),
]]

# Xavfli amallar: bajarishdan oldin "Tasdiqlang" ekrani (regex, matn)
_DANGEROUS = [(re.compile(p), text) for p, text in [
    (r"^ban_\d+$", "🚫 Foydalanuvchi <b>BAN</b> qilinadi (botdan foydalana olmaydi)."),
    (r"^gp_", "🎁 Foydalanuvchiga <b>pullik reja</b> beriladi."),
    (r"^bc_send_now$", "📣 Xabar tanlangan foydalanuvchilarga <b>YUBORILADI</b> (qaytarib bo'lmaydi)."),
    (r"^send_specific_", "📣 Xabar tanlangan foydalanuvchilarga <b>YUBORILADI</b>."),
    (r"^sett_toggle_maint$", "🛠 <b>Texnik rejim</b> holati o'zgaradi (bot hamma uchun to'xtashi mumkin)."),
    (r"^del_ch_", "🗑 Majburiy <b>kanal o'chiriladi</b>."),
    (r"^approve_pay:", "✅ To'lov <b>tasdiqlanadi</b> va reja beriladi."),
    (r"^sa_sayY$", "✍️ Xabar <b>bot nomidan</b> chatga yuboriladi."),
]]

# PIN talab qiladigan sohalar (PIN o'rnatilgan bo'lsa)
_PIN_RE = re.compile(r"^sa_|^(adm_admins|adm_add_admin|adm_remove_admin)$|^role_")


def required_perm(data: str):
    for rx, perm in _RULES:
        if rx.search(data or ""):
            return perm
    return None


def confirm_text(data: str):
    for rx, text in _DANGEROUS:
        if rx.search(data or ""):
            return text
    return None


def needs_pin(data: str) -> bool:
    return bool(_PIN_RE.search(data or ""))


def effective_perms(admin_row) -> set:
    """admins qatoridan ruxsatlar to'plami. perms NULL bo'lsa eski rol/can_* maydonlaridan hosil qilinadi."""
    raw = admin_row["perms"] if "perms" in admin_row.keys() else None
    if raw is not None:
        return {p for p in raw.split(",") if p in PERMS}
    if (admin_row["role"] or "admin") == "moderator":
        s = set(PRESETS["moderator"][1])
        if admin_row["can_ban"]: s.add("ban")
        if admin_row["can_broadcast"]: s.add("broadcast")
        if not (admin_row["can_add"] or admin_row["can_delete"]): s.discard("movies")
        return s
    return set(PERMS)


def get_perms(user_id: int) -> set:
    if SUPERADMIN_ID and user_id == SUPERADMIN_ID:
        return set(PERMS) | {"super"}
    if user_id in ADMIN_IDS:                    # .env dagi adminlar: to'liq admin (superadmin emas)
        return set(PERMS)
    a = db.get_admin(user_id)
    return effective_perms(a) if a else set()


def has_perm(user_id: int, perm: str) -> bool:
    return perm in get_perms(user_id)
