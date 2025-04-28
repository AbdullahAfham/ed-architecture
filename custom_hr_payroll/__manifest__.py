{
    'name': 'Custom HR Payroll',
    'summary': """
        Add total amount in batch and fields in tree view
        """,
    'description': """
        Display in 
        - hr.payslip.run
        - hr.payslip
    """,

    # Author
    'author': 'ERP CAMBODIA',
    'website': 'https://www.erpcambodia.biz/',
    'maintainer': 'ERP CAMBODIA',

    # Categories can be used to filter modules in modules listing
    # for the full list
    'category': 'ERP CAMBODIA/ERP CAMBODIA',
    'version': '18.0.1.0.0',
    
    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'hr',
        'hr_payroll'
    ],
    'data': [
        'views/hr_payslip.xml',
        'views/hr_payslip_run.xml',
    ],
    'demo': [],
}
