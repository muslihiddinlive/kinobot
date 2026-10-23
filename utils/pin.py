"""Superadmin PIN: salted scrypt hash (DB'da), vaqtinchalik sessiya, noto'g'ri urinishlarda bloklash."""
import hashlib
import hmac
import os
import time

from aiogram.fsm.state import State, StatesGroup

import database as db

KEY = "sa_pin"
TTL_KEY = "sa_pin_ttl"          # daqiqa
MAX_FAILS = 5
LOCK_SEC = 600

_unlocked: dict = {}
_fails: dict = {}


class PinState(StatesGroup):
    waiting = State()           # kirishda PIN kutish
    new = State()               # yangi PIN
    confirm_new = State()       # yangi PINni takrorlash


def enabled() -> bool:
    if os.getenv("SA_PIN_DISABLE") == "1":      # PIN esdan chiqsa: env orqali vaqtincha o'chirish
        return False
    return bool(db.get_setting(KEY, ""))


def valid_format(pin: str) -> bool:
    return pin.isdigit() and 4 <= len(pin) <= 8


def _hash(pin: str, salt: bytes) -> bytes:
    return hashlib.scrypt(pin.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)


def set_pin(pin: str) -> None:
    salt = os.urandom(16)
    db.set_setting(KEY, salt.hex() + "$" + _hash(pin, salt).hex())


def disable() -> None:
    db.set_setting(KEY, "")


def verify(pin: str) -> bool:
    stored = db.get_setting(KEY, "")
    if "$" not in stored:
        return False
    salt_hex, h_hex = stored.split("$", 1)
    return hmac.compare_digest(_hash(pin, bytes.fromhex(salt_hex)), bytes.fromhex(h_hex))


def ttl_minutes() -> int:
    try:
        return max(1, int(db.get_setting(TTL_KEY, "15") or 15))
    except ValueError:
        return 15


def unlocked(uid: int) -> bool:
    return time.time() < _unlocked.get(uid, 0)


def unlock(uid: int) -> None:
    _unlocked[uid] = time.time() + ttl_minutes() * 60
    _fails.pop(uid, None)


def lock(uid: int) -> None:
    _unlocked.pop(uid, None)


def lockout_left(uid: int) -> int:
    c, until = _fails.get(uid, (0, 0))
    return max(0, int(until - time.time()))


def attempt(uid: int, pin: str):
    """('ok'|'bad'|'locked', qolgan_urinish_yoki_soniya)"""
    left = lockout_left(uid)
    if left:
        return "locked", left
    if verify(pin):
        unlock(uid)
        return "ok", 0
    c, _ = _fails.get(uid, (0, 0))
    c += 1
    if c >= MAX_FAILS:
        _fails[uid] = (0, time.time() + LOCK_SEC)
        return "locked", LOCK_SEC
    _fails[uid] = (c, 0)
    return "bad", MAX_FAILS - c
