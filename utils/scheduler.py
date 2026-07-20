import asyncio
import logging
import json
from datetime import datetime, date
import database as db

logger = logging.getLogger(__name__)

async def weekly_referral_stats(bot):
    """Har dushanba 06:00 — referal statistikasi kanalga"""
    from config import REQUIRED_CHANNEL_URL
    channels = db.get_required_channels()
    if not channels: return

    referrers = db.get_top_referrers(limit=50)
    if not referrers: return

    top5 = referrers[:5]
    rest = referrers[5:]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    # TOP 5 xabar
    top_text = (
        "🏆 <b>Haftalik Referal Reytingi</b>\n"
        f"📅 {date.today().strftime('%d.%m.%Y')}\n\n"
        "🔝 <b>TOP 5 Referal Yig'uvchilar:</b>\n\n"
    )
    for i, u in enumerate(top5):
        name = u["full_name"] or u["username"] or "Foydalanuvchi"
        points = int(float(u["referral_points"]))
        top_text += f"{medals[i]} <b>{name}</b> — {points} 🪙\n"

    # Qolganlar xabar
    rest_text = ""
    if rest:
        rest_text = "📋 <b>Boshqa faol referallar:</b>\n\n"
        for i, u in enumerate(rest, 6):
            name = u["full_name"] or u["username"] or "Foydalanuvchi"
            points = int(float(u["referral_points"]))
            rest_text += f"{i}. {name} — {points} 🪙\n"

    for ch in channels:
        try:
            await bot.send_message(ch["channel_id"], top_text, parse_mode="HTML")
            if rest_text:
                await bot.send_message(ch["channel_id"], rest_text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Referal stats xato {ch['channel_id']}: {e}")

async def daily_subscribers_report(bot):
    """Har kuni 06:00 — PRO/VIP obunachilar kanalga"""
    channels = db.get_required_channels()
    if not channels: return

    pro_list, vip_list = db.get_active_subscribers()
    if not pro_list and not vip_list: return

    text = (
        f"💎 <b>Faol Obunalar Ro'yxati</b>\n"
        f"📅 {date.today().strftime('%d.%m.%Y')}\n\n"
    )

    if vip_list:
        text += f"👑 <b>VIP ({len(vip_list)} ta):</b>\n"
        for u in vip_list[:20]:
            name = u["full_name"] or u["username"] or "Foydalanuvchi"
            text += f"  └ {name} — {u['plan_until']} gacha\n"
        text += "\n"

    if pro_list:
        text += f"💎 <b>PRO ({len(pro_list)} ta):</b>\n"
        for u in pro_list[:20]:
            name = u["full_name"] or u["username"] or "Foydalanuvchi"
            text += f"  └ {name} — {u['plan_until']} gacha\n"

    for ch in channels:
        try:
            await bot.send_message(ch["channel_id"], text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Subscribers report xato {ch['channel_id']}: {e}")

async def weekly_report_to_db(bot):
    """Haftalik statistika DB topic ga"""
    from config import DB_GROUP_ID, TOPIC_STATS
    s = db.get_stats()
    text = (
        f"📊 <b>Haftalik hisobot</b>\n📅 {date.today()}\n\n"
        f"👥 Jami: {s['total']} | 🆕 Bugun: {s['new_today']}\n"
        f"💎 PRO: {s['pro']} | 👑 VIP: {s['vip']}\n"
        f"⭐ Jami yulduz: {s['total_stars']}\n"
        f"🎬 Kinolar: {s['total_movies']} | 📥 Yuklashlar: {s['total_downloads']}\n"
    )
    try:
        await bot.send_message(DB_GROUP_ID, text, message_thread_id=TOPIC_STATS, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Haftalik hisobot xato: {e}")

async def process_scheduled_broadcasts(bot):
    """Rejalashtirilgan reklamalar"""
    broadcasts = db.get_pending_broadcasts()
    for bc in broadcasts:
        try:
            msgs = json.loads(bc["msgs"])
            target_type = bc["target_type"]

            if target_type.startswith("lang_"):
                users = db.get_users_by_lang(target_type.replace("lang_",""))
            else:
                users = db.get_users_by_plan(target_type)

            chats = db.get_bot_chats(exclude_db=True)
            all_targets = list(users) + [c["chat_id"] for c in chats]

            sent = failed = 0
            for target in all_targets:
                for m in msgs:
                    try:
                        await bot.copy_message(target, m["chat_id"], m["message_id"])
                        sent += 1
                    except: failed += 1

            db.mark_broadcast_sent(bc["id"])
            logger.info(f"Broadcast yuborildi: {sent} muvaffaqiyatli")

            from config import SUPERADMIN_ID
            try:
                await bot.send_message(SUPERADMIN_ID,
                    f"✅ Rejalashtirilgan reklama yuborildi!\n"
                    f"📤 {sent} ta | ❌ {failed} ta | 🎯 {target_type}")
            except: pass

        except Exception as e:
            logger.error(f"Broadcast xato: {e}")

async def cleanup_expired_plans():
    """Muddati tugagan planlarni tozalash"""
    today = str(date.today())
    conn = db.get_conn()
    conn.execute(
        "UPDATE users SET plan='free' WHERE plan IN ('pro','vip') "
        "AND plan_until < ? AND plan_until IS NOT NULL", (today,)
    )
    conn.commit()
    conn.close()

async def scheduler_loop(bot):
    """Asosiy scheduler loop"""
    while True:
        now = datetime.now()

        # Har daqiqa: rejalashtirilgan reklamalar
        await process_scheduled_broadcasts(bot)

        # Soat 06:00 da
        if now.hour == 6 and now.minute == 0:
            await cleanup_expired_plans()
            await daily_subscribers_report(bot)

            # Dushanba — haftalik hisobot
            if now.weekday() == 0:
                await weekly_referral_stats(bot)
                await weekly_report_to_db(bot)

        await asyncio.sleep(60)
