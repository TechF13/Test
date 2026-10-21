from odoo import fields, models


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    constituency_id = fields.Many2one('political.constituency', 'Area', index='btree_not_null')
    expected_attendance = fields.Integer('Expected Attendance')
    actual_attendance = fields.Integer('Actual Attendance')
    press_article_ids = fields.Many2many(
        'political.news.article', 'political_event_article_rel', 'event_id', 'article_id', 'Press Coverage',
    )
