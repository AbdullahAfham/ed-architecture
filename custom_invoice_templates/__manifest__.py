{
    'name': 'Custom Invoice Template',
    'version': '1.0',
    'sequence': 7,
    'summary': 'Official Invoice Templates',
    'description': '''
    Official Invoice Templates
    ''',

    ############################ERP#####################################
    # Author
    'author': 'ERP CAMBODIA',
    'website': 'https://www.erpcambodia.biz/',
    'maintainer': 'ERP CAMBODIA',

    # Categories can be used to filter modules in modules listing
    # for the full list
    'category': 'ERP CAMBODIA/ERP CAMBODIA',

    # Technical
    'support': 'info@erpcambodia.biz',
    ############################ERP#####################################

    'depends': [
        'web',
        'account',
        'report_layout_template',
    ],
    'data': [
        'reports/commercial_invoice_template.xml',
        'reports/tax_invoice_template.xml',
        'reports/state_charge_invoice_template.xml',
        'reports/normal_invoice_template.xml',
        'reports/normal_invoice_signed_template.xml',
        'reports/journal_entry_template.xml',
        'reports/sale_voucher_template.xml',
        'reports/purchase_voucher_template.xml',
        'reports/official_receipt_template.xml',
        'reports/service_quotation_template.xml',
        'reports/term_and_condition_template.xml',
        'reports/account_report.xml',
        'reports/purchase_order_template.xml',
        'reports/register_form_template.xml',
        'views/account_move_view.xml',
        'views/account_payment_view.xml',
        

    ],
    'qweb':[
        # 'views/res_company_view.xml'
    ],
    'images': [],
    'license': 'LGPL-3',
    'price': 240.0,
    'currency': 'USD',
    'installable': True,
    'auto_install': False,
}
