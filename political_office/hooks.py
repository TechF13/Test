"""Create the tags the module relies on without clashing with existing ones.

project.tags, calendar.event.type and res.partner.category enforce unique names,
so creating them from XML fails on databases that already contain a tag with the
same name. Existing tags are reused instead; only the tags created here get an
external id (so uninstalling the module never deletes a tag the user owned).
"""

TAGS = {
    'project.tags': [
        ('tag_request_infrastructure', {'name': 'Altyapı ve Belediye Hizmetleri', 'political_sla_days': 20}),
        ('tag_request_health', {'name': 'Sağlık', 'political_sla_days': 7}),
        ('tag_request_education', {'name': 'Eğitim', 'political_sla_days': 15}),
        ('tag_request_employment', {'name': 'İstihdam', 'political_sla_days': 30}),
        ('tag_request_social', {'name': 'Sosyal Yardım', 'political_sla_days': 10}),
        ('tag_request_transport', {'name': 'Ulaşım', 'political_sla_days': 20}),
        ('tag_request_legal', {'name': 'Hukuki / İdari Süreçler', 'political_sla_days': 15}),
        ('tag_motion_question', {'name': 'Soru Önergesi'}),
        ('tag_motion_bill', {'name': 'Kanun Teklifi'}),
        ('tag_motion_research', {'name': 'Araştırma Önergesi'}),
        ('tag_motion_committee', {'name': 'Komisyon Çalışması'}),
        ('tag_campaign_door', {'name': 'Kapı Kapı Ziyaret'}),
        ('tag_campaign_stand', {'name': 'Stant / Bildiri Dağıtımı'}),
    ],
    'calendar.event.type': [
        ('event_type_citizen_day', {'name': 'Halk Günü'}),
        ('event_type_field_visit', {'name': 'Saha Ziyareti'}),
        ('event_type_rally', {'name': 'Miting / Halk Buluşması'}),
        ('event_type_parliament', {'name': 'Meclis / Komisyon'}),
        ('event_type_party', {'name': 'Parti Toplantısı'}),
        ('event_type_media', {'name': 'Basın / Röportaj'}),
        ('event_type_citizen_meeting', {'name': 'Vatandaş Görüşmesi'}),
    ],
    'res.partner.category': [
        ('partner_category_citizen', {'name': 'Vatandaş'}),
        ('partner_category_party_member', {'name': 'Parti Üyesi'}),
        ('partner_category_volunteer', {'name': 'Gönüllü'}),
        ('partner_category_journalist', {'name': 'Gazeteci'}),
        ('partner_category_ngo', {'name': 'STK / Dernek'}),
        ('partner_category_institution', {'name': 'Kamu Kurumu'}),
    ],
}


def find_or_create_tag(env, model, xmlid, vals):
    """Return the tag named ``vals['name']``, creating it (with ``xmlid``) if missing."""
    record = env.ref(f'political_office.{xmlid}', raise_if_not_found=False)
    if record:
        return record
    Model = env[model].with_context(active_test=False)
    record = Model.search([('name', '=ilike', vals['name'])], limit=1)
    if record:
        extra = {key: value for key, value in vals.items() if key != 'name' and not record[key]}
        if extra:
            record.write(extra)
        return record
    record = Model.create(vals)
    env['ir.model.data'].create({
        'module': 'political_office',
        'name': xmlid,
        'model': model,
        'res_id': record.id,
        'noupdate': True,
    })
    return record


def post_init_hook(env):
    for model, tags in TAGS.items():
        for xmlid, vals in tags:
            find_or_create_tag(env, model, xmlid, vals)


def get_tag(env, model, name):
    """Look a module tag up by name (it may be a pre-existing, reused tag)."""
    return env[model].with_context(active_test=False).search([('name', '=ilike', name)], limit=1)
