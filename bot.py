import asyncio
import logging
import time
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ChatMemberUpdated, ErrorEvent

from config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBHOOK_HEADER_SECRET, WEBAPP_HOST, WEBAPP_PORT
from database import init_db, init_episodes, save_bot_chat
from middlewares.subscription import SubscriptionMiddleware
from middlewares.maintenance import MaintenanceMiddleware
from middlewares.antiflood import AntiFloodMiddleware
from middlewares.dedupe import DedupeMiddleware
from middlewares.reactions import ReactionMiddleware
from middlewares.activity import ActivityMiddleware
from middlewares.guard import GuardMiddleware, set_dispatcher
from handlers import admin, movies, payment, user, search
from handlers import vip, inline_handler, broadcast_adv, admin_search, superadmin, dashboard, audit_view, user_notes, sa_tools
from utils.scheduler import scheduler_loop
from utils import tg_backup, health, reports, admin_data
from utils.profile_sync import profile_sync_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
_last_alert = {"t": 0.0}

def setup_dispatcher():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Webhook: Telegram qayta yuborgan takroriy update'larni o'tkazib yuboramiz
    dp.update.outer_middleware(DedupeMiddleware())
    dp.update.outer_middleware(ActivityMiddleware())     # DAU/WAU/MAU (kuniga 1 ta DB yozuvi / user)
    # Admin tugmalari: ruxsatlar (RBAC), superadmin PIN, xavfli amallarga tasdiq
    dp.callback_query.outer_middleware(GuardMiddleware())
    set_dispatcher(dp)
    # Guruhlarda superadmin/adminlar xabariga avto-reaksiya (handlerlarni to'smaydi)
    dp.message.outer_middleware(ReactionMiddleware())

    dp.message.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(MaintenanceMiddleware())
    dp.message.middleware(AntiFloodMiddleware(rate=5, per=5))
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    @dp.my_chat_member()
    async def on_chat_member(event: ChatMemberUpdated):
        chat = event.chat
        if chat.type == "private":      # foydalanuvchi botni bloklagan/ochgan: guruh ro'yxatiga kirmaydi
            return
        # holat saqlanadi (administrator/member/left/kicked): chiqarib yuborilgan chatlarga reklama ketmaydi
        save_bot_chat(chat.id, chat.type, getattr(chat, "title", "") or "", event.new_chat_member.status)

    # MUHIM: global error handler.
    # Har qanday handlerda kutilmagan xato (DB xatosi, None obyekt va h.k.)
    # chiqsa ham, callback tugmasi "yuklanmoqda" holatida abadiy qotib
    # qolmasligi kerak — shuning uchun bu yerda har doim cb.answer() yoki
    # xabar yuborish kafolatlanadi.
    @dp.errors()
    async def global_error_handler(event: ErrorEvent):
        logger.error(
            f"Handler xatosi: {event.exception} | update_id={event.update.update_id}",
            exc_info=event.exception,
        )
        try:
            if event.update.callback_query:
                await event.update.callback_query.answer(
                    "⚠️ Xatolik yuz berdi, qayta urining.", show_alert=True
                )
            elif event.update.message:
                await event.update.message.answer(
                    "⚠️ Xatolik yuz berdi, qayta urining."
                )
        except Exception:
            pass
        try:
            admin_data.log_error("handler", f"{type(event.exception).__name__}: {event.exception}", event.update.update_id)
        except Exception:
            pass
        # Xato xabarlari 30 soniyada bittadan (bir xil xato oqimi guruhni to'ldirib yubormasligi uchun)
        if time.time() - _last_alert["t"] > 30:
            _last_alert["t"] = time.time()
            try:
                from config import DB_GROUP_ID
                await bot.send_message(
                    DB_GROUP_ID,
                    f"🚨 Bot xatosi:\n<code>{event.exception}</code>\nupdate_id: {event.update.update_id}",
                )
            except Exception:
                pass
        return True

    # MUHIM: search.router oxirida bo'lishi kerak!
    # Chunki catch_any_text handler bor — boshqa handlerlar birinchi ishlashi shart.
    dp.include_router(admin.router)
    dp.include_router(admin_search.router)   # harfli qidiruv (lq_*)
    dp.include_router(superadmin.router)     # superadmin paneli (sa_*)
    dp.include_router(sa_tools.router)       # RBAC muharriri, salomatlik, PIN, hisobot
    dp.include_router(dashboard.router)      # Dashboard 2.0
    dp.include_router(audit_view.router)     # Audit 2.0
    dp.include_router(user_notes.router)     # eslatma va teglar
    dp.include_router(broadcast_adv.router)
    dp.include_router(movies.router)
    dp.include_router(payment.router)
    dp.include_router(vip.router)
    dp.include_router(user.router)
    dp.include_router(inline_handler.router)
    dp.include_router(search.router)   # ← OXIRDA (catch-all shu yerda)

    return bot, dp

def run_webhook():
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    from aiohttp import web

    bot, dp = setup_dispatcher()

    async def on_startup(app):
        # 1) Render Free'da disk bo'sh bo'lishi mumkin: DB'ni Telegram backup'dan tiklaymiz.
        #    Backup bor-u tiklab bo'lmasa RuntimeError: bot bo'sh DB bilan ishga tushmaydi.
        await tg_backup.restore_if_needed(bot)
        init_db()
        init_episodes()
        # MUHIM: drop_pending_updates=False.
        # Render Free plan harakatsizlikdan keyin dyno'ni "uxlatib qo'yadi".
        # Foydalanuvchi shu vaqtda /start deeplink (masalan /start movie_XXXX)
        # yuborsa, Telegram uni navbatga qo'yadi. Dyno uyg'onganda
        # drop_pending_updates=True bo'lsa, aynan shu navbatdagi xabarlar
        # (jumladan deeplink) butunlay o'chirilib yuborilardi — bu deeplink
        # "ishlamasligi"ning asosiy sababi edi.
        await bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=WEBHOOK_HEADER_SECRET,            # Telegram har so'rovda shu sarlavhani yuboradi
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=False,
        )
        # Fon vazifalariga havola saqlanadi (aks holda asyncio ularni axlat yig'uvchiga berib yuborishi mumkin)
        app["bg_tasks"] = [
            asyncio.create_task(scheduler_loop(bot)),
            asyncio.create_task(tg_backup.backup_loop(bot)),
            asyncio.create_task(profile_sync_loop(bot)),
            asyncio.create_task(reports.report_loop(bot)),
        ]
        health.register_tasks(app["bg_tasks"])
        # URL'da maxfiy yo'l bor: logga to'liq yozilmaydi
        logger.info("✅ Webhook o'rnatildi: %s/wh/…", WEBHOOK_URL.split("/wh/")[0])

    async def on_shutdown(app):
        # MUHIM: bu yerda delete_webhook() chaqirilmasin!
        # Render deploy qilganda eski instance shutdown bo'lganda, agar shu
        # yerda webhook o'chirilsa - yangi instance allaqachon o'rnatgan
        # webhookni o'chirib tashlaydi (race condition). Webhook har doim
        # on_startup orqali qayta o'rnatiladi, shutdown'da o'chirish shart emas.
        for t in app.get("bg_tasks", []):
            t.cancel()
        try:                                              # so'nggi o'zgarishlar yo'qolmasligi uchun
            await asyncio.wait_for(tg_backup.backup_now(bot), timeout=20)
        except Exception as e:  # noqa: BLE001
            logger.warning("Yakuniy backup olinmadi: %s", e)
        logger.info("Bot to'xtatilmoqda (webhook saqlab qolinadi)")

    async def health(request):
        return web.Response(text="OK", status=200)

    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/health", health)
    app.router.add_get("/", health)

    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_HEADER_SECRET).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    logger.info(f"🚀 Webhook: {WEBAPP_HOST}:{WEBAPP_PORT}")
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)

async def run_polling():
    bot, dp = setup_dispatcher()
    await tg_backup.restore_if_needed(bot)
    init_db()
    init_episodes()
    tasks = [asyncio.create_task(scheduler_loop(bot)),
             asyncio.create_task(tg_backup.backup_loop(bot)),
             asyncio.create_task(profile_sync_loop(bot)),
             asyncio.create_task(reports.report_loop(bot))]
    health.register_tasks(tasks)
    logger.info("🚀 Polling rejimi")
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types() + ["inline_query"]
    )

if __name__ == "__main__":
    if WEBHOOK_URL:
        logger.info("Webhook rejimi")
        run_webhook()
    else:
        logger.warning("Polling rejimi (WEBHOOK_DOMAIN yo'q)")
        asyncio.run(run_polling())
