from odoo import http, Command
from odoo.http import request, content_disposition
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    valid_response, invalid_response, valid_response_http, invalid_response_http,\
    get_selection_string_value, combine_date_with_current_time

from .product_api import get_product_domain_for_user


class StockOnHandAPI(http.Controller):

    @validate_jwt
    @http.route('/api/get_stock_on_hand', type="http", auth="none", methods=["get"], csrf=False)
    def get_stock_on_hand(self, uid, **payload):
        try:
            current_user = get_table_model('res.users').search([('id', '=', uid)], limit=1)
            if not current_user:
                return invalid_response_http("Not Found", 'User not found.', status=404)

            user_stock_location = current_user.property_warehouse_id.lot_stock_id
            if not user_stock_location:
                return invalid_response_http("Not Found", 'The default warehouse is not defined.', status=404)

            # filter options for mobile
            extra_domain = self._get_stock_on_hand_domain_filters(**payload)

            # get accessible products
            domain = get_product_domain_for_user(current_user, extra_domain)
            products = get_table_model('product.product').search(domain, order="create_date desc")

            # filter by user stock location
            current_stock = products.stock_quant_ids.filtered(lambda x: x.location_id == user_stock_location)

            response = [{
                "id": quant.product_id.id,
                "name": quant.product_id.name,
                "price": quant.product_id.lst_price,
                "quantity": quant.available_quantity,
            } for quant in current_stock]

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    def _get_stock_on_hand_domain_filters(self, **payload):
        """ Returns a search domain provided by query parameters `payload`. """
        domain = []

        # by `Product Name`
        if payload.get('keyword'):
            domain += [('name', 'ilike', payload['keyword'])]

        return domain
