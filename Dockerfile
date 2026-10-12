FROM python:3.12-slim

WORKDIR /code

# Bog'liqliklarni o'rnatish (keshni samarali ishlatish uchun alohida qatlam)
# Eslatma: asyncpg, argon2-cffi va boshqa kutubxonalar tayyor "wheel" (kompilyatsiya
# qilingan) holatda keladi — shuning uchun gcc/libpq-dev kabi og'ir build vositalari
# kerak emas. Bu image'ni ham kichraytiradi, ham qurish vaqtini tezlashtiradi.
COPY pyproject.toml ./
# MUHIM: ".[dev]" bilan o'rnatiladi (faqat "." emas) — docker-compose.yml'da
# `api` xizmati `./tests:/code/tests`ni ataylab volume sifatida ulaydi, ya'ni
# pytest/ruff/black AYNAN shu konteyner ichida ishlatilishi mo'ljallangan.
# Avval bu qatorda faqat "." bo'lgani uchun pytest image'ga hech qachon
# kirmagan edi — ilgari testlar ishlagani, konteyner qayta build qilinmay,
# birov uni qo'lda `pip install ".[dev]"` bilan to'ldirgani sababli edi; har
# safar `docker compose build` qilinganda bu holat yo'qolib qolardi (xuddi
# shu auditning rate-limit o'zgarishi uchun build qilinganda yuz bergani kabi).
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ".[dev]"

# Ilova kodini nusxalash
COPY ./app ./app
COPY ./alembic ./alembic
COPY ./alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]