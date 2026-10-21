import json
from datetime import datetime
from unittest.mock import patch

from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.political_office.models.political_news_article import normalize_url
from odoo.addons.political_office.models.political_news_keyword import fold_text
from odoo.addons.political_office.models.political_news_source import extract_article_text, parse_feed

RSS_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE rss [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<rss version="2.0">
  <channel>
    <title>Test Gazetesi</title>
    <item>
      <title>Ahmet Y\xc4\xb1lmaz Ankara'da hastane a\xc3\xa7\xc4\xb1l\xc4\xb1\xc5\x9f\xc4\xb1na kat\xc4\xb1ld\xc4\xb1 - Test Gazetesi</title>
      <link>https://example.com/haber/1?utm_source=rss&amp;id=5#yorumlar</link>
      <description>&lt;p&gt;Yeni hastane &lt;b&gt;bug\xc3\xbcn&lt;/b&gt; a\xc3\xa7\xc4\xb1ld\xc4\xb1.&lt;/p&gt;</description>
      <pubDate>Tue, 20 Oct 2026 09:30:00 +0300</pubDate>
      <source url="https://example.com">Test Gazetesi</source>
    </item>
    <item>
      <title>Hava durumu: yar\xc4\xb1n ya\xc4\x9fmur bekleniyor &amp;xxe;</title>
      <link>https://example.com/haber/2</link>
      <description>Meteoroloji uyard\xc4\xb1.</description>
      <pubDate>Tue, 20 Oct 2026 10:00:00 +0300</pubDate>
    </item>
  </channel>
</rss>"""

ATOM_FEED = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Meclis gundemi</title>
    <link rel="alternate" href="https://example.org/meclis"/>
    <summary>Ahmet Yilmaz soru onergesi verdi.</summary>
    <updated>2026-10-20T08:00:00Z</updated>
  </entry>
</feed>"""


@tagged('post_install', '-at_install')
class TestNewsPipeline(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Keyword = cls.env['political.news.keyword']
        cls.tag_health = cls.env.ref('political_office.tag_health')
        cls.env['political.news.source'].search([]).active = False
        cls.kw_person = cls.Keyword.create({'name': 'Ahmet Yılmaz', 'keyword_type': 'self'})
        cls.kw_city = cls.Keyword.create({
            'name': 'Ankara', 'keyword_type': 'region', 'tag_ids': [(4, cls.tag_health.id)],
        })
        cls.source = cls.env['political.news.source'].create({
            'name': 'Test RSS', 'source_type': 'rss', 'url': 'https://example.com/rss',
        })

    def test_fold_text(self):
        self.assertEqual(fold_text('İSTANBUL ışığı'), 'istanbul isigi')
        self.assertEqual(fold_text('  Çağrı\n Öztürk '), 'cagri ozturk')

    def test_keyword_matching(self):
        match = self.Keyword._match_text
        self.assertEqual(match("AHMET YILMAZ Ankara'da konuştu"), self.kw_person | self.kw_city)
        # prefix mode tolerates Turkish suffixes but not a word starting before
        self.assertEqual(match('Ankaralı esnaf'), self.kw_city)
        self.assertFalse(match('Başkentankara'))
        self.kw_city.match_mode = 'exact'
        self.assertFalse(match('Ankaralı esnaf'))
        self.kw_city.write({'match_mode': 'prefix', 'exclude_terms': 'Ankaragücü, maç'})
        self.assertFalse(match('Ankaragücü maçı kazandı'))

    def test_parse_rss(self):
        items = parse_feed(RSS_FEED)
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first['title'], "Ahmet Yılmaz Ankara'da hastane açılışına katıldı")
        self.assertEqual(first['publisher'], 'Test Gazetesi')
        self.assertEqual(first['summary'], 'Yeni hastane bugün açıldı.')
        self.assertEqual(first['published'], datetime(2026, 10, 20, 6, 30))
        self.assertNotIn('root:', items[1]['title'], 'external entities must not be resolved')

    def test_parse_atom(self):
        items = parse_feed(ATOM_FEED)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['url'], 'https://example.org/meclis')
        self.assertEqual(items[0]['published'], datetime(2026, 10, 20, 8, 0))

    def test_normalize_url(self):
        self.assertEqual(
            normalize_url('HTTPS://Example.com/haber/1?utm_source=rss&id=5#yorumlar'),
            'https://example.com/haber/1?id=5',
        )

    def test_extract_article_text(self):
        page = b"""<html><body><nav><p>Menu menu menu menu menu menu menu menu menu menu</p></nav>
            <article><p>Kisa</p><p>Bu paragraf haberin asil metnidir ve yeterince uzun bir cumledir.</p></article>
            <script>var x = 1;</script></body></html>"""
        self.assertEqual(extract_article_text(page), 'Bu paragraf haberin asil metnidir ve yeterince uzun bir cumledir.')

    def test_fetch_creates_and_deduplicates(self):
        with patch('odoo.addons.political_office.models.political_news_source.http_get', return_value=RSS_FEED):
            articles = self.source._fetch_articles()
            self.assertEqual(len(articles), 1, 'only the item matching a keyword is kept')
            self.assertEqual(articles.url, 'https://example.com/haber/1?id=5')
            self.assertEqual(articles.keyword_ids, self.kw_person | self.kw_city)
            self.assertEqual(articles.tag_ids, self.tag_health, 'keyword tags are applied automatically')
            self.assertEqual(articles.ai_state, 'pending')
            self.assertEqual(self.source.last_fetch_count, 1)
            self.assertFalse(self.source._fetch_articles(), 'already fetched articles are skipped')

        self.source.filter_by_keywords = False
        with patch('odoo.addons.political_office.models.political_news_source.http_get', return_value=RSS_FEED):
            self.assertEqual(len(self.source._fetch_articles()), 1, 'unmatched item is stored when filtering is off')

    def test_google_news_url(self):
        google = self.env.ref('political_office.source_google_news')
        google.keyword_ids = self.kw_person
        url = google._google_news_url(self.kw_person)
        self.assertTrue(url.startswith('https://news.google.com/rss/search?q=%22Ahmet+Y%C4%B1lmaz%22+when%3A2d'))
        self.assertTrue(url.endswith('&hl=tr&gl=TR&ceid=TR:tr'))
        with patch('odoo.addons.political_office.models.political_news_source.http_get', return_value=ATOM_FEED):
            articles = google._fetch_articles()
        self.assertEqual(articles.keyword_ids, self.kw_person, 'the searched keyword is linked even without a text match')

    def test_ai_analysis_applies_result(self):
        district = self.env['political.constituency'].create({'name': 'Çankaya', 'level': 'district'})
        article = self.env['political.news.article'].create({
            'name': 'Ahmet Yılmaz hastane açılışında',
            'url': 'https://example.com/a',
            'content': 'Açılış yapıldı.',
        })
        result = {
            'summary': 'Hastane açıldı.',
            'sentiment': 'positive',
            'importance': 'medium',
            'relevance': 140,
            'tags': ['saglik', 'Bilinmeyen'],
            'new_tags': ['Hastane Açılışı'],
            'people': ['Ahmet Yılmaz'],
            'organizations': [],
            'locations': ['Ankara', 'ÇANKAYA'],
            'action_required': True,
            'action_suggestion': 'Teşekkür mesajı paylaşılabilir.',
        }
        self.env['ir.config_parameter'].set_param('political_office.ai_allow_new_tags', True)
        with patch.object(type(self.env['political.ai.service']), '_generate_json', return_value=result) as call:
            article.action_ai_analyze()
        system, prompt, _schema = call.call_args.args
        self.assertIn('<haber>', prompt)
        self.assertIn(self.tag_health.name, system)
        self.assertEqual(article.ai_state, 'done')
        self.assertEqual(article.sentiment, 'positive')
        self.assertEqual(article.relevance, 100, 'relevance is clamped')
        self.assertEqual(article.constituency_id, district)
        self.assertIn(self.tag_health, article.tag_ids, 'tag names are matched accent-insensitively')
        new_tag = article.tag_ids - self.tag_health
        self.assertEqual(new_tag.name, 'Hastane Açılışı')
        self.assertTrue(new_tag.created_by_ai)

    def test_daily_report(self):
        self.env['political.news.article'].create([{
            'name': f'Haber {i}', 'url': f'https://example.com/r{i}', 'ai_state': 'done',
            'relevance': relevance, 'sentiment': 'negative', 'importance': 'high', 'ai_summary': 'Özet',
        } for i, relevance in enumerate((80, 10))])
        report = self.env['political.news.report'].create({'name': 'Test', 'min_relevance': 30})
        report.action_collect_articles()
        self.assertEqual(report.article_count, 1, 'low relevance news is left out')
        result = {
            'headline': 'Manşet <script>',
            'executive_summary': 'Özet',
            'themes': [{'title': 'Sağlık', 'summary': 'Detay', 'article_numbers': [1, 7]}],
            'risks': ['Risk'],
            'opportunities': [],
            'recommended_actions': ['Açıklama yap'],
        }
        with patch.object(type(self.env['political.ai.service']), '_generate_json', return_value=result):
            report.action_generate()
        self.assertEqual(report.state, 'done')
        self.assertEqual(report.negative_count, 1)
        self.assertIn('https://example.com/r0', report.report_html)
        self.assertNotIn('<script>', report.report_html)


YOUTUBE_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>abc</yt:videoId>
    <title>Ahmet Y\xc4\xb1lmaz meclis konu\xc5\x9fmas\xc4\xb1</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc"/>
    <published>2026-10-20T08:00:00+00:00</published>
    <media:group><media:description>Genel kurulda b\xc3\xbct\xc3\xa7e konu\xc5\x9fmas\xc4\xb1</media:description></media:group>
  </entry>
</feed>"""


@tagged('post_install', '-at_install')
class TestNewsExtensions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.keyword = cls.env['political.news.keyword'].create({'name': 'Ahmet Yılmaz', 'keyword_type': 'self'})
        cls.Article = cls.env['political.news.article']

    def test_youtube_source(self):
        source = self.env['political.news.source'].create({
            'name': 'Kanal', 'source_type': 'youtube', 'youtube_channel_id': 'UC123', 'platform': 'YouTube',
        })
        self.assertEqual(source.media_type, 'video')
        with patch('odoo.addons.political_office.models.political_news_source.http_get', return_value=YOUTUBE_FEED) as get:
            article = source._fetch_articles()
        self.assertEqual(get.call_args.args[0], 'https://www.youtube.com/feeds/videos.xml?channel_id=UC123')
        self.assertEqual(article.media_type, 'video')
        self.assertEqual(article.content, 'Genel kurulda bütçe konuşması')

    def test_story_clustering(self):
        first = self.Article.create({'name': 'Çankaya Belediyesi su kesintisi için açıklama yaptı', 'url': 'https://e.com/s1'})
        second = self.Article.create({'name': 'Çankaya su kesintisi: Belediye açıklama yaptı', 'url': 'https://e.com/s2'})
        other = self.Article.create({'name': 'Dolar güne yükselişle başladı', 'url': 'https://e.com/s3'})
        self.assertTrue(first.story_id)
        self.assertEqual(first.story_id, second.story_id)
        self.assertNotEqual(first.story_id, other.story_id)
        self.assertEqual(first.story_id.article_count, 2)

        # the AI can merge an article into an existing story
        result = {'summary': 'x', 'sentiment': 'neutral', 'importance': 'low', 'relevance': 10, 'tags': [],
                  'new_tags': [], 'people': [], 'organizations': [], 'locations': [], 'action_required': False,
                  'action_suggestion': '', 'same_story_as': 1}
        old_story = other.story_id
        with patch.object(type(other), '_ai_story_candidates', return_value=first.story_id), \
                patch.object(type(self.env['political.ai.service']), '_generate_json', return_value=result):
            other.action_ai_analyze()
        self.assertEqual(other.story_id, first.story_id)
        self.assertFalse(old_story.exists(), 'the emptied story is removed')

    def test_alert_and_press_statement(self):
        self.env['ir.config_parameter'].set_param('political_office.alert_level', 'high')
        admin = self.env.ref('base.user_admin')
        self.env.company.political_alert_user_ids = admin
        article = self.Article.create({'name': 'Kriz haberi', 'url': 'https://e.com/k1', 'content': 'Kriz'})
        result = {'summary': 'Kriz özeti', 'sentiment': 'negative', 'importance': 'critical', 'relevance': 90,
                  'tags': [], 'new_tags': [], 'people': [], 'organizations': [], 'locations': [],
                  'action_required': True, 'action_suggestion': 'Açıklama yap', 'same_story_as': 0}
        with patch.object(type(self.env['political.ai.service']), '_generate_json', return_value=result):
            article.action_ai_analyze()
            article.action_ai_analyze()
        self.assertTrue(article.alert_sent)
        alerts = article.message_ids.filtered(lambda m: m.subject and m.subject.startswith('Medya uyarısı'))
        self.assertEqual(len(alerts), 1, 'an article triggers a single alert')
        self.assertIn(admin.partner_id, alerts.partner_ids)

        statement = {'title': 'Açıklama', 'statement': 'Birinci paragraf.\n\nİkinci <b>paragraf</b>.',
                     'key_messages': ['Mesaj'], 'cautions': []}
        with patch.object(type(self.env['political.ai.service']), '_generate_json', return_value=statement):
            article.story_id.action_ai_press_statement()
        self.assertIn('<p>Birinci paragraf.</p>', article.story_id.press_statement)
        self.assertNotIn('<b>paragraf</b>', article.story_id.press_statement)

    def test_dashboard_data(self):
        self.Article.create({'name': 'Olumsuz', 'url': 'https://e.com/d1', 'sentiment': 'negative',
                             'importance': 'high', 'action_required': True})
        data = self.env['political.dashboard'].get_dashboard_data()
        self.assertEqual(len(data['trend']['days']), 7)
        self.assertGreaterEqual(data['trend']['days'][-1]['negative'], 1)
        self.assertGreaterEqual(data['kpis']['action_news'], 1)
        self.assertTrue(any(n['name'] == 'Olumsuz' for n in data['important_news']))
        action = self.env['political.dashboard'].open_kpi('overdue_requests')
        self.assertEqual(action['res_model'], 'project.task')


@tagged('post_install', '-at_install')
class TestSocialWebhook(HttpCase):

    def test_webhook(self):
        self.env['political.news.keyword'].create({'name': 'Ankara'})
        source = self.env['political.news.source'].create({'name': 'X hesabı', 'source_type': 'webhook', 'platform': 'X'})
        self.assertTrue(source.webhook_token)
        self.assertEqual(source.media_type, 'social')
        url = f'/political_office/webhook/{source.webhook_token}'
        payload = {'items': [
            {'text': 'Ankara için yeni metro hattı müjdesi', 'url': 'https://x.com/a/status/1', 'author': '@a'},
            {'text': 'Alakasız paylaşım', 'url': 'https://x.com/a/status/2'},
            {'text': 'URL yok'},
        ]}
        response = self.url_open(url, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        self.assertEqual(response.json(), {'received': 2, 'created': 1})
        article = self.env['political.news.article'].search([('url', '=', 'https://x.com/a/status/1')])
        self.assertEqual((article.media_type, article.platform, article.publisher), ('social', 'X', '@a'))
        self.assertEqual(self.url_open('/political_office/webhook/wrong', data='{}').status_code, 404)
