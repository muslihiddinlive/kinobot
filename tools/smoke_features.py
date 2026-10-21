"""Kartochka (blockquote/escape/caption limiti), protect_content va rangli tugmalarni sinash."""
import ast, html, os, re, sys, importlib
from html.parser import HTMLParser
os.environ.update(BOT_TOKEN="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", SUPERADMIN_ID="1", DB_GROUP_ID="-100123", DB_PATH="/tmp/smoke_feat.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.exists("/tmp/smoke_feat.db"): os.remove("/tmp/smoke_feat.db")
import database as db; db.init_db()
from utils.helpers import format_movie_card, protect_for, effective_plan

# 1) kartochka
base = {"title": "Tom & Jerry <Show>", "code": "TOM1", "topic_id": 2, "status": "completed", "total_episodes": 1, "downloads": 5,
        "country": "AQSH & Kanada", "format": "1080p", "year": 2020, "language": "o'zbek", "user_rating": 4.2, "rating_count": 17}
class Chk(HTMLParser):
    def __init__(s): super().__init__(); s.stack=[]; s.ok=True
    def handle_starttag(s,t,a): s.stack.append(t)
    def handle_endtag(s,t):
        if not s.stack or s.stack.pop()!=t: s.ok=False
def plain(card): return html.unescape(re.sub(r"<[^>]+>", "", card))
long_desc = ("Juda uzun & <b>xavfli</b> tavsif. " * 120)
card = format_movie_card({**base, "description": long_desc, "title": "T"*150}, for_caption=True)
c = Chk(); c.feed(card); assert c.ok and not c.stack, "HTML teglari to'g'ri yopilmagan"
assert len(plain(card)) <= 1024, len(plain(card))
assert "<blockquote expandable>" in card and "&lt;b&gt;" in card and "<b>xavfli" not in card
short = format_movie_card({**base, "description": "Qisqa tavsif <i>"}, for_caption=True)
assert "<blockquote" not in short and "&lt;i&gt;" in short and "Tom &amp; Jerry &lt;Show&gt;" in short and "AQSH &amp; Kanada" in short
full = format_movie_card({**base, "description": long_desc}, for_caption=False); assert len(plain(full)) < 4096 and "<blockquote expandable>" in full
print("OK 1: kartochka (escape, expandable blockquote, caption <= 1024:", len(plain(card)), "belgi)")

# 2) protect_content
U = lambda plan, until=None: {"plan": plan, "plan_until": until}
db.set_setting("protect_mode", "off");  assert not protect_for(U("free"))
db.set_setting("protect_mode", "free"); assert protect_for(U("free")) and protect_for(U("pro", "2000-01-01")) and not protect_for(U("pro", "2999-01-01")) and not protect_for(U("vip", "2999-01-01"))
db.set_setting("protect_mode", "all");  assert protect_for(U("vip", "2999-01-01"))
print("OK 2: protect_for off/free/all, muddati o'tgan PRO = free")
src = open("handlers/search.py").read(); tree = ast.parse(src)
calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "copy_message"]
assert len(calls) == 2 and all(any(k.arg == "protect_content" for k in n.keywords) for n in calls)
print("OK 2b: ikkala copy_message protect_content bilan")

# 3) rangli tugmalar
import utils.keyboards as kb
b = kb.sbtn("x", "danger", callback_data="y"); assert b.model_dump(exclude_none=True)["style"] == "danger"
assert "style" not in kb.sbtn("x", callback_data="y").model_dump(exclude_none=True)
styles = lambda m: {x.text: x.model_dump(exclude_none=True).get("style") for r in m.inline_keyboard for x in r}
assert styles(kb.subscription_keyboard([], "uz"))["✅ Obunani tekshirish"] == "success"
st = styles(kb.plans_keyboard()); assert st["👑 VIP 3 oy — ⭐100"] == "primary" and sum(1 for v in st.values() if v) == 1, st
st = styles(kb.user_actions_keyboard(5)); assert st["🚫 Ban"] == "danger" and st["✅ Unban"] == "success"
os.environ["BUTTON_STYLES"] = "0"; importlib.reload(kb)
assert "style" not in kb.sbtn("x", "danger", callback_data="y").model_dump(exclude_none=True)
print("OK 3: rangli tugmalar (va BUTTON_STYLES=0 bilan o'chadi)")
print("ALL FEATURES OK")
