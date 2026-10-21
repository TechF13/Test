from random import randint

from odoo import fields, models


class PoliticalNewsTag(models.Model):
    _name = 'political.news.tag'
    _description = 'News Tag'
    _order = 'name'

    name = fields.Char('Tag', required=True)
    color = fields.Integer('Color', default=lambda self: randint(1, 11))
    description = fields.Text(
        'Description for the AI',
        help='The AI uses this description to decide which articles get this tag.',
    )
    ai_assignable = fields.Boolean('AI Can Assign', default=True)
    created_by_ai = fields.Boolean('Created by AI', readonly=True)
    article_count = fields.Integer('Article Count', compute='_compute_article_count')
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint('UNIQUE(name)', 'This tag already exists.')

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
