from odoo import http, Command
from odoo.http import request
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    valid_response, invalid_response, valid_response_http, invalid_response_http, get_selection_string_value

import json


class PaymentAPI(http.Controller):
    
    @validate_jwt
    @http.route([
        '/api/get_payments', 
        '/api/get_payments/<int:payment_id>'], type="http", auth="none", methods=["get"], csrf=False
    )
    def get_payments(self, uid, payment_id=None, **payload):
        try:
            domain = [('create_uid', '=', uid)]

            if payment_id:
                domain += [('id', '=', payment_id)]
            elif payload.get('keyword'):
                domain += [('name', 'ilike', payload['keyword'])]

            # Add datetime filter
            date_from = payload.get('date_from')
            date_to = payload.get('date_to')
            if date_from:
                domain += [('create_date', '>=', date_from)]
            if date_to:
                domain += [('create_date', '<=', date_to)]

            payments = get_table_model('account.payment').search(domain, limit=120, order="create_date desc")

            # For multiple payments.
            response = [{
                'id': payment.id,
                'name': payment.name,
                'name_en': payment.partner_id.khmer_name or payment.partner_id.name,
                'name_km': payment.partner_id.name,
                'dms_code': "",
                'payment_date': payment.date and payment.date.strftime('%Y-%m-%d') or "",
                'amount': payment.amount,
                'state': get_selection_string_value(payment, 'state'),
                
            } for payment in payments]

            # For optimization purpose, we include the details only when viewing specific payment.
            if payment_id and len(payments) == 1:
                response = [{
                    **response[0],
                    'body': self._get_payment_detail(payments)
                }]

            return valid_response_http(data=response, status=200)
        
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    def _get_payment_detail(self, payment):
        return [
            {
                "key": "partner_id",
                "label": "Customer",
                "value": payment.partner_id.name,
                "is_highlight": True
            },
            {
                "key": "dms_code",
                "label": "DMS code",
                "value": "",
                "is_highlight": False
            },
            {
                "key": "address",
                "label": "Address",
                "value": " ".join(payment.partner_id._display_address(without_company=True).split()),    # remove white-space
                "is_highlight": False
            },
            {
                "key": "phone",
                "label": "Phone",
                "value": payment.partner_id.phone or "",
                "is_highlight": False
            },
            {
                "key": "payment_date",
                "label": "Payment Date",
                "value": payment.date and payment.date.strftime('%d-%m-%Y') or "",
                "is_highlight": False
            },
            {
                "key": "journal_type",
                "label": "Journal Type",
                "value": get_selection_string_value(payment.journal_id, 'type'),
                "is_highlight": False
            },
            {
                "key": "payment_method",
                "label": "Payment Method",
                "value": payment.payment_method_line_id.name or "",
                "is_highlight": False
            },
            {
                "key": "amount",
                "label": "Amount",
                "value": payment.amount,
                "is_highlight": False
            },
            {
                "key": "memo",
                "label": "Memo",
                "value": payment.memo or "",
                "is_highlight": False
            },
        ]
