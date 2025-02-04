# -*- coding: utf-8 -*-
{
    'name': "Custom Sale Order Date",
    'version': '18.0',
    'summary': """Allow selecting 'date_order' and prevent updates after confirming quotations""",
    'description': """Allow selecting 'date_order' and prevent updates after confirming quotations""",
    'author': 'ERP CAMBODIA',
    'website': 'https://www.erpcambodia.biz/',
    'maintainer': 'ERP CAMBODIA',
    'category': 'ERP CAMBODIA/ERP CAMBODIA',
    # any module necessary for this one to work correctly
    'depends': ['base', 'sale'],
    
    # always loaded
    'data': [
        'views/sale_order_view.xml'
    ],        
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
