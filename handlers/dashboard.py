"""Dashboard 2.0: DAU/WAU/MAU, o'sish, daromad, konversiya, mini-grafiklar va rasmli diagramma."""
import asyncio
import html

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

import database as db
from utils import admin_data as ad, charts, reports

router = Router()
PERIODS = (7, 30, 90)


def _n(v) -> str:
    return f"{int(v):,}".replace(",", " ")


def _spark(series) -> str:
    return ad.sparkline(v for _, v in series)


def _kb(days: int, extra=None):
    mark = lambda d: f"✅ {d} kun" if d == days else f"{d} kun"
    rows = [[InlineKeyboardButton(text=mark(d), callback_data=f"dash_{d}") for d in PERIODS],
            [InlineKeyboardButton(text="📈 Grafik", callback_data=f"dash_chart_{days}"),
             InlineKeyboardButton(text="🏆 Top kinolar", callback_data="dash_top")],
            [InlineKeyboardButton(text="🔎 Top so'rovlar", callback_data=f"dash_q_{days}"),
             InlineKeyboardButton(text="📤 Hisobot (XLSX)", callback_data=f"dash_rep_{days}")],
            [InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"dash_{days}"),
             InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def render(days: int = 30) -> str:
    d = ad.dashboard(days)
    s = db.get_stats()
    w = min(days, 14)
    lines = [
        f"📊 <b>Dashboard</b> ({days} kun)", "",
        f"👥 <b>{_n(d['total'])}</b> user · +{d['new_today']} bugun · +{_n(d['new_period'])} ({days}k)",
        f"🟢 DAU <b>{_n(d['dau'])}</b> · WAU <b>{_n(d['wau'])}</b> · MAU <b>{_n(d['mau'])}</b> · yopishqoqlik <b>{d['stickiness']}%</b>",
        f"💎 Pullik: <b>{_n(d['paid_now'])}</b> ({d['paid_pct']}%) · 🚫 Ban: {_n(d['banned'])}",
        f"💰 ⭐{_n(d['stars_7'])} (7k) · ⭐{_n(d['stars_period'])} ({days}k) · {d['pay_count']} to'lov · konversiya <b>{d['conversion']}%</b>",
        f"🔎 Bugun {_n(d['searches_today'])} qidiruv · topilmagan <b>{d['miss_pct']}%</b>",
        f"🎬 {_n(s['total_movies'])} kino · 📥 {_n(s['total_downloads'])} yuklash", "",
        f"📈 Yangi ({w}k): <code>{_spark(ad.series_new_users(w))}</code>",
        f"📈 DAU ({w}k): <code>{_spark(ad.series_dau(w))}</code>",
        f"📈 Qidiruv ({w}k): <code>{_spark(ad.series_searches(w))}</code>",
        f"📈 Stars ({w}k): <code>{_spark(ad.series_stars(w))}</code>",
    ]
    if d["activity_since"]:
        lines += ["", f"<i>DAU/WAU/MAU {html.escape(d['activity_since'])} dan beri o'lchanmoqda (dastlabki kunlarda kam ko'rinadi).</i>"]
    return "\n".join(lines)


async def _show(cb: CallbackQuery, days: int):
    text = await asyncio.to_thread(render, days)
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=_kb(days))
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            raise


@router.callback_query(F.data == "adm_stats")
async def adm_stats(cb: CallbackQuery):
    await _show(cb, 30)
    await cb.answer()


@router.callback_query(F.data.regexp(r"^dash_(7|30|90)$"))
async def dash_period(cb: CallbackQuery):
    await _show(cb, int(cb.data.replace("dash_", "")))
    await cb.answer()


def _chart_png(days: int) -> bytes:
    w = min(days, 30)
    nu, dau, se, st = ad.series_new_users(w), ad.series_dau(w), ad.series_searches(w), ad.series_stars(w)
    labels = [f"{d[8:10]}.{d[5:7]}" for d, _ in nu]
    return charts.render([
        {"title": f"Yangi va faol userlar ({w} kun)", "labels": labels, "series": [
            {"name": "Yangi", "values": [v for _, v in nu], "kind": "bar"},
            {"name": "DAU", "values": [v for _, v in dau], "kind": "line"}]},
        {"title": f"Qidiruvlar va Stars ({w} kun)", "labels": labels, "series": [
            {"name": "Qidiruv", "values": [v for _, v in se], "kind": "line"},
            {"name": "Stars", "values": [v for _, v in st], "kind": "bar"}]},
    ])


@router.callback_query(F.data.regexp(r"^dash_chart_\d+$"))
async def dash_chart(cb: CallbackQuery):
    days = int(cb.data.replace("dash_chart_", ""))
    await cb.answer("⏳ Grafik chizilmoqda...")
    png = await asyncio.to_thread(_chart_png, days)
    await cb.message.answer_photo(BufferedInputFile(png, "dashboard.png"), caption=f"📈 Oxirgi {min(days, 30)} kun")


@router.callback_query(F.data == "dash_top")
async def dash_top(cb: CallbackQuery):
    rows = await asyncio.to_thread(ad.top_movies, 10)
    body = "\n".join(f"{i}. {'🔥 ' if m['is_trending'] else ''}<b>{html.escape(str(m['title']))}</b> — {_n(m['downloads'])}" for i, m in enumerate(rows, 1)) or "Hozircha yo'q."
    await cb.message.edit_text(f"🏆 <b>Top kinolar</b> (yuklashlar bo'yicha)\n\n{body}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Dashboard", callback_data="adm_stats")]]))
    await cb.answer()


@router.callback_query(F.data.regexp(r"^dash_q_\d+$"))
async def dash_queries(cb: CallbackQuery):
    days = int(cb.data.replace("dash_q_", ""))
    rows = await asyncio.to_thread(ad.top_queries, days, 12)
    body = "\n".join(f"{i}. <b>{html.escape(r['q'])}</b> — {r['c']}× {'✅' if r['f'] else '❌'}" for i, r in enumerate(rows, 1)) or "Hozircha yo'q."
    await cb.message.edit_text(f"🔎 <b>Top so'rovlar</b> ({days} kun)\n\n{body}\n\n<i>✅ topilgan, ❌ topilmagan</i>", parse_mode="HTML",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Dashboard", callback_data="adm_stats")]]))
    await cb.answer()


@router.callback_query(F.data.regexp(r"^dash_rep_\d+$"))
async def dash_report(cb: CallbackQuery, bot: Bot):
    days = int(cb.data.replace("dash_rep_", ""))
    await cb.answer("⏳ Hisobot tayyorlanmoqda...")
    await reports.send_report(bot, days, chat_id=cb.from_user.id)
    db.audit(cb.from_user.id, "report", f"{days}k")
