import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN     = os.getenv("BOT_TOKEN", "")
SUPERADMIN_ID = int(os.getenv("SUPERADMIN_ID", "0"))
ADMIN_IDS     = list(map(int, os.getenv("ADMIN_IDS", str(SUPERADMIN_ID)).split(",")))

DB_GROUP_ID   = int(os.getenv("DB_GROUP_ID", "0"))

# Kino topiclar
TOPIC_FILMLAR       = 2
TOPIC_SERIALLAR     = 4
TOPIC_DRAMALAR      = 6
TOPIC_MULTFILMLAR   = 8
TOPIC_ANIMELAR      = 10
TOPIC_HUJJATLI      = 12
TOPIC_MINI_SERIAL   = 14
TOPIC_STANDUP       = 16
TOPIC_KONSERT       = 18
TOPIC_UZBEK_KINO    = 20
TOPIC_BOLALAR       = 21
TOPIC_SPORT         = 23
TOPIC_KOMEDIYA      = 44
TOPIC_TRILLER       = 46
TOPIC_ANIMATSION    = 50  # Yangi topic — supergroup da oching
TOPIC_VIP_CLUB      = 55

# Admin topiclar
TOPIC_USERS         = 24
TOPIC_SUBSCRIPTIONS = 26
TOPIC_PAYMENTS      = 28
TOPIC_LIVE          = 32
TOPIC_REQUESTS      = 34
TOPIC_LOGS          = 35
TOPIC_ADMIN_LOGS    = 40
TOPIC_STATS         = 41
TOPIC_ERRORS        = 48

GENRES = {
    TOPIC_FILMLAR:     ("🎬 Filmlar",        "media_film"),
    TOPIC_SERIALLAR:   ("📺 Seriallar",       "media_serial"),
    TOPIC_DRAMALAR:    ("🔥 Dramalar",        "media_drama"),
    TOPIC_MULTFILMLAR: ("👑 Multfilmlar",     "media_cartoon"),
    TOPIC_ANIMELAR:    ("🐱 Animelar",        "media_anime"),
    TOPIC_HUJJATLI:    ("🎭 Hujjatli",        "media_documentary"),
    TOPIC_MINI_SERIAL: ("📺 Mini seriallar",  "media_miniserial"),
    TOPIC_STANDUP:     ("⚡ Stand-up",        "media_standup"),
    TOPIC_KONSERT:     ("🎵 Konsert",         "media_concert"),
    TOPIC_UZBEK_KINO:  ("🎬 O'zbek kinolar",  "media_film"),
    TOPIC_BOLALAR:     ("👦 Bolalar",         "media_kids"),
    TOPIC_SPORT:       ("⚽ Sport",           "media_sport"),
    TOPIC_KOMEDIYA:    ("😂 Komediya",        "media_comedy"),
    TOPIC_TRILLER:     ("🔪 Triller/Jangari", "media_thriller"),
    TOPIC_VIP_CLUB:    ("👑 VIP Club",        "media_vip"),
    TOPIC_ANIMATSION:  ("🎮 Animatsion",      "media_animatsion"),
}

FREE_DAILY_LIMIT   = 5
PRO_DAILY_LIMIT    = 10
VIP_DAILY_LIMIT    = 999999

# Yangi narxlar
PRICE_PRO_1M       = 30   # 1 oylik PRO
PRICE_PRO_3M       = 50   # 3 oylik PRO
PRICE_VIP_3M       = 100  # 3 oylik VIP
PRICE_LIMIT_PACK   = 50   # +50 limit (ishlatilganda tugaydi)

REFERRAL_POINTS_FOR_PRO = 10
LEADERBOARD_SIZE        = 10

# Yangi kanal
REQUIRED_CHANNEL_USERNAME = "@Yoqolganstudio"
REQUIRED_CHANNEL_URL      = "https://t.me/Yoqolganstudio"

BOT_NAME   = "YoqolganRobot"
DEFAULT_LANG = "uz"

# Superadmin salomlashuv ketma-ketligi
SUPERADMIN_GREETINGS = ["BOSS", "Janob", "Ega"]

# ── WEBHOOK (Railway / Render / cPanel hosting) ───────
import os as _os

# Port — Railway/Render avtomatik beradi, cPanel uchun qo'lda
WEBAPP_PORT = int(_os.getenv("PORT", 8080))
WEBAPP_HOST = "0.0.0.0"

# Domain: Railway, Render yoki o'z domeningiz
# Railway:  https://yourapp.up.railway.app
# Render:   https://yourapp.onrender.com
# cPanel:   https://yourdomain.com
_DOMAIN = _os.getenv(
    "WEBHOOK_DOMAIN",
    _os.getenv("RAILWAY_STATIC_URL",
    _os.getenv("RENDER_EXTERNAL_URL", ""))
)

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL  = f"{_DOMAIN.rstrip('/')}{WEBHOOK_PATH}" if _DOMAIN else ""
