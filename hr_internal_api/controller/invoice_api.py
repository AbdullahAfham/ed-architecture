from odoo import http, Command
from odoo.http import request
from odoo.tools import html2plaintext
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    valid_response, invalid_response, valid_response_http, invalid_response_http, _get_selection_string_value

import json


class InvoiceAPI(http.Controller):
    
    @validate_jwt
    @http.route([
        '/api/get_invoices', 
        '/api/get_invoices/<int:invoice_id>'], type="http", auth="none", methods=["get"], csrf=False
    )
    def get_invoices(self, uid, invoice_id=None, **payload):
        try:
            domain = [
                ('move_type', '=', 'out_invoice'),  # Customer Invoice
                ('create_uid', '=', uid),
            ]

            if invoice_id:
                domain += [('id', '=', invoice_id)]
            elif payload.get('keyword'):
                domain += [('name', 'ilike', payload['keyword'])]
            
            # Add datetime filter
            date_from = payload.get('date_from')
            date_to = payload.get('date_to')
            if date_from:
                domain += [('create_date', '>=', date_from)]
            if date_to:
                domain += [('create_date', '<=', date_to)]

            invoices = get_table_model('account.move').search(domain, limit=120, order="create_date desc")

            # For multiple invoices.
            response = [{
                'id': invoice.id,
                'name': invoice.name,
                'name_en': invoice.partner_id.khmer_name or invoice.partner_id.name,
                'name_km': invoice.partner_id.name,
                'dms_code': invoice.partner_id.dms_code or "",
                'invoice_date': invoice.invoice_date and invoice.invoice_date.strftime('%Y-%m-%d') or "",
                'amount_total': invoice.amount_total,
                'state': _get_selection_string_value(invoice, 'status_in_payment'),
            } for invoice in invoices]

            # For optimization purpose, we include the details only when viewing specific invoice.
            if invoice_id and len(invoices) == 1:
                response = [{
                    **response[0],
                    **self._get_invoice_detail(invoices)
                }]

            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @staticmethod
    def _get_invoice_detail(invoice):
        return {
            'body': [
                {
                    "key": "partner_id",
                    "label": "Customer",
                    "value": invoice.partner_id.name,
                    "is_highlight": True
                },
                {
                    "key": "dms_code",
                    "label": "DMS code",
                    "value": invoice.partner_id.dms_code or "",
                    "is_highlight": False
                },
                {
                    "key": "address",
                    "label": "Address",
                    "value": " ".join(invoice.partner_id._display_address(without_company=True).split()),    # remove white-space
                    "is_highlight": False
                },
                {
                    "key": "phone",
                    "label": "Phone",
                    "value": invoice.partner_id.phone or "",
                    "is_highlight": False
                },
                {
                    "key": "invoice_date",
                    "label": "Invoice Date",
                    "value": invoice.invoice_date and invoice.invoice_date.strftime('%d-%m-%Y') or "",
                    "is_highlight": False
                },
                {
                    "key": "due_date",
                    "label": "Due Date",
                    "value": invoice.invoice_date_due and invoice.invoice_date_due.strftime('%d-%m-%Y') or "",
                    "is_highlight": False
                },
                {
                    "key": "journal_type",
                    "label": "Journal Type",
                    "value": _get_selection_string_value(invoice.journal_id, 'type'),
                    "is_highlight": False
                },
                {
                    "key": "payment_terms",
                    "label": "Payment Terms",
                    "value": invoice.invoice_payment_term_id.name or "",
                    "is_highlight": False
                },
                {
                    "key": "payment_ref",
                    "label": "Payment Ref",
                    "value": invoice.matched_payment_ids and max(invoice.matched_payment_ids, key=lambda payment: payment.date).name or "",     # get the last payment
                    "is_highlight": False
                },
                {
                    "key": "terms_conditions",
                    "label": "Terms & Conditions",
                    "value": html2plaintext(invoice.narration or ""),
                    "is_highlight": False
                },
            ],
            'invoice_line': {
                'products': [{
                    'id': line.product_id.id, 
                    'image_url': f'/web/image/product.product/{line.product_id.id}/image_1024', 
                    'name': line.product_id.name, 
                    'quantity': line.quantity, 
                    'uom': line.product_uom_id.name,
                    'unit_price': line.price_unit,
                    'subtotal': line.price_subtotal} for line in invoice.invoice_line_ids
                ],
                'subtotal': invoice.amount_untaxed,
                'tax': invoice.amount_tax,
                'total': invoice.amount_total
            },
            'payments': [{
                'id': payment.id,
                'name': f"Paid on {payment.date.strftime('%d %B %Y')} by {_get_selection_string_value(payment.journal_id, 'type')}",
                'date': payment.date and payment.date.strftime('%d-%m-%Y') or "",
                'amount': payment.amount,
            } for payment in invoice.matched_payment_ids
            ],
        }

    @validate_jwt
    @http.route('/api/get_invoices_by_sale_id/<int:sale_id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_invoices_by_sale_id(self, uid, sale_id, **payload):
        try:
            sale_order = get_table_model('sale.order').search([('id', '=', sale_id)], limit=1)

            if not sale_order.exists():
                return invalid_response_http("Not Found", "Sale not found.", status=404)

            # For multiple invoices.
            response = [{
                'id': invoice.id,
                'name': invoice.name,
                'name_en': invoice.partner_id.khmer_name or invoice.partner_id.name,
                'name_km': invoice.partner_id.name,
                'dms_code': invoice.partner_id.dms_code or "",
                'invoice_date': invoice.invoice_date and invoice.invoice_date.strftime('%Y-%m-%d') or "",
                'amount_total': invoice.amount_total,
                'state': _get_selection_string_value(invoice, 'status_in_payment'),
            } for invoice in sale_order.invoice_ids]

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
