"""Backup/tiklash mantiqini soxta Telegram bilan sinash:  python tools/smoke_backup.py"""
import asyncio, os, sys, types, io
os.environ.setdefault("BOT_TOKEN", "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
os.environ["SUPERADMIN_ID"] = "1"; os.environ["DB_GROUP_ID"] = "-100123"
os.environ["BACKUP_CHAT_ID"] = "-100999"; os.environ["DB_PATH"] = "/tmp/smoke_kino.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db
from utils import tg_backup as tb
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import GetChat

NS = types.SimpleNamespace

class FakeBot:
    def __init__(self): self.msgs = {}; self.files = {}; self.pinned = None; self.n = 100; self.fail_get_chat = False; self.edits = 0; self.sent = 0
    async def get_chat(self, chat_id):
        if self.fail_get_chat: raise TelegramNetworkError(GetChat(chat_id=chat_id), "boom")
        return NS(pinned_message=self.msgs.get(self.pinned) if self.pinned else None)
    def _mk(self, data, caption, name):
        self.n += 1; fid = f"F{self.n}"; self.files[fid] = data
        m = NS(message_id=self.n, caption=caption, document=NS(file_id=fid, file_size=len(data), file_name=name)); self.msgs[self.n] = m; return m
    async def send_document(self, chat_id, document, caption=None, **kw):
        self.sent += 1; return self._mk(document.data, caption, document.filename)
    async def edit_message_media(self, chat_id, message_id, media, **kw):
        self.edits += 1; old = self.msgs[message_id]; m = self._mk(media.media.data, media.caption, media.media.filename); m.message_id = message_id; self.msgs[message_id] = m
    async def pin_chat_message(self, chat_id, message_id, **kw): self.pinned = message_id
    async def delete_message(self, chat_id, message_id, **kw): self.msgs.pop(message_id, None)
    async def get_file(self, file_id): return NS(file_path=file_id)
    async def download_file(self, file_path, destination): destination.write(self.files[file_path])

def users(): c = db.get_conn(); n = c.execute("select count(*) from users").fetchone()[0]; c.close(); return n

async def main():
    for p in (db.DB_PATH, db.DB_PATH + "-wal", db.DB_PATH + "-shm"):
        if os.path.exists(p): os.remove(p)
    bot = FakeBot()
    # 1) bo'sh disk + backup yo'q -> fresh
    assert await tb.restore_if_needed(bot) == "fresh"
    db.init_db(); [db.register_user(i, f"u{i}", f"User {i}") for i in range(1, 6)]
    # 2) birinchi backup: yuboriladi va pin qilinadi
    r = await tb.backup_now(bot); assert r["ok"] and r["pinned"] and bot.sent >= 1 and bot.pinned, r
    first_id = bot.pinned
    # 3) o'zgarmagan -> skip (birinchi backupdan keyin arxiv yozuvi DB'ni 1 marta o'zgartiradi: avval o'shani yutamiz)
    await tb.backup_now(bot)
    r = await tb.backup_now(bot); assert r.get("skipped"), r
    # 4) o'zgarish -> xabar TAHRIRLANADI (yangi xabar emas), pin o'sha
    db.register_user(6, "u6", "User 6"); sent_before = bot.sent; edits_before = bot.edits
    r = await tb.backup_now(bot); assert r["ok"] and not r.get("skipped") and bot.edits == edits_before + 1 and bot.pinned == first_id, (r, bot.edits)
    assert bot.sent == sent_before, "yangi xabar yuborilmasligi kerak: mavjud xabar tahrirlanadi"
    # 5) disk tozalandi (Render redeploy) -> tiklanadi
    os.remove(db.DB_PATH); tb._state.update(msg_id=None, last_hash=None)
    assert tb.db_is_empty()
    assert await tb.restore_if_needed(bot) == "restored" and users() == 6, users()
    # 6) DB bor -> tiklash shart emas
    assert await tb.restore_if_needed(bot) == "present"
    # 7) Telegram ishlamayapti + backup bor -> bot BO'SH DB bilan boshlamaydi
    os.remove(db.DB_PATH); bot.fail_get_chat = True
    try: await tb.restore_if_needed(bot); raise SystemExit("RuntimeError kutilgan edi")
    except RuntimeError as e: print("OK (kutilgan xato):", str(e)[:70])
    bot.fail_get_chat = False
    # 8) buzilgan backup -> RuntimeError
    bad = bot.pinned; bot.files[bot.msgs[bad].document.file_id] = b"not gzip"
    try: await tb.restore_if_needed(bot); raise SystemExit("RuntimeError kutilgan edi")
    except RuntimeError as e: print("OK (buzilgan backup):", str(e)[:70])
    assert not os.path.exists(db.DB_PATH) or tb.db_is_empty()
    print("status:", tb.status_text().replace("\n", " | ")[:160])
    print("ALL OK")

asyncio.run(main())
