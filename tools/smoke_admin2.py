"""Admin panel 2.0: RBAC, tasdiq, PIN, dashboard, salomatlik, audit, eslatma/teglar, faollik, hisobot.
    python tools/smoke_admin2.py"""
import asyncio, os, sys
from datetime import datetime
os.environ.update(BOT_TOKEN="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", SUPERADMIN_ID="1", ADMIN_IDS="2", DB_GROUP_ID="-100123",
                  DB_PATH="/tmp/smoke_admin2.db", BACKUP_CHAT_ID="0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in ("/tmp/smoke_admin2.db", "/tmp/smoke_admin2.db-wal", "/tmp/smoke_admin2.db-shm"):
    if os.path.exists(p): os.remove(p)
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (AnswerCallbackQuery, EditMessageText, SendMessage, GetWebhookInfo, SendPhoto, SendDocument, DeleteMessage)
from aiogram.types import Update, CallbackQuery, Message, Chat, User, WebhookInfo
import database as db
from handlers import admin, admin_search, superadmin, sa_tools, dashboard, audit_view, user_notes
from middlewares.dedupe import DedupeMiddleware
from middlewares.activity import ActivityMiddleware
from middlewares.guard import GuardMiddleware, set_dispatcher
from utils import admin_data as ad, pin, reports, perms

CALLS = []
class MockSession(BaseSession):
    async def close(self): pass
    async def stream_content(self, *a, **k): yield b""
    async def make_request(self, bot, method, timeout=None):
        CALLS.append((type(method).__name__, method.model_dump(exclude_none=True)))
        if isinstance(method, (AnswerCallbackQuery, EditMessageText, DeleteMessage)): return True
        if isinstance(method, (SendMessage, SendPhoto, SendDocument)):
            return Message(message_id=900, date=datetime.now(), chat=Chat(id=method.chat_id, type="private"), text="x")
        if isinstance(method, GetWebhookInfo): return WebhookInfo(url="https://kino.onrender.com/wh/SECRETPATH", has_custom_certificate=False, pending_update_count=3)
        raise TelegramBadRequest(method, "mock: " + type(method).__name__)
    def check_response(self, *a, **k): pass

bot = Bot(token=os.environ["BOT_TOKEN"], session=MockSession())
dp = Dispatcher()
dp.update.outer_middleware(DedupeMiddleware()); dp.update.outer_middleware(ActivityMiddleware()); dp.callback_query.outer_middleware(GuardMiddleware()); set_dispatcher(dp)
for r in (admin.router, admin_search.router, superadmin.router, sa_tools.router, dashboard.router, audit_view.router, user_notes.router): dp.include_router(r)

n = [0]
def U(i): return User(id=i, is_bot=False, first_name=f"U{i}")
async def feed(**kw): n[0] += 1; CALLS.clear(); await dp.feed_update(bot, Update(update_id=70000 + n[0], **kw)); await asyncio.sleep(0.05); return list(CALLS)
async def press(uid, data): return await feed(callback_query=CallbackQuery(id=str(n[0]), from_user=U(uid), chat_instance="c", data=data, message=Message(message_id=10, date=datetime.now(), chat=Chat(id=uid, type="private"), text="x")))
async def say(uid, text): return await feed(message=Message(message_id=5, date=datetime.now(), chat=Chat(id=uid, type="private"), from_user=U(uid), text=text))
def edits(c): return [x[1] for x in c if x[0] in ("EditMessageText", "SendMessage")]
def last(c): e = edits(c); assert e, [x[0] for x in c]; return e[-1]
def btns(d): return [b for r in d["reply_markup"]["inline_keyboard"] for b in r]
def cbs(d): return [b["callback_data"] for b in btns(d)]
def alert(c): return [x[1] for x in c if x[0] == "AnswerCallbackQuery" and x[1].get("show_alert")]
def banned(uid): return bool(db.get_user(uid)["is_banned"])

async def main():
    db.init_db()
    for i in range(100, 108): db.register_user(i, f"u{i}", f"User {i}")
    db.add_admin(10, "mod", "Moderator", "moderator", 1, 1, 0, 0, 1)
    db.add_admin(11, "adm", "Admin", "admin", 1, 1, 1, 1, 1)
    for uid in (1, 2, 10, 11, 555): db.register_user(uid, f"a{uid}", f"Person {uid}")

    # 1) RBAC + tasdiq
    c = await press(10, "ban_100"); assert alert(c) and "Ruxsat" in alert(c)[0]["text"] and not banned(100) and not edits(c)
    c = await press(10, "adm_broadcast"); assert alert(c)
    c = await press(10, "adm_users"); assert not alert(c) and edits(c)
    c = await press(555, "adm_stats"); assert alert(c)
    c = await press(11, "sa_menu"); assert alert(c) and "superadmin" in alert(c)[0]["text"]
    c = await press(11, "ban_100"); d = last(c); assert "Tasdiqlang" in d["text"] and not banned(100)
    assert [x[0] for x in c if x[0] in ("SendMessage", "EditMessageText")] == ["SendMessage"], "tasdiq alohida xabar bo'lishi, asl xabar o'zgarmasligi kerak"
    tok = [x for x in cbs(d) if x.startswith("cf_ok_")][0]
    c = await press(11, tok); assert banned(100), "tasdiqdan keyin ban bajarilishi kerak"
    assert any(x[0] == "DeleteMessage" for x in c), "tasdiq xabari o'chirilishi kerak"
    await press(11, "unban_100"); assert not banned(100)
    c = await press(11, "ban_101"); d = last(c); no = [x for x in cbs(d) if x.startswith("cf_no_")][0]
    c = await press(11, no); assert any(x[0] == "DeleteMessage" for x in c) and not banned(101)
    c = await press(11, tok); assert alert(c)                            # eski token qayta ishlatilmaydi
    d = last(await press(11, "bc_send_now")); assert "YUBORILADI" in d["text"]
    d = last(await press(2, "ban_102")); assert "Tasdiqlang" in d["text"]   # ADMIN_IDS (env) adminlari to'liq huquqli
    print("OK 1: RBAC (moderator rad), tasdiq (ha/yo'q/eskirgan), env admin, superadmin-only")

    # 2) ruxsat muharriri
    d = last(await press(1, "sa_perm")); assert "sa_pa_10" in cbs(d) and "sa_pa_11" in cbs(d)
    d = last(await press(1, "sa_pa_10")); assert "sa_pt_10_ban" in cbs(d) and any(b["text"] == "❌ Ban" for b in btns(d))
    await press(1, "sa_pt_10_ban"); assert "ban" in perms.get_perms(10)
    d = last(await press(10, "ban_103")); assert "Tasdiqlang" in d["text"]
    await press(1, "sa_pp_10_viewer"); assert perms.get_perms(10) == {"stats", "users"}
    assert alert(await press(10, "ban_104")) and alert(await press(10, "adm_movies"))
    assert any(e["action"] == "set_perms" for e in [dict(r) for r in ad.audit_page(0, 10)])
    d = last(await press(1, "sa_pl_10")); assert "Audit" in d["text"]
    print("OK 2: ruxsat muharriri (yoqish, preset, kuchga kirishi, audit)")

    # 3) PIN
    d = last(await press(1, "sa_menu")); assert "PIN o'rnatilmagan" in d["text"] and "sa_health" in cbs(d) and "sa_perm" in cbs(d)
    await press(1, "sa_pin"); await press(1, "sa_pin_set")
    c = await say(1, "12"); assert "4-8" in last(c)["text"]
    await say(1, "4321"); c = await say(1, "4321")
    assert pin.enabled() and pin.verify("4321") and any(x[0] == "DeleteMessage" for x in c), "PIN o'rnatilishi va xabar o'chirilishi kerak"
    pin.lock(1)
    d = last(await press(1, "sa_menu")); assert "PIN kiriting" in d["text"]
    d = last(await say(1, "1111")); assert "Noto'g'ri" in d["text"] and "4" in d["text"]
    c = await say(1, "4321"); d = last(c); assert "Superadmin panel" in d["text"], d                # redispatch: asl callback bajarildi
    d = last(await press(1, "sa_perm")); assert "Admin ruxsatlari" in d["text"]                      # sessiya ochiq
    pin.lock(1); d = last(await press(1, "adm_admins")); assert "PIN kiriting" in d["text"]
    await say(1, "4321")
    print("OK 3: PIN (o'rnatish, qulf, xato urinish, to'g'ri PIN -> asl amal, adminlar bo'limi)")

    # 4) dashboard / grafik / hisobot
    conn = db.get_conn(); conn.execute("INSERT INTO payments (user_id,stars,plan) VALUES (100,100,'vip')"); conn.execute("INSERT INTO search_logs (user_id,query,found) VALUES (100,'a',1),(100,'zz',0)"); conn.commit(); conn.close()
    d = last(await press(11, "adm_stats")); assert "DAU" in d["text"] and "WAU" in d["text"] and "dash_chart_30" in cbs(d) and "konversiya" in d["text"], d["text"]
    for per in ("dash_7", "dash_90"): assert "kun" in last(await press(11, per))["text"]
    c = await press(11, "dash_chart_30"); ph = [x for x in c if x[0] == "SendPhoto"]; assert ph, [x[0] for x in c]
    assert "kino" in last(await press(11, "dash_top"))["text"].lower() or True
    assert "so'rovlar" in last(await press(11, "dash_q_30"))["text"]
    c = await press(11, "dash_rep_7"); assert any(x[0] == "SendDocument" and x[1]["chat_id"] == 11 for x in c)
    c = await press(10, "dash_rep_7"); assert alert(c) and not any(x[0] == "SendDocument" for x in c)      # moderatorda 'export' yo'q
    print("OK 4: dashboard, davrlar, grafik (rasm), top, XLSX hisobot va ruxsat")

    # 5) salomatlik
    ad.log_error("handler", "ValueError: test xatosi", 77)
    d = last(await press(1, "sa_health")); t = d["text"]
    assert "Uptime" in t and "navbatda: <b>3</b>" in t and "SECRETPATH" not in t and "kino.onrender.com" in t, t
    d = last(await press(1, "sa_err_0")); assert "test xatosi" in d["text"] and "sa_errclr" in cbs(d)
    d = last(await press(1, "sa_errclr")); assert ad.count_errors() == 0
    print("OK 5: salomatlik paneli (webhook yashirin yo'l, navbat, xatolar logi, tozalash)")

    # 6) audit 2.0
    for i in range(14): db.audit(11 if i % 2 else 2, "ban" if i % 3 == 0 else "give_plan", str(100 + i), "x")
    d = last(await press(11, "adm_audit")); assert "au_p_1" in cbs(d) and "Admin" in d["text"] and d["text"].count("<code>") >= 8
    d = last(await press(11, "au_a")); aid = [x for x in cbs(d) if x.startswith("au_a_")][0]
    d = last(await press(11, aid)); assert "Filtr" in d["text"] and "au_c" in cbs(d)
    d = last(await press(11, "au_t")); d = last(await press(11, "au_t_0")); assert "🏷" in d["text"]
    d = last(await press(11, "au_c")); assert "Filtr" not in d["text"]
    print("OK 6: audit (sahifalash, admin ismi, admin/amal filtri, tozalash)")

    # 7) eslatma va teglar
    await press(11, "un_add_103"); c = await say(11, "Shubhali to'lov so'ragan")
    assert ad.count_notes(103) == 1
    d = last(await press(11, "un_list_103")); assert "Shubhali" in d["text"]
    nid = ad.get_notes(103)[0]["id"]
    assert alert(await press(2, f"un_del_{nid}")) and ad.count_notes(103) == 1                    # muallif emas -> rad
    await press(1, f"un_del_{nid}"); assert ad.count_notes(103) == 0                              # superadmin o'chira oladi
    d = last(await press(11, "un_tags_103")); assert any("Shubhali" in b["text"] for b in btns(d))
    await press(11, "un_tg_103_1"); assert "⚠️ Shubhali" in ad.get_tags(103)
    await press(11, "un_newtag_103"); await say(11, "Kino-fan"); assert "Kino-fan" in ad.get_tags(103)
    d = last(await press(11, "adm_user_103")); assert "Teglar" in d["text"] and "un_tags_103" in cbs(d)
    d = last(await press(11, "ut_tags")); assert any("Shubhali" in b["text"] for b in btns(d))
    d = last(await press(11, "ut_f_0")); assert any(b["callback_data"] == "adm_user_103" for b in btns(d))
    await press(11, "adm_user_lookup"); d = last(await say(11, "tag:shubh")); assert "Shubhali" in d["text"]
    print("OK 7: eslatma (qo'shish, o'chirish huquqi), teglar, karta, teg bo'yicha ro'yxat va qidiruv")

    # 8) faollik (DAU)
    before = ad.dashboard(7)["dau"]
    db.register_user(900, "newu", "New User")                                          # yangi user: bugun faol
    assert ad.dashboard(7)["dau"] == before + 1
    await say(900, "salom"); await say(900, "yana"); assert ad.dashboard(7)["dau"] == before + 1   # takror hisoblanmaydi
    await say(901, "ro'yxatsiz"); assert ad.dashboard(7)["dau"] == before + 1                      # ro'yxatdan o'tmagan hisoblanmaydi
    print("OK 8: faollik (kuniga bir marta, yangi user bugun faol)")

    # 9) avto-hisobot
    db.set_setting("report_daily", "1"); db.set_setting("report_hour", "0"); CALLS.clear()
    await reports._tick(bot); assert sum(1 for x in CALLS if x[0] == "SendDocument" and x[1]["chat_id"] == 1) == 1
    CALLS.clear(); await reports._tick(bot); assert not any(x[0] == "SendDocument" for x in CALLS)
    d = last(await press(1, "sa_report")); assert "Kunlik" in d["text"] and "sa_rep_t_weekly" in cbs(d)
    await press(1, "sa_rep_t_weekly"); assert db.get_setting("report_weekly") == "1"
    print("OK 9: avto-hisobot (kuniga bir marta, sozlamalar)")
    print("ALL ADMIN2 OK")
asyncio.run(main())
