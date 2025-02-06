{
    'name': "ERP Currency Exchange",
    'version': "18.0",
    'sequence': 7,
    'summary': """Adds multi-currency exchange functionality to invoices, sales and purchases, 
        including automatic exchange rate calculations for USD and KHR""",
    'description':  """Adds multi-currency exchange functionality to invoices, sales and purchase, 
        including automatic exchange rate calculations for USD and KHR""",

    # Author
    'author': 'ERP CAMBODIA',
    'website': 'https://www.erpcambodia.biz/',
    'maintainer': 'ERP CAMBODIA',

    # Categories can be used to filter modules in modules listing
    # for the full list
    'category': 'ERP CAMBODIA/ERP CAMBODIA',

    # Technical
    'support': 'info@erpcambodia.biz',
    'depends': [
        'web',
        'account',
        'purchase',
        'sale'
    ],
    'data': [
        'views/purhcase_order_view.xml',
        'views/sale_order_view.xml',
        'views/account_move_view.xml',
    ],
    'qweb':[],    
    'images': [],
    'license': "LGPL-3",
    'currency': 'USD',
    'installable': True,
    'auto_install': False,
}
