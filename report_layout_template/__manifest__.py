{
    'name': "Report Layout Template",
    'version': "1.0",
    'sequence': 7,
    'summary': "Report Layout Templates",
    'description': "",

    ############################ERP######################################
    # Author
    'author': 'ERP CAMBODIA',
    'website': 'https://www.erpcambodia.biz/',
    'maintainer': 'ERP CAMBODIA',

    # Categories can be used to filter modules in modules listing
    # for the full list
    'category': 'ERP CAMBODIA/ERP CAMBODIA',

    # Technical
    'support': 'info@erpcambodia.biz',
    ############################ERP######################################
    'depends': [
        'web',
        'account',
        'erp_currency_exchange',
    ],
    'data': [
        'data/report_layout.xml',
        'data/report_paperformat_view.xml',
        'views/res_company_view.xml',
    ],
    'assets': {
            'web.assets_backend': [
                '/report_layout_template/static/src/scss/layout_center.scss',
            ],
        },
    'qweb':[
        # 'views/res_company_view.xml'
    ],
    'images': [],
    'license': "LGPL-3",
    'price': 240.0,
    'currency': 'USD',
    'installable': True,
    'auto_install': False,
}
