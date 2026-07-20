# 🚀 Render + UptimeRobot — Deploy yo'riqnomasi

## 1️⃣ GitHub ga yuklash

```cmd
cd Desktop\kinobot_v6\kinobot6
git init
git add .
git commit -m "KinoBot v6"
git remote add origin https://github.com/USERNAME/kinobot.git
git push -u origin main
```

---

## 2️⃣ Render da deploy

1. [render.com](https://render.com) → **Sign up with GitHub**
2. **New** → **Web Service** → GitHub repo tanlang
3. Sozlamalar:
   - Runtime: `Python`
   - Build: `pip install -r requirements.txt`
   - Start: `python bot.py`
4. **Environment Variables**:
```
BOT_TOKEN=YOUR_BOT_TOKEN
ADMIN_IDS=YOUR_TELEGRAM_ID
```
5. **Create Web Service** → Deploy tugashini kuting
6. URL oling: `https://kinobot.onrender.com`
7. Shu URLni **Environment Variables** ga qo'shing:
```
WEBHOOK_DOMAIN=https://kinobot.onrender.com
```
8. **Manual Deploy** → **Deploy latest commit**

---

## 3️⃣ UptimeRobot sozlash (bot o'chmasin!)

1. [uptimerobot.com](https://uptimerobot.com) → Bepul akkaunt oching
2. **Add New Monitor** bosing
3. Sozlamalar:
   - Monitor Type: `HTTP(s)`
   - Friendly Name: `KinoBot`
   - URL: `https://kinobot.onrender.com/health`
   - Monitoring Interval: `5 minutes`
4. **Create Monitor** bosing

✅ Endi UptimeRobot har 5 daqiqada ping yuboradi → bot hech qachon o'chmaydi!

---

## 4️⃣ Bot sozlamalari

1. Botni supergroup va kanalga **admin** qiling
2. Botda `/admin` → **Kanallar** → kanal qo'shing
3. `@BotFather` → `/setinline` → botni tanlang → yoqing

---

## 5️⃣ Tekshirish

- `https://kinobot.onrender.com/health` → "OK" chiqishi kerak
- Botga `/start` yuboring → ishlashi kerak
