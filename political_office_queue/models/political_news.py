import requests
from lxml import etree

from odoo import api, models
from odoo.exceptions import UserError

from odoo.addons.political_office.models.political_ai_service import AiRateLimitError
from odoo.addons.queue_job.exception import RetryableJobError
from odoo.addons.queue_job.job import identity_exact

CHANNEL = 'root.political_office'


class PoliticalNewsSource(models.Model):
    _inherit = 'political.news.source'

    @api.model
    def _cron_fetch_news(self):
        """Enqueue one job per source instead of fetching them all in the cron."""
        for source in self.search([('source_type', '!=', 'webhook')]):
            source.with_delay(
                channel=CHANNEL, identity_key=identity_exact,
                description=self.env._('Fetch news: %s', source.name),
            )._job_fetch_articles()

    def _job_fetch_articles(self):
        self.ensure_one()
        try:
            articles = self._fetch_articles()
        except (requests.RequestException, etree.XMLSyntaxError) as e:
            self.write({'last_error': str(e)[:2000]})
            raise RetryableJobError(str(e), ignore_retry=False) from e
        return self.env._('%s new articles', len(articles))


class PoliticalNewsArticle(models.Model):
    _inherit = 'political.news.article'

    @api.model_create_multi
    def create(self, vals_list):
        articles = super().create(vals_list)
        service = self.env['political.ai.service']
        if service._get_param('ai_auto_process') and service._is_configured():
            articles.filtered(lambda a: a.ai_state == 'pending')._enqueue_ai_analysis()
        return articles

    def _enqueue_ai_analysis(self):
        for article in self:
            article.with_delay(
                channel=CHANNEL, identity_key=identity_exact,
                description=self.env._('AI analysis: %s', article.name[:80]),
            )._job_ai_analyze()

    @api.model
    def _cron_ai_process(self):
        """Safety net: enqueue pending articles that have no job yet (the job
        identity key prevents duplicates)."""
        service = self.env['political.ai.service']
        if not service._get_param('ai_auto_process') or not service._is_configured():
            return
        self.search([('ai_state', '=', 'pending')], limit=500)._enqueue_ai_analysis()

    def _job_ai_analyze(self):
        self.ensure_one()
        if self.ai_state != 'pending':
            return self.env._('Already analyzed')
        try:
            self._ai_analyze()
        except AiRateLimitError as e:
            raise RetryableJobError(str(e), seconds=120, ignore_retry=True) from e
        except UserError as e:
            self.write({'ai_state': 'error', 'ai_error': str(e)})
        return self.ai_state
