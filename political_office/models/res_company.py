from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    political_digest_user_ids = fields.Many2many(
        'res.users', 'political_company_digest_user_rel', 'company_id', 'user_id', 'Bulletin Recipients',
    )
    political_alert_user_ids = fields.Many2many(
        'res.users', 'political_company_alert_user_rel', 'company_id', 'user_id', 'Media Alert Recipients',
    )
