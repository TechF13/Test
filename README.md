# testproje

Odoo 19.0 projesi — OdooPanel ile yönetilir.

## Modüller

| Modül | Açıklama |
|---|---|
| `political_office` | Siyasi Ofis Yönetimi: vatandaş talepleri (Proje), ajanda (Takvim), meclis ve saha çalışmaları, RSS / Google News / YouTube / webhook ile medya takibi, Claude ile haber analizi, gündemler, anlık uyarılar, basın açıklaması taslağı, günlük basın bülteni ve panel. |
| `political_office_queue` | İsteğe bağlı: haber çekme ve AI analizini OCA `queue_job` ile kuyrukta çalıştırır (`queue_job` kuruluysa otomatik kurulur). |
| `third_party/queue_job` | OCA queue 19.0 (alt modül). |

Python bağımlılıkları `requirements.txt` dosyasındadır (`anthropic`, `openupgradelib`).

## Yerelde çalıştırma (Docker)

Gerekenler: Docker Desktop (veya Docker Engine + Compose) ve Git.

```bash
git clone <repo-adresi> && cd Test
git checkout feature/political-office
./local/kur.sh            # isteğe bağlı: ./local/kur.sh veritabani_adi
```

Betik queue_job alt modülünü indirir, Odoo 19 imajını (`anthropic` paketiyle) derler, PostgreSQL'i başlatır,
`siyasi_ofis` veritabanını Türkçe olarak oluşturup `political_office` ve `political_office_queue` modüllerini kurar
ve Odoo'yu http://localhost:8069 adresinde açar (kullanıcı `admin`, şifre `admin`).

Windows'ta betiği Git Bash veya WSL ile çalıştırın ya da `local` klasöründe şu komutları sırayla verin:

```bash
git submodule update --init .addons/oca-queue
docker compose build
docker compose up -d --wait db
docker compose run --rm odoo odoo -d siyasi_ofis -i political_office,political_office_queue --load-language=tr_TR --without-demo=True --stop-after-init
docker compose up -d odoo
```

Diğer komutlar (`local` klasöründe): `docker compose logs -f odoo` (loglar), `docker compose down` (durdur),
`docker compose run --rm odoo odoo -d siyasi_ofis -u political_office --stop-after-init` (kod değişince modülü güncelle),
`docker compose down -v` (veritabanıyla birlikte her şeyi sil).

Kullanım kılavuzu: [docs/Siyasi_Ofis_Kullanim_Kilavuzu.pdf](docs/Siyasi_Ofis_Kullanim_Kilavuzu.pdf)
