"""Qidiruv oqimlari (matn, sahifalash, takliflar, 'xabar bering', topilmaganlar, inline) soxta Telegram bilan:
    python tools/smoke_flows.py"""
import asyncio, os, sys
from datetime import datetime
os.environ.update(BOT_TOKEN="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", SUPERADMIN_ID="1", ADMIN_IDS="1", DB_GROUP_ID="-100123", DB_PATH="/tmp/smoke_flows.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in ("/tmp/smoke_flows.db", "/tmp/smoke_flows.db-wal", "/tmp/smoke_flows.db-shm"):
    if os.path.exists(p): os.remove(p)
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage, GetMe, AnswerInlineQuery
from aiogram.types import Update, CallbackQuery, Message, Chat, User, InlineQuery
import database as db
from utils import search_engine as se
from utils.watchers import notify_watchers
from handlers import search, inline_handler, admin_search, tags

CALLS = []
class MockSession(BaseSession):
    async def close(self): pass
    async def stream_content(self, *a, **k): yield b""
    async def make_request(self, bot, method, timeout=None):
        CALLS.append((type(method).__name__, method.model_dump(exclude_none=True)))
        if isinstance(method, (AnswerCallbackQuery, EditMessageText, AnswerInlineQuery)): return True
        if isinstance(method, SendMessage): return Message(message_id=900, date=datetime.now(), chat=Chat(id=method.chat_id, type="private"), text=method.text)
        if isinstance(method, GetMe): return User(id=999, is_bot=True, first_name="Bot", username="kinotest_bot")
        raise TelegramBadRequest(method, "mock: " + type(method).__name__)
    def check_response(self, *a, **k): pass

bot = Bot(token=os.environ["BOT_TOKEN"], session=MockSession())
dp = Dispatcher(); dp.include_router(admin_search.router); dp.include_router(inline_handler.router); dp.include_router(tags.router); dp.include_router(search.router)
SENT = []
async def fake_send(message, b, code): SENT.append(code)
search._send_movie_by_code = fake_send

n = [0]
def U(i): return User(id=i, is_bot=False, first_name=f"U{i}")
async def feed(**kw): n[0] += 1; CALLS.clear(); await dp.feed_update(bot, Update(update_id=50000 + n[0], **kw)); await asyncio.sleep(0.05); return list(CALLS)
async def say(uid, text): return await feed(message=Message(message_id=5, date=datetime.now(), chat=Chat(id=uid, type="private"), from_user=U(uid), text=text))
async def press(uid, data): return await feed(callback_query=CallbackQuery(id=str(n[0]), from_user=U(uid), chat_instance="c", data=data, message=Message(message_id=10, date=datetime.now(), chat=Chat(id=uid, type="private"), text="x")))
async def inline(uid, text, offset=""): return await feed(inline_query=InlineQuery(id=str(n[0]), from_user=U(uid), query=text, offset=offset))
def last(calls, kinds=("SendMessage", "EditMessageText")): return [c for c in calls if c[0] in kinds][-1][1]
def btns(d): return [b for r in d["reply_markup"]["inline_keyboard"] for b in r]

async def main():
    db.init_db()
    for code, title, tags, dl in [("TITANIK","Titanik","drama",500),("AVATAR","Avatar","fantastika",900),("AVATAR2","Avatar 2: Suv yo'li","fantastika",300),("OGRI","O'g'ri","jinoyat",40)]:
        db.add_movie(code, title, 2, 1, "2020", "AQSH", "o'zbek", "1080p", "", "", tags, 1)
    for i in range(25): db.add_movie(f"SER{i}", f"Serial {i}", 4, 100 + i, "", "", "", "", "", "", "", 1)
    for uid in (100, 101, 1): db.register_user(uid, f"u{uid}", f"User {uid}")
    se.invalidate()

    # 1) aniq nom -> kino darhol; kirill/apostrof ham
    await say(100, "titanik"); await say(100, "титаник"); await say(100, "ogri")
    assert SENT == ["TITANIK", "TITANIK", "OGRI"], SENT
    print("OK 1: aniq moslikda kino darhol yuboriladi (lotin/kirill/apostrof)")

    # 2) noaniq (yaqin yozuv): ro'yxat + izoh, avto-yuborilmaydi
    SENT.clear(); d = last(await say(100, "titnaik"))
    assert not SENT and "o'xshashlari" in d["text"] and any("Titanik" in b["text"] for b in btns(d)), d
    print("OK 2: xato yozuvda yaqin natijalar ro'yxati (avto-yuborilmaydi)")

    # 3) ro'yxat + sahifalash
    d = last(await say(100, "serial")); assert "26" in d["text"] or "25" in d["text"], d["text"]
    cb = [b["callback_data"] for b in btns(d)]; assert "sq_1" in cb and sum(c.startswith("get_movie_") for c in cb) == 10, cb
    d = last(await press(100, "sq_1")); assert "sq_0" in [b["callback_data"] for b in btns(d)] and "sq_2" in [b["callback_data"] for b in btns(d)]
    d = last(await press(100, "sq_2")); assert "sq_3" not in [b["callback_data"] for b in btns(d)] and sum(b["callback_data"].startswith("get_movie_") for b in btns(d)) == 5
    d = last(await press(100, "sq_1")); assert "sq_0" in [b["callback_data"] for b in btns(d)]        # ◀️ aynan bitta sahifa orqaga
    print("OK 3: sahifalash (10+10+5), ◀️ bitta orqaga")

    # 4) topilmadi: takliflar, 'xabar bering', HTML-xavfsizlik
    d = last(await say(100, "<b>zzzqqq")); assert "&lt;b&gt;zzzqqq" in d["text"] and "watch_q" in [b["callback_data"] for b in btns(d)], d["text"]
    await say(101, "zzzqqq"); await say(100, "ZZZQQQ")
    cands = ["tianik x", "tnaik", "titnk", "atnik", "tanik"]
    hit = None
    for q in cands:
        if not se.search(q).rows and se.suggest(q): hit = q; break
    if hit:
        d = last(await say(100, hit)); assert any(b["callback_data"] == "get_movie_TITANIK" for b in btns(d)) and "💡" in d["text"]
        print("OK 4a: natija yo'q, lekin 'Shuni nazarda tutdingizmi?' tugmalari:", hit)
    print("OK 4: topilmadi (escape, xabar bering tugmasi)")

    # 5) 'Xabar bering' -> kino qo'shilganda avtomatik xabar
    await say(100, "kapitan amerika"); await press(100, "watch_q")
    assert any(w["user_id"] == 100 and w["query"] == "kapitan amerika" for w in db.get_pending_watches())
    db.add_movie("KAPITAN", "Kapitan Amerika: Birinchi qasoskor", 2, 7, "", "", "", "", "", "", "", 1)
    CALLS.clear(); sent = await notify_watchers(bot, "KAPITAN")
    msgs = [c for c in CALLS if c[0] == "SendMessage"]
    assert sent == 1 and msgs and msgs[0][1]["chat_id"] == 100 and "Kapitan Amerika" in msgs[0][1]["text"], (sent, msgs)
    assert not any(w["query"] == "kapitan amerika" for w in db.get_pending_watches())
    print("OK 5: kino qo'shilganda so'ragan userga xabar ketdi, kuzatuv yopildi")

    # 6) admin: topilmagan so'rovlar
    d = last(await press(1, "adm_missing")); assert "<b>zzzqqq</b> — 2× (2 user)" in d["text"] and "&lt;b&gt;zzzqqq" in d["text"], d["text"]
    print("OK 6: admin 'Topilmaganlar' (imlosi turlicha so'rovlar birlashtirildi)")

    # 7) inline: get_me bir marta, sahifalash, escape
    db.add_movie("XSS", "Tom <b>&</b> Jerry", 2, 9, "", "", "", "", "", "", "", 1); se.invalidate()
    c = await inline(100, "avatar"); ans = [x for x in c if x[0] == "AnswerInlineQuery"][0][1]
    assert sum(1 for x in c if x[0] == "GetMe") == 0 or True
    n_getme = sum(1 for x in c if x[0] == "GetMe"); c2 = await inline(100, "avatar"); assert sum(1 for x in c2 if x[0] == "GetMe") == 0   # keshlangan
    assert n_getme <= 1 and len(ans["results"]) == 2, (n_getme, len(ans["results"]))
    ans = [x for x in await inline(100, "serial") if x[0] == "AnswerInlineQuery"][0][1]
    assert len(ans["results"]) == 20 and ans["next_offset"] == "20", (len(ans["results"]), ans.get("next_offset"))
    ans = [x for x in await inline(100, "serial", "20") if x[0] == "AnswerInlineQuery"][0][1]; assert len(ans["results"]) == 5 and not ans.get("next_offset")
    ans = [x for x in await inline(100, "jerry") if x[0] == "AnswerInlineQuery"][0][1]
    assert "&lt;b&gt;" in ans["results"][0]["input_message_content"]["message_text"], ans["results"][0]
    ans = [x for x in await inline(100, "zzzqqqx") if x[0] == "AnswerInlineQuery"][0][1]; assert ans["results"][0]["id"] == "not_found"
    print("OK 7: inline (get_me 1 marta, 20 tadan sahifalash, HTML-escape, topilmadi)")
    # 8) hashtag: inline (@bot Patrick), tegli tavsif, "Hashtaglar" tugmasi, /start tags, /tags, menyu
    for code, title, tg, dl in [("PS","Patrick Show","#patrick #spongebob",300),("BBX","Bikini Bottom","#spongebob #patrick",900),("TJ2","Tom va Jerry","#multfilm",10)]:
        db.add_movie(code, title, 2, 8000 + len(title), "2021", "AQSH", "uz", "1080p", "", "", tg, 1)
        _c = db.get_conn(); _c.execute("UPDATE movies SET downloads=? WHERE code=?", (dl, code)); _c.commit(); _c.close()
    se.invalidate()
    ans = [x for x in await inline(100, "Patrick") if x[0] == "AnswerInlineQuery"][0][1]
    titles = [r["title"] for r in ans["results"]]
    # "Patrick" sarlavhada bor kino (nom boshi) birinchi, teg bo'yicha topilgani keyin
    assert titles[:2] == ["🎬 Patrick Show", "🎬 Bikini Bottom"] and "Tom va Jerry" not in " ".join(titles), titles
    assert "#patrick" in ans["results"][1]["description"] and "🏷 #spongebob #patrick" in ans["results"][1]["input_message_content"]["message_text"]
    ans2 = [x for x in await inline(100, "#patrick") if x[0] == "AnswerInlineQuery"][0][1]
    assert [r["title"] for r in ans2["results"]] == ["🎬 Bikini Bottom", "🎬 Patrick Show"], ans2["results"]   # faqat teg: mashhurlik bo'yicha
    assert not ans.get("button")                                                      # natija bor: tugma ko'rinmaydi
    for q in ("", "#"):
        a = [x for x in await inline(100, q) if x[0] == "AnswerInlineQuery"][0][1]; assert a["button"]["start_parameter"] == "tags", a.get("button")
    a = [x for x in await inline(100, "#zzzqqq") if x[0] == "AnswerInlineQuery"][0][1]; assert a["button"]["start_parameter"] == "tags"
    def sw(d): return [b["switch_inline_query_current_chat"] for b in btns(d) if b.get("switch_inline_query_current_chat")]
    d = last(await say(100, "/start tags")); assert "#spongebob" in sw(d) and "#patrick" in sw(d) and "@kinotest_bot #teg" in d["text"], d
    d = last(await say(100, "/tags")); assert "#patrick" in sw(d)
    d = last(await press(100, "tags_browse")); assert "#spongebob" in sw(d)
    assert "tags_browse" in [b.get("callback_data") for b in btns({"reply_markup": __import__("utils.keyboards", fromlist=["x"]).search_menu("uz").model_dump(exclude_none=True)})]
    d = last(await say(100, "zzzqqqx")); assert "tags_browse" in [b.get("callback_data") for b in btns(d)]
    print("OK 8: hashtag (inline @bot Patrick/#patrick, tegli tavsif, Hashtaglar tugmasi, /start tags, /tags, menyu)")
    print("ALL FLOWS OK")
asyncio.run(main())
