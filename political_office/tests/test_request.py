from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPoliticalRequest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.citizen = cls.env['res.partner'].create({'name': 'Ayşe Demir', 'phone': '+90 555 000 00 00'})
        cls.category = cls.env.ref('political_office.category_health')
        cls.solved = cls.env.ref('political_office.stage_solved')

    def test_request_lifecycle(self):
        request = self.env['political.request'].create({
            'name': 'Randevu sorunu',
            'partner_id': self.citizen.id,
            'category_id': self.category.id,
        })
        self.assertTrue(request.reference.startswith('TLP/'))
        self.assertEqual(request.contact_phone, '+90 555 000 00 00')
        self.assertEqual(request.stage_id, self.env.ref('political_office.stage_new'))
        self.assertEqual(request.date_deadline, request.date_received.date() + timedelta(days=self.category.sla_days))
        self.assertEqual(self.citizen.political_request_count, 1)

        request.date_deadline = fields.Date.today() - timedelta(days=1)
        self.assertTrue(request.is_overdue)
        self.assertIn(request, self.env['political.request'].search([('is_overdue', '=', True)]))

        request.stage_id = self.solved
        self.assertTrue(request.date_closed)
        self.assertFalse(request.is_overdue)
        self.assertNotIn(request, self.env['political.request'].search([('is_overdue', '=', True)]))

    def test_schedule_meeting_links_event(self):
        request = self.env['political.request'].create({'name': 'Görüşme talebi', 'partner_id': self.citizen.id})
        action = request.action_schedule_meeting()
        event = self.env['calendar.event'].with_context(action['context']).create({
            'start': fields.Datetime.now(), 'stop': fields.Datetime.now() + timedelta(hours=1),
        })
        self.assertEqual(event.political_request_ids, request)
        self.assertEqual(request.event_count, 1)
        self.assertIn(self.citizen, event.partner_ids)

    def test_ai_analyze(self):
        request = self.env['political.request'].create({'name': 'Okul servisi', 'description': '<p>Servis yok</p>'})
        result = {'summary': 'Servis talebi', 'category': 'eğitim', 'priority': '2', 'draft_reply': 'Sayın vatandaşımız...'}
        with patch.object(type(self.env['political.ai.service']), '_generate_json', return_value=result):
            request.action_ai_analyze()
        self.assertEqual(request.category_id, self.env.ref('political_office.category_education'))
        self.assertEqual(request.priority, '2')
        self.assertEqual(request.ai_draft_reply, 'Sayın vatandaşımız...')
