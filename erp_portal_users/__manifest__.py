# -*- coding: utf-8 -*-
{
    'name': "ERP PORTAL USERS",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    # Author
    'author': 'ERP CAMBODIA',
    'website': 'https://www.erpcambodia.biz/',
    'maintainer': 'ERP CAMBODIA',


    # Categories can be used to filter modules in modules listing
    # for the full list
    'category': 'ERP CAMBODIA/ERP CAMBODIA',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/portal_users_views.xml',
        # 'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'license': 'LGPL-3',
    'installable': True,
}