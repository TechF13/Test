from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.political_office.models.political_ai_service import AiRateLimitError
from odoo.addons.queue_job.exception import RetryableJobError
from odoo.addons.queue_job.tests.common import trap_jobs

RSS = b"""<rss><channel><item><title>Ankara haberi</title><link>https://example.com/q1</link>
<description>Ankara</description></item></channel></rss>"""


@tagged('post_install', '-at_install')
class TestPoliticalQueue(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['political.news.source'].search([]).active = False
        cls.env['political.news.keyword'].create({'name': 'Ankara'})
        cls.source = cls.env['political.news.source'].create({
            'name': 'Kuyruk', 'source_type': 'rss', 'url': 'https://example.com/rss',
        })
        ICP = cls.env['ir.config_parameter']
        ICP.set_param('political_office.ai_auto_process', True)
        ICP.set_param('political_office.anthropic_api_key', 'test-key')

    def test_fetch_is_enqueued_per_source(self):
        with trap_jobs() as trap:
            self.env['political.news.source']._cron_fetch_news()
            trap.assert_jobs_count(1, only=self.source._job_fetch_articles)
            with patch('odoo.addons.political_office.models.political_news_source.http_get', return_value=RSS):
                trap.perform_enqueued_jobs()
        self.assertEqual(self.source.article_count, 1)

    def test_new_articles_are_enqueued_for_ai(self):
        with trap_jobs() as trap:
            article = self.env['political.news.article'].create({'name': 'Test', 'url': 'https://example.com/q2'})
            trap.assert_enqueued_job(article._job_ai_analyze)

    def test_rate_limit_is_retried(self):
        article = self.env['political.news.article'].create({'name': 'Test', 'url': 'https://example.com/q3'})
        service = type(self.env['political.ai.service'])
        with patch.object(service, '_generate_json', side_effect=AiRateLimitError('limit')):
            with self.assertRaises(RetryableJobError):
                article._job_ai_analyze()
        self.assertEqual(article.ai_state, 'pending')
