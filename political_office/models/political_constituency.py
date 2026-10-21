from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PoliticalConstituency(models.Model):
    _name = 'political.constituency'
    _description = 'Area'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    name = fields.Char('Name', required=True)
    complete_name = fields.Char('Full Name', compute='_compute_complete_name', recursive=True, store=True)
    code = fields.Char('Code')
    level = fields.Selection([
        ('province', 'Province'),
        ('district', 'District'),
        ('neighborhood', 'Neighborhood / Village'),
    ], string='Level', required=True, default='district')
    state_id = fields.Many2one(
        'res.country.state', 'Province (Odoo)', index='btree_not_null',
        help='Links a province level area to the Odoo province record.',
    )
    parent_id = fields.Many2one('political.constituency', 'Parent Area', index=True, ondelete='cascade')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('political.constituency', 'parent_id', 'Sub-areas')
    responsible_user_id = fields.Many2one('res.users', 'Area Manager')
    population = fields.Integer('Population')
    voter_count = fields.Integer('Voters')
    notes = fields.Html('Notes')
    active = fields.Boolean(default=True)
    request_count = fields.Integer('Request Count', compute='_compute_request_count')

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for zone in self:
            if zone.parent_id:
                zone.complete_name = f'{zone.parent_id.complete_name} / {zone.name}'
            else:
                zone.complete_name = zone.name

    @api.onchange('state_id')
    def _onchange_state_id(self):
        if self.state_id and not self.name:
            self.name = self.state_id.name
            self.level = 'province'

    def _compute_request_count(self):
        counts = dict(self.env['project.task']._read_group(
            [('constituency_id', 'in', self.ids)], ['constituency_id'], ['__count'],
        ))
        for zone in self:
            zone.request_count = counts.get(zone, 0)

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if self._has_cycle():
            raise ValidationError(self.env._('Areas cannot form a recursive hierarchy.'))

    def action_view_requests(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('political_office.action_political_request')
        action['domain'] = [('project_id.political_project_type', '=', 'request'), ('constituency_id', 'child_of', self.id)]
        action['context'] = dict(self.env['project.task']._political_request_context(), default_constituency_id=self.id)
        return action
