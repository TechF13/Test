{
    'name': 'Siyasi Ofis Yönetimi',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Vatandaş talepleri, ajanda, medya takibi ve yapay zekâ destekli haber analizi',
    'description': """
Siyasetçi ve ekibi için uçtan uca ofis yönetimi:

* Seçim bölgesi (il / ilçe / mahalle) hiyerarşisi
* Vatandaş talepleri: Proje uygulamasında ayrı bir proje (aşamalar, atama, son tarih,
  memnuniyet anketi, e-posta ile talep alma standart Odoo'dan gelir); bölge, kanal,
  kuruma yönlendirme, etiket bazlı çözüm süresi ve AI yanıt taslağı eklenir
* Siyasi ajanda: standart Takvim; etkinlik türleri takvim etiketleri, kişi türleri kişi etiketleri
* Medya takibi: RSS ve Google News kaynaklarından anahtar kelimeyle otomatik haber çekme
* Kural tabanlı ve yapay zekâ ile otomatik etiketleme, özet, duygu ve önem analizi
* Günlük basın bülteni (AI raporu, PDF çıktısı)
""",
    'author': 'F13 İstanbul',
    'license': 'LGPL-3',
    'depends': ['mail', 'calendar', 'contacts', 'project'],
    'data': [
        'security/political_office_security.xml',
        'security/ir.model.access.csv',
        'data/political_request_data.xml',
        'data/political_news_data.xml',
        'data/ir_cron_data.xml',
        'views/political_constituency_views.xml',
        'views/project_views.xml',
        'views/calendar_event_views.xml',
        'views/res_partner_views.xml',
        'views/political_news_source_views.xml',
        'views/political_news_keyword_views.xml',
        'views/political_news_tag_views.xml',
        'views/political_news_article_views.xml',
        'report/political_news_report_templates.xml',
        'views/political_news_report_views.xml',
        'views/res_config_settings_views.xml',
        'views/political_office_menus.xml',
    ],
    'application': True,
    'installable': True,
}
