#!/usr/bin/env bash
# Creates a local Odoo 19 database with the Siyasi Ofis modules installed.
# Usage: ./kur.sh [database_name]
set -euo pipefail
cd "$(dirname "$0")"
DB="${1:-siyasi_ofis}"

echo "==> queue_job alt modülü indiriliyor"
git -C .. submodule update --init .addons/oca-queue

echo "==> Odoo imajı hazırlanıyor"
docker compose build

echo "==> PostgreSQL başlatılıyor"
docker compose up -d --wait db

echo "==> '$DB' veritabanı oluşturuluyor ve modüller kuruluyor"
docker compose run --rm odoo odoo -d "$DB" \
    -i political_office,political_office_queue \
    --load-language=tr_TR --without-demo=True --stop-after-init

echo "==> Yönetici kullanıcısı Türkçe ve İstanbul saatine ayarlanıyor"
docker compose run --rm -T odoo odoo shell -d "$DB" --no-http --log-level=warn <<'PY'
env.ref('base.user_admin').write({'lang': 'tr_TR', 'tz': 'Europe/Istanbul'})
env.cr.commit()
PY

echo "==> Odoo başlatılıyor"
docker compose up -d odoo

echo
echo "Hazır: http://localhost:8069"
echo "Veritabanı: $DB   Kullanıcı: admin   Şifre: admin"
