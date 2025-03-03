from odoo import http, Command
from odoo.http import request
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    valid_response, invalid_response, valid_response_http, invalid_response_http

from datetime import datetime, date, time, timedelta
from odoo.osv import expression
import json


class PartnerVisitHistoryAPI(http.Controller):

    def _prepare_visit_history_values(self, uid, payload):
        """ Prepare the values to create/update a `visit.history`.
        :param uid (int): current logged in user id
        :param payload (dict)
        """
        partner_id = payload.get('partner_id')
        reason = payload.get('reason')
        latitude = payload.get('latitude')
        longitude = payload.get('longitude')

        # validation here
        if not latitude or not longitude:
            return invalid_response_http('Bad Request', 'Coordinates is required.', status=400)
        
        # if not visit_datetime:
        #     return invalid_response_http('Bad Request', 'Visit Date and Time is required.', status=400)
        
        partner = get_table_model('res.partner').browse(partner_id)
        if not partner:
            return invalid_response_http('Not Found', 'Customer not found.', status=404)
        
        # handle timezone offset
        # visit_datetime_utc = datetime.strptime(visit_datetime, '%Y-%m-%d %H:%M:%S') - timedelta(hours=7)
        current_datetime = datetime.now()

        return {
            'partner_id': partner.id,
            'salesperson_id': uid,
            'date': current_datetime.date(),
            'visit_location_ids': [
                Command.create({
                    'visit_datetime': current_datetime, 
                    'latitude': latitude, 
                    'longitude': longitude,
                    'reason': reason,
                })
            ]
        }

    @validate_jwt
    @http.route('/api/check_in', type="http", auth="none", methods=["post"], csrf=False)
    def create_visit_history(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)
        
        try:
            values = self._prepare_visit_history_values(uid, payload)

            # This will create a new one, or update the existing one
            visit_history, is_updated = get_table_model('visit.history').create_or_update_visit_history(values)

            response = {
                'id': visit_history.id, 
                'message': 'Created Successfully'
            }
            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
    
    @validate_jwt
    @http.route('/api/check_out', type="http", auth="none", methods=["post"], csrf=False)
    def update_visit_history(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)
        
        try:
            values = self._prepare_visit_history_values(uid, payload)
            visit_history, is_updated = get_table_model('visit.history').create_or_update_visit_history(values)

            response = {
                'id': visit_history.id, 
                'message': 'Updated Successfully'
            }
            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
    
    @validate_jwt
    @http.route('/api/refresh_location', type="http", auth="none", methods=["get"], csrf=False)
    def refresh_location(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        latitude = payload.get('latitude')
        longitude = payload.get('longitude')

        if not latitude or not longitude:
            return invalid_response_http('Bad Request', 'Coordinates is required.', status=400)

        from_coordinate = (latitude, longitude)  # current user location
        
        try:
            from geopy.distance import geodesic
            from geopy.geocoders import Nominatim

            # geolocator = Nominatim(user_agent="odoo_find_nearest_location")
            # location = geolocator.reverse("11.534942, 104.8852981")
            # print('===Address:', location.address)

            # test dataset
            # customers = [
            #     {'name': 'SMC', 'partner_latitude': 11.534942, 'partner_longitude': 104.8852981},
            #     {'name': 'Chom Chao', 'partner_latitude': 11.5346056, 'partner_longitude': 104.8302377},
            #     {'name': 'Olympic', 'partner_latitude': 11.5565293, 'partner_longitude': 104.9088534},
            #     {'name': 'Royal Phnom Penh Hospital', 'partner_latitude': 11.5622474, 'partner_longitude': 104.8767528},
            #     {'name': 'K Mall', 'partner_latitude': 11.5316058, 'partner_longitude': 104.8678757},
            #     {'name': 'SMC', 'partner_latitude': 11.534942, 'partner_longitude': 104.8852981},
            # ]

            # A list of dictionaries
            customers = get_table_model('res.partner').search([]).read(
                ['name', 'partner_latitude', 'partner_longitude']
            )

            for customer in customers:
                to_coordinate = (customer['partner_latitude'], customer['partner_longitude'])
                distance_in_km = geodesic(from_coordinate, to_coordinate).km  # Get distance between 2 coordinates
                customer['distance'] = round(distance_in_km, 2)

            # comparing distance to get the nearest customer
            nearest_customer = min(customers, key=lambda customer: customer["distance"])

            # check whether the `nearest_customer` has visit history for today or not
            has_visit_history = get_table_model('visit.history').search([
                ('partner_id', '=', nearest_customer['id']), 
                ('date', '=', date.today())
            ], limit=1).exists()
            
            response = {
                **nearest_customer, 
                'check_type': 'in' if not has_visit_history else 'out' 
            }
            return valid_response_http(data=response, status=200)
        
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/get_orders_invoices_count', type="http", auth="none", methods=["post"], csrf=False)
    def get_orders_invoices_count(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        current_user = get_table_model('res.users').search([('id', '=', uid)])
        if not current_user:
            return invalid_response_http('Not Found', 'User not found.', status=404)

        order_date = payload.get('order_date')
        if not order_date:
            return invalid_response_http('Bad Request', 'Order Date is required.', status=400)
        
        try:
            order_date = datetime.strptime(order_date, '%Y-%m-%d')
            order_date_min = datetime.combine(order_date.date(), time.min)  # 00:00:00
            order_date_max = datetime.combine(order_date.date(), time.max)  # 23:59:59.999999

            domain = expression.AND([
                [('state', '=', 'sale')],
                [('create_date', '>=', order_date_min)],
                [('create_date', '<=', order_date_max)],
                [('company_id', 'in', current_user.company_ids.ids)],
                expression.OR([
                    [('create_uid', '=', uid)],
                    # [('employee_id', 'in', current_user.employee_ids.ids)],
                ])
            ])

            orders = get_table_model('sale.order').search(domain)
            
            response = [{
                'order_count': len(orders),
                'total_orders': sum(order.amount_total for order in orders),
                'total_invoices': sum(invoice.amount_total for invoice in orders.invoice_ids if invoice.state == 'posted'),
                'total_payments': sum(payment.amount for payment in orders.invoice_ids.matched_payment_ids if payment.state == 'paid'),
            }]
            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
