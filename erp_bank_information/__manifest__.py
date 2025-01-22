# -*- coding: utf-8 -*-
{
    'name': "ERP Bank Information",
    'version': '18.0',
    'summary': """ Manage and Display Bank Information in Reports """,
    'description': """ Manage and Display Bank Information in Reports """,
    'author': 'ERP CAMBODIA',
    'website': 'https://www.erpcambodia.biz/',
    'maintainer': 'ERP CAMBODIA',
    'category': 'ERP CAMBODIA/ERP CAMBODIA',
    # any module necessary for this one to work correctly
    'depends': ['base', 'sale', 'account', 'web'],
    
    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/bank_info_view.xml',
        'views/account_move_view.xml',
        'views/sale_order_view.xml'
    ],        
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
