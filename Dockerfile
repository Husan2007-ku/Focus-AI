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
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir ".[dev]"

# Ilova kodini nusxalash
COPY ./app ./app
COPY ./alembic ./alembic
COPY ./alembic.ini ./alembic.ini

# MUHIM: konteyner ichida root sifatida ishlamaymiz (xavfsizlik auditi, P2).
# Agar ilovada kelajakda RCE turidagi zaiflik topilsa, root bo'lmagan
# foydalanuvchi konteyner ichidagi zararni cheklaydi (masalan, boshqa
# fayllarni o'zgartirish yoki konteynerdan "escape" qilish ancha qiyinlashadi).
# UID 1000 ataylab tanlangan — ko'pchilik Linux host'larida (va dev
# compose'dagi ./app bind-mount'ida) birinchi oddiy foydalanuvchining UID'i
# shu bo'lgani uchun fayl egligi masalalari minimal bo'ladi.
RUN useradd --create-home --uid 1000 --shell /bin/bash appuser && \
    chown -R appuser:appuser /code
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]