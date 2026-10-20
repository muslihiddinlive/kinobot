"""DB zaxira nusxasi Telegram'da: SQLite -> gzip -> pin qilingan hujjat.

Nega kerak: Render Free'da disk vaqtincha. Har redeploy/restart/uxlashdan keyin
kinobot.db o'chib ketadi (foydalanuvchilar, VIP, to'lovlar, referal, katalog).

Qanday ishlaydi
  * backup_loop: har BACKUP_INTERVAL_MIN daqiqada DB o'zgargan bo'lsa, snapshot
    olinadi (sqlite backup API, integrity_check) va BITTA xabar tahrirlanib
    (editMessageMedia) yangilanadi. Xabar chatda pin qilingan.
  * Sutkada bir marta alohida arxiv xabari yuboriladi (oxirgi 7 tasi saqlanadi).
  * restore_if_needed: bot bo'sh diskda ishga tushsa, getChat().pinned_message
    orqali oxirgi backup topilib, DB tiklanadi (init_db'dan OLDIN).
  * Xavfsizlik: backup bor-u tiklab bo'lmasa — bot ishga tushmaydi (bo'sh DB
    bilan ishlab, yaxshi backup'ni ustidan yozib yubormaslik uchun).

Cheklovlar: Bot API yuklab olish limiti 20 MB (gzip'langan hajm), yuklash 50 MB.
Ikki instance bir vaqtda ishlasa (redeploy paytida) oxirgi daqiqalardagi
o'zgarishlar yo'qolishi mumkin: BACKUP_INTERVAL_MIN ni kichik tuting.
"""
import asyncio
import gzip
import hashlib
import io
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import time
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import BufferedInputFile, InputMediaDocument

import database as db
from config import BACKUP_CHAT_ID, BACKUP_TOPIC_ID, BACKUP_INTERVAL_MIN, BACKUP_ENABLED

log = logging.getLogger(__name__)

MARK = "#kinobot_db"            # pin qilingan backup izohi shu bilan boshlanadi
ARCHIVE_MARK = "#kinobot_db_archive"
MAX_DOWNLOAD = 19 * 1024 * 1024  # getFile limiti 20 MB
MAX_UPLOAD = 45 * 1024 * 1024    # sendDocument limiti 50 MB
KEEP_ARCHIVES = 7
ARCHIVE_EVERY_SEC = 24 * 3600

_lock = asyncio.Lock()
_state = {
    "msg_id": None, "last_hash": None, "last_ok": None, "last_error": None,
    "size": 0, "pinned": None, "restored": None, "last_archive": 0.0,
    "archive_ids": [],
}


# ───────────────────────── yordamchilar ─────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def db_is_empty() -> bool:
    """Diskda DB yo'q yoki jadvallari yo'q bo'lsa True (yangi/tozalangan disk)."""
    p = db.DB_PATH
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return True
    try:
        c = sqlite3.connect(p)
        n = c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        c.close()
        return n == 0
    except sqlite3.Error:
        return False


def make_snapshot() -> tuple[bytes, str, int]:
    """Ishlayotgan DB'ning izchil nusxasi -> (gzip bytes, sha256(raw), users soni)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    src = sqlite3.connect(db.DB_PATH, timeout=30)
    try:
        dst = sqlite3.connect(tmp.name)
        try:
            src.backup(dst)
            ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
            if ok != "ok":
                raise RuntimeError(f"integrity_check: {ok}")
            try:
                users = dst.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            except sqlite3.Error:
                users = 0
        finally:
            dst.close()
        with open(tmp.name, "rb") as f:
            raw = f.read()
    finally:
        src.close()
        try: os.unlink(tmp.name)
        except OSError: pass
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6, mtime=0) as gz:
        gz.write(raw)
    return buf.getvalue(), hashlib.sha256(raw).hexdigest(), users


def _restore_bytes(gz_bytes: bytes, expect_sha16: str | None) -> int:
    """gzip bytes -> tekshirish -> DB_PATH. Tiklangan users sonini qaytaradi."""
    raw = gzip.decompress(gz_bytes)
    if expect_sha16 and hashlib.sha256(raw).hexdigest()[:16] != expect_sha16:
        raise RuntimeError("sha256 mos kelmadi (backup buzilgan)")
    d = os.path.dirname(db.DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = db.DB_PATH + ".restore"
    with open(tmp, "wb") as f:
        f.write(raw)
    try:
        c = sqlite3.connect(tmp)
        ok = c.execute("PRAGMA integrity_check").fetchone()[0]
        users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        c.close()
        if ok != "ok":
            raise RuntimeError(f"integrity_check: {ok}")
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise
    for ext in ("-wal", "-shm"):          # eski WAL qoldiqlari bo'lsa o'chiramiz
        try: os.unlink(db.DB_PATH + ext)
        except OSError: pass
    shutil.move(tmp, db.DB_PATH)
    return users


def _caption(sha: str, size: int, users: int, archive=False) -> str:
    mark = ARCHIVE_MARK if archive else MARK
    return f"{mark} v1\n🕒 {_now()}\n👥 {users} user | 📦 {size // 1024} KB\nsha={sha[:16]}"


def _parse_sha(caption: str | None) -> str | None:
    for part in (caption or "").split():
        if part.startswith("sha="):
            return part[4:]
    return None


async def _find_pinned(bot: Bot):
    chat = await bot.get_chat(BACKUP_CHAT_ID)
    pm = getattr(chat, "pinned_message", None)
    if pm and pm.document and (pm.caption or "").startswith(MARK) and not (pm.caption or "").startswith(ARCHIVE_MARK):
        return pm
    return None


# ───────────────────────── tiklash ─────────────────────────
async def restore_if_needed(bot: Bot) -> str:
    """init_db'dan OLDIN chaqiring. Qaytaradi: 'skipped' | 'present' | 'fresh' | 'restored'.

    Backup bor, lekin tiklab bo'lmasa RuntimeError ko'taradi (bot ishga tushmaydi).
    """
    if not BACKUP_ENABLED:
        log.warning("Backup o'chiq (BACKUP_CHAT_ID/DB_GROUP_ID yo'q): DB Render Free'da yo'qolishi mumkin!")
        return "skipped"
    if not db_is_empty():
        log.info("DB diskda bor, tiklash shart emas")
        return "present"

    pm = None
    last_err = None
    for delay in (0, 4, 12):
        if delay:
            await asyncio.sleep(delay)
        try:
            pm = await _find_pinned(bot)
            last_err = None
            break
        except TelegramAPIError as e:
            last_err = e
            log.warning("Backup izlashda xato: %s", e)
    if last_err is not None:
        raise RuntimeError(f"Backup chatiga ulanib bo'lmadi ({last_err}). Bo'sh DB bilan ishga tushmaymiz.")

    if pm is None:
        log.warning("Pin qilingan backup topilmadi: yangi (bo'sh) DB bilan boshlanadi")
        _state["restored"] = "fresh"
        return "fresh"

    size = pm.document.file_size or 0
    if size > MAX_DOWNLOAD:
        raise RuntimeError(f"Backup {size // 1024} KB: Bot API 20 MB limitidan katta, tiklab bo'lmaydi")
    for attempt in range(3):
        try:
            f = await bot.get_file(pm.document.file_id)
            buf = io.BytesIO()
            await bot.download_file(f.file_path, destination=buf)
            users = await asyncio.to_thread(_restore_bytes, buf.getvalue(), _parse_sha(pm.caption))
            _state.update(msg_id=pm.message_id, restored=f"{users} user", last_hash=None)
            log.info("✅ DB Telegram backup'dan tiklandi: %s user, %s KB", users, size // 1024)
            return "restored"
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("Tiklash urinishi %s muvaffaqiyatsiz: %s", attempt + 1, e)
            await asyncio.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Backup bor, lekin tiklab bo'lmadi ({last_err}). Bo'sh DB bilan ishga tushmaymiz.")


# ───────────────────────── zaxira olish ─────────────────────────
async def backup_now(bot: Bot, force: bool = False) -> dict:
    """Snapshot -> Telegram. O'zgarmagan bo'lsa (force=False) yubormaydi."""
    if not BACKUP_ENABLED:
        return {"ok": False, "error": "backup o'chiq"}
    async with _lock:
        try:
            gz, sha, users = await asyncio.to_thread(make_snapshot)
            if len(gz) > MAX_UPLOAD:
                raise RuntimeError(f"gzip {len(gz) // 1024} KB: 50 MB limitidan katta")
            if len(gz) > MAX_DOWNLOAD:
                log.warning("Backup %s KB: 20 MB yuklab olish limitiga yaqinlashdi!", len(gz) // 1024)
            if not force and sha == _state["last_hash"]:
                return {"ok": True, "skipped": True}

            fname = f"kinobot_{datetime.now(timezone.utc):%Y%m%d_%H%M}.db.gz"
            cap = _caption(sha, len(gz), users)
            msg_id = _state["msg_id"]
            if msg_id:
                try:
                    await bot.edit_message_media(
                        chat_id=BACKUP_CHAT_ID, message_id=msg_id,
                        media=InputMediaDocument(media=BufferedInputFile(gz, fname), caption=cap))
                except TelegramBadRequest as e:
                    if "not modified" in str(e).lower():
                        pass
                    else:
                        log.warning("Backup xabarini tahrirlab bo'lmadi (%s): yangisi yuboriladi", e)
                        msg_id = None
            if not msg_id:
                m = await bot.send_document(
                    BACKUP_CHAT_ID, BufferedInputFile(gz, fname), caption=cap,
                    message_thread_id=BACKUP_TOPIC_ID or None, disable_notification=True)
                msg_id = m.message_id
                try:
                    await bot.pin_chat_message(BACKUP_CHAT_ID, msg_id, disable_notification=True)
                    _state["pinned"] = True
                except TelegramAPIError as e:
                    _state["pinned"] = False
                    log.error("Backup xabarini PIN qilib bo'lmadi: %s. Botga 'Xabarlarni pin qilish' huquqini bering, "
                              "aks holda tiklash ishlamaydi!", e)
            _state.update(msg_id=msg_id, last_hash=sha, last_ok=_now(), last_error=None, size=len(gz))
            await _maybe_archive(bot, gz, sha, users, fname)
            return {"ok": True, "size": len(gz), "users": users, "pinned": _state["pinned"]}
        except Exception as e:  # noqa: BLE001
            _state["last_error"] = f"{_now()}: {e}"
            log.error("Backup xatosi: %s", e)
            return {"ok": False, "error": str(e)}


async def _maybe_archive(bot: Bot, gz: bytes, sha: str, users: int, fname: str):
    """Sutkada bir marta alohida arxiv (buzilgan snapshot yagona nusxani yo'qotmasligi uchun)."""
    if not _state["last_archive"]:
        try: _state["last_archive"] = float(db.get_setting("backup_last_archive", "0") or 0)
        except ValueError: _state["last_archive"] = 0.0
        try: _state["archive_ids"] = json.loads(db.get_setting("backup_archive_ids", "[]") or "[]")
        except ValueError: _state["archive_ids"] = []
    if time.time() - _state["last_archive"] < ARCHIVE_EVERY_SEC:
        return
    try:
        m = await bot.send_document(
            BACKUP_CHAT_ID, BufferedInputFile(gz, "archive_" + fname),
            caption=_caption(sha, len(gz), users, archive=True),
            message_thread_id=BACKUP_TOPIC_ID or None, disable_notification=True)
    except TelegramAPIError as e:
        log.warning("Arxiv yuborilmadi: %s", e)
        return
    ids = (_state["archive_ids"] + [m.message_id])
    for old in ids[:-KEEP_ARCHIVES]:
        try: await bot.delete_message(BACKUP_CHAT_ID, old)
        except TelegramAPIError: pass
    _state["archive_ids"] = ids[-KEEP_ARCHIVES:]
    _state["last_archive"] = time.time()
    db.set_setting("backup_last_archive", str(_state["last_archive"]))
    db.set_setting("backup_archive_ids", json.dumps(_state["archive_ids"]))


async def backup_loop(bot: Bot):
    """Fon vazifasi. Birinchi backup 60 s dan keyin, so'ng har BACKUP_INTERVAL_MIN daqiqada."""
    if not BACKUP_ENABLED:
        return
    await asyncio.sleep(60)
    while True:
        try:
            await backup_now(bot)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.error("backup_loop: %s", e)
        await asyncio.sleep(BACKUP_INTERVAL_MIN * 60)


def status_text() -> str:
    if not BACKUP_ENABLED:
        return ("💾 <b>Backup: O'CHIQ</b>\n\n⚠️ BACKUP_CHAT_ID (yoki DB_GROUP_ID) berilmagan. "
                "Render Free'da DB redeploydan keyin yo'qoladi!")
    pin = {True: "✅ pin qilingan", False: "❌ pin QILINMAGAN (tiklash ishlamaydi!)", None: "—"}[_state["pinned"]]
    lines = [
        "💾 <b>DB backup (Telegram)</b>", "",
        f"🕒 Oxirgi muvaffaqiyatli: {_state['last_ok'] or 'hali yo`q'}",
        f"📦 Hajmi: {_state['size'] // 1024} KB (limit 20 MB)",
        f"📌 {pin}",
        f"🔁 Har {BACKUP_INTERVAL_MIN} daqiqada (o'zgargan bo'lsa)",
    ]
    if _state["restored"]:
        lines.append(f"♻️ Ishga tushganda: {_state['restored']}")
    if _state["last_error"]:
        lines.append(f"⚠️ Oxirgi xato: <code>{_state['last_error'][:200]}</code>")
    return "\n".join(lines)
