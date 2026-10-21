{
    'name': 'Siyasi Ofis - İş Kuyruğu',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Haber çekme ve AI analizini OCA queue_job kuyruğunda paralel ve yeniden denemeli çalıştırır',
    'author': 'F13 İstanbul',
    'license': 'LGPL-3',
    'depends': ['political_office', 'queue_job'],
    'data': [
        'data/queue_job_data.xml',
    ],
    'installable': True,
    'auto_install': True,
}
