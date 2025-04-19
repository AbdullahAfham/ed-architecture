{
    "name": "Payroll Report",
    "version": "1.0",
    "sequence": 7,
    "summary": "Report for Payroll information",
    "support": "info@erpcambodia.biz",
    "description": "",
    "depends": [
        'web',
        'account',
        'hr_contract',
        'hr_payroll',
    ],
    "data": [
        # 'wizard/print_payroll_wizard_view.xml',
        'security/ir.model.access.csv',
        # 'reports/report_payroll_info_view.xml',
        # 'reports/report_tax_calculation_template.xml',
        'reports/reports_view.xml',
        'data/paper_format.xml',
        'views/hr_employee.xml',
        'views/hr_payslip_view.xml',
        'views/hr_payslip_run_view.xml',
        # 'wizard/print_ibanking_wizard.xml',
        'wizard/hr_payroll_report_wizard.xml',
    ],
    "qweb":[
        'reports/report_payroll_info_view.xml',
    ],

    ##################################################################################
    # Author
    'author': 'ERP CAMBODIA',
    'website': 'https://www.erpcambodia.biz/',
    'maintainer': 'ERP CAMBODIA',

    # Categories can be used to filter modules in modules listing
    # for the full list
    'category': 'ERP CAMBODIA/ERP CAMBODIA',
    # Technical
    'support': 'info@erpcambodia.biz',

    ##################################################################################

    "images": [],
    "license": "LGPL-3",
    'price': 240.0,
    'currency': 'USD',
    "installable": True,
    "auto_install": False,
}
