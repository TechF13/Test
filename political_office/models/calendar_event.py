from odoo import fields, models


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    political_event_type = fields.Selection([
        ('meeting', 'Görüşme / Randevu'),
        ('citizen_day', 'Halk Günü'),
        ('field_visit', 'Saha Ziyareti'),
        ('rally', 'Miting / Halk Buluşması'),
        ('parliament', 'Meclis / Komisyon'),
        ('party', 'Parti Toplantısı'),
        ('media', 'Basın / Röportaj'),
        ('ceremony', 'Tören / Ziyaret'),
        ('other', 'Diğer'),
    ], string='Siyasi Etkinlik Türü', index=True)
    constituency_id = fields.Many2one('political.constituency', 'Bölge', index='btree_not_null')
    political_request_ids = fields.Many2many(
        'political.request', 'political_request_calendar_event_rel', 'event_id', 'request_id', 'İlgili Talepler',
    )
    expected_attendance = fields.Integer('Beklenen Katılım')
    actual_attendance = fields.Integer('Gerçekleşen Katılım')
    outcome_notes = fields.Html('Sonuç / Notlar')
    press_article_ids = fields.Many2many(
        'political.news.article', 'political_event_article_rel', 'event_id', 'article_id', 'Basın Yansımaları',
    )
