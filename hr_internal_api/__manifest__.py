{
    'name': 'HR Internal REST API',
    'version': '18.0.1.0',
    'category': 'ERP CAMBODIA/ERP CAMBODIA',
    'sequence': 6,
    'summary': 'HR Internal REST API',
    'license': 'LGPL-3',
    'description': """

    Internal REST API

    """,
    'depends': ['base', 'mail', 'hr', 'erp_mobile_users'],

    'external_dependencies': {
        'python': ['firebase_admin', 'geopy']
    },

    'data': [
        'data/data.xml',
        'data/mobile_modules_data.xml',
        'security/ir.model.access.csv',
        'views/partner_visit_history.xml',
        'views/res_partner_views.xml',
        'views/res_users_views.xml',
        'views/product_pricelist_views.xml',
        # 'views/hr_employee_views.xml',
        # 'views/hr_payslip_run_form_inherit.xml',
        # 'views/project_form_inherit.xml',
    ],
    # Odoo Store Specific
    'live_test_url': 'https://www.erpcambodia.biz/',
    'images': [
        'static/description/main_screenshot.png',
    ],

    # Author
    'author': 'ERP CAMBODIA, NUN SOPHANON',
    'website': 'https://www.erpcambodia.biz/',
    'maintainer': 'ERP CAMBODIA',

    # Technical
    'installable': True,
    'auto_install': False,
    'support': 'info@erpcambodia.biz',
}