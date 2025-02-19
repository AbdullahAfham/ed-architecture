# -*- coding: utf-8 -*-
{
    'name': 'Point of Sale Khmer',
    'summary': 'Add Cambodia Operation in the Point of Sale ',
    'description': """ This module used for support POS Cambodia Operation. """,
    'category': 'ERP CAMBODIA/ERP CAMBODIA',
    'version': '0.1',
    "license": "LGPL-3",

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'analytic',
        'point_of_sale',
        'pos_settle_due',
        'pos_hr',
    ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/res_groups.xml',
        'security/ir_rule_data.xml',
        'views/point_of_sale_dashboard.xml',
        'views/pos_config.xml',
        'views/pos_payment_views.xml',
        'views/pos_session_view.xml',
        'views/res_config_settings_views.xml',
        'views/account_view.xml',
        'views/views.xml',
    ],

    # Frontend assets,
    'assets': {
        'web.assets_backend': [
            'pos_two_currencies/static/src/web/**/*',
        ],
        'point_of_sale._assets_pos': [
            'pos_two_currencies/static/src/app/**/*',
            'pos_two_currencies/static/src/overrides/**/*',
            ('after', 'point_of_sale/static/src/scss/pos.scss', 'pos_two_currencies/static/src/scss/pos.scss'),
        ],
    },
}

