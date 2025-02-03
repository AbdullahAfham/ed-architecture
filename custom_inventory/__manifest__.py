# -*- coding: utf-8 -*-
{
    'name': "Custom Inventory",
    'version': '18.0',
    'summary': """ Adds Internal Reference and Cost to Stock Quant """,
    'description': """ Adds Internal Reference and Cost to Stock Quant """,
    'author': 'ERP CAMBODIA',
    'website': 'https://www.erpcambodia.biz/',
    'maintainer': 'ERP CAMBODIA',
    'category': 'ERP CAMBODIA/ERP CAMBODIA',
    # any module necessary for this one to work correctly
    'depends': ['base', 'product', 'stock'],
    
    # always loaded
    'data': [
        'views/stock_quant_view.xml'
    ],        
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}