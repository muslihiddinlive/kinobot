import sqlite3, os
from datetime import date, timedelta

# Railway/Render/hosting da persistent volume yo'li
# .env da DB_PATH=/data/kinobot.db qilib belgilang
# Agar yo'l mavjud bo'lmasa, papkani yaratamiz
DB_PATH = os.getenv("DB_PATH", "kinobot.db")

# DB papkasi mavjud bo'lmasa yaratamiz
_db_dir = os.path.dirname(DB_PATH)
if _db_dir and not os.path.exists(_db_dir):
    try:
        os.makedirs(_db_dir, exist_ok=True)
    except Exception:
        pass

def get_conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    conn = get_conn(); c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id         INTEGER PRIMARY KEY,
        username        TEXT, full_name TEXT,
        joined_at       TEXT DEFAULT (date('now')),
        plan            TEXT DEFAULT 'free',
        plan_until      TEXT,
        bought_limit    INTEGER DEFAULT 0,
        daily_used      INTEGER DEFAULT 0,
        last_used_date  TEXT DEFAULT (date('now')),
        referral_points REAL DEFAULT 0,
        referred_by     INTEGER,
        total_stars     INTEGER DEFAULT 0,
        is_banned       INTEGER DEFAULT 0,
        lang            TEXT DEFAULT 'uz',
        last_admin_msg  TEXT,
        greeting_index  INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS movies (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        code        TEXT UNIQUE, title TEXT,
        topic_id    INTEGER, message_id INTEGER,
        year TEXT, country TEXT, language TEXT,
        format TEXT, rating TEXT, description TEXT,
        tags TEXT, downloads INTEGER DEFAULT 0,
        is_trending INTEGER DEFAULT 0,
        user_rating REAL DEFAULT 0,
        rating_count INTEGER DEFAULT 0,
        added_by INTEGER,
        added_at TEXT DEFAULT (datetime('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS ratings (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER, movie_id INTEGER,
        rating   INTEGER, comment TEXT,
        rated_at TEXT DEFAULT (datetime('now')),
        UNIQUE(user_id, movie_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS favorites (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER, movie_id INTEGER,
        added_at TEXT DEFAULT (datetime('now')),
        UNIQUE(user_id, movie_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id      INTEGER PRIMARY KEY,
        username TEXT, full_name TEXT,
        role TEXT DEFAULT 'admin',
        can_add INTEGER DEFAULT 1,
        can_delete INTEGER DEFAULT 1,
        can_ban INTEGER DEFAULT 0,
        can_broadcast INTEGER DEFAULT 0,
        added_by INTEGER,
        added_at TEXT DEFAULT (datetime('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT
    )''')

    defaults = [
        ("free_daily_limit","5"), ("pro_daily_limit","10"),
        ("maintenance_mode","0"), ("maintenance_text","🔧 Texnik ishlar!"),
        ("welcome_text","🎬 Kino Botga xush kelibsiz!"),
        ("referral_points_for_pro","10"),
        ("weekly_report_chat",""), ("scheduled_broadcast",""),
    ]
    for k,v in defaults:
        c.execute("INSERT OR IGNORE INTO settings VALUES (?,?)",(k,v))

    c.execute('''CREATE TABLE IF NOT EXISTS required_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT UNIQUE, channel_name TEXT, invite_link TEXT
    )''')
    c.execute("INSERT OR IGNORE INTO required_channels VALUES (?,?,?,?)",
              (None,"@Yoqolganstudio","Yoqolgan Studio","https://t.me/Yoqolganstudio"))

    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE, reward_type TEXT, reward_value INTEGER,
        max_uses INTEGER DEFAULT 1, used_count INTEGER DEFAULT 0,
        expires_at TEXT, created_at TEXT DEFAULT (datetime('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS promo_uses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, code TEXT, used_at TEXT DEFAULT (datetime('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, stars INTEGER, plan TEXT,
        paid_at TEXT DEFAULT (datetime('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER, referred_id INTEGER,
        created_at TEXT DEFAULT (datetime('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS search_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, query TEXT, found INTEGER DEFAULT 0,
        searched_at TEXT DEFAULT (datetime('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS movie_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, request TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER, action TEXT, target TEXT,
        detail TEXT, done_at TEXT DEFAULT (datetime('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS bot_chats (
        chat_id   INTEGER PRIMARY KEY,
        chat_type TEXT,
        title     TEXT,
        added_at  TEXT DEFAULT (datetime('now'))
    )''')

    conn.commit(); conn.close()

# ── Settings ──────────────────────────────────────────
def get_setting(key,default=""):
    conn=get_conn(); r=conn.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone(); conn.close()
    return r["value"] if r else default

def set_setting(key,value):
    conn=get_conn(); conn.execute("INSERT OR REPLACE INTO settings VALUES (?,?)",(key,value)); conn.commit(); conn.close()

# ── Users ─────────────────────────────────────────────
def get_user(user_id):
    conn=get_conn(); r=conn.execute("SELECT * FROM users WHERE user_id=?",(user_id,)).fetchone(); conn.close(); return r

def register_user(user_id,username,full_name,referred_by=None):
    conn=get_conn()
    conn.execute("INSERT OR IGNORE INTO users (user_id,username,full_name,referred_by) VALUES (?,?,?,?)",
                 (user_id,username,full_name,referred_by))
    conn.commit(); conn.close()

def set_user_lang(user_id,lang):
    conn=get_conn(); conn.execute("UPDATE users SET lang=? WHERE user_id=?",(lang,user_id)); conn.commit(); conn.close()

def get_user_lang(user_id):
    conn=get_conn(); r=conn.execute("SELECT lang FROM users WHERE user_id=?",(user_id,)).fetchone(); conn.close()
    return r["lang"] if r else "uz"

def update_user_plan(user_id,plan,until,stars):
    conn=get_conn()
    conn.execute("UPDATE users SET plan=?,plan_until=?,total_stars=total_stars+? WHERE user_id=?",(plan,until,stars,user_id))
    if stars>0: conn.execute("INSERT INTO payments (user_id,stars,plan) VALUES (?,?,?)",(user_id,stars,plan))
    conn.commit(); conn.close()

def add_bought_limit(user_id,amount,stars):
    conn=get_conn()
    conn.execute("UPDATE users SET bought_limit=bought_limit+?,total_stars=total_stars+? WHERE user_id=?",(amount,stars,user_id))
    if stars>0: conn.execute("INSERT INTO payments (user_id,stars,plan) VALUES (?,?,?)",(user_id,stars,f"limit+{amount}"))
    conn.commit(); conn.close()

def get_daily_limit(user):
    from config import SUPERADMIN_ID, ADMIN_IDS
    if user["user_id"]==SUPERADMIN_ID or user["user_id"] in ADMIN_IDS or is_admin(user["user_id"]):
        return 999999
    free=int(get_setting("free_daily_limit","5")); pro=int(get_setting("pro_daily_limit","10"))
    today=str(date.today())
    conn=get_conn()
    if user["last_used_date"]!=today:
        conn.execute("UPDATE users SET daily_used=0,last_used_date=? WHERE user_id=?",(today,user["user_id"]))
        conn.commit(); daily_used=0
    else: daily_used=user["daily_used"]
    conn.close()
    plan=user["plan"]; until=user["plan_until"]
    if until and until<today and plan not in ("free","banned"): plan="free"
    base=999999 if plan=="vip" else (pro if plan=="pro" else free)
    return max(0, base+user["bought_limit"]-daily_used)

def use_one_limit(user_id):
    conn=get_conn(); conn.execute("UPDATE users SET daily_used=daily_used+1 WHERE user_id=?",(user_id,)); conn.commit(); conn.close()

def add_referral_points(user_id,points):
    conn=get_conn(); conn.execute("UPDATE users SET referral_points=referral_points+? WHERE user_id=?",(points,user_id)); conn.commit(); conn.close()

def deduct_referral_points(user_id,points):
    conn=get_conn(); conn.execute("UPDATE users SET referral_points=referral_points-? WHERE user_id=?",(points,user_id)); conn.commit(); conn.close()

def redeem_referral_points(user_id, points, plan_until):
    """Ballarni PRO tarifga almashtiradi — ATOMIK.
    WHERE shartida referral_points>=points tekshiriladi, shuning uchun
    ikki so'rov bir vaqtda kelsa ham (masalan tugma tez-tez bosilsa),
    faqat BITTASI muvaffaqiyatli bo'ladi (ballar yetarli bo'lgan
    birinchi UPDATE). rowcount orqali natija qaytariladi.
    """
    conn = get_conn()
    cur = conn.execute(
        "UPDATE users SET referral_points=referral_points-?,plan='pro',plan_until=? "
        "WHERE user_id=? AND referral_points>=?",
        (points, plan_until, user_id, points)
    )
    success = cur.rowcount > 0
    conn.commit(); conn.close()
    return success

def ban_user(user_id):
    conn=get_conn(); conn.execute("UPDATE users SET is_banned=1,plan='banned' WHERE user_id=?",(user_id,)); conn.commit(); conn.close()

def unban_user(user_id):
    conn=get_conn(); conn.execute("UPDATE users SET is_banned=0,plan='free' WHERE user_id=?",(user_id,)); conn.commit(); conn.close()

def get_all_users():
    conn=get_conn(); r=conn.execute("SELECT user_id FROM users WHERE is_banned=0").fetchall(); conn.close()
    return [u["user_id"] for u in r]

def get_users_page(offset=0,limit=10):
    conn=get_conn(); r=conn.execute("SELECT * FROM users ORDER BY joined_at DESC LIMIT ? OFFSET ?",(limit,offset)).fetchall(); conn.close(); return r

def get_users_count():
    conn=get_conn(); r=conn.execute("SELECT COUNT(*) as c FROM users").fetchone(); conn.close(); return r["c"]

def get_user_by_username(username):
    conn=get_conn(); r=conn.execute("SELECT * FROM users WHERE username=?",(username.lstrip("@"),)).fetchone(); conn.close(); return r

def update_last_admin_msg(user_id,today):
    conn=get_conn(); conn.execute("UPDATE users SET last_admin_msg=? WHERE user_id=?",(today,user_id)); conn.commit(); conn.close()

def get_stats():
    conn=get_conn()
    total=conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    pro=conn.execute("SELECT COUNT(*) as c FROM users WHERE plan='pro'").fetchone()["c"]
    vip=conn.execute("SELECT COUNT(*) as c FROM users WHERE plan='vip'").fetchone()["c"]
    banned=conn.execute("SELECT COUNT(*) as c FROM users WHERE is_banned=1").fetchone()["c"]
    today=str(date.today())
    new_today=conn.execute("SELECT COUNT(*) as c FROM users WHERE joined_at=?",(today,)).fetchone()["c"]
    total_stars=conn.execute("SELECT SUM(stars) as s FROM payments").fetchone()["s"] or 0
    total_movies=conn.execute("SELECT COUNT(*) as c FROM movies").fetchone()["c"]
    total_downloads=conn.execute("SELECT SUM(downloads) as s FROM movies").fetchone()["s"] or 0
    top_movies=conn.execute("SELECT title,code,downloads FROM movies ORDER BY downloads DESC LIMIT 5").fetchall()
    conn.close()
    return {"total":total,"pro":pro,"vip":vip,"banned":banned,"new_today":new_today,
            "total_stars":total_stars,"total_movies":total_movies,
            "total_downloads":total_downloads,"top_movies":top_movies}

def get_leaderboard(limit=10):
    conn=get_conn(); r=conn.execute("SELECT * FROM users WHERE total_stars>0 ORDER BY total_stars DESC LIMIT ?",(limit,)).fetchall(); conn.close(); return r

# ── Movies ────────────────────────────────────────────
def _ensure_episode_type_column():
    """episode_type kolonkasi yo'q bo'lsa qo'shadi (migration fallback)"""
    conn = get_conn()
    try:
        conn.execute("ALTER TABLE movies ADD COLUMN episode_type TEXT DEFAULT 'single'")
        conn.commit()
    except: pass
    conn.close()

def add_movie(code,title,topic_id,message_id,year,country,language,format_,rating,description,tags,added_by,episode_type="single"):
    _ensure_episode_type_column()
    conn=get_conn()
    conn.execute('''INSERT OR REPLACE INTO movies
        (code,title,topic_id,message_id,year,country,language,format,rating,description,tags,added_by,episode_type)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (code,title,topic_id,message_id,year,country,language,format_,rating,description,tags,added_by,episode_type))
    conn.commit(); conn.close()

def get_movie_by_code(code):
    conn=get_conn(); r=conn.execute("SELECT * FROM movies WHERE code=?",(code.upper(),)).fetchone(); conn.close(); return r

def search_movies(query):
    conn=get_conn(); q=f"%{query.lower()}%"
    r=conn.execute("SELECT * FROM movies WHERE lower(title) LIKE ? OR lower(code) LIKE ? OR lower(tags) LIKE ? ORDER BY is_trending DESC,downloads DESC LIMIT 10",(q,q,q)).fetchall()
    conn.close(); return r

def get_movies_by_topic(topic_id,limit=20):
    conn=get_conn(); r=conn.execute("SELECT * FROM movies WHERE topic_id=? ORDER BY is_trending DESC,downloads DESC LIMIT ?",(topic_id,limit)).fetchall(); conn.close(); return r

def get_random_movie(topic_id=None):
    conn=get_conn()
    if topic_id: r=conn.execute("SELECT * FROM movies WHERE topic_id=? ORDER BY RANDOM() LIMIT 1",(topic_id,)).fetchone()
    else: r=conn.execute("SELECT * FROM movies ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close(); return r

def get_trending_movies(limit=10):
    conn=get_conn(); r=conn.execute("SELECT * FROM movies WHERE is_trending=1 OR downloads>0 ORDER BY is_trending DESC,downloads DESC LIMIT ?",(limit,)).fetchall(); conn.close(); return r

def increment_downloads(movie_id):
    conn=get_conn(); conn.execute("UPDATE movies SET downloads=downloads+1 WHERE id=?",(movie_id,)); conn.commit(); conn.close()

def update_movie(movie_id,**kwargs):
    conn=get_conn()
    fields=", ".join(f"{k}=?" for k in kwargs)
    conn.execute(f"UPDATE movies SET {fields} WHERE id=?",list(kwargs.values())+[movie_id])
    conn.commit(); conn.close()

def delete_movie(movie_id):
    conn = get_conn()
    # Avval ma'lumotlarni olamiz (DB guruhidan o'chirish uchun)
    row = conn.execute("SELECT message_id, topic_id FROM movies WHERE id=?", (movie_id,)).fetchone()
    conn.execute("DELETE FROM movies WHERE id=?", (movie_id,))
    conn.execute("DELETE FROM episodes WHERE movie_id=?", (movie_id,))
    conn.execute("DELETE FROM favorites WHERE movie_id=?", (movie_id,))
    conn.execute("DELETE FROM ratings WHERE movie_id=?", (movie_id,))
    conn.commit(); conn.close()
    return dict(row) if row else None

def list_movies(topic_id=None,limit=20,offset=0):
    conn=get_conn()
    if topic_id: r=conn.execute("SELECT * FROM movies WHERE topic_id=? ORDER BY added_at DESC LIMIT ? OFFSET ?",(topic_id,limit,offset)).fetchall()
    else: r=conn.execute("SELECT * FROM movies ORDER BY added_at DESC LIMIT ? OFFSET ?",(limit,offset)).fetchall()
    conn.close(); return r

def set_trending(movie_id,value):
    conn=get_conn(); conn.execute("UPDATE movies SET is_trending=? WHERE id=?",(value,movie_id)); conn.commit(); conn.close()

def get_popular_tags(limit=10):
    conn=get_conn(); r=conn.execute("SELECT tags FROM movies WHERE tags!=''").fetchall(); conn.close()
    from collections import Counter
    all_tags=[]
    for row in r:
        all_tags.extend(row["tags"].split())
    return Counter(all_tags).most_common(limit)

# ── Ratings ───────────────────────────────────────────
def add_rating(user_id,movie_id,rating,comment=""):
    conn=get_conn()
    conn.execute("INSERT OR REPLACE INTO ratings (user_id,movie_id,rating,comment) VALUES (?,?,?,?)",(user_id,movie_id,rating,comment))
    avg=conn.execute("SELECT AVG(rating) as a, COUNT(*) as c FROM ratings WHERE movie_id=?",(movie_id,)).fetchone()
    conn.execute("UPDATE movies SET user_rating=?,rating_count=? WHERE id=?",(round(avg["a"],1),avg["c"],movie_id))
    conn.commit(); conn.close()

def get_user_rating(user_id,movie_id):
    conn=get_conn(); r=conn.execute("SELECT * FROM ratings WHERE user_id=? AND movie_id=?",(user_id,movie_id)).fetchone(); conn.close(); return r

# ── Favorites ─────────────────────────────────────────
def add_favorite(user_id,movie_id):
    conn=get_conn()
    conn.execute("INSERT OR IGNORE INTO favorites (user_id,movie_id) VALUES (?,?)",(user_id,movie_id))
    conn.commit(); conn.close()

def remove_favorite(user_id,movie_id):
    conn=get_conn(); conn.execute("DELETE FROM favorites WHERE user_id=? AND movie_id=?",(user_id,movie_id)); conn.commit(); conn.close()

def is_favorite(user_id,movie_id):
    conn=get_conn(); r=conn.execute("SELECT id FROM favorites WHERE user_id=? AND movie_id=?",(user_id,movie_id)).fetchone(); conn.close(); return r is not None

def get_favorites(user_id):
    conn=get_conn(); r=conn.execute("SELECT m.* FROM movies m JOIN favorites f ON m.id=f.movie_id WHERE f.user_id=? ORDER BY f.added_at DESC",(user_id,)).fetchall(); conn.close(); return r

# ── Admins ────────────────────────────────────────────
def get_all_admins():
    conn=get_conn(); r=conn.execute("SELECT * FROM admins").fetchall(); conn.close(); return r

def add_admin(user_id,username,full_name,role,can_add,can_delete,can_ban,can_broadcast,added_by):
    conn=get_conn()
    conn.execute("INSERT OR REPLACE INTO admins (user_id,username,full_name,role,can_add,can_delete,can_ban,can_broadcast,added_by) VALUES (?,?,?,?,?,?,?,?,?)",
                 (user_id,username,full_name,role,can_add,can_delete,can_ban,can_broadcast,added_by))
    conn.commit(); conn.close()

def remove_admin(user_id):
    conn=get_conn(); conn.execute("DELETE FROM admins WHERE user_id=?",(user_id,)); conn.commit(); conn.close()

def get_admin(user_id):
    conn=get_conn(); r=conn.execute("SELECT * FROM admins WHERE user_id=?",(user_id,)).fetchone(); conn.close(); return r

def is_admin(user_id):
    from config import SUPERADMIN_ID,ADMIN_IDS
    if user_id==SUPERADMIN_ID or user_id in ADMIN_IDS: return True
    return get_admin(user_id) is not None

# ── Channels ──────────────────────────────────────────
def get_required_channels():
    conn=get_conn(); r=conn.execute("SELECT * FROM required_channels").fetchall(); conn.close(); return r

def add_required_channel(channel_id,channel_name,invite_link):
    conn=get_conn(); conn.execute("INSERT OR IGNORE INTO required_channels (channel_id,channel_name,invite_link) VALUES (?,?,?)",(channel_id,channel_name,invite_link)); conn.commit(); conn.close()

def remove_required_channel(channel_id):
    conn=get_conn(); conn.execute("DELETE FROM required_channels WHERE channel_id=?",(channel_id,)); conn.commit(); conn.close()

# ── Promo ─────────────────────────────────────────────
def get_promo(code):
    conn=get_conn(); r=conn.execute("SELECT * FROM promo_codes WHERE code=?",(code,)).fetchone(); conn.close(); return r

def has_used_promo(user_id,code):
    conn=get_conn(); r=conn.execute("SELECT id FROM promo_uses WHERE user_id=? AND code=?",(user_id,code)).fetchone(); conn.close(); return r is not None

def use_promo(user_id,code):
    conn=get_conn(); conn.execute("UPDATE promo_codes SET used_count=used_count+1 WHERE code=?",(code,)); conn.execute("INSERT INTO promo_uses (user_id,code) VALUES (?,?)",(user_id,code)); conn.commit(); conn.close()

def create_promo(code,reward_type,reward_value,max_uses,expires_at):
    conn=get_conn(); conn.execute("INSERT INTO promo_codes (code,reward_type,reward_value,max_uses,expires_at) VALUES (?,?,?,?,?)",(code,reward_type,reward_value,max_uses,expires_at)); conn.commit(); conn.close()

def delete_promo(code):
    conn=get_conn(); conn.execute("DELETE FROM promo_codes WHERE code=?",(code,)); conn.commit(); conn.close()

def list_promos():
    conn=get_conn(); r=conn.execute("SELECT * FROM promo_codes ORDER BY created_at DESC").fetchall(); conn.close(); return r

# ── Referrals ─────────────────────────────────────────
def record_referral(referrer_id,referred_id):
    conn=get_conn(); conn.execute("INSERT INTO referrals (referrer_id,referred_id) VALUES (?,?)",(referrer_id,referred_id)); conn.commit(); conn.close()

# ── Audit log ─────────────────────────────────────────
def audit(admin_id,action,target="",detail=""):
    conn=get_conn(); conn.execute("INSERT INTO audit_log (admin_id,action,target,detail) VALUES (?,?,?,?)",(admin_id,action,target,detail)); conn.commit(); conn.close()

# ── Bot chats (broadcast uchun) ───────────────────────
def save_bot_chat(chat_id,chat_type,title=""):
    conn=get_conn(); conn.execute("INSERT OR IGNORE INTO bot_chats VALUES (?,?,?,datetime('now'))",(chat_id,chat_type,title)); conn.commit(); conn.close()

def get_bot_chats(exclude_db=True):
    from config import DB_GROUP_ID
    conn=get_conn()
    if exclude_db: r=conn.execute("SELECT * FROM bot_chats WHERE chat_id!=?",(DB_GROUP_ID,)).fetchall()
    else: r=conn.execute("SELECT * FROM bot_chats").fetchall()
    conn.close(); return r

# ── Misc ──────────────────────────────────────────────
def log_search(user_id,query,found):
    conn=get_conn(); conn.execute("INSERT INTO search_logs (user_id,query,found) VALUES (?,?,?)",(user_id,query,int(found))); conn.commit(); conn.close()

def add_movie_request(user_id,request):
    conn=get_conn(); conn.execute("INSERT INTO movie_requests (user_id,request) VALUES (?,?)",(user_id,request)); conn.commit(); conn.close()

# ── Scheduled broadcasts ───────────────────────────────
def add_scheduled_broadcast(admin_id, msgs_json, target_type, send_at):
    conn = get_conn()
    conn.execute('''CREATE TABLE IF NOT EXISTS scheduled_broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER, msgs TEXT,
        target_type TEXT DEFAULT 'all',
        send_at TEXT, sent INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )''')
    conn.execute("INSERT INTO scheduled_broadcasts (admin_id,msgs,target_type,send_at) VALUES (?,?,?,?)",
                 (admin_id, msgs_json, target_type, send_at))
    conn.commit(); conn.close()

def get_pending_broadcasts():
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM scheduled_broadcasts WHERE sent=0 AND send_at <= datetime('now')"
        ).fetchall()
    except: rows = []
    conn.close(); return rows

def mark_broadcast_sent(bid):
    conn = get_conn()
    conn.execute("UPDATE scheduled_broadcasts SET sent=1 WHERE id=?", (bid,))
    conn.commit(); conn.close()

def get_users_by_plan(plan):
    conn = get_conn()
    if plan == "all":
        rows = conn.execute("SELECT user_id FROM users WHERE is_banned=0").fetchall()
    elif plan == "vip":
        rows = conn.execute("SELECT user_id FROM users WHERE plan='vip' AND is_banned=0").fetchall()
    elif plan == "pro":
        rows = conn.execute("SELECT user_id FROM users WHERE plan IN ('pro','vip') AND is_banned=0").fetchall()
    elif plan == "free":
        rows = conn.execute("SELECT user_id FROM users WHERE plan='free' AND is_banned=0").fetchall()
    else:
        rows = conn.execute("SELECT user_id FROM users WHERE is_banned=0").fetchall()
    conn.close(); return [r["user_id"] for r in rows]

def get_users_by_lang(lang):
    conn = get_conn()
    rows = conn.execute("SELECT user_id FROM users WHERE lang=? AND is_banned=0", (lang,)).fetchall()
    conn.close(); return [r["user_id"] for r in rows]

def get_vip_movies(limit=20):
    conn = get_conn()
    from config import TOPIC_VIP_CLUB
    rows = conn.execute(
        "SELECT * FROM movies WHERE topic_id=? ORDER BY added_at DESC LIMIT ?",
        (TOPIC_VIP_CLUB, limit)
    ).fetchall()
    conn.close(); return rows

def check_duplicate_movie(title=None, tags=None):
    conn = get_conn()
    results = []
    if title:
        q = f"%{title.lower()}%"
        rows = conn.execute("SELECT * FROM movies WHERE lower(title) LIKE ?", (q,)).fetchall()
        results.extend(rows)
    conn.close()
    return results

def get_pending_requests(limit=20):
    conn = get_conn()
    try:
        rows = conn.execute('''SELECT mr.*, u.username, u.full_name FROM movie_requests mr
                               LEFT JOIN users u ON mr.user_id = u.user_id
                               WHERE mr.status='pending'
                               ORDER BY mr.created_at DESC LIMIT ?''', (limit,)).fetchall()
    except: rows = []
    conn.close(); return rows

def get_greeting_index(user_id: int) -> int:
    conn = get_conn()
    r = conn.execute("SELECT greeting_index FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return r["greeting_index"] if r else 0

def increment_greeting_index(user_id: int, max_val: int):
    conn = get_conn()
    r = conn.execute("SELECT greeting_index FROM users WHERE user_id=?", (user_id,)).fetchone()
    current = r["greeting_index"] if r else 0
    next_val = (current + 1) % max_val
    conn.execute("UPDATE users SET greeting_index=? WHERE user_id=?", (next_val, user_id))
    conn.commit()
    conn.close()

def get_limit_pack_balance(user_id: int) -> int:
    conn = get_conn()
    r = conn.execute("SELECT bought_limit FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return r["bought_limit"] if r else 0

# ── EPISODES ───────────────────────────────────────────
def update_movie_status(movie_id: int, status: str):
    conn = get_conn()
    conn.execute("UPDATE movies SET status=? WHERE id=?", (status, movie_id))
    conn.commit()
    conn.close()

# ── REKLAMA BUYURTMALAR ────────────────────────────────
def init_ads_table():
    conn = get_conn()
    conn.execute('''CREATE TABLE IF NOT EXISTS ad_orders (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        channel_ids TEXT,
        channels_count INTEGER DEFAULT 1,
        amount      INTEGER,
        payment_type TEXT DEFAULT 'stars',
        status      TEXT DEFAULT 'pending',
        screenshot_msg_id INTEGER,
        content_msgs TEXT,
        created_at  TEXT DEFAULT (datetime('now')),
        approved_at TEXT
    )''')
    conn.commit()
    conn.close()

def create_ad_order(user_id, channel_ids, channels_count, amount, payment_type):
    conn = get_conn()
    import json
    conn.execute('''INSERT INTO ad_orders
        (user_id, channel_ids, channels_count, amount, payment_type)
        VALUES (?, ?, ?, ?, ?)''',
        (user_id, json.dumps(channel_ids), channels_count, amount, payment_type))
    order_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    conn.commit()
    conn.close()
    return order_id

def get_ad_order(order_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM ad_orders WHERE id=?", (order_id,)).fetchone()
    conn.close()
    return row

def update_ad_order(order_id, **kwargs):
    conn = get_conn()
    fields = ", ".join(f"{k}=?" for k in kwargs)
    conn.execute(f"UPDATE ad_orders SET {fields} WHERE id=?",
                 list(kwargs.values()) + [order_id])
    conn.commit()
    conn.close()

# ── HAFTALIK STATISTIKA ────────────────────────────────
def get_active_subscriptions():
    conn = get_conn()
    from datetime import date
    today = str(date.today())
    pro = conn.execute(
        "SELECT COUNT(*) as c FROM users WHERE plan='pro' AND plan_until >= ?", (today,)
    ).fetchone()["c"]
    vip = conn.execute(
        "SELECT COUNT(*) as c FROM users WHERE plan='vip' AND plan_until >= ?", (today,)
    ).fetchone()["c"]
    # To'liq ro'yxat
    pro_users = conn.execute(
        "SELECT user_id, full_name, username, plan_until FROM users WHERE plan='pro' AND plan_until >= ? ORDER BY plan_until",
        (today,)
    ).fetchall()
    vip_users = conn.execute(
        "SELECT user_id, full_name, username, plan_until FROM users WHERE plan='vip' AND plan_until >= ? ORDER BY plan_until",
        (today,)
    ).fetchall()
    conn.close()
    return {"pro_count": pro, "vip_count": vip, "pro_users": pro_users, "vip_users": vip_users}

# ── EPISODES ──────────────────────────────────────────
def init_episodes():
    conn = get_conn()
    conn.execute('''CREATE TABLE IF NOT EXISTS episodes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id    INTEGER NOT NULL,
        episode_num INTEGER NOT NULL,
        message_id  INTEGER NOT NULL,
        topic_id    INTEGER,
        added_at    TEXT DEFAULT (datetime('now')),
        UNIQUE(movie_id, episode_num)
    )''')
    # movies jadvaliga qo'shimcha ustunlar
    try:
        conn.execute("ALTER TABLE movies ADD COLUMN total_episodes INTEGER DEFAULT 1")
    except: pass
    try:
        conn.execute("ALTER TABLE movies ADD COLUMN status TEXT DEFAULT 'completed'")
        # completed | ongoing | announced
    except: pass
    try:
        conn.execute("ALTER TABLE movies ADD COLUMN season INTEGER DEFAULT 1")
    except: pass
    conn.commit()
    conn.close()

def add_episode(movie_id: int, episode_num: int, message_id: int, topic_id: int):
    conn = get_conn()
    conn.execute('''INSERT OR REPLACE INTO episodes
        (movie_id, episode_num, message_id, topic_id)
        VALUES (?, ?, ?, ?)''', (movie_id, episode_num, message_id, topic_id))
    # Jami qismlar sonini yangilash
    count = conn.execute(
        "SELECT COUNT(*) as c FROM episodes WHERE movie_id=?", (movie_id,)
    ).fetchone()["c"]
    conn.execute("UPDATE movies SET total_episodes=? WHERE id=?", (count, movie_id))
    conn.commit()
    conn.close()

def get_episode(movie_id: int, episode_num: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM episodes WHERE movie_id=? AND episode_num=?",
        (movie_id, episode_num)
    ).fetchone()
    conn.close()
    return row

def get_episodes(movie_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM episodes WHERE movie_id=? ORDER BY episode_num ASC",
        (movie_id,)
    ).fetchall()
    conn.close()
    return rows

def get_episode_count(movie_id: int) -> int:
    conn = get_conn()
    r = conn.execute(
        "SELECT COUNT(*) as c FROM episodes WHERE movie_id=?", (movie_id,)
    ).fetchone()
    conn.close()
    return r["c"] if r else 0

def get_last_episode_num(movie_id: int) -> int:
    conn = get_conn()
    r = conn.execute(
        "SELECT MAX(episode_num) as m FROM episodes WHERE movie_id=?", (movie_id,)
    ).fetchone()
    conn.close()
    return r["m"] if r and r["m"] else 0

def get_top_referrers(limit=20):
    conn = get_conn()
    rows = conn.execute('''
        SELECT user_id, username, full_name, referral_points
        FROM users WHERE referral_points > 0
        ORDER BY referral_points DESC LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return rows

def get_active_subscribers():
    from datetime import date
    today = str(date.today())
    conn = get_conn()
    pro = conn.execute('''
        SELECT user_id, username, full_name, plan, plan_until
        FROM users WHERE plan='pro' AND plan_until >= ? AND is_banned=0
        ORDER BY plan_until ASC
    ''', (today,)).fetchall()
    vip = conn.execute('''
        SELECT user_id, username, full_name, plan, plan_until
        FROM users WHERE plan='vip' AND plan_until >= ? AND is_banned=0
        ORDER BY plan_until ASC
    ''', (today,)).fetchall()
    conn.close()
    return list(pro), list(vip)
