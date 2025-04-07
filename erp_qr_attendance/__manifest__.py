# -*- coding: utf-8 -*-
{
    'name': "QR SCAN",

    'summary': """
        ERP QR SCAN
        """,

    'description': """
        ERP QR SCAN
    """,

    # Author
    'author': 'ERP CAMBODIA',
    'website': 'https://www.erpcambodia.biz/',
    'maintainer': 'ERP CAMBODIA',

    # Categories can be used to filter modules in modules listing
    # for the full list
    'category': 'ERP CAMBODIA/ERP CAMBODIA',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'mail',
        'project',
        'hr_overtime',
        'hr_attendance',
        'hr_internal_api',
    ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/resource_calendar_views.xml',
        'views/erp_qr_generate_views.xml',
        'views/scan_qr_attendance_views.xml',
        'views/scan_qr_overtime_views.xml',
        'views/hr_attendance_views.xml',
        'views/res_config_settings_views.xml',
        'views/hr_leave_view.xml',
        'reports/qr_code_reports.xml',
        'reports/report_qr_generate_template.xml',
        'wizards/update_attendance_wizard.xml',
        'wizards/create_attendance_wizard.xml',
        'wizards/create_absent_attendance_wizard.xml',
        'data/ir_cron_data.xml',
        'data/data.xml',
    ],

    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}