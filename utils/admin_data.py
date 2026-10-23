"""Admin panel 2.0 ma'lumotlar qatlami: ruxsatlar, faollik/tahlil, audit, eslatma/teglar, xatolar logi."""
from datetime import date, timedelta

import database as db


# ═══════════════ Ruxsatlar (RBAC) ═══════════════
def get_admin_perms_raw(user_id: int):
    a = db.get_admin(user_id)
    return None if not a else a["perms"]


def set_admin_perms(user_id: int, perms) -> None:
    conn = db.get_conn()
    conn.execute("UPDATE admins SET perms=? WHERE user_id=?", (",".join(sorted(perms)), user_id))
    conn.commit(); conn.close()


# ═══════════════ Faollik (DAU/WAU/MAU) ═══════════════
def touch_active(user_id: int):
    """Bugungi birinchi faollikni qayd qiladi (kuniga 1 marta yozadi). True = yangi faol, False = bugun allaqachon,
    None = foydalanuvchi hali ro'yxatdan o'tmagan (register_user o'zi hisoblaydi)."""
    today = str(date.today())
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT last_active FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return None
        if row["last_active"] == today:
            return False
        conn.execute("UPDATE users SET last_active=? WHERE user_id=?", (today, user_id))
        conn.execute("INSERT INTO daily_active (day, active) VALUES (?,1) ON CONFLICT(day) DO UPDATE SET active=active+1", (today,))
        if not db.get_setting("activity_since", ""):
            conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('activity_since',?)", (today,))
        conn.commit()
        return True
    finally:
        conn.close()


def _days(n: int):
    today = date.today()
    return [str(today - timedelta(days=i)) for i in range(n - 1, -1, -1)]


def _series(sql: str, days: int, params=()):
    start = _days(days)[0]
    conn = db.get_conn()
    rows = conn.execute(sql, (start, *params)).fetchall()
    conn.close()
    m = {r[0]: (r[1] or 0) for r in rows}
    return [(d, m.get(d, 0)) for d in _days(days)]


def series_new_users(days):  return _series("SELECT joined_at d, COUNT(*) FROM users WHERE joined_at>=? GROUP BY joined_at", days)
def series_dau(days):        return _series("SELECT day, active FROM daily_active WHERE day>=?", days)
def series_searches(days):   return _series("SELECT date(searched_at) d, COUNT(*) FROM search_logs WHERE date(searched_at)>=? GROUP BY d", days)
def series_stars(days):      return _series("SELECT date(paid_at) d, SUM(stars) FROM payments WHERE date(paid_at)>=? GROUP BY d", days)


def dashboard(days: int = 30) -> dict:
    today = str(date.today())
    conn = db.get_conn()
    one = lambda sql, *p: (conn.execute(sql, p).fetchone()[0] or 0)
    d = {
        "total": one("SELECT COUNT(*) FROM users"),
        "new_today": one("SELECT COUNT(*) FROM users WHERE joined_at=?", today),
        "new_period": one("SELECT COUNT(*) FROM users WHERE joined_at>=?", _days(days)[0]),
        "dau": one("SELECT active FROM daily_active WHERE day=?", today),
        "wau": one("SELECT COUNT(*) FROM users WHERE last_active>=?", _days(7)[0]),
        "mau": one("SELECT COUNT(*) FROM users WHERE last_active>=?", _days(30)[0]),
        "paid_now": one("SELECT COUNT(*) FROM users WHERE plan IN ('pro','vip') AND (plan_until IS NULL OR plan_until>=?)", today),
        "banned": one("SELECT COUNT(*) FROM users WHERE is_banned=1"),
        "stars_7": one("SELECT SUM(stars) FROM payments WHERE date(paid_at)>=?", _days(7)[0]),
        "stars_period": one("SELECT SUM(stars) FROM payments WHERE date(paid_at)>=?", _days(days)[0]),
        "pay_count": one("SELECT COUNT(*) FROM payments WHERE date(paid_at)>=?", _days(days)[0]),
        "payers": one("SELECT COUNT(DISTINCT user_id) FROM payments WHERE date(paid_at)>=?", _days(days)[0]),
        "searches_today": one("SELECT COUNT(*) FROM search_logs WHERE date(searched_at)=?", today),
        "miss_period": one("SELECT COUNT(*) FROM search_logs WHERE found=0 AND date(searched_at)>=?", _days(days)[0]),
        "search_period": one("SELECT COUNT(*) FROM search_logs WHERE date(searched_at)>=?", _days(days)[0]),
        "activity_since": db.get_setting("activity_since", ""),
    }
    conn.close()
    d["stickiness"] = round(100 * d["dau"] / d["mau"], 1) if d["mau"] else 0.0
    d["paid_pct"] = round(100 * d["paid_now"] / d["total"], 1) if d["total"] else 0.0
    d["conversion"] = round(100 * d["payers"] / d["mau"], 1) if d["mau"] else 0.0
    d["miss_pct"] = round(100 * d["miss_period"] / d["search_period"], 1) if d["search_period"] else 0.0
    return d


def top_movies(limit=5):
    conn = db.get_conn()
    r = conn.execute("SELECT code,title,downloads,is_trending FROM movies ORDER BY downloads DESC LIMIT ?", (limit,)).fetchall()
    conn.close(); return r


def top_queries(days=30, limit=10):
    conn = db.get_conn()
    r = conn.execute("""SELECT lower(query) q, COUNT(*) c, SUM(found) f FROM search_logs
                        WHERE date(searched_at)>=? GROUP BY lower(query) ORDER BY c DESC LIMIT ?""",
                     (_days(days)[0], limit)).fetchall()
    conn.close(); return r


SPARK = "▁▂▃▄▅▆▇█"
def sparkline(values) -> str:
    vals = list(values)
    if not vals: return ""
    hi = max(vals)
    if hi <= 0: return SPARK[0] * len(vals)
    return "".join(SPARK[min(7, int(v / hi * 7.999))] for v in vals)


# ═══════════════ Audit 2.0 ═══════════════
def _audit_where(admin_id, action):
    w, p = [], []
    if admin_id: w.append("admin_id=?"); p.append(admin_id)
    if action:   w.append("action=?");   p.append(action)
    return (" WHERE " + " AND ".join(w)) if w else "", p


def audit_page(offset=0, limit=8, admin_id=None, action=None):
    where, p = _audit_where(admin_id, action)
    conn = db.get_conn()
    rows = conn.execute(f"SELECT * FROM audit_log{where} ORDER BY id DESC LIMIT ? OFFSET ?", (*p, limit, offset)).fetchall()
    conn.close(); return rows


def audit_count(admin_id=None, action=None) -> int:
    where, p = _audit_where(admin_id, action)
    conn = db.get_conn(); n = conn.execute(f"SELECT COUNT(*) FROM audit_log{where}", p).fetchone()[0]; conn.close(); return n


def audit_admins():
    conn = db.get_conn()
    r = conn.execute("SELECT admin_id, COUNT(*) c FROM audit_log GROUP BY admin_id ORDER BY c DESC LIMIT 20").fetchall()
    conn.close(); return r


def audit_actions():
    conn = db.get_conn()
    r = conn.execute("SELECT action, COUNT(*) c FROM audit_log GROUP BY action ORDER BY c DESC LIMIT 20").fetchall()
    conn.close(); return r


def person_name(user_id) -> str:
    """Admin/foydalanuvchi ismi (admins -> users -> id)."""
    from config import SUPERADMIN_ID
    if user_id == SUPERADMIN_ID and SUPERADMIN_ID:
        return "👑 Superadmin"
    conn = db.get_conn()
    r = conn.execute("SELECT full_name, username FROM admins WHERE user_id=?", (user_id,)).fetchone()
    if not r or not (r["full_name"] or r["username"]):
        r = conn.execute("SELECT full_name, username FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if r and (r["full_name"] or r["username"]):
        return r["full_name"] or f"@{r['username']}"
    return str(user_id)


# ═══════════════ Xatolar logi ═══════════════
def log_error(kind: str, message: str, update_id=None) -> None:
    conn = db.get_conn()
    conn.execute("INSERT INTO error_log (kind,message,update_id) VALUES (?,?,?)", (kind[:40], (message or "")[:600], update_id))
    conn.execute("DELETE FROM error_log WHERE id <= (SELECT MAX(id) FROM error_log) - 300")
    conn.commit(); conn.close()


def get_errors(limit=5, offset=0):
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM error_log ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    conn.close(); return r


def count_errors(hours=None) -> int:
    conn = db.get_conn()
    if hours:
        n = conn.execute("SELECT COUNT(*) FROM error_log WHERE at >= datetime('now', ?)", (f"-{int(hours)} hours",)).fetchone()[0]
    else:
        n = conn.execute("SELECT COUNT(*) FROM error_log").fetchone()[0]
    conn.close(); return n


def clear_errors() -> None:
    conn = db.get_conn(); conn.execute("DELETE FROM error_log"); conn.commit(); conn.close()


# ═══════════════ Eslatma va teglar ═══════════════
PRESET_TAGS = ["⭐ VIP-mijoz", "⚠️ Shubhali", "🎁 Bonus berilgan", "💬 Faol", "🧪 Test", "🚫 Spam"]


def add_note(user_id, admin_id, note) -> int:
    conn = db.get_conn()
    cur = conn.execute("INSERT INTO user_notes (user_id,admin_id,note) VALUES (?,?,?)", (user_id, admin_id, note.strip()[:500]))
    conn.commit(); nid = cur.lastrowid; conn.close(); return nid


def get_notes(user_id, limit=5):
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM user_notes WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
    conn.close(); return r


def count_notes(user_id) -> int:
    conn = db.get_conn(); n = conn.execute("SELECT COUNT(*) FROM user_notes WHERE user_id=?", (user_id,)).fetchone()[0]; conn.close(); return n


def delete_note(note_id) -> None:
    conn = db.get_conn(); conn.execute("DELETE FROM user_notes WHERE id=?", (note_id,)); conn.commit(); conn.close()


def get_note(note_id):
    conn = db.get_conn(); r = conn.execute("SELECT * FROM user_notes WHERE id=?", (note_id,)).fetchone(); conn.close(); return r


def get_tags(user_id):
    conn = db.get_conn(); r = conn.execute("SELECT tag FROM user_tags WHERE user_id=? ORDER BY added_at", (user_id,)).fetchall(); conn.close()
    return [x["tag"] for x in r]


def toggle_tag(user_id, tag, admin_id) -> bool:
    """Qo'shsa True, olib tashlasa False."""
    tag = tag.strip()[:24]
    conn = db.get_conn()
    ex = conn.execute("SELECT 1 FROM user_tags WHERE user_id=? AND tag=?", (user_id, tag)).fetchone()
    if ex:
        conn.execute("DELETE FROM user_tags WHERE user_id=? AND tag=?", (user_id, tag)); added = False
    else:
        conn.execute("INSERT INTO user_tags (user_id,tag,added_by) VALUES (?,?,?)", (user_id, tag, admin_id)); added = True
    conn.commit(); conn.close(); return added


def all_tags():
    conn = db.get_conn(); r = conn.execute("SELECT tag, COUNT(*) c FROM user_tags GROUP BY tag ORDER BY c DESC").fetchall(); conn.close()
    return [(x["tag"], x["c"]) for x in r]


def users_with_tag(tag, offset=0, limit=10):
    conn = db.get_conn()
    r = conn.execute("""SELECT u.* FROM users u JOIN user_tags t ON t.user_id=u.user_id
                        WHERE t.tag=? ORDER BY t.added_at DESC LIMIT ? OFFSET ?""", (tag, limit, offset)).fetchall()
    conn.close(); return r


def count_users_with_tag(tag) -> int:
    conn = db.get_conn(); n = conn.execute("SELECT COUNT(*) FROM user_tags WHERE tag=?", (tag,)).fetchone()[0]; conn.close(); return n
