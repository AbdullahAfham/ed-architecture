{
    'name': 'POS Payway QR API',
    'version': '1.0',
    'category': 'Sales/Point of Sale',
    'sequence': 6,
    'summary': 'Allow Connection between POS and Payway QR API',
    'description': """

Allow Connection between POS and PayWay QR API

""",
    'depends': ['point_of_sale', 'pos_two_currencies'],
    'data': [
        'views/view.xml',
    ],

    # Author
    'author': "Kimteng LEY",
    'website': "https://leykimteng.pages.dev",

    'assets': {
        'point_of_sale.assets_prod': [
            'pos_payway_qr/static/src/app/**/*',
            'pos_payway_qr/static/src/overrides/pos_overrides/**/*',
        ],
        'point_of_sale.customer_display_assets': [
            'pos_payway_qr/static/src/overrides/customer_display_overrides/**/*',
        ],
    },

    'installable': True,
    'license': 'LGPL-3',
}
