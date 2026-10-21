from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    political_digest_user_ids = fields.Many2many(
        'res.users', 'political_company_digest_user_rel', 'company_id', 'user_id', 'Bülten Alıcıları',
    )
