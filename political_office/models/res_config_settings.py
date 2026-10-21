from odoo import fields, models

from .political_ai_service import AI_MODELS, DEFAULT_MODEL


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    political_politician_name = fields.Char('Politician Name', config_parameter='political_office.politician_name')
    political_politician_title = fields.Char('Title / Position', config_parameter='political_office.politician_title')
    political_politician_party = fields.Char('Party', config_parameter='political_office.politician_party')
    political_politician_region = fields.Char('Constituency', config_parameter='political_office.politician_region')

    political_anthropic_api_key = fields.Char('Anthropic API Key', config_parameter='political_office.anthropic_api_key')
    political_ai_use_env_credentials = fields.Boolean(
        'Use the key from the environment', config_parameter='political_office.ai_use_env_credentials',
        help='When the API key is empty, the ANTHROPIC_API_KEY environment variable of the server is used.',
    )
    political_ai_model = fields.Selection(AI_MODELS, 'AI Model', default=DEFAULT_MODEL, config_parameter='political_office.ai_model')
    political_ai_auto_process = fields.Boolean('Analyze new articles automatically', config_parameter='political_office.ai_auto_process')
    political_ai_allow_new_tags = fields.Boolean('AI can create new tags', config_parameter='political_office.ai_allow_new_tags')
    political_ai_batch_size = fields.Integer('Articles analyzed per run', default=20, config_parameter='political_office.ai_batch_size')
    political_digest_min_relevance = fields.Integer(
        'Minimum relevance for the bulletin', default=30, config_parameter='political_office.digest_min_relevance',
    )
    political_public_form_enabled = fields.Boolean(
        'Web request form (/talep)', config_parameter='political_office.public_form_enabled',
        help='Lets citizens send requests directly from /talep on your website.',
    )
    political_alert_level = fields.Selection([
        ('high', 'High and critical articles'),
        ('critical', 'Critical articles only'),
        ('off', 'Off'),
    ], string='Instant media alert', default='high', config_parameter='political_office.alert_level')
    political_alert_user_ids = fields.Many2many(related='company_id.political_alert_user_ids', readonly=False)
    political_digest_user_ids = fields.Many2many(related='company_id.political_digest_user_ids', readonly=False)
