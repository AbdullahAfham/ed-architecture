# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Point of Sale Khmer Restaurant',
    'version': '1.0',
    'category': 'Hidden',
    'summary': 'Link module between pos_two_currencies and pos_restaurant',
    'description': """
This module adapts the behavior of the PoS when the pos_two_currencies and pos_restaurant are installed.
""",
    'depends': ['pos_two_currencies', 'pos_restaurant'],
    'auto_install': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_two_currencies_restaurant/static/src/**/*',
        ],
    },
    'license': 'LGPL-3',
}
