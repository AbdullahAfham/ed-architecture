# -*- coding: utf-8 -*-
{
    'name': "HR Announcement",
    'summary': """ This module allows to create Announcement and release it to Mobile App """,
    'sequence': 10,
    # Author
    'author': 'ERP CAMBODIA',
    'website': 'https://www.erpcambodia.biz/',
    'maintainer': 'ERP CAMBODIA',

    # Categories can be used to filter modules in modules listing
    # for the full list
    'category': 'ERP CAMBODIA/ERP CAMBODIA',
    'website': "https://www.erpcambodia.biz/",
    'version': '18.0.1.0',
    'depends': ['mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/announcement_views.xml',
    ],
    'installable': True,
}
