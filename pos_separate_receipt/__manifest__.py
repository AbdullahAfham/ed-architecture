# -*- coding: utf-8 -*-
{
    'name': "POS Separate Receipt",

    'summary': """
        Multi pos and different header information on receipt
    """,

    'description': """
    """,

    'author': "ERP CAMBODIA",
    'website': "https://www.erpcambodia.biz/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Sales',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['point_of_sale', 'pos_restaurant'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/pos_config_form_view_inherit.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_separate_receipt/static/src/**/*',
        ],
    },
    'license': 'LGPL-3',
}
