from odoo import http, Command
from odoo.http import request, content_disposition
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    valid_response, invalid_response, valid_response_http, invalid_response_http,\
    get_selection_string_value, combine_date_with_current_time

import json


# REUSABLE FUNCTIONS

def _prepare_stock_delivery(picking) -> dict:
    return {
        "picking_id": picking.id,
        "name": picking.name,
        "partner_id": picking.partner_id.id,
        "name_en": picking.partner_id.khmer_name or picking.partner_id.name,
        "name_km": picking.partner_id.name,
        "dms_code": picking.partner_id.dms_code or "",
        "delivery_date": picking.date_done and picking.date_done.strftime('%d-%m-%Y') or "",
        "warehouse_location": _get_warehouse_location_name(picking),
        "operation_type": picking.picking_type_id.name,
        "source": picking.origin or "",
        "state": get_selection_string_value(picking, 'state'),
    }

def _get_warehouse_location_name(picking) -> str:
    """ Returns complete name of location (including parent location) based on operation type. """
    name = ""
    if picking.picking_type_id.code == 'incoming':
        name = picking.location_dest_id.complete_name
    elif picking.picking_type_id.code == 'outgoing':
        name = picking.location_id.complete_name
    return name

class StockDeliveryAPI(http.Controller):

    @validate_jwt
    @http.route([
        '/api/get_stock_delivery', 
        '/api/get_stock_delivery/<int:picking_id>'], type="http", auth="none", methods=["get"], csrf=False
    )
    def get_stock_delivery(self, uid, picking_id=None, **payload):
        try:
            current_user = get_table_model('res.users').search([('id', '=', uid)], limit=1)

            if not current_user:
                return invalid_response_http("Not Found", 'User not found.', status=404)

            if not current_user.employee_ids:
                return invalid_response_http("Bad Request", 'User has no related employees.', status=400)

            # make sure current_user must be included
            payload.update({'current_user': current_user})

            if not picking_id:
                domain = self._get_stock_delivery_domain_filters(**payload)
            else:
                domain = [('id', '=', picking_id)]    # view picking detail

            pickings = get_table_model('stock.picking').search(domain, order="create_date desc")

            # For multiple pickings.
            response = [_prepare_stock_delivery(picking) for picking in pickings]

            # For optimization purpose, we include the details only when viewing specific picking.
            if picking_id and len(pickings) == 1:
                response = [{
                    **response[0],
                    **self._get_stock_delivery_detail(pickings)
                }]

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    def _get_stock_delivery_detail(self, picking) -> dict:
        """ Currently, there are only two keys which going to be returned:
        - body: a list of dictionaries
        - stock_move: a dictionary
        """
        return {
            "body": [
                {
                    "key": "partner_id",
                    "label": "Customer",
                    "value": picking.partner_id.name,
                    "is_highlight": True
                },
                {
                    "key": "dms_code",
                    "label": "DMS code",
                    "value": picking.partner_id.dms_code or "",
                    "is_highlight": False
                },
                {
                    "key": "address",
                    "label": "Address",
                    "value": " ".join(picking.partner_id._display_address(without_company=True).split()),    # remove white-space
                    "is_highlight": False
                },
                {
                    "key": "phone",
                    "label": "Phone",
                    "value": picking.partner_id.phone or "",
                    "is_highlight": False
                },
                {
                    "key": "delivery_date",
                    "label": "Delivery Date",
                    "value": picking.date_done and picking.date_done.strftime('%d-%m-%Y') or "",
                    "is_highlight": False
                },
                {
                    "key": "warehouse_location",
                    "label": "WH Location",
                    "value": self._get_warehouse_location_name(picking),
                    "is_highlight": False
                },
                {
                    "key": "operation_type",
                    "label": "Operation Type",
                    "value": picking.picking_type_id.name or "",
                    "is_highlight": False
                },
                {
                    "key": "source",
                    "label": "Source Doc",
                    "value": picking.origin or "",
                    "is_highlight": False
                },
                # {
                #     "key": "remark",
                #     "label": "Remark",
                #     "value": picking.remark or "",
                #     "is_highlight": False
                # },
            ],
            "stock_move": {
                "products": [{
                    'id': move.product_id.id, 
                    'image_url': f'/web/image/product.product/{move.product_id.id}/image_1024', 
                    'name': move.product_id.name, 
                    'demand': move.product_uom_qty, 
                    'quantity': move.quantity, 
                    'uom': move.product_uom.name,
                    'move_id': move.id } for move in picking.move_ids
                ],
            }
        }

    def _get_stock_delivery_domain_filters(self, **payload):
        """ Returns a search domain provided by query parameters `payload`. """

        # by `Delivery` and `Created by`
        domain = [
            ('picking_type_id.code', '=', 'outgoing'),
            ('create_uid', '=', payload['current_user'].id)
        ]

        # by `Create Date`
        if payload.get('date_from') and payload.get('date_to'):
            domain += [('create_date', '>=', payload['date_from']), ('create_date', '<=', payload['date_to'])]

        # by `Reference` or `Customer Name`
        if payload.get('keyword'):
            domain += ['|', ('name', 'ilike', payload['keyword']), ('partner_id.name', 'ilike', payload['keyword'])]

        return domain
