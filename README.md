# Takrorla_Bot — O'rnatish va joylashtirish qo'llanmasi

## 1. Zudlik bilan qiling
Eski bot tokeningiz ushbu loyihada ochiq holda bo'lgan edi. **BotFather**'ga o'ting →
`/mybots` → botingiz → `Bot Settings` → `Revoke current token` → yangi token oling.
Bu yangi tokenni pastda ko'rsatilgandek faqat environment variable sifatida ishlating.

## 2. Local sozlash
```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # keyin .env faylini o'zingizning qiymatlaringiz bilan to'ldiring
```
`.env` faylini avtomatik yuklash uchun `python-dotenv` o'rnatib, `bot.py` boshiga
`from dotenv import load_dotenv; load_dotenv()` qo'shishingiz mumkin, yoki
o'zgaruvchilarni terminalda `export BOT_TOKEN=...` orqali qo'lda belgilang.

## 3. Heroku'ga joylashtirish
```bash
heroku create sizning-bot-nomi
heroku addons:create heroku-postgresql:mini

heroku config:set BOT_TOKEN=yangi_token
heroku config:set ADMIN_IDS=123456789
heroku config:set CHANNELS=@kanal1,@kanal2
heroku config:set TRIAL_DAYS=3
heroku config:set REMINDER_HOUR=9
heroku config:set TIMEZONE=Asia/Tashkent

git push heroku main
heroku ps:scale worker=1
```
`DATABASE_URL` — Postgres addon o'rnatilganda Heroku tomonidan **avtomatik** qo'shiladi, uni qo'lda kiritish shart emas.

## 4. Bot sozlamalari (Telegram tomonda)
- Bot ikkala kanalda (`CHANNELS`) **admin** bo'lishi shart — aks holda `getChatMember` orqali a'zolikni tekshira olmaydi.
- Admin bo'lish uchun: kanal → Administrators → Add Administrator → botingizni qo'shing (minimal huquqlar yetarli).

## 5. Admin buyruqlari
- `/admin` — statistika, foydalanuvchilar ro'yxati, broadcast (faqat `ADMIN_IDS`dagi ID'lar uchun).
- O'z Telegram ID'ingizni bilish uchun [@userinfobot](https://t.me/userinfobot) ga yozing.

## 6. Fayl tuzilishi
```
bot.py          — handlerlar va ishga tushirish nuqtasi
config.py       — barcha environment variable sozlamalari
database.py     — PostgreSQL bilan ishlash (asyncpg)
keyboards.py    — barcha tugmalar
subscription.py — majburiy obunani tekshirish logikasi
scheduler.py    — kunlik eslatma (APScheduler)
TZ.md           — to'liq texnik topshiriq
```

## 7. Muhim eslatmalar
- Ma'lumotlar bazasi endi PostgreSQL'da — Heroku dyno qayta ishga tushsa ham ma'lumot yo'qolmaydi.
- Majburiy obuna foydalanuvchi ro'yxatdan o'tgandan **3 kun** o'tgach ishga tushadi (`TRIAL_DAYS` orqali o'zgartiriladi).
- "❌ Qiyin bo'ldi" xatti-harakati har bir foydalanuvchi uchun ⚙️ Sozlamalar orqali tanlanadi (qattiy/yumshoq rejim).
