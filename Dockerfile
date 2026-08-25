FROM python:3.12-slim

WORKDIR /code

# Bog'liqliklarni o'rnatish (keshni samarali ishlatish uchun alohida qatlam)
# Eslatma: asyncpg, argon2-cffi va boshqa kutubxonalar tayyor "wheel" (kompilyatsiya
# qilingan) holatda keladi — shuning uchun gcc/libpq-dev kabi og'ir build vositalari
# kerak emas. Bu image'ni ham kichraytiradi, ham qurish vaqtini tezlashtiradi.
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Ilova kodini nusxalash
COPY ./app ./app
COPY ./alembic ./alembic
COPY ./alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]