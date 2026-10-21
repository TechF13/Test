from random import randint

from odoo import fields, models


class PoliticalNewsTag(models.Model):
    _name = 'political.news.tag'
    _description = 'Haber Etiketi'
    _order = 'name'

    name = fields.Char('Etiket', required=True)
    color = fields.Integer('Renk', default=lambda self: randint(1, 11))
    description = fields.Text(
        'AI için Açıklama',
        help='Yapay zekâ bu etiketi hangi haberlere vereceğine karar verirken bu açıklamayı kullanır.',
    )
    ai_assignable = fields.Boolean('AI Atayabilir', default=True)
    created_by_ai = fields.Boolean('AI Tarafından Oluşturuldu', readonly=True)
    article_count = fields.Integer('Haber Sayısı', compute='_compute_article_count')
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint('UNIQUE(name)', 'Bu etiket zaten mevcut.')

    def _compute_article_count(self):
        counts = dict(self.env['political.news.article']._read_group(
            [('tag_ids', 'in', self.ids)], ['tag_ids'], ['__count'],
        ))
        for tag in self:
            tag.article_count = counts.get(tag, 0)

    def action_view_articles(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('political_office.action_political_news_article')
        action['domain'] = [('tag_ids', 'in', self.ids)]
        return action
