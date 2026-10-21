from ast import literal_eval
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.political_office.hooks import get_tag


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
            'category_id': [(4, get_tag(cls.env, 'res.partner.category', 'Vatandaş').id)],
        })
        cls.tag_health = get_tag(cls.env, 'project.tags', 'Sağlık')
        cls.Task = cls.env['project.task'].with_context(cls.env['project.task']._political_request_context())

    def test_request_is_a_project_task(self):
        request = self.Task.create({
            'name': 'Randevu sorunu',
            'partner_id': self.citizen.id,
            'tag_ids': [(4, self.tag_health.id)],
            'political_channel': 'phone',
        })
        self.assertEqual(request.project_id, self.project)
        self.assertEqual(request.political_project_type, 'request')
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
        education = get_tag(self.env, 'project.tags', 'Eğitim')
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

    def test_stage_templates_notify_citizen(self):
        self.citizen.email = 'ayse@example.com'
        request = self.Task.create({'name': 'Bildirim', 'partner_id': self.citizen.id})
        request.stage_id = self.env.ref('political_office.stage_forwarded')
        self.env.flush_all()
        self.env.cr.precommit.run()
        subjects = request.message_ids.mapped('subject')
        self.assertTrue(any(s and 'kuruma iletildi' in s for s in subjects), subjects)

    def test_parliament_and_field_work(self):
        parliament = self.env.ref('political_office.project_parliament')
        motion = self.env['project.task'].create({
            'name': 'Hastane soru önergesi', 'project_id': parliament.id,
            'tag_ids': [(4, get_tag(self.env, 'project.tags', 'Soru Önergesi').id)],
        })
        self.assertEqual(motion.political_project_type, 'parliament')
        self.assertFalse(motion.date_deadline, 'resolution times are only for citizen requests')
        self.assertEqual(motion.stage_id, self.env.ref('political_office.stage_motion_draft'))

        volunteer = self.env['res.partner'].create({
            'name': 'Gönüllü Ali', 'category_id': [(4, get_tag(self.env, 'res.partner.category', 'Gönüllü').id)],
        })
        field_task = self.env['project.task'].create({
            'name': 'Kapı kapı ziyaret', 'project_id': self.env.ref('political_office.project_campaign').id,
            'political_volunteer_ids': [(4, volunteer.id)],
            'political_target_count': 200, 'political_reached_count': 50,
        })
        self.assertEqual(field_task.political_progress, 25.0)
        domain = self.env['ir.actions.act_window']._for_xml_id('political_office.action_political_volunteers')['domain']
        volunteers = self.env['res.partner'].search(literal_eval(domain) if isinstance(domain, str) else domain)
        self.assertIn(volunteer, volunteers)

    def test_existing_tags_are_reused(self):
        from odoo.addons.political_office.hooks import find_or_create_tag
        existing = self.env['project.tags'].create({'name': 'Mevcut Etiket'})
        tag = find_or_create_tag(self.env, 'project.tags', 'tag_test_reuse', {'name': 'mevcut etiket', 'political_sla_days': 3})
        self.assertEqual(tag, existing)
        self.assertEqual(tag.political_sla_days, 3)
        self.assertFalse(self.env.ref('political_office.tag_test_reuse', raise_if_not_found=False),
                         'a reused tag gets no external id so uninstalling never deletes it')


@tagged('post_install', '-at_install')
class TestPublicRequestForm(HttpCase):

    def test_public_form(self):
        self.assertEqual(self.url_open('/talep').status_code, 404, 'the form is disabled by default')
        self.env['ir.config_parameter'].set_param('political_office.public_form_enabled', True)
        page = self.url_open('/talep')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Talebi Gönder', page.text)
        csrf = page.text.split('name="csrf_token" value="')[1].split('"')[0]
        data = {
            'csrf_token': csrf, 'name': 'Mehmet Kaya', 'email': 'mehmet@example.com', 'phone': '',
            'subject': 'Park bakımı', 'description': 'Parktaki banklar kırık.', 'consent': '1',
        }
        response = self.url_open('/talep/gonder', data=data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Talebiniz alındı', response.text)
        task = self.env['project.task'].search([('name', '=', 'Park bakımı')])
        self.assertEqual(task.project_id, self.env.ref('political_office.project_citizen_requests'))
        self.assertEqual(task.political_channel, 'website')
        self.assertEqual(task.partner_id.email, 'mehmet@example.com')

        # missing consent and contact information are rejected
        response = self.url_open('/talep/gonder', data=dict(data, email='', consent='', subject='Eksik'))
        self.assertIn('telefon veya e-posta', response.text)
        self.assertFalse(self.env['project.task'].search([('name', '=', 'Eksik')]))

        # honeypot
        self.url_open('/talep/gonder', data=dict(data, website='spam', subject='Spam'))
        self.assertFalse(self.env['project.task'].search([('name', '=', 'Spam')]))
