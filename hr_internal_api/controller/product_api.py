from odoo import http, Command
from odoo.http import request
from odoo.osv import expression

from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    valid_response, invalid_response, valid_response_http, invalid_response_http

import base64
import logging

_logger = logging.getLogger(__name__)


# REUSABLE FUNCTIONS

def get_product_domain_for_user(user, extra_domain=None):
    domain = [
        ('sale_ok', '=', True), 
        ('type', '=', 'consu'), 
        ('is_storable', '=', True),
        '|',
        ('company_id', '=', False),
        ('company_id', 'in', user.company_ids.ids),
    ]
    if extra_domain:
        domain = expression.AND([domain, extra_domain])
    return domain

class ProductAPI(http.Controller):

    @validate_jwt
    @http.route('/api/get_products', type="http", auth="none", methods=["get"], csrf=False)
    def get_products(self, uid, **payload):
        try:
            current_user = get_table_model('res.users').search([('id', '=', uid)])
            if not current_user:
                return invalid_response_http("Not Found", 'User not found.', status=404)

            domain = get_product_domain_for_user(current_user)

            products = get_table_model('product.product').search(domain)

            response = [{
                'id': product.id,
                'name': product.name,
                'price': product.lst_price,
                'currency': {
                    'id': product.currency_id.id,
                    'name': product.currency_id.name,
                    'symbol': product.currency_id.symbol,
                },
                'on_hand': product.qty_available,
                'uom': {
                    'id': product.uom_id.id,
                    'name': product.uom_id.name,
                },
                'type': [{
                    'id': variant_value.id,
                    'name': variant_value.name
                    } for variant_value in product.product_template_variant_value_ids
                ],
                'image_url': f'/api/get_product_image/{product.id}',
                'internal_reference': product.default_code,
            } for product in products]

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @http.route('/api/get_product_image/<int:product_id>', type='http', auth='public', cors="*")
    def get_product_image(self, product_id, **kwargs):
        product = get_table_model('product.product').browse(product_id)

        if not product or not product.image_1024:
            return invalid_response_http("Not Found", 'Product image not found.', status=404)

        image_data = base64.b64decode(product.image_1024)

        return request.make_response(image_data, headers=[
            ('Content-Type', 'image/png'),
            ('Content-Length', str(len(image_data)))
        ])
