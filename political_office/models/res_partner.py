from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    constituency_id = fields.Many2one('political.constituency', 'Bölge', index='btree_not_null')
    political_contact_type = fields.Selection([
        ('citizen', 'Vatandaş'),
        ('party_member', 'Parti Üyesi'),
        ('journalist', 'Gazeteci'),
        ('ngo', 'STK / Dernek'),
        ('institution', 'Kamu Kurumu'),
        ('business', 'İş Dünyası'),
        ('other', 'Diğer'),
    ], string='Kişi Türü')
    political_request_ids = fields.One2many('political.request', 'partner_id', 'Talepler')
    political_request_count = fields.Integer('Talep Sayısı', compute='_compute_political_request_count')

    def _compute_political_request_count(self):
        counts = dict(self.env['political.request']._read_group(
            [('partner_id', 'in', self.ids)], ['partner_id'], ['__count'],
        ))
        for partner in self:
            partner.political_request_count = counts.get(partner, 0)

    def action_view_political_requests(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('political_office.action_political_request')
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id, 'default_constituency_id': self.constituency_id.id}
        return action
