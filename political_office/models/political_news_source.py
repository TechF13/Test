import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import requests
from lxml import etree, html as lxml_html

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

USER_AGENT = 'Mozilla/5.0 (compatible; OdooPoliticalOffice/19.0; +https://www.odoo.com)'
HTTP_TIMEOUT = 20
MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024
GOOGLE_NEWS_URL = 'https://news.google.com/rss/search?q={query}&hl={lang}&gl={country}&ceid={country}:{lang}'


def http_get(url):
    """Download ``url`` and return its body, refusing responses above MAX_DOWNLOAD_BYTES."""
    with requests.get(url, timeout=HTTP_TIMEOUT, headers={'User-Agent': USER_AGENT}, stream=True) as response:
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(64 * 1024):
            size += len(chunk)
            if size > MAX_DOWNLOAD_BYTES:
                raise UserError(f'{url}: yanıt çok büyük')
            chunks.append(chunk)
        return b''.join(chunks)


def _local(tag):
    return etree.QName(tag).localname.lower() if isinstance(tag, str) else ''


def _html_to_text(value):
    if not value:
        return ''
    try:
        return ' '.join(lxml_html.fromstring(value).text_content().split())
    except (etree.ParserError, ValueError):
        return ' '.join(value.split())


def _parse_date(value):
    """Parse RFC 822 (RSS) or ISO 8601 (Atom) dates into naive UTC datetimes."""
    if not value:
        return False
    value = value.strip()
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return False
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def parse_feed(content):
    """Parse an RSS 2.0 / RSS 1.0 / Atom document into a list of item dicts."""
    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True, huge_tree=False)
    root = etree.fromstring(content, parser)
    if root is None:
        return []
    items = []
    for node in root.iter():
        if _local(node.tag) not in ('item', 'entry'):
            continue
        item = {'title': '', 'url': '', 'summary': '', 'published': False, 'publisher': ''}
        for child in node:
            name = _local(child.tag)
            text = (child.text or '').strip()
            if name == 'title':
                item['title'] = _html_to_text(text)
            elif name == 'link':
                href = child.get('href')
                if href and child.get('rel', 'alternate') == 'alternate':
                    item['url'] = href.strip()
                elif text and not item['url']:
                    item['url'] = text
            elif name in ('description', 'summary', 'encoded', 'content') and text:
                if len(text) > len(item['summary']):
                    item['summary'] = text
            elif name in ('pubdate', 'published', 'updated', 'date') and not item['published']:
                item['published'] = _parse_date(text)
            elif name == 'source' and text:
                item['publisher'] = text
            elif name == 'guid' and text.startswith('http') and child.get('isPermaLink', 'true') != 'false':
                item['url'] = item['url'] or text
        item['summary'] = _html_to_text(item['summary'])
        # Google News titles look like "Başlık - Yayın Organı".
        if item['publisher'] and item['title'].endswith(f' - {item["publisher"]}'):
            item['title'] = item['title'][: -len(item['publisher']) - 3]
        if item['title'] and item['url']:
            items.append(item)
    return items


def extract_article_text(content, max_chars=20000):
    """Best-effort extraction of the main text of a news page."""
    try:
        doc = lxml_html.fromstring(content)
    except (etree.ParserError, ValueError):
        return ''
    for bad in doc.xpath('//script|//style|//noscript|//nav|//header|//footer|//aside|//form'):
        bad.drop_tree()
    containers = doc.xpath('//article') or doc.xpath('//body') or [doc]
    paragraphs = []
    for para in containers[0].xpath('.//p'):
        text = ' '.join(para.text_content().split())
        if len(text) >= 40:
            paragraphs.append(text)
    return '\n\n'.join(paragraphs)[:max_chars]


class PoliticalNewsSource(models.Model):
    _name = 'political.news.source'
    _description = 'Haber Kaynağı'
    _order = 'sequence, name'

    name = fields.Char('Kaynak Adı', required=True)
    sequence = fields.Integer(default=10)
    source_type = fields.Selection([
        ('rss', 'RSS / Atom Beslemesi'),
        ('google_news', 'Google News Araması'),
    ], string='Tür', required=True, default='rss')
    url = fields.Char('Besleme Adresi', help='RSS veya Atom besleme URL adresi.')
    website = fields.Char('Web Sitesi')
    language = fields.Char('Dil', default='tr')
    country = fields.Char('Ülke', default='TR')
    google_news_period = fields.Integer('Arama Aralığı (gün)', default=2)
    filter_by_keywords = fields.Boolean(
        'Sadece eşleşen haberleri al', default=True,
        help='İşaretliyse sadece anahtar kelimelerden en az biriyle eşleşen haberler kaydedilir.',
    )
    keyword_ids = fields.Many2many(
        'political.news.keyword', 'political_news_source_keyword_rel', 'source_id', 'keyword_id', 'Anahtar Kelimeler',
        help='Boş bırakılırsa tüm aktif anahtar kelimeler kullanılır.',
    )
    tag_ids = fields.Many2many(
        'political.news.tag', 'political_news_source_tag_rel', 'source_id', 'tag_id', 'Varsayılan Etiketler',
    )
    fetch_full_content = fields.Boolean(
        'Haber metnini siteden indir',
        help='Beslemedeki özete ek olarak haber sayfasındaki metin çıkarılır. Google News bağlantılarında çalışmaz.',
    )
    last_fetch_date = fields.Datetime('Son Çekim', readonly=True)
    last_fetch_count = fields.Integer('Son Çekimde Yeni Haber', readonly=True)
    last_error = fields.Text('Son Hata', readonly=True)
    article_count = fields.Integer('Haber Sayısı', compute='_compute_article_count')
    active = fields.Boolean(default=True)

    def _compute_article_count(self):
        counts = dict(self.env['political.news.article']._read_group(
            [('source_id', 'in', self.ids)], ['source_id'], ['__count'],
        ))
        for source in self:
            source.article_count = counts.get(source, 0)

    @api.constrains('source_type', 'url')
    def _check_url(self):
        for source in self:
            if source.source_type == 'rss' and not (source.url or '').startswith(('http://', 'https://')):
                raise ValidationError(self.env._('%s: geçerli bir http(s) besleme adresi girin.', source.name))

    def _get_keywords(self):
        self.ensure_one()
        return self.keyword_ids.filtered('active') or self.env['political.news.keyword'].search([])

    def _google_news_url(self, keyword):
        query = keyword._get_google_query()
        if self.google_news_period:
            query = f'{query} when:{self.google_news_period}d'
        return GOOGLE_NEWS_URL.format(
            query=quote_plus(query), lang=self.language or 'tr', country=(self.country or 'TR').upper(),
        )

    def _collect_items(self):
        """Download the source and return feed items. Each item may carry the
        keyword whose search produced it under ``query_keyword``."""
        self.ensure_one()
        if self.source_type == 'google_news':
            items = []
            for keyword in self._get_keywords():
                for item in parse_feed(http_get(self._google_news_url(keyword))):
                    item['query_keyword'] = keyword
                    items.append(item)
            return items
        return parse_feed(http_get(self.url))

    def _fetch_articles(self):
        self.ensure_one()
        articles = self.env['political.news.article']._create_from_feed_items(self, self._collect_items())
        self.write({
            'last_fetch_date': fields.Datetime.now(),
            'last_fetch_count': len(articles),
            'last_error': False,
        })
        return articles

    def action_fetch(self):
        total = self.env['political.news.article']
        for source in self:
            try:
                total |= source._fetch_articles()
            except (requests.RequestException, etree.XMLSyntaxError) as e:
                raise UserError(self.env._('%(source)s kaynağından haber çekilemedi: %(error)s', source=source.name, error=e))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': self.env._('%s yeni haber kaydedildi.', len(total)),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_view_articles(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('political_office.action_political_news_article')
        action['domain'] = [('source_id', '=', self.id)]
        return action

    @api.model
    def _cron_fetch_news(self):
        sources = self.search([])
        cron = self.env['ir.cron']
        cron._commit_progress(remaining=len(sources))
        for source in sources:
            try:
                with self.env.cr.savepoint():
                    source._fetch_articles()
            except Exception as e:  # noqa: BLE001 - one broken feed must not block the others
                _logger.warning('News source %s (%s) failed: %s', source.name, source.id, e)
                source.write({'last_fetch_date': fields.Datetime.now(), 'last_error': str(e)[:2000]})
            if not cron._commit_progress(1):
                break
