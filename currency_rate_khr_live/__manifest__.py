# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Live Currency Exchange Rate KHR',
    'version': '1.0',
    'sequence': 6,
    'summary': 'Live Currency Exchange Rate KHR',
    'description': """
Live Currency Exchange Rate KHR
""",

############################ERP#####################################
    # Author
    'author': 'ERP CAMBODIA',
    'website': 'https://www.erpcambodia.biz/',
    'maintainer': 'ERP CAMBODIA',

    # Categories can be used to filter modules in modules listing
    # for the full list
    'category': 'ERP CAMBODIA/ERP CAMBODIA',

    # Technical
    'support': 'info@erpcambodia.biz',
############################ERP#####################################

    'depends': ['currency_rate_live'],
    'data': [
        "security/security.xml",
        "security/ir.model.access.csv",
        'views/views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
}