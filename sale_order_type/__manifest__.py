
{
    "name": "Sale Order Type",
    "version": "18.0.1.0.2",
    "category": "Sales Management",
    "author": "Grupo Vermon,"
    "AvanzOSC,"
    "Tecnativa,"
    "Agile Business Group,"
    "Niboo,"
    "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/sale-workflow",
    "license": "AGPL-3",
    "depends": ["sale_stock", "account", "sale_management", "analytic"],
    "demo": ["demo/sale_order_demo.xml"],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "views/sale_order_view.xml",
        "views/sale_order_type_view.xml",
        "views/account_move_views.xml",
        "views/res_partner_view.xml",
        "data/default_type.xml",
        "reports/account_invoice_report_view.xml",
        "reports/sale_report_view.xml",
    ],
    "installable": True,
}
