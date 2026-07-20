import csv
import io
import sqlite3
import database as db
from datetime import date

def export_users_csv() -> bytes:
    """Barcha foydalanuvchilarni CSV ga eksport qilish"""
    conn = db.get_conn()
    users = conn.execute(
        "SELECT user_id, username, full_name, plan, plan_until, "
        "bought_limit, referral_points, total_stars, is_banned, lang, joined_at "
        "FROM users ORDER BY joined_at DESC"
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Username", "Ism", "Plan", "Muddati",
        "Abadiy limit", "Ball", "Yulduz", "Ban", "Til", "Qo'shilgan"
    ])
    for u in users:
        writer.writerow([
            u["user_id"],
            f"@{u['username']}" if u["username"] else "—",
            u["full_name"],
            u["plan"].upper(),
            u["plan_until"] or "—",
            u["bought_limit"],
            u["referral_points"],
            u["total_stars"],
            "Ha" if u["is_banned"] else "Yo'q",
            u["lang"].upper(),
            u["joined_at"]
        ])

    return output.getvalue().encode("utf-8-sig")  # Excel uchun BOM

def export_payments_csv() -> bytes:
    """To'lovlar tarixi CSV"""
    conn = db.get_conn()
    payments = conn.execute(
        "SELECT p.*, u.username, u.full_name FROM payments p "
        "LEFT JOIN users u ON p.user_id = u.user_id "
        "ORDER BY p.paid_at DESC"
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Username", "Ism", "Paket", "Yulduz", "Sana"])
    for p in payments:
        writer.writerow([
            p["user_id"],
            f"@{p['username']}" if p["username"] else "—",
            p["full_name"],
            p["plan"],
            p["stars"],
            p["paid_at"]
        ])

    return output.getvalue().encode("utf-8-sig")

def export_movies_csv() -> bytes:
    """Kinolar ro'yxati CSV"""
    conn = db.get_conn()
    movies = conn.execute(
        "SELECT code, title, year, country, language, format, "
        "downloads, user_rating, rating_count, tags, added_at FROM movies ORDER BY added_at DESC"
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Kod", "Nom", "Yil", "Davlat", "Til", "Format",
        "Yuklashlar", "Reyting", "Baholar", "Fishkalar", "Qo'shilgan"
    ])
    for m in movies:
        writer.writerow([
            m["code"], m["title"], m["year"], m["country"],
            m["language"], m["format"], m["downloads"],
            m["user_rating"], m["rating_count"], m["tags"], m["added_at"]
        ])

    return output.getvalue().encode("utf-8-sig")
