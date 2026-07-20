import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ChatMemberUpdated

from config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBAPP_HOST, WEBAPP_PORT
from database import init_db, init_episodes, save_bot_chat
from middlewares.subscription import SubscriptionMiddleware
from middlewares.maintenance import MaintenanceMiddleware
from middlewares.antiflood import AntiFloodMiddleware
from handlers import admin, movies, payment, user, search
from handlers import vip, inline_handler, broadcast_adv
from utils.scheduler import scheduler_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def setup_dispatcher():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.message.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(MaintenanceMiddleware())
    dp.message.middleware(AntiFloodMiddleware(rate=5, per=5))
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    @dp.my_chat_member()
    async def on_chat_member(event: ChatMemberUpdated):
        if event.new_chat_member.status in ("member", "administrator"):
            chat = event.chat
            save_bot_chat(chat.id, chat.type, getattr(chat, "title", ""))

    # MUHIM: search.router oxirida bo'lishi kerak!
    # Chunki catch_any_text handler bor — boshqa handlerlar birinchi ishlashi shart.
    dp.include_router(admin.router)
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

    async def on_startup(_):
        init_db()
        init_episodes()
        await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
        asyncio.create_task(scheduler_loop(bot))
        logger.info(f"✅ Webhook: {WEBHOOK_URL}")

    async def on_shutdown(_):
        # MUHIM: bu yerda delete_webhook() chaqirilmasin!
        # Render deploy qilganda eski instance shutdown bo'lganda, agar shu
        # yerda webhook o'chirilsa - yangi instance allaqachon o'rnatgan
        # webhookni o'chirib tashlaydi (race condition). Webhook har doim
        # on_startup orqali qayta o'rnatiladi, shutdown'da o'chirish shart emas.
        logger.info("Bot to'xtatilmoqda (webhook saqlab qolinadi)")

    async def health(request):
        return web.Response(text="OK", status=200)

    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/health", health)
    app.router.add_get("/", health)

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    logger.info(f"🚀 Webhook: {WEBAPP_HOST}:{WEBAPP_PORT}")
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)

async def run_polling():
    bot, dp = setup_dispatcher()
    init_db()
    init_episodes()
    asyncio.create_task(scheduler_loop(bot))
    logger.info("🚀 Polling rejimi")
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types() + ["inline_query"]
    )

if __name__ == "__main__":
    if WEBHOOK_URL:
        logger.info(f"Webhook rejimi: {WEBHOOK_URL}")
        run_webhook()
    else:
        logger.warning("Polling rejimi (WEBHOOK_DOMAIN yo'q)")
        asyncio.run(run_polling())
