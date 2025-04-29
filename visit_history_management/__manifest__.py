{
    'name': 'Visit History Management',
    'version': '18.0.1.0',
    'category': 'ERP CAMBODIA/ERP CAMBODIA',
    'summary': 'Managing visit history of Saleperson with Customer.',
    'sequence': 10,
    'author': 'ERP CAMBODIA',
    'maintainer': 'ERP CAMBODIA',
    'website': 'https://www.erpcambodia.biz/',
    'depends': ['base', 'hr_internal_api'],
    'data': [
        'security/ir.model.access.csv',
        'views/partner_visit_history_views.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False
}