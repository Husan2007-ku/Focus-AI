# Postgres — zaxira (backup) va tiklash (restore)

**Nega muhim:** FocusAI'ning pul bilan bog'liq ma'lumotlari (`financial_commitments`,
`transactions`, `ledger_entries` — TZ 3-band, "Fail-safe pul tizimi") faqat shu
Postgres bazasida saqlanadi. Hozircha avtomatik, jadvalga asoslangan zaxira
mavjud EMAS — faqat Docker'ning `postgres_data` named volume'i bor, bu esa
disk/konteyner halokatidan himoya qilmaydi (masalan, `docker compose down -v`
yoki diskning o'zi buzilishi). Quyidagi qo'lda bajariladigan protsedura
birinchi qadam; avtomatlashtirish (masalan, kunlik cron + off-site saqlash)
hali amalga oshirilmagan — bu alohida, kelgusidagi vazifa (P2).

**MUHIM:** zaxira faqat tiklash muvaffaqiyatli sinab ko'rilgandan keyin
"ishlaydi" deb hisoblanadi. Quyidagi 2-bo'lim shuni bir marta sinab ko'rish
uchun — iltimos, buni PowerShell'da bir marta ishga tushirib, natijani
tasdiqlang.

## 1. Zaxira olish (backup)

Loyiha papkasida (PowerShell):

```powershell
cd C:\Users\jamsh\Downloads\focusai-backend-faza1\focusai-backend

# Custom-format dump — pg_restore bilan tezroq va tanlab tiklash imkonini beradi.
docker compose exec -T postgres pg_dump -U focusai -d focusai_db -F c -f /tmp/focusai_backup.dump
docker compose cp postgres:/tmp/focusai_backup.dump ".\backups\focusai_$(Get-Date -Format yyyy-MM-dd_HHmm).dump"
```

(`.\backups\` papkasini oldindan yarating: `mkdir backups`.) Bu faylni
kompyuterdan tashqarida ham saqlang (masalan, Google Drive/boshqa disk) —
faqat shu kompyuterda saqlangan zaxira "zaxira" hisoblanmaydi.

Tavsiya etilgan chastota: kuniga kamida 1 marta, real foydalanuvchilar
paydo bo'lgach.

## 2. Tiklashni sinab ko'rish (restore test) — BIR MARTA QILISH KERAK

Haqiqiy bazaga emas, alohida vaqtinchalik bazaga tiklab, ma'lumot
yo'qolmaganini tekshiramiz:

```powershell
# Vaqtinchalik test bazasini yaratish
docker compose exec -T postgres psql -U focusai -d postgres -c "DROP DATABASE IF EXISTS focusai_restore_test;"
docker compose exec -T postgres psql -U focusai -d postgres -c "CREATE DATABASE focusai_restore_test;"

# Zaxiradan tiklash
docker compose cp ".\backups\<fayl_nomi>.dump" postgres:/tmp/restore_test.dump
docker compose exec -T postgres pg_restore -U focusai -d focusai_restore_test /tmp/restore_test.dump

# Qator sonlarini solishtirish — asl baza bilan bir xil bo'lishi kerak
docker compose exec -T postgres psql -U focusai -d focusai_db -c "SELECT count(*) FROM transactions;"
docker compose exec -T postgres psql -U focusai -d focusai_restore_test -c "SELECT count(*) FROM transactions;"

# Tozalash
docker compose exec -T postgres psql -U focusai -d postgres -c "DROP DATABASE focusai_restore_test;"
```

Ikkala `count(*)` natijasi bir xil chiqsa — zaxira ishonchli.

## 3. Haqiqiy halokatdan keyin tiklash

```powershell
docker compose down
docker volume ls | findstr postgres_data   # aniq nomini tekshiring (masalan, focusai-backend_postgres_data)
docker volume rm <yuqoridagi natijadagi aniq nom>
docker compose up -d postgres
# Postgres sog'lom bo'lguncha kuting (docker compose ps), keyin:
docker compose cp ".\backups\<eng_so'nggi>.dump" postgres:/tmp/restore.dump
docker compose exec -T postgres pg_restore -U focusai -d focusai_db /tmp/restore.dump
alembic upgrade head   # agar zaxiradan keyin yangi migratsiyalar bo'lsa
docker compose up -d
```

## 4. Hali qilinmagan (P2, keyingi bosqich)

- Avtomatik kunlik backup (Celery Beat task yoki tashqi cron + off-site
  saqlash, masalan S3/Backblaze)
- Backup fayllarini saqlash muddati siyosati (masalan, oxirgi 30 kun)
- Monitoring: backup muvaffaqiyatsiz bo'lsa ogohlantirish
