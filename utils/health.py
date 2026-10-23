"""Bot salomatligi: uptime, xotira, DB hajmi, fon vazifalari."""
import asyncio
import os
import sys
import time

import database as db

START = time.time()
_tasks: list = []


def register_tasks(tasks) -> None:
    _tasks[:] = list(tasks)


def uptime_text() -> str:
    s = int(time.time() - START)
    d, s = divmod(s, 86400); h, s = divmod(s, 3600); m, _ = divmod(s, 60)
    return (f"{d}k " if d else "") + f"{h}s {m}d"


def rss_mb() -> float:
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:  # noqa: BLE001
        return 0.0


def db_info() -> dict:
    size = os.path.getsize(db.DB_PATH) if os.path.exists(db.DB_PATH) else 0
    wal = os.path.getsize(db.DB_PATH + "-wal") if os.path.exists(db.DB_PATH + "-wal") else 0
    conn = db.get_conn()
    counts = {}
    for t in ("users", "movies", "search_logs", "audit_log", "error_log", "user_notes"):
        try:
            counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception:  # noqa: BLE001
            counts[t] = 0
    conn.close()
    return {"size_mb": size / 1048576, "wal_mb": wal / 1048576, "counts": counts}


async def loop_lag_ms() -> float:
    """Event loop kechikishi (qancha ko'p bo'lsa, bot shuncha 'qotadi')."""
    t0 = time.perf_counter()
    await asyncio.sleep(0.05)
    return max(0.0, (time.perf_counter() - t0 - 0.05) * 1000)


def tasks_status() -> list:
    out = []
    for t in _tasks:
        name = getattr(t.get_coro(), "__name__", "task")
        out.append((name, "✅" if not t.done() else "❌"))
    return out


def versions() -> str:
    import aiogram
    return f"Python {sys.version.split()[0]} · aiogram {aiogram.__version__}"
