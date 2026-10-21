from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    constituency_id = fields.Many2one('political.constituency', 'Bölge', index='btree_not_null')
