"""Admin panel / qidiruv / superadmin / reaksiya / dedupe oqimlarini soxta Telegram bilan sinash:
    python tools/smoke_ui.py
"""
import asyncio, os, sys, types
from datetime import datetime

os.environ.update(BOT_TOKEN="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", SUPERADMIN_ID="1", ADMIN_IDS="1,2",
                  DB_GROUP_ID="-100123", DB_PATH="/tmp/smoke_ui.db", BACKUP_CHAT_ID="-100999")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in ("/tmp/smoke_ui.db", "/tmp/smoke_ui.db-wal", "/tmp/smoke_ui.db-shm"):
    if os.path.exists(p): os.remove(p)

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (AnswerCallbackQuery, EditMessageText, SendMessage, CopyMessage, GetChat, GetChatMemberCount,
                             GetChatMember, LeaveChat, SetMessageReaction, TelegramMethod)
from aiogram.types import (Update, CallbackQuery, Message, Chat, User, MessageId, ChatFullInfo)

import database as db
from handlers import admin, admin_search, superadmin
from middlewares.dedupe import DedupeMiddleware
from middlewares.reactions import ReactionMiddleware, invalidate

CALLS = []

class MockSession(BaseSession):
    async def close(self): pass
    async def stream_content(self, *a, **k): yield b""
    async def make_request(self, bot, method, timeout=None):
        CALLS.append((type(method).__name__, method.model_dump(exclude_none=True)))
        if isinstance(method, (AnswerCallbackQuery, LeaveChat, SetMessageReaction)): return True
        if isinstance(method, EditMessageText): return True
        if isinstance(method, SendMessage): return Message(message_id=900, date=datetime.now(), chat=Chat(id=method.chat_id, type="private"), text=method.text)
        if isinstance(method, CopyMessage): return MessageId(message_id=1)
        if isinstance(method, GetChat): return ChatFullInfo(id=method.chat_id, type="supergroup", title="T", accent_color_id=0, max_reaction_count=11, accepted_gift_types=None) if False else (_ for _ in ()).throw(TelegramBadRequest(method, "mock no chat"))
        if isinstance(method, GetChatMemberCount): return 42
        raise TelegramBadRequest(method, "mock: " + type(method).__name__)
    def check_response(self, *a, **k): pass

bot = Bot(token=os.environ["BOT_TOKEN"], session=MockSession())
dp = Dispatcher()
dp.update.outer_middleware(DedupeMiddleware())
dp.message.outer_middleware(ReactionMiddleware())
dp.include_router(admin.router); dp.include_router(admin_search.router); dp.include_router(superadmin.router)

uid_counter = [0]
def U(i): return User(id=i, is_bot=False, first_name=f"U{i}")
async def cb(uid, data, mid=10):
    uid_counter[0] += 1; CALLS.clear()
    c = CallbackQuery(id=str(uid_counter[0]), from_user=U(uid), chat_instance="ci", data=data,
                      message=Message(message_id=mid, date=datetime.now(), chat=Chat(id=uid, type="private"), text="x"))
    await dp.feed_update(bot, Update(update_id=10000 + uid_counter[0], callback_query=c))
    return list(CALLS)
async def msg(uid, text, chat=None, ctype="private", mid=50):
    uid_counter[0] += 1; CALLS.clear()
    m = Message(message_id=mid, date=datetime.now(), chat=Chat(id=chat or uid, type=ctype, title="G" if ctype != "private" else None), from_user=U(uid), text=text)
    await dp.feed_update(bot, Update(update_id=10000 + uid_counter[0], message=m))
    await asyncio.sleep(0.05)
    return list(CALLS)
def last_edit(calls):
    e = [c for c in calls if c[0] in ("EditMessageText", "SendMessage")]
    assert e, f"edit/send yo'q: {[c[0] for c in calls]}"; return e[-1][1]
def buttons(d): return [b for row in d["reply_markup"]["inline_keyboard"] for b in row]
def cbs(d): return [b["callback_data"] for b in buttons(d)]
def texts(d): return [b["text"] for b in buttons(d)]

async def main():
    db.init_db()
    names = ["Ali Karimov", "Vali", "Gulnora Oʻrinova", "Alisher", "Bek", "Nodira", "Sardor", "Zilola", "Jasur", "Malika"] * 3
    for i, n in enumerate(names, start=100): db.register_user(i, f"user{i}", n)
    conn = db.get_conn(); conn.execute("UPDATE users SET bio='kino sevaman' WHERE user_id=105"); conn.commit(); conn.close()

    # 1) Foydalanuvchilar ro'yxati, sahifalash va "Orqaga"
    d = last_edit(await cb(1, "adm_users"))
    assert "jami 30" in d["text"] or "30" in d["text"], d["text"]
    d = last_edit(await cb(1, "users_page_2"))
    assert "◀️" in texts(d) and "users_page_1" in cbs(d) and "▶️" not in texts(d), texts(d)
    d = last_edit(await cb(1, "users_page_1")); assert "users_page_0" in cbs(d) and "users_page_2" in cbs(d)
    await cb(1, "users_page_2")                                   # 3-sahifaga o'tamiz
    uid = [c for c in cbs(last_edit(await cb(1, "users_page_2"))) if c.startswith("adm_user_")][0]
    d = last_edit(await cb(1, uid))                               # karta
    assert "users_page_2" in cbs(d), cbs(d)                       # "Orqaga" = aynan 3-sahifa
    d = last_edit(await cb(1, "users_page_2")); assert "◀️" in texts(d)
    print("OK 1: ro'yxat, ◀️ bitta orqaga, kartadan Orqaga -> o'sha sahifa")

    # 2) Harfli qidiruv (real-time)
    d = last_edit(await cb(1, "lq_start")); assert "Qidiruv" in d["text"] and "lq_k_A" in cbs(d)
    for k in "ALI": d = last_edit(await cb(1, f"lq_k_{k}"))
    assert "<code>ALI</code>" in d["text"] and any("Ali" in t for t in texts(d)), d["text"]
    d = last_edit(await cb(1, "lq_k_SP")); d = last_edit(await cb(1, "lq_k_BS")); d = last_edit(await cb(1, "lq_k_BS")); d = last_edit(await cb(1, "lq_k_BS"))
    assert "<code>A</code>" in d["text"]
    for k in ["O\u02bb", "R"]: d = last_edit(await cb(1, f"lq_k_{k}"))        # "AOʻR" -> topilmaydi, keyin tozalaymiz
    d = last_edit(await cb(1, "lq_k_CL")); assert "…" in d["text"]
    for k in ["O", "'", "R"]: d = last_edit(await cb(1, f"lq_k_{k}"))         # "O'R" apostrof tenglashtirilgan: Oʻrinova
    assert any("Gulnora" in t for t in texts(d)), texts(d)
    sug = [c for c in cbs(d) if c.startswith("adm_user_")][0]
    d = last_edit(await cb(1, sug)); assert "lq_view" in cbs(d)               # kartadan Orqaga -> qidiruv ekrani
    d = last_edit(await cb(1, "lq_view")); assert "<code>O&#x27;R</code>" in d["text"] or "O'R" in d["text"] or "O&#x27;R" in d["text"], d["text"]
    d = last_edit(await cb(1, "lq_l_cyr")); assert "Ё" in texts(d)
    d = last_edit(await cb(1, "lq_l_num")); assert "@" in texts(d)
    d = last_edit(await cb(1, "lq_start")); d = last_edit(await cb(1, "lq_k_A")); d = last_edit(await cb(1, "lqr_0")); assert "natija" in d["text"] and "lq_view" in cbs(d)
    print("OK 2: harfli qidiruv, apostrof, kartadan qaytish, kirill/raqam, lqr natijalar")

    # 3) Matnli qidiruv (ism/bio/ID) holati orqali
    d = last_edit(await cb(1, "adm_user_lookup")); assert "lq_start" in cbs(d)
    r = await msg(1, "kino sevaman"); d = last_edit(r); assert "Men" in d["text"] or "👤" in d["text"], d["text"]  # bio bo'yicha 1 ta -> karta
    await cb(1, "adm_user_lookup"); r = await msg(1, "Ali"); d = last_edit(r); assert "topildi" in d["text"], d["text"]
    print("OK 3: matn bilan qidiruv (bio, ism)")

    # 4) Superadmin: ruxsat va menyu
    r = await cb(2, "sa_menu"); assert any(c[0] == "AnswerCallbackQuery" and c[1].get("show_alert") for c in r) and not any(c[0] == "EditMessageText" for c in r)
    d = last_edit(await cb(1, "sa_menu")); assert "sa_chats_0" in cbs(d) and "sa_backup" in cbs(d)
    d = last_edit(await cb(1, "sa_chats_0")); assert "Hozircha yo'q" in d["text"]
    db.save_bot_chat(-100777, "supergroup", "Test guruh", "administrator"); db.save_bot_chat(-100888, "channel", "Kanal", "member")
    d = last_edit(await cb(1, "sa_chats_0")); assert "sa_chat_-100777_0" in cbs(d), cbs(d)
    d = last_edit(await cb(1, "sa_chat_-100777_0")); assert "sa_say_-100777_0" in cbs(d) and "sa_chats_0" in cbs(d)
    print("OK 4: superadmin ruxsat, chatlar ro'yxati va kartasi")

    # 5) Bot nomidan yozish
    d = last_edit(await cb(1, "sa_say_-100777_0")); assert "bot nomidan" in d["text"]
    r = await msg(1, "Salom guruh!", mid=77); d = last_edit(r); assert "sa_sayY" in cbs(d)
    r = await cb(1, "sa_sayY"); cp = [c for c in r if c[0] == "CopyMessage"]; assert cp and cp[0][1]["chat_id"] == -100777 and cp[0][1]["message_id"] == 77, r
    print("OK 5: bot nomidan yozish (copy_message -> guruh)")

    # 6) Reyting + reaksiya sozlamasi + backup paneli
    db.log_search(100, "q", 1); db.log_search(100, "q2", 1); db.log_search(101, "q", 1)
    d = last_edit(await cb(1, "sa_rank_7")); assert "🥇" in d["text"] and "Ali Karimov" in d["text"], d["text"]
    d = last_edit(await cb(1, "sa_react")); assert "sa_rt_super" in cbs(d)
    d = last_edit(await cb(1, "sa_rt_channel")); assert "sa_re_channel_0" in cbs(d) and "sa_re_channel_x" in cbs(d)
    d = last_edit(await cb(1, "sa_re_channel_2")); assert db.get_setting("react_channel") == "🔥", db.get_setting("react_channel")
    d = last_edit(await cb(1, "sa_backup")); assert "sa_backup_now" in cbs(d)
    print("OK 6: reyting, reaksiya sozlamasi, backup paneli")

    # 7) Reaksiyalar: guruhda superadmin/admin xabari va oddiy user
    invalidate()
    r = await msg(1, "salom", chat=-100555, ctype="supergroup"); assert any(c[0] == "SetMessageReaction" and c[1]["reaction"][0]["emoji"] == "🔥" for c in r), r
    r = await msg(2, "salom", chat=-100555, ctype="supergroup"); assert any(c[0] == "SetMessageReaction" and c[1]["reaction"][0]["emoji"] == "👍" for c in r), r
    r = await msg(555, "salom", chat=-100555, ctype="supergroup"); assert not any(c[0] == "SetMessageReaction" for c in r), r
    uid_counter[0] += 1; CALLS.clear()
    from aiogram.types import Message as M
    post = M(message_id=5, date=datetime.now(), chat=Chat(id=-100888, type="channel", title="Kanal"), text="post")
    await dp.feed_update(bot, Update(update_id=99999, channel_post=post)); await asyncio.sleep(0.05)
    assert any(c[0] == "SetMessageReaction" and c[1]["chat_id"] == -100888 for c in CALLS), CALLS
    print("OK 7: guruhda superadmin/admin reaksiyasi, oddiy user yo'q, kanal posti")

    # 8) Dedupe: bir xil update_id ikki marta
    CALLS.clear(); c1 = CallbackQuery(id="z", from_user=U(1), chat_instance="ci", data="sa_menu", message=Message(message_id=10, date=datetime.now(), chat=Chat(id=1, type="private"), text="x"))
    await dp.feed_update(bot, Update(update_id=777777, callback_query=c1)); n1 = len(CALLS)
    await dp.feed_update(bot, Update(update_id=777777, callback_query=c1)); assert len(CALLS) == n1 and n1 > 0
    print("OK 8: takroriy update o'tkazib yuborildi")
    print("ALL UI OK")

asyncio.run(main())
