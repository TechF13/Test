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
    _description = 'Tracked Keyword'
    _order = 'priority desc, name'

    name = fields.Char('Keyword / Phrase', required=True)
    keyword_type = fields.Selection([
        ('self', 'The Politician'),
        ('party', 'Party'),
        ('rival', 'Rival'),
        ('topic', 'Topic'),
        ('region', 'Area'),
        ('other', 'Other'),
    ], string='Type', required=True, default='topic')
    match_mode = fields.Selection([
        ('prefix', 'Word start (includes suffixes)'),
        ('exact', 'Whole word'),
        ('substring', 'Anywhere in the text'),
    ], string='Matching', required=True, default='prefix',
        help="Word start: 'Ankara' also matches 'Ankara'da' and 'Ankaralı'.")
    exclude_terms = fields.Char(
        'Excluded Terms',
        help='Comma separated phrases. Articles containing one of them do not match this keyword (reduces false positives).',
    )
    search_query = fields.Char(
        'Search Query',
        help='Custom Google News query (e.g. "Ahmet Yılmaz" OR "A. Yılmaz"). When empty, the phrase is searched in quotes.',
    )
    tag_ids = fields.Many2many(
        'political.news.tag', 'political_news_keyword_tag_rel', 'keyword_id', 'tag_id', 'Automatic Tags',
        help='Tags added automatically to articles matching this keyword.',
    )
    priority = fields.Selection([('0', 'Normal'), ('1', 'High')], string='Priority', default='0')
    article_count = fields.Integer('Article Count', compute='_compute_article_count')
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint('UNIQUE(name)', 'This keyword already exists.')

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
