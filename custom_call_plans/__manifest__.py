# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Custom Call Plans',
    'version': '18.0',
    'category': 'CallPlan',
    'summary': '',
    'description': """
    """,
    'sequence': '10',
    'author': 'ERP CAMBODIA',
    'maintainer': 'ERP CAMBODIA',
    'website': 'erpcambodia.biz',
    'depends': ['mail'],
    'data': [
        'views/call_plans_configuration_view.xml',
        'views/call_plans_view.xml',
        'views/menu.xml',
        'security/ir.model.access.csv'
    ],
    'installable': True,
    'auto_install': False
}