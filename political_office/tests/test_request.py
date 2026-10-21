from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPoliticalRequest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env.ref('political_office.project_citizen_requests')
        cls.zone = cls.env['political.constituency'].create({'name': 'Çankaya', 'level': 'district'})
        cls.citizen = cls.env['res.partner'].create({
            'name': 'Ayşe Demir',
            'constituency_id': cls.zone.id,
            'category_id': [(4, cls.env.ref('political_office.partner_category_citizen').id)],
        })
        cls.tag_health = cls.env.ref('political_office.tag_request_health')
        cls.Task = cls.env['project.task'].with_context(cls.env['project.task']._political_request_context())

    def test_request_is_a_project_task(self):
        request = self.Task.create({
            'name': 'Randevu sorunu',
            'partner_id': self.citizen.id,
            'tag_ids': [(4, self.tag_health.id)],
            'political_channel': 'phone',
        })
        self.assertEqual(request.project_id, self.project)
        self.assertTrue(request.is_political_request)
        self.assertEqual(request.stage_id, self.env.ref('political_office.stage_new'))
        self.assertEqual(request.constituency_id, self.zone, 'constituency comes from the citizen')
        self.assertEqual(
            request.date_deadline.date(), (request.create_date + timedelta(days=self.tag_health.political_sla_days)).date(),
            'deadline comes from the tag resolution time',
        )
        self.assertEqual(self.zone.request_count, 1)
        self.assertIn(request, self.env['project.task'].search([('constituency_id', 'child_of', self.zone.id)]))

        manual = self.Task.create({
            'name': 'Elle tarih', 'tag_ids': [(4, self.tag_health.id)], 'date_deadline': '2030-01-01 00:00:00',
        })
        self.assertEqual(fields.Datetime.to_string(manual.date_deadline), '2030-01-01 00:00:00')

        other = self.env['project.task'].create({
            'name': 'Normal görev', 'project_id': self.env['project.project'].create({'name': 'Diğer'}).id,
            'tag_ids': [(4, self.tag_health.id)],
        })
        self.assertFalse(other.date_deadline, 'resolution times only apply to citizen request projects')

    def test_schedule_meeting_links_event(self):
        request = self.Task.create({'name': 'Görüşme talebi', 'partner_id': self.citizen.id})
        action = request.action_political_schedule_meeting()
        event = self.env['calendar.event'].with_context(action['context']).create({
            'start': fields.Datetime.now(), 'stop': fields.Datetime.now() + timedelta(hours=1),
        })
        self.assertEqual((event.res_model, event.res_id), ('project.task', request.id))
        self.assertEqual(event.constituency_id, self.zone)
        self.assertIn(self.citizen, event.partner_ids)
        self.assertEqual(request.political_event_count, 1)

    def test_ai_analyze(self):
        request = self.Task.create({'name': 'Okul servisi', 'description': '<p>Servis yok</p>'})
        result = {'summary': 'Servis talebi', 'tag': 'EĞİTİM', 'priority': '2', 'draft_reply': 'Sayın vatandaşımız...'}
        with patch.object(type(self.env['political.ai.service']), '_generate_json', return_value=result):
            request.action_political_ai_analyze()
        education = self.env.ref('political_office.tag_request_education')
        self.assertEqual(request.tag_ids, education)
        self.assertEqual(request.priority, '2')
        self.assertTrue(request.date_deadline, 'deadline is set once the AI picks a category')
        self.assertEqual(request.political_ai_draft_reply, 'Sayın vatandaşımız...')

    def test_news_article_creates_request(self):
        article = self.env['political.news.article'].create({
            'name': 'Su kesintisi', 'url': 'https://example.com/su', 'constituency_id': self.zone.id,
        })
        action = article.action_create_request()
        request = self.env['project.task'].with_context(action['context']).create({'name': action['context']['default_name']})
        self.assertEqual(request.project_id, self.project)
        self.assertEqual(request.political_article_id, article)
        self.assertEqual(request.political_channel, 'news')
        self.assertEqual(article.request_count, 1)
