# O'quv Markaz CRM Boti (1-bosqich / MVP)

Texnik topshiriqdagi **1-bosqich (MVP)** talablari asosida qurilgan Telegram bot:
- Ro'yxatdan o'tish + admin tomonidan tasdiqlash oqimi
- Rol tizimi (admin / o'qituvchi / o'quvchi)
- Modullarni yoqish/o'chirish skeleti (`module_guard`)
- Majburiy kanalga a'zolik tekshiruvi
- Guruh yaratish
- Vazifa berish / topshirish (oddiy)

> Bu MVP skeleti — 2 va 3-bosqich funksiyalari (baholash tizimi, referal/konkurs,
> to'lov moduli, backup, Excel eksport va h.k.) keyingi iteratsiyalarda qo'shiladi.

## 📁 Loyiha tuzilishi

```
crm-bot/
├── main.py                  # Bot ishga tushirish nuqtasi
├── bot/
│   ├── config.py             # .env o'zgaruvchilarini o'qish
│   ├── database/
│   │   ├── models.py         # SQLAlchemy modellar (4-bo'limdagi barcha jadvallar)
│   │   └── engine.py         # Async DB ulanish
│   ├── middlewares/
│   │   ├── db_session.py     # Har bir update uchun DB session
│   │   ├── access_control.py # Pending/blocked foydalanuvchilarni bloklash (2.4)
│   │   ├── subscription_check.py # Majburiy obuna tekshiruvi (7-bo'lim)
│   │   ├── module_guard.py   # Modul yoqilgan/o'chiqligini tekshiruvchi dekorator (3.3)
│   │   └── role_check.py     # Rol bo'yicha ruxsat dekoratori (11-bo'lim)
│   ├── handlers/
│   │   ├── start.py          # /start va ro'yxatdan o'tish FSM
│   │   ├── common.py
│   │   ├── admin/            # Tasdiqlash, modullar, guruhlar
│   │   ├── teacher/          # Guruhlar, vazifa berish
│   │   └── student/          # Kabinet, vazifalarni ko'rish/topshirish
│   ├── keyboards/
│   ├── services/              # Biznes-logika (user, module, subscription)
│   └── utils/states.py        # FSM holatlari
├── requirements.txt
├── Procfile                  # Railway uchun start buyrug'i
├── railway.json
├── .env.example
└── .gitignore
```

## 🚀 1-qadam: Lokal sinov (ixtiyoriy)

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # so'ng .env faylini to'ldiring
python main.py
```

`.env` da kerakli qiymatlar:
- `BOT_TOKEN` — @BotFather dan olinadi
- `DATABASE_URL` — PostgreSQL manzili (lokal test uchun Docker'da PostgreSQL ko'tarishingiz mumkin)
- `SUPER_ADMIN_ID` — sizning Telegram ID raqamingiz (@userinfobot orqali bilib oling). Shu ID bilan `/start` bosilganda avtomatik ADMIN bo'lasiz.

## 🐙 2-qadam: GitHub'ga yuklash

```bash
cd crm-bot
git init
git add .
git commit -m "MVP: CRM bot skeleti (aiogram 3 + PostgreSQL)"
git branch -M main
git remote add origin https://github.com/<username>/<repo-nomi>.git
git push -u origin main
```

> `.env` fayli `.gitignore` da — u hech qachon GitHub'ga yuklanmaydi. Bu to'g'ri, chunki
> tokenlar maxfiy bo'lishi kerak. Railway'da ularni alohida Variables sifatida kiritasiz.

## 🚂 3-qadam: Railway'da deploy qilish

1. [railway.app](https://railway.app) ga kiring, **"New Project" → "Deploy from GitHub repo"** tanlang va repo'ingizni ulang.
2. Loyiha ichida **"+ New" → "Database" → "Add PostgreSQL"** tugmasini bosing — Railway avtomatik `DATABASE_URL` o'zgaruvchisini yaratadi.
3. Bot xizmati (service) ustiga bosing → **Variables** bo'limiga o'ting va qo'shing:
   - `BOT_TOKEN` = @BotFather'dan olingan token
   - `SUPER_ADMIN_ID` = sizning Telegram ID
   - `DATABASE_URL` = PostgreSQL xizmatidan **Reference** qilib ulang (Railway "Add reference" tugmasi orqali PostgreSQL'ning `DATABASE_URL`'ini avtomatik bog'lab beradi)
   - `TIMEZONE` = `Asia/Tashkent`
4. **Settings → Deploy** bo'limida start buyruq avtomatik `Procfile`/`railway.json` dan olinadi (`python main.py`). Qo'shimcha sozlash shart emas.
5. Deploy tugagach, **Logs** bo'limida `Bot ishga tushmoqda...` yozuvini ko'rishingiz kerak.
6. Telegram'da botga `/start` bosing — `SUPER_ADMIN_ID` bilan mos bo'lsa, avtomatik admin bo'lasiz va admin menyusi ochiladi.

### Muhim eslatma (Railway + polling)
Bot hozircha **long polling** rejimida ishlaydi (`Procfile`da `worker:` turi). Bu Railway'da
alohida "Worker" xizmati sifatida ishlaydi — HTTP port ochish shart emas. Agar kelajakda
webhook rejimiga o'tmoqchi bo'lsangiz, alohida FastAPI/aiohttp server qo'shish kerak bo'ladi.

## ✅ Birinchi ishga tushirishdan keyin nima qilish kerak

1. Admin sifatida `/start` bosib, botni sinab ko'ring.
2. `⚙️ Modullar` bo'limidan kerakli modullarni yoqing (standart holatda hammasi o'chiq — 3.3-bo'lim talabiga ko'ra).
3. `/new_group` orqali birinchi guruhni yarating.
4. Boshqa foydalanuvchilar `/start` bossa, ular "🆕 Yangi so'rovlar" bo'limida sizga ko'rinadi — tasdiqlang.

## 🔜 Keyingi bosqichlar (hali qo'shilmagan)

- Davomat olish to'liq oqimi, dars jadvali FSM
- Baholash tizimi, progress hisobotlari, Excel eksport
- Referal havola generatsiyasi va konkurs moduli (draft/active/finished)
- To'lov moduli
- Alembic migratsiyalari (hozircha `create_all` orqali avtomatik jadval yaratiladi — production uchun tavsiya etilmaydi, faqat MVP bosqichi uchun qulay)
- Anti-flood middleware, markazlashgan xatolik monitoring (Sentry)
- Kunlik avtomatik DB backup

Bu fayllarni to'ldirish uchun keyingi chatda davom etishingiz mumkin — loyiha strukturasi
kengaytirish uchun tayyor holda qurilgan (har bir modul alohida fayl/service sifatida ajratilgan).
