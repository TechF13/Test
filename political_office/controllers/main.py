import json
import logging

from odoo import http
from odoo.http import request
from odoo.tools import email_normalize

from ..models.political_news_source import parse_date

_logger = logging.getLogger(__name__)

MAX_WEBHOOK_ITEMS = 100
MAX_LENGTHS = {'name': 128, 'email': 128, 'phone': 32, 'subject': 200, 'description': 5000}


class PoliticalOfficeController(http.Controller):

    def _public_form_enabled(self):
        return bool(request.env['ir.config_parameter'].sudo().get_param('political_office.public_form_enabled'))

    def _render_form(self, values=None, errors=None):
        constituencies = request.env['political.constituency'].sudo().search([('level', '!=', 'neighborhood')])
        return request.render('political_office.public_request_form', {
            'values': values or {},
            'errors': errors or {},
            'constituencies': constituencies,
            'company': request.env.company,
        })

    @http.route('/talep', type='http', auth='public', methods=['GET'], website=True, sitemap=False)
    def request_form(self, **kwargs):
        if not self._public_form_enabled():
            raise request.not_found()
        return self._render_form()

    @http.route('/talep/gonder', type='http', auth='public', methods=['POST'], website=True, sitemap=False)
    def request_submit(self, **post):
        if not self._public_form_enabled():
            raise request.not_found()
        values = {key: (post.get(key) or '').strip()[:limit] for key, limit in MAX_LENGTHS.items()}
        # Bots fill in every field, including the hidden one.
        if post.get('website'):
            return request.render('political_office.public_request_thanks', {'task': False})
        errors = {}
        for field in ('name', 'subject', 'description'):
            if not values[field]:
                errors[field] = True
        if not values['email'] and not values['phone']:
            errors['contact'] = True
        if values['email'] and not email_normalize(values['email']):
            errors['email'] = True
        if not post.get('consent'):
            errors['consent'] = True
        try:
            values['constituency_id'] = int(post.get('constituency_id') or 0)
        except ValueError:
            values['constituency_id'] = 0
        if errors:
            return self._render_form(values, errors)
        task = request.env['project.task'].sudo()._political_create_public_request(values)
        _logger.info('Public citizen request %s created', task.id)
        return request.render('political_office.public_request_thanks', {'task': task})


class PoliticalSocialWebhook(http.Controller):
    """Receives posts pushed by automation tools (n8n, Make, Zapier...) for
    platforms without a free API such as X or Instagram.

    Payload: a post object, a list of posts or ``{"items": [...]}`` where each
    post has ``title``/``text``, ``url`` and optionally ``published``,
    ``author`` and ``platform``.
    """

    @http.route('/political_office/webhook/<string:token>', type='http', auth='public', methods=['POST'],
                csrf=False, sitemap=False)
    def social_webhook(self, token, **kwargs):
        source = request.env['political.news.source'].sudo().search(
            [('source_type', '=', 'webhook'), ('webhook_token', '=', token)], limit=1,
        )
        if not token or not source:
            return request.make_json_response({'error': 'unknown webhook'}, status=404)
        try:
            payload = json.loads(request.httprequest.get_data() or b'null')
        except ValueError:
            return request.make_json_response({'error': 'invalid JSON'}, status=400)
        if isinstance(payload, dict) and isinstance(payload.get('items'), list):
            posts = payload['items']
        elif isinstance(payload, list):
            posts = payload
        else:
            posts = [payload]
        items = []
        for post in posts[:MAX_WEBHOOK_ITEMS]:
            if not isinstance(post, dict):
                continue
            text = str(post.get('text') or post.get('content') or post.get('summary') or '')
            title = ' '.join(str(post.get('title') or text[:140]).split())
            url = str(post.get('url') or post.get('link') or '')
            if not title or not url.startswith(('http://', 'https://')):
                continue
            items.append({
                'title': title[:500],
                'url': url[:2000],
                'summary': text[:20000],
                'published': parse_date(str(post.get('published') or post.get('date') or '')),
                'publisher': str(post.get('author') or post.get('publisher') or source.platform or source.name)[:200],
                'platform': str(post.get('platform') or source.platform or '')[:64],
            })
        articles = request.env['political.news.article'].sudo()._create_from_feed_items(source, items)
        return request.make_json_response({'received': len(items), 'created': len(articles)})
