from odoo import http, Command
from odoo.http import request
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    valid_response, invalid_response, valid_response_http, invalid_response_http, _get_selection_string_value

import json


class CustomerAPI(http.Controller):
    
    @validate_jwt
    @http.route([
        '/api/get_customers', 
        '/api/get_customers/<int:customer_id>'], type="http", auth="none", methods=["get"], csrf=False
    )
    def get_customers(self, uid, customer_id=None, **payload):
        try:
            current_user = get_table_model('res.users').search([('id', '=', uid)], limit=1)

            if not current_user:
                return invalid_response_http("Not Found", 'User not found.', status=404)
            
            if not current_user.employee_ids:
                return invalid_response_http("Bad Request", 'User has no related employees.', status=400)

            # Filtered by `Employee` and `Allowed Companies`
            domain = [
                # ('employee_id', 'in', current_user.employee_ids.ids),
                ('company_id', 'in', current_user.company_ids.ids),
            ]

            if customer_id:
                domain += [('id', '=', customer_id)]
            elif payload.get('keyword'):
                domain += [('name', 'ilike', payload['keyword'])]

            customers = get_table_model('res.partner').search(domain, order="create_date desc")     # limit=120
            
            # For multiple customers.
            response = [{
                'id': customer.id,
                'name_en': customer.khmer_name or customer.name,
                'name_km': customer.name,
                'dms_code': "",
                'phone': customer.phone or "",
                'address': " ".join(customer._display_address(without_company=True).split()),    # remove white-space
                'outlet_grade': int(1), # int(customer.outlet_grade),
                'image_url': f'/web/image/res.partner/{customer.id}/image_1024',
            } for customer in customers]

            # For optimization purpose, we include the details only when viewing specific customer.
            if customer_id and len(customers) == 1:
                response = [{
                    **response[0],
                    **self._get_customer_detail(customers)
                }]

            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
        
    def _get_customer_detail(self, customer):
        orders = get_table_model('sale.order').search([
            ('partner_id', '=', customer.id),
            ('state', '=', 'sale'),
        ])

        # NOTE currently, we're using `matched_payment_ids` of invoice_ids from searched orders
        # 
        # payments = get_table_model('account.payment').search([
        #     ('partner_id', '=', customer.id),
        #     ('payment_type', '=', 'inbound'),
        #     ('state', 'in', ['in_process','paid']),
        # ])

        return {
            'owner_name': "",
            'outlet_type': _get_selection_string_value(customer, 'outlet_type'),
            'channel_type': _get_selection_string_value(customer, 'channel_type'),
            'volume_classification': _get_selection_string_value(customer, 'volume_classification'),
            'customer_credit': f"{customer.credit}/{customer.credit_limit if customer.use_partner_credit_limit else customer.credit}",
            'total_orders': sum(order.amount_total for order in orders),
            'total_invoices': customer.total_invoiced,
            'total_payments': sum(payment.amount for payment in orders.invoice_ids.matched_payment_ids),    # This consist of `paid` and `in_process` payments
            'total_receivable': customer.credit,
            # 'return_empty_bottle': customer.return_empty_bottle,
            'geo_location': {
                'latitude': customer.partner_latitude, 
                'longitude': customer.partner_longitude,
            },
        }

    @validate_jwt
    @http.route('/api/update_customer/<int:customer_id>', type="http", auth="none", methods=["post"], csrf=False)
    def update_customer(self, uid, customer_id, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        customer = get_table_model('res.partner').browse(customer_id)
        if not customer.exists():
            return invalid_response_http("Not Found", "Customer not found.", status=404)
        
        try:
            # expected fields
            fields_to_update = ['name', 'street', 'street2', 'city', 'state_id', 'country_id', 'phone', 'outlet_grade']

            # and only fields with valid values
            values_to_update = {key: payload[key] for key in fields_to_update if payload.get(key, None)}

            # to evaluate correctly between `None` and `False`
            # return_empty_bottle = payload.get('return_empty_bottle', None)
            # if isinstance(return_empty_bottle, bool):
            #     values_to_update.update({'return_empty_bottle': return_empty_bottle})

            latitude, longitude = payload.get('latitude'), payload.get('longitude')
            if latitude and longitude:
                values_to_update.update({
                    'partner_latitude': latitude, 'partner_longitude': longitude,
                })
            
            # execute an update
            customer.sudo().write(values_to_update)

            response = {
                'id': customer.id, 
                'message': 'Updated Successfully'
            }
            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
