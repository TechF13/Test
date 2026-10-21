import re
import unicodedata

from odoo import api, fields, models

# Turkish dotted/dotless I must be lowered explicitly, then everything is
# folded to ASCII so "İstanbul", "ISTANBUL" and "istanbul" match each other.
_TR_LOWER = str.maketrans({'İ': 'i', 'I': 'ı'})
_TR_FOLD = str.maketrans({'ı': 'i', 'ş': 's', 'ğ': 'g', 'ü': 'u', 'ö': 'o', 'ç': 'c', 'â': 'a', 'î': 'i', 'û': 'u'})
_WHITESPACE = re.compile(r'\s+')


def fold_text(text):
    """Normalize text for accent and case insensitive Turkish matching."""
    text = (text or '').translate(_TR_LOWER).lower().translate(_TR_FOLD)
    text = ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
    return _WHITESPACE.sub(' ', text).strip()


class PoliticalNewsKeyword(models.Model):
    _name = 'political.news.keyword'
    _description = 'Takip Edilen Anahtar Kelime'
    _order = 'priority desc, name'

    name = fields.Char('Anahtar Kelime / İfade', required=True)
    keyword_type = fields.Selection([
        ('self', 'Siyasetçinin Kendisi'),
        ('party', 'Parti'),
        ('rival', 'Rakip'),
        ('topic', 'Gündem / Konu'),
        ('region', 'Bölge'),
        ('other', 'Diğer'),
    ], string='Tür', required=True, default='topic')
    match_mode = fields.Selection([
        ('prefix', 'Kelime başı (ekleri kapsar)'),
        ('exact', 'Tam kelime'),
        ('substring', 'Metnin herhangi bir yerinde'),
    ], string='Eşleşme', required=True, default='prefix',
        help="Kelime başı: 'Ankara' ifadesi 'Ankara'da', 'Ankaralı' kelimelerini de yakalar.")
    exclude_terms = fields.Char(
        'Hariç Tutulacaklar',
        help='Virgülle ayrılmış ifadeler. Bunlardan biri geçen haberler bu kelimeyle eşleşmez (yanlış pozitifleri azaltır).',
    )
    search_query = fields.Char(
        'Arama Sorgusu',
        help='Google News araması için özel sorgu (ör. "Ahmet Yılmaz" OR "A. Yılmaz"). Boşsa ifade tırnak içinde aranır.',
    )
    tag_ids = fields.Many2many(
        'political.news.tag', 'political_news_keyword_tag_rel', 'keyword_id', 'tag_id', 'Otomatik Etiketler',
        help='Bu kelimeyle eşleşen haberlere otomatik eklenecek etiketler.',
    )
    priority = fields.Selection([('0', 'Normal'), ('1', 'Yüksek')], string='Öncelik', default='0')
    article_count = fields.Integer('Haber Sayısı', compute='_compute_article_count')
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint('UNIQUE(name)', 'Bu anahtar kelime zaten tanımlı.')

    def _compute_article_count(self):
        counts = dict(self.env['political.news.article']._read_group(
            [('keyword_ids', 'in', self.ids)], ['keyword_ids'], ['__count'],
        ))
        for keyword in self:
            keyword.article_count = counts.get(keyword, 0)

    def _get_pattern(self):
        self.ensure_one()
        term = re.escape(fold_text(self.name))
        if self.match_mode == 'prefix':
            return re.compile(rf'(?<!\w){term}')
        if self.match_mode == 'exact':
            return re.compile(rf'(?<!\w){term}(?!\w)')
        return re.compile(term)

    def _get_google_query(self):
        self.ensure_one()
        return self.search_query or f'"{self.name}"'

    @api.model
    def _match_text(self, text, keywords=None):
        """Return the keywords (among ``keywords`` or all active ones) found in ``text``."""
        keywords = self.search([]) if keywords is None else keywords
        folded = fold_text(text)
        matched = self.browse()
        if not folded:
            return matched
        for keyword in keywords:
            if not keyword.name or not keyword._get_pattern().search(folded):
                continue
            excludes = [fold_text(t) for t in (keyword.exclude_terms or '').split(',') if t.strip()]
            if any(term in folded for term in excludes):
                continue
            matched |= keyword
        return matched

    def action_view_articles(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('political_office.action_political_news_article')
        action['domain'] = [('keyword_ids', 'in', self.ids)]
        return action
