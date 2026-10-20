"""Webhook xavfsizligini sinash: noto'g'ri sarlavha/yo'l rad etilishi, to'g'ri so'rov qabul qilinishi."""
import asyncio, os, sys
os.environ.update(BOT_TOKEN="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", SUPERADMIN_ID="1", DB_GROUP_ID="-100123",
                  DB_PATH="/tmp/smoke_wh.db", WEBHOOK_DOMAIN="https://example.onrender.com")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in ("/tmp/smoke_wh.db",):
    if os.path.exists(p): os.remove(p)
import config, database as db
import bot as botmod                      # barcha routerlar import bo'lishini ham tekshiradi
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

async def main():
    db.init_db(); db.init_episodes()
    bot, dp = botmod.setup_dispatcher()
    assert config.BOT_TOKEN not in config.WEBHOOK_PATH and config.BOT_TOKEN not in config.WEBHOOK_URL, "token URLda ko'rinmasligi kerak"
    print("webhook yo'li:", config.WEBHOOK_PATH[:10] + "…", "| allowed_updates:", dp.resolve_used_update_types())
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=config.WEBHOOK_HEADER_SECRET).register(app, path=config.WEBHOOK_PATH)
    upd = {"update_id": 1, "message": {"message_id": 1, "date": 1700000000, "chat": {"id": 5, "type": "private"}, "from": {"id": 5, "is_bot": False, "first_name": "X"}, "text": "/zzz"}}
    async with TestClient(TestServer(app)) as c:
        r = await c.post(config.WEBHOOK_PATH, json=upd);                                        print("sarlavhasiz:", r.status); assert r.status == 401
        r = await c.post(config.WEBHOOK_PATH, json=upd, headers={"X-Telegram-Bot-Api-Secret-Token": "x" * 64}); print("noto'g'ri sarlavha:", r.status); assert r.status == 401
        r = await c.post(f"/webhook/{config.BOT_TOKEN}", json=upd, headers={"X-Telegram-Bot-Api-Secret-Token": config.WEBHOOK_HEADER_SECRET}); print("eski yo'l:", r.status); assert r.status == 404
        r = await c.post(config.WEBHOOK_PATH, json=upd, headers={"X-Telegram-Bot-Api-Secret-Token": config.WEBHOOK_HEADER_SECRET}); print("to'g'ri so'rov:", r.status); assert r.status == 200
    # WEBHOOK_SECRET berilsa yo'l o'zgaradi (deterministik, tokendan mustaqil kalit)
    print("OK webhook xavfsizligi")
    await bot.session.close()
asyncio.run(main())
