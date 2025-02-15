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
        'point_of_sale._assets_pos': [
            'pos_payway_qr/static/src/**/*',
        ],
    },

    'installable': True,
    'license': 'LGPL-3',
}
