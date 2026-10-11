# FocusAI Backend

FocusAI — AI-yordamchili fokus va produktivlik ilovasi uchun backend. To'liq TZ: `TZ.md`.

Flutter mobil ilova uchun yagona API manba — auth, focus session, kunlik routine, AI agent (Claude), gamifikatsiya, moliyaviy javobgarlik (Payme/Click), obuna va B2B (organizations) shu backend orqali boshqariladi.

## Tezkor ishga tushirish

```bash
cp .env.example .env   # keyin .env'ni to'ldiring (ANTHROPIC_API_KEY, SECRET_KEY, JWT_SECRET_KEY va h.k.)
docker-compose up --build
```

Servislar:
- API: http://localhost:8010 (konteyner ichida 8000, docker-compose orqali 8010'ga map qilingan) — `/docs` (Swagger, DEBUG=true bo'lsa)
- Postgres: localhost:5434
- Redis: localhost:6381

Birinchi ishga tushirishda migratsiyalarni qo'llash:

```bash
docker-compose exec api alembic upgrade head
```

## Lokal (Docker'siz) ishlash

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

**Muhim:** loyiha `Python >= 3.12` talab qiladi (`pyproject.toml`) — kodda yangi f-string sintaksisi ishlatilgan. Eski Python (masalan 3.10/3.11) bilan `SyntaxError` chiqishi mumkin.

## Testlar

```bash
pytest -v --cov=app --cov-report=term-missing
ruff check app tests
```

CI (`.github/workflows/ci.yml`) har push/PR'da real Postgres+Redis service bilan shu testlarni avtomatik ishga tushiradi.

## Loyiha tuzilishi

```
app/
├── main.py            # FastAPI entrypoint, router'lar shu yerda ulanadi
├── core/               # config, security (JWT/hash), database, redis, logging, exceptions
├── models/             # SQLAlchemy ORM modellari
├── schemas/            # Pydantic request/response
├── api/v1/             # Endpoint'lar (auth, focus, ai_agent, routine, gamification,
│                         notifications, finance, payments, subscriptions, organizations)
├── services/           # Biznes logika
├── integrations/       # Tashqi API klientlari (Claude, Payme, Click, Firebase, SMS)
└── tasks/              # Celery fon vazifalari
alembic/                # DB migratsiyalar
tests/                  # unit + integration
```

To'liq arxitektura printsiplari, DB sxemasi va roadmap uchun `TZ.md`ga qarang.

## Muhim eslatmalar

- Payme/Click webhook'lari imzo tekshiruvidan o'tadi — `.env`dagi `*_SECRET_KEY` qiymatlari productionda hech qachon commit qilinmasin.
- AI so'rovlari kunlik limitga ega (`AI_DAILY_REQUEST_LIMIT_FREE`/`_PREMIUM`) — xarajat nazorati uchun.
- `AI_MODEL` — `.env`da Claude model ID'ni belgilaydi (masalan `claude-sonnet-4-6`); yangi model chiqsa shu yerda almashtiriladi, kodga qattiq yozilmagan.
