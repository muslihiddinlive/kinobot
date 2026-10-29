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

## 4️⃣½ DB yo'qolishidan himoya (MUHIM)

Render **Free** rejasida disk vaqtincha: har redeploy/restartda `kinobot.db` o'chadi
(foydalanuvchilar, VIP, to'lovlar, referal, kino katalogi). Shuning uchun bot DB'ni
**Telegram'ga zaxiralaydi** va bo'sh diskda **avtomatik tiklaydi**:

1. Alohida **yopiq** guruh yoki kanal yarating (kino bazasi guruhidan boshqa, tavsiya).
2. Botni u yerda **admin** qiling: xabar yozish, xabarni tahrirlash, **xabarni pin qilish**.
3. Chat ID sini Render → Environment → `BACKUP_CHAT_ID` ga yozing (bo'sh qolsa `DB_GROUP_ID` ishlatiladi).
4. `/admin` → **👑 Superadmin** → **💾 Backup** → "Hozir backup" tugmasini bosing, holat `📌 pin qilingan` bo'lsin.

Qanday ishlaydi: har 10 daqiqada (DB o'zgargan bo'lsa) `kinobot.db` gzip qilinib, chatdagi **bitta pin qilingan xabar** tahrirlanadi;
sutkada bir marta alohida arxiv (oxirgi 7 tasi) saqlanadi. Bot bo'sh diskda ishga tushsa, pin qilingan xabardan DB tiklanadi.
Backup bor-u tiklab bo'lmasa, bot **ishga tushmaydi** (bo'sh DB bilan ishlab yaxshi backupni ustidan yozib yubormaslik uchun).

Cheklovlar: gzip hajmi 20 MB dan oshmasin (Bot API yuklab olish limiti); redeploy paytidagi oxirgi bir necha daqiqalik o'zgarishlar
yo'qolishi mumkin (`BACKUP_INTERVAL_MIN` ni kichik qiling). Katta o'sishda tashqi DB (Neon/Turso) ga o'tish tavsiya etiladi.

## 🛡 Admin panel 2.0

- **Ruxsatlar (RBAC):** `/admin` → 👑 Superadmin → 🛡 Ruxsatlar: har admin uchun 13 ta ruxsat tugmalari (ban, reklama, kinolar, eksport...) va tayyor rollar
  (👑 To'liq, 🛠 Moderator, 👁 Kuzatuvchi). Ruxsatlar HAR tugmada tekshiriladi. `ADMIN_IDS` (env) dagilar to'liq huquqli.
- **Xavfli amallarga tasdiq:** ban, pullik reja berish, reklama yuborish, texnik rejim, kanal o'chirish, to'lovni tasdiqlash — alohida "Tasdiqlang" xabari bilan.
- **PIN (superadmin):** 🔐 PIN bo'limida 4-8 raqamli PIN; superadmin paneli va adminlarni boshqarish PIN bilan ochiladi
  (sessiya 5/15/60 daqiqa, 5 xato urinishdan keyin 10 daqiqa blok). PIN esdan chiqsa: Render'da `SA_PIN_DISABLE=1` o'rnating, kiring, yangi PIN qo'ying.
- **Dashboard 2.0** (`/admin` → 📊 Statistika): DAU/WAU/MAU, yopishqoqlik, o'sish, daromad, konversiya, mini-grafiklar, rasmli diagramma, top kinolar/so'rovlar.
  DAU/WAU/MAU o'lchash yangilanish kunidan boshlanadi (dastlabki kunlarda kam ko'rinadi).
- **Salomatlik** (👑 → 🩺): uptime, RAM, event loop kechikishi, webhook navbati/xatosi, DB hajmi, backup holati, fon vazifalari, xatolar logi.
- **Audit 2.0** (📋): sahifalash, admin/amal bo'yicha filtr, admin ismi bilan.
- **Eslatma va teglar:** foydalanuvchi kartasida 🗒 Eslatmalar va 🏷 Teglar; teg bo'yicha ro'yxat (`🏷 Teglar bo'yicha`) va `tag:nom` qidiruvi.
- **Avto-hisobot** (👑 → 📤 Hisobot): kunlik (7 kun) / haftalik (dushanba, 30 kun) XLSX Excel diagrammalari bilan, superadminga. Vaqt zonasi: `TZ_OFFSET_HOURS` (standart 5).

## 🔎 Qidiruv

Qidiruv motori (`utils/search_engine.py`) xotiradagi indeks bilan ishlaydi (30 000 kinoda ~60-130 ms):
lotin ↔ kirill, apostrof (`o'g'ri` = `oʻgʻri` = `ogri`), ko'p so'zli so'rov (`avatar suv`), xato yozuv (`titnaik` → Titanik, `узбек` ≈ `Ўзбек`),
natijalar sahifalanadi. Faqat **aniq** moslikda (aniq kod/nom) kino darhol yuboriladi, qolganida ro'yxat ko'rsatiladi.
Topilmasa: "Shuni nazarda tutdingizmi?" va **🔔 Qo'shilganda xabar bering** (kino qo'shilganda foydalanuvchiga avtomatik xabar boradi).
**Hashtag qidiruvi:** kino teglari (`#patrick #spongebob`) bo'yicha ham qidiriladi: botda yoki istalgan chatda `@BotNomi Patrick` / `@BotNomi #patrick`
(inline rejim, `@BotFather` → `/setinline` yoqilgan bo'lsin). Natijada kino tavsifida teglari ko'rinadi. `/tags` yoki 🔍 Qidirish → 🏷 Hashtaglar:
mashhur teglar ro'yxati, tugmani bosganda inline qidiruv shu teg bilan ochiladi. Teglarni kino qo'shishda yoki ✏️ Tahrirlash → 🏷 Fishkalar orqali kiritasiz.
Admin: `/admin` → **🔎 Topilmaganlar**: foydalanuvchilar eng ko'p qidirib topa olmagan kinolar (qaysi kinoni qo'shish kerakligini ko'rsatadi).
`requirements.txt` dagi `rapidfuzz` ni olib tashlamang: usiz xato yozuv qidiruvi ~10 marta sekinroq (difflib).

## 🔒 Kontent himoyasi (forward/saqlash)

`/admin` → ⚙️ Sozlamalar → **Kontent himoyasi**: ❌ Yopiq → 🆓 Faqat Free → 🔒 Hamma.
"Faqat Free" rejimida Free foydalanuvchilar kinoni forward qila olmaydi va saqlay olmaydi, PRO/VIP esa saqlay oladi
(PRO/VIP uchun yana bir foyda). Standart: yopiq (hech narsa o'zgarmaydi).

## 🔐 Webhook xavfsizligi

Token endi URL'da yurmaydi: yo'l `/wh/<maxfiy>` va Telegram har so'rovda `X-Telegram-Bot-Api-Secret-Token` sarlavhasini yuboradi
(noto'g'ri sarlavha `401`). Maxfiy qiymatlar `BOT_TOKEN` dan (yoki ixtiyoriy `WEBHOOK_SECRET` dan) hosil qilinadi, qo'shimcha sozlash shart emas.
Deploydan keyin webhook yangi manzilga avtomatik o'rnatiladi.

---

## 5️⃣ Tekshirish

- `https://kinobot.onrender.com/health` → "OK" chiqishi kerak
- Botga `/start` yuboring → ishlashi kerak
