from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models

DEFAULT_TZ = 'Europe/Istanbul'
TREND_DAYS = 7
SENTIMENTS = ('positive', 'neutral', 'negative')


class PoliticalDashboard(models.AbstractModel):
    _name = 'political.dashboard'
    _description = 'Siyasi Ofis Paneli'

    @api.model
    def _tz(self):
        return pytz.timezone(self.env.user.tz or DEFAULT_TZ)

    @api.model
    def _today(self):
        return datetime.now(self._tz()).date()

    @api.model
    def _local_day_bounds(self, day):
        """UTC naive bounds of a local calendar day."""
        tz = self._tz()
        start = tz.localize(datetime.combine(day, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        return start, start + timedelta(days=1)

    @api.model
    def _kpi_domains(self):
        now = fields.Datetime.now()
        today_start, today_end = self._local_day_bounds(self._today())
        open_requests = [('project_id.political_project_type', '=', 'request'), ('is_closed', '=', False)]
        return {
            'open_requests': ('project.task', open_requests),
            'overdue_requests': ('project.task', open_requests + [('date_deadline', '<', now)]),
            'open_motions': ('project.task', [('project_id.political_project_type', '=', 'parliament'), ('is_closed', '=', False)]),
            'today_events': ('calendar.event', [('start', '<', today_end), ('stop', '>=', today_start)]),
            'new_news': ('political.news.article', [('fetch_date', '>=', now - timedelta(days=1))]),
            'negative_news': ('political.news.article', [
                ('sentiment', '=', 'negative'), ('published_date', '>=', now - timedelta(days=TREND_DAYS)),
            ]),
            'action_news': ('political.news.article', [('action_required', '=', True), ('review_state', '=', 'new')]),
        }

    @api.model
    def open_kpi(self, key):
        model, domain = self._kpi_domains()[key]
        names = {
            'project.task': self.env._('Görevler'),
            'calendar.event': self.env._('Bugünkü Etkinlikler'),
            'political.news.article': self.env._('Haberler'),
        }
        return {
            'type': 'ir.actions.act_window',
            'name': names[model],
            'res_model': model,
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'target': 'current',
        }

    @api.model
    def _format_local(self, value, fmt='%H:%M'):
        if not value:
            return ''
        return pytz.utc.localize(value).astimezone(self._tz()).strftime(fmt)

    @api.model
    def get_dashboard_data(self):
        kpis = {
            key: self.env[model].search_count(domain)
            for key, (model, domain) in self._kpi_domains().items()
        }
        today_start, today_end = self._local_day_bounds(self._today())
        events = self.env['calendar.event'].search(
            [('start', '<', today_end), ('stop', '>=', today_start)], order='start', limit=8,
        )
        Article = self.env['political.news.article']
        important = Article.search([
            ('review_state', '=', 'new'),
            '|', ('importance', 'in', ['high', 'critical']), ('action_required', '=', True),
        ], order='published_date desc', limit=6)
        stories = self.env['political.news.story'].search([
            ('date_last', '>=', fields.Datetime.now() - timedelta(days=3)), ('article_count', '>', 1),
        ], order='article_count desc, date_last desc', limit=6)
        by_zone = self.env['project.task']._read_group(
            self._kpi_domains()['open_requests'][1] + [('constituency_id', '!=', False)],
            ['constituency_id'], ['__count'], order='__count desc', limit=6,
        )
        importance_labels = dict(Article._fields['importance'].selection)
        sentiment_labels = dict(Article._fields['sentiment'].selection)
        return {
            'kpis': kpis,
            'events': [{
                'id': event.id,
                'name': event.name,
                'time': self.env._('Tüm gün') if event.allday else self._format_local(event.start),
                'location': event.location or '',
                'tags': event.categ_ids.mapped('name'),
            } for event in events],
            'important_news': [{
                'id': article.id,
                'name': article.name,
                'publisher': article.publisher or '',
                'date': self._format_local(article.published_date, '%d.%m %H:%M'),
                'importance': article.importance or '',
                'importance_label': importance_labels.get(article.importance, ''),
                'sentiment': article.sentiment or '',
                'sentiment_label': sentiment_labels.get(article.sentiment, ''),
                'action': article.action_suggestion or '',
            } for article in important],
            'stories': [{
                'id': story.id,
                'name': story.name,
                'count': story.article_count,
                'publishers': story.publisher_count,
                'negative': story.negative_count,
            } for story in stories],
            'zones': [{'id': zone.id, 'name': zone.complete_name, 'count': count} for zone, count in by_zone],
            'trend': self._sentiment_trend(sentiment_labels),
        }

    @api.model
    def _sentiment_trend(self, labels):
        today = self._today()
        days = [today - timedelta(days=offset) for offset in range(TREND_DAYS - 1, -1, -1)]
        start, _end = self._local_day_bounds(days[0])
        groups = self.env['political.news.article'].with_context(tz=self._tz().zone)._read_group(
            [('published_date', '>=', start), ('sentiment', 'in', SENTIMENTS)],
            ['published_date:day', 'sentiment'], ['__count'],
        )
        counts = {}
        for day, sentiment, count in groups:
            key = day.date() if isinstance(day, datetime) else day
            counts[key, sentiment] = count
        series = []
        for day in days:
            values = {sentiment: counts.get((day, sentiment), 0) for sentiment in SENTIMENTS}
            series.append({'day': day.strftime('%d.%m'), 'total': sum(values.values()), **values})
        return {'days': series, 'labels': [{'key': key, 'label': labels[key]} for key in SENTIMENTS]}
