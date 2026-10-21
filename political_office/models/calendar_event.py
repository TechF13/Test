from odoo import fields, models


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    constituency_id = fields.Many2one('political.constituency', 'Bölge', index='btree_not_null')
    expected_attendance = fields.Integer('Beklenen Katılım')
    actual_attendance = fields.Integer('Gerçekleşen Katılım')
    press_article_ids = fields.Many2many(
        'political.news.article', 'political_event_article_rel', 'event_id', 'article_id', 'Basın Yansımaları',
    )
