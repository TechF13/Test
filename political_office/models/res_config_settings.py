from odoo import fields, models

from .political_ai_service import AI_MODELS, DEFAULT_MODEL


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    political_politician_name = fields.Char('Siyasetçi Adı', config_parameter='political_office.politician_name')
    political_politician_title = fields.Char('Unvan / Görev', config_parameter='political_office.politician_title')
    political_politician_party = fields.Char('Parti', config_parameter='political_office.politician_party')
    political_politician_region = fields.Char('Seçim Bölgesi', config_parameter='political_office.politician_region')

    political_anthropic_api_key = fields.Char('Anthropic API Anahtarı', config_parameter='political_office.anthropic_api_key')
    political_ai_use_env_credentials = fields.Boolean(
        'Ortam değişkenindeki anahtarı kullan', config_parameter='political_office.ai_use_env_credentials',
        help='API anahtarı boşsa sunucudaki ANTHROPIC_API_KEY ortam değişkeni kullanılır.',
    )
    political_ai_model = fields.Selection(AI_MODELS, 'AI Modeli', default=DEFAULT_MODEL, config_parameter='political_office.ai_model')
    political_ai_auto_process = fields.Boolean('Yeni haberleri otomatik analiz et', config_parameter='political_office.ai_auto_process')
    political_ai_allow_new_tags = fields.Boolean('AI yeni etiket oluşturabilir', config_parameter='political_office.ai_allow_new_tags')
    political_ai_batch_size = fields.Integer('Cron başına analiz edilecek haber', default=20, config_parameter='political_office.ai_batch_size')
    political_digest_min_relevance = fields.Integer(
        'Bülten için asgari ilgililik', default=30, config_parameter='political_office.digest_min_relevance',
    )
    political_digest_user_ids = fields.Many2many(related='company_id.political_digest_user_ids', readonly=False)
