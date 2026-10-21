# testproje

Odoo 19.0 projesi — OdooPanel ile yönetilir.

## Modüller

| Modül | Açıklama |
|---|---|
| `political_office` | Siyasi Ofis Yönetimi: vatandaş talepleri (Proje), ajanda (Takvim), meclis ve saha çalışmaları, RSS / Google News / YouTube / webhook ile medya takibi, Claude ile haber analizi, gündemler, anlık uyarılar, basın açıklaması taslağı, günlük basın bülteni ve panel. |
| `political_office_queue` | İsteğe bağlı: haber çekme ve AI analizini OCA `queue_job` ile kuyrukta çalıştırır (`queue_job` kuruluysa otomatik kurulur). |
| `third_party/queue_job` | OCA queue 19.0 (alt modül). |

Python bağımlılıkları `requirements.txt` dosyasındadır (`anthropic`, `openupgradelib`).

Kullanım kılavuzu: [docs/Siyasi_Ofis_Kullanim_Kilavuzu.pdf](docs/Siyasi_Ofis_Kullanim_Kilavuzu.pdf)
