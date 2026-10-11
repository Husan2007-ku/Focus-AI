# FocusAI — Backend Texnik Topshiriq (TZ)
### Versiya 2.0 | Yagona haqiqat manbai (single source of truth)

> Bu hujjat v1.0 (g'oya bosqichi) va undan keyingi real kod audit natijalarini birlashtirib, **bitta yagona va toza** hujjat qilib qayta tuzilgan. Loyihaning keyingi har bir bosqichi shu TZ'ga qarab boradi — eski v1.0/v1.1 endi ishlatilmaydi.

---

## 1. LOYIHA UMUMIY TAVSIFI

**Nomi:** FocusAI
**Missiya:** Diqqatni qaytarib beruvchi AI yordamchi — odamlarni Instagram/TikTok kabi chalg'ituvchi platformalardan ozod qilish. "Iroda kuchi yetarli emas, tizim kerak."

Bu loyiha shoshilib qilinadigan MVP emas — maqsad uni **mukammal va mas'uliyat bilan** qurib, ommaga shu darajada taqdim etish. Diqqat pastligi bugungi kunda keng tarqalgan muammo; FocusAI shu muammoga jiddiy, uzoq muddatli yechim bo'lishi kerak.

**Tizim komponentlari:**

| Qism | Texnologiya | Holat |
|---|---|---|
| Mobil ilova | Flutter (Dart) | Alohida (frontend jamoasi) |
| **Backend (biz quramiz)** | **Python (FastAPI)** | ✅ Ushbu TZ predmeti |
| Ilova bloklash | Android UsageStats/AccessibilityService | Mobil tomonda |
| AI | Claude API (Anthropic) | Backend orqali integratsiya |
| To'lov | Payme, Click | Backend orqali integratsiya |
| Push | Firebase FCM | Backend orqali integratsiya |

Backend Flutter ilovasi uchun **yagona API manba**: barcha biznes logika, AI, pul aylanmasi va ma'lumotlar shu yerda boshqariladi. Mobil ilova "aqlsiz client" (thin client).

---

## 2. TEXNOLOGIK STEK

| Kategoriya | Tanlov | Asos |
|---|---|---|
| Framework | **FastAPI** | Async, avtomatik OpenAPI docs, Pydantic bilan chuqur integratsiya |
| DB | **PostgreSQL 16** | Tranzaksiyalar (pul!) uchun ACID kafolat |
| ORM | **SQLAlchemy 2.0 (async) + Alembic** | Migratsiyalar nazorati |
| Validatsiya | **Pydantic v2** | Schema-first |
| Cache/Broker | **Redis** | Sessiya, rate-limit, Celery broker |
| Fon vazifalari | **Celery + Redis** | Kunlik reset, eslatmalar, AI tahlil, moliyaviy tekshiruv |
| Auth | **JWT (access+refresh)** + Telefon OTP (SMS) + Google OAuth | |
| AI integratsiya | **Anthropic Python SDK** (to'g'ridan-to'g'ri, LangChain'siz) | Kamroq abstraksiya = kamroq xato, to'liq tool-use nazorati |
| To'lov | **Payme Merchant API + Click Merchant API** (custom client) | Mahalliy standart |
| Push | **Firebase Admin SDK** | FCM |
| Fayl saqlash | **S3-compatible (MinIO dev / S3 yoki mahalliy provider prod)** | Ovozli hisobotlar uchun — ❌ hali qo'shilmagan |
| Konteynerizatsiya | **Docker + docker-compose** | Dev va prod bir xil |
| Test | **pytest + pytest-asyncio + httpx** | |
| Monitoring | **Sentry + structlog** | |
| CI/CD | **GitHub Actions** | ✅ ishlaydi |

**Qaror:** Supabase ishlatilmaydi — to'liq nazorat, to'lov xavfsizligi, AI cost-control va custom biznes logika uchun o'z FastAPI+PostgreSQL backend. **Pitch deck va boshqa har qanday taqdimot material shu qarorga mos bo'lishi shart** (10-band).

---

## 3. ARXITEKTURA PRINSIPLARI

1. **Layered Architecture:** `API (routers) → Services (biznes logika) → Repositories (DB) → Models`. ✅ **To'liq bajarildi** (2026-09-15) — barcha 7 domen (finance, user/auth, focus_session, routine, gamification, subscription, organization) endi Repository orqali ishlaydi.
2. **Domain-based modullar:** har funksiya (auth, focus, ai, finance, gamification...) alohida papkada. ✅
3. **Async-first:** barcha DB va tashqi API chaqiruvlar `async/await` bilan. ✅
4. **Fail-safe pul tizimi:** ledger pattern — har pul harakati alohida yozuv, hech narsa ustidan yozilmaydi. ✅ (`ledger_entries`)
5. **Idempotency:** Payme/Click webhook va Celery vazifalari idempotent. ✅ webhook'larda; Celery vazifalarining bir qismi hali yozilmagan (8-band)
6. **AI cost governance:** kunlik so'rov limiti, tarix uzunligi cheklovi. ✅ (`MAX_HISTORY_MESSAGES`, `AI_DAILY_REQUEST_LIMIT_*`)
7. **Observability:** structlog, Sentry. ✅
8. **B2B tayyorlik:** `organization_id` oldindan tayyor. ✅ — hatto TZ v1.0 rejalashtirganidan ham to'liqroq (`organizations` to'liq modul)

---

## 4. FAYL STRUKTURASI (haqiqiy holat + qo'shilishi kerak)

```
focusai-backend/
├── app/
│   ├── main.py                       ✅
│   ├── core/                         ✅ config, security, database, redis_client, logging, exceptions, cache
│   ├── models/                       ✅ user, focus_session, routine, finance, gamification, ai_chat, device, organization, subscription
│   ├── schemas/                      ✅ (models bilan bir xil qamrov)
│   ├── api/v1/
│   │   ├── auth.py                   ✅ (otp, google, refresh, logout, /me)
│   │   ├── focus.py                  ✅
│   │   ├── ai_agent.py               ✅
│   │   ├── routine.py                ✅
│   │   ├── gamification.py           ✅
│   │   ├── notifications.py          ✅
│   │   ├── finance.py                ✅
│   │   ├── payments.py               ✅ (webhook'lar)
│   │   ├── subscriptions.py          ✅
│   │   ├── organizations.py          ✅
│   │   ├── users.py                  ✅ **2026-09-15** — profil CRUD: GET/PATCH/DELETE `/me`
│   │   ├── stats.py                  ✅ **2026-09-15** — jami+haftalik statistika, haftalik AI xulosa
│   │   └── admin.py                  ✅ **2026-09-15** — `/dashboard` (X-Admin-Key bilan himoyalangan)
│   ├── services/                     ✅ ai, ai_tools, auth, click, finance, focus, gamification, notification, organization, payme, routine, subscription, user, stats, admin
│   ├── repositories/                 ✅ **TO'LIQ** (2026-09-15) — finance, user, focus_session,
│   │   │                                routine, gamification, subscription, organization, admin.
│   │   │                                52/52 test (12 yangi: user/stats/admin) + qo'lda smoke
│   │   │                                test (obuna yangilash, tashkilotga qo'shilish, users/
│   │   │                                stats/admin uchdan-uchga HTTP) real Postgres bilan o'tdi.
│   ├── integrations/                 ✅ claude, click, firebase, payme, sms — ❌ s3/minio client yo'q
│   ├── tasks/
│   │   ├── celery_app.py             ✅
│   │   ├── finance_tasks.py          ✅
│   │   ├── daily_tasks.py            ✅ **2026-09-15** — streak reset (00:05) + kunlik eslatma push (20:00)
│   │   └── ai_tasks.py               ✅ **2026-09-15** — haftalik AI xulosa + push (yakshanba 20:30), Celery Beat bilan
│   └── utils/                        ✅
├── alembic/                          ✅ 8 migratsiya
├── tests/                            ✅ unit + integration
├── docker-compose.yml / Dockerfile   ✅
├── pyproject.toml / .env.example     ✅
├── README.md                         ✅ (2026-09-09 yozildi)
└── TZ.md                             ✅ (shu hujjat)
```

---

## 5. MA'LUMOTLAR BAZASI

| Jadval | Vazifasi | Holat |
|---|---|---|
| `users` | Profil (telefon/google, yosh, maqsad, tarif) | ✅ |
| `focus_sessions` | Fokus seansi | ✅ |
| `daily_routines` | Ertalabki reja + kechqurun hisobot + AI fikri | ✅ |
| `ai_conversations` / `ai_messages` | AI suhbat tarixi | ✅ |
| `financial_commitments`, `ledger_entries`, `transactions` | Moliyaviy javobgarlik + audit | ✅ (`finance.py` modelida) |
| `subscriptions` | Premium/Yillik tarif | ✅ |
| `streaks`, `badges`, `user_xp` | Gamification | ✅ (`gamification.py` modelida) |
| `devices` | FCM token | ✅ |
| `organizations` | B2B | ✅ |

---

## 6. API MODULLARI

```
/api/v1/auth          ✅ register/login (OTP/Google), refresh, logout, /me
/api/v1/focus         ✅ sessiya boshlash/tugatish, tarix
/api/v1/ai-agent      ✅ chat, tool-use, kunlik limit
/api/v1/routine       ✅ ertalabki reja, kechqurun hisobot
/api/v1/finance       ✅ maqsad, holat
/api/v1/payments      ✅ Payme/Click webhook
/api/v1/subscriptions ✅
/api/v1/organizations ✅ (B2B)
/api/v1/gamification  ✅ streak, badge, XP
/api/v1/notifications ✅ push sozlamalari
/api/v1/users         ✅ profil CRUD: GET/PATCH/DELETE /me
/api/v1/stats         ✅ statistika (/summary), haftalik AI xulosa (/weekly-ai-summary)
/api/v1/admin         ✅ ichki monitoring (/dashboard) — X-Admin-Key header bilan himoyalangan,
                         mobil ilova foydalanuvchilariga ko'rinmaydi. `.env`da ADMIN_API_KEY
                         sozlanmaguncha butunlay yopiq (bo'sh qiymat bilan hech kim kira olmaydi).
```

Barcha endpoint versiyalangan (`/v1/`), OpenAPI orqali avtomatik hujjatlashtirilgan.

---

## 7. XAVFSIZLIK TALABLARI

- JWT access (qisqa) + refresh (uzoq, rotatsiya) — ✅
- Parol/OTP `bcrypt`/`argon2` bilan hash — ✅
- Payme/Click webhook imzo tekshiruvi — ✅
- Moliyaviy endpoint'larda qo'shimcha rate-limit va audit-log — ✅ (ledger orqali)
- `.env` orqali sirlar, kodga yozilmaydi — ✅
- AI endpoint'da foydalanuvchi bo'yicha so'rov limiti — ✅
- `/api/v1/admin/*` — oddiy foydalanuvchi tokenidan mustaqil, alohida `X-Admin-Key` header bilan himoyalangan; `ADMIN_API_KEY` sozlanmagan bo'lsa endpoint hech kim uchun ochilmaydi — ✅
- HTTPS majburiy (prod) — deploy vaqtida tasdiqlash kerak

---

## 8. QOLGAN ISHLAR (ustuvorlik tartibida)

1. ~~Repository qatlami — barcha domenlar~~ ✅ **2026-09-15 to'liq bajarildi** (7 domen, 40/40 test + qo'lda smoke test real Postgres bilan)
2. ~~`app/api/v1/users.py`, `stats.py`, `admin.py` yozish~~ ✅ **2026-09-15 to'liq bajarildi** (52/52 test + uchdan-uchga HTTP smoke test)
3. ~~`app/tasks/daily_tasks.py` (streak reset, kunlik eslatma) va `ai_tasks.py` (haftalik AI xulosa)~~ ✅ **2026-09-15 to'liq bajarildi** — Celery Beat jadvali bilan (59/59 test + real DB bilan qo'lda smoke test)
4. **S3/MinIO integratsiyasi** — ovozli hisobot funksiyasi ishga tushganda
5. Pitch deck 10-slaydni shu TZ'ga (2-band) mos qilib yangilash — hozir "Supabase"/"LangChain Agent" yozilgan, bu eskirgan

---

## 9. KOD STANDARTLARI

- PEP8 + `ruff`
- Har funksiya/klassda type hints majburiy
- Har servis funksiyasida try/except + structlog
- Global exception handler — xom Python xatosi foydalanuvchiga qaytmaydi
- Har yangi modul uchun kamida asosiy pytest testi
- Conventional Commits format

---

## 10. RIVOJLANISH BOSQICHLARI

| Faza | Muddat | Reja | Haqiqiy holat |
|---|---|---|---|
| 1 — MVP | 1–2 oy | Skelet, Docker, DB, Auth, Focus session, AI chat | ✅ barchasi bajarilgan |
| 2 — Beta | 3–4 oy | Daily routine, Gamification, Push, Statistika | ✅ routine/gamification/push bor, ❌ stats API yo'q |
| 3 — Monetizatsiya | 5–6 oy | Payme/Click, Ledger, Premium/Yillik obuna | ✅ barchasi bajarilgan |
| 4 — O'sish | 7–12 oy | AI Agent (tool-use), B2B/multi-tenant, scaling | ✅ AI agent va organizations erta qilingan, ❌ scaling/yuk testi hali yo'q |

Xulosa: kod bazasi fazalar bo'yicha ketma-ket emas, hammasi bitta commit'da qilingan — shuning uchun har fazaning "orqa fon" qismlari (background task'lar, repository qatlami, stats/admin) notekis qolgan. Keyingi ish — fazalarni **chuqurlashtirish**, kenglikni oshirish emas.

---

## 11. PITCH DECK BILAN MOSLIK

Pitch deck (10-slayd, "Texnik arxitektura") shu TZ'ga mos bo'lishi shart:

| Slaydda bo'lishi kerak | Hozir slaydda (eski, tuzatilmagan) |
|---|---|
| FastAPI + PostgreSQL | ~~Supabase~~ |
| Anthropic SDK (to'g'ridan-to'g'ri) | ~~LangChain Agent~~ |
| Redis + Celery (fon vazifalar) | ko'rsatilmagan |

---

## 12. ISHNI OLIB BORISH TARTIBI

1. Har bosqichda avval shu bosqichning fayl ro'yxati kelishiladi
2. Fayllar birma-bir, to'liq va ishga tayyor holda beriladi
3. Har faylda: `Target File`, `Code Block`, `Action Items`
4. Tanlov kerak bo'lgan joyda — maksimal 2 variant taklif qilinadi
5. Har o'zgarishdan keyin: `pytest` + `ruff check` toza o'tishi shart

**Keyingi qadam:** 8-banddagi ro'yxatdan birinchisi — Repository qatlami.
