import json
import logging

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import anthropic
except ImportError:
    anthropic = None

DEFAULT_MODEL = 'claude-opus-5-5'
AI_MODELS = [
    ('claude-opus-5-5', 'Claude Opus 5.5 (recommended)'),
    ('claude-sonnet-5-5', 'Claude Sonnet 5.5'),
    ('claude-haiku-5-5', 'Claude Haiku 5.5 (most economical)'),
]
# Models that accept the server-side refusal fallback ("default" routing).
FALLBACK_MODELS = {'claude-opus-5-5', 'claude-sonnet-5-5'}
FALLBACK_BETA = 'server-side-fallback-2026-07-01'


class AiRateLimitError(UserError):
    """Raised when the API is rate limited: batch jobs should stop and retry later."""


class PoliticalAiService(models.AbstractModel):
    _name = 'political.ai.service'
    _description = 'AI Service'

    @api.model
    def _get_param(self, key, default=False):
        return self.env['ir.config_parameter'].sudo().get_param(f'political_office.{key}', default)

    @api.model
    def _is_configured(self):
        """AI is usable when the SDK is installed and a key is set (or the
        environment provides credentials to the SDK)."""
        return anthropic is not None and bool(
            self._get_param('anthropic_api_key') or self._get_param('ai_use_env_credentials')
        )

    @api.model
    def _get_politician_profile(self):
        lines = []
        for label, key in (
            ('Ad Soyad', 'politician_name'),
            ('Unvan / Görev', 'politician_title'),
            ('Parti', 'politician_party'),
            ('Seçim Bölgesi', 'politician_region'),
        ):
            value = self._get_param(key)
            if value:
                lines.append(f'- {label}: {value}')
        return '\n'.join(lines) or '- (Profil bilgisi girilmemiş)'

    @api.model
    def _get_client(self):
        if anthropic is None:
            raise UserError(self.env._(
                "The AI features need the 'anthropic' Python package: pip install anthropic"
            ))
        api_key = self._get_param('anthropic_api_key') or None
        if not api_key and not self._get_param('ai_use_env_credentials'):
            raise UserError(self.env._('Enter the Anthropic API key in Settings > Political Office.'))
        # api_key=None lets the SDK resolve ANTHROPIC_API_KEY from the environment.
        return anthropic.Anthropic(api_key=api_key, timeout=120.0, max_retries=2)

    @api.model
    def _generate_json(self, system, prompt, schema, effort='low', max_tokens=16000):
        """Call Claude with a JSON schema constrained output and return the parsed dict.

        Raises UserError with a readable message on any failure so callers can
        store it on the record.
        """
        client = self._get_client()
        model = self._get_param('ai_model') or DEFAULT_MODEL
        params = {
            'model': model,
            'max_tokens': max_tokens,
            'system': system,
            'messages': [{'role': 'user', 'content': prompt}],
            'output_config': {
                'effort': effort,
                'format': {'type': 'json_schema', 'schema': schema},
            },
        }
        try:
            if model in FALLBACK_MODELS:
                response = client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks='default', **params)
            else:
                response = client.messages.create(**params)
        except anthropic.AuthenticationError:
            raise UserError(self.env._('The Anthropic API key is invalid.'))
        except anthropic.PermissionDeniedError:
            raise UserError(self.env._('The API key has no access to this model.'))
        except anthropic.RateLimitError:
            raise AiRateLimitError(self.env._('The Anthropic API rate limit was reached; it will be retried later.'))
        except anthropic.APIStatusError as e:
            _logger.warning('Anthropic API error %s (request id %s): %s', e.status_code, e.request_id, e.message)
            raise UserError(self.env._('Anthropic API error (%(code)s): %(msg)s', code=e.status_code, msg=e.message))
        except anthropic.APIConnectionError:
            raise UserError(self.env._('Could not connect to the Anthropic API.'))

        if response.stop_reason == 'refusal':
            raise UserError(self.env._('The model declined to process this content.'))
        if response.stop_reason == 'max_tokens':
            raise UserError(self.env._('The model answer was cut at the token limit.'))
        text = next((block.text for block in response.content if block.type == 'text'), '')
        try:
            return json.loads(text)
        except ValueError:
            _logger.warning('Unparsable AI response (request id %s): %r', response._request_id, text[:500])
            raise UserError(self.env._('The model did not return valid JSON.'))
