from odoo import http, Command
from odoo.http import request, content_disposition
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    valid_response, invalid_response, valid_response_http, invalid_response_http,\
    get_selection_string_value, combine_date_with_current_time

import json


class StockRequestAPI(http.Controller):

    @validate_jwt
    @http.route([
        '/api/get_stock_request', 
        '/api/get_stock_request/<int:picking_id>'], type="http", auth="none", methods=["get"], csrf=False
    )
    def get_stock_request(self, uid, picking_id=None, **payload):
        try:
            current_user = get_table_model('res.users').search([('id', '=', uid)], limit=1)

            if not current_user:
                return invalid_response_http("Not Found", 'User not found.', status=404)

            if not current_user.employee_ids:
                return invalid_response_http("Bad Request", 'User has no related employees.', status=400)

            # make sure current_user must be included
            payload.update({'current_user': current_user})

            if not picking_id:
                domain = self._get_stock_request_domain_filters(**payload)
            else:
                domain = [('id', '=', picking_id)]    # view picking detail

            pickings = get_table_model('stock.picking').search(domain, order="create_date desc")

            # For multiple pickings.
            response = [{
                "picking_id": picking.id,
                "name": picking.name,
                "partner_id": picking.partner_id.id,
                "name_en": picking.partner_id.khmer_name or picking.partner_id.name,
                "name_km": picking.partner_id.name,
                "request_date": picking.scheduled_date and picking.scheduled_date.strftime('%d-%m-%Y') or "",
                "warehouse_location": self._get_warehouse_location_name(picking) or "",
                "state": get_selection_string_value(picking, 'state') or "",
                "state_key": picking.state or "",
                "next_transfer_id": self._get_next_transfer_data(picking)["id"] or "",
                "next_transfer_name": self._get_next_transfer_data(picking)["name"] or "",
                "next_transfer_state": self._get_next_transfer_data(picking)["state"] or "",
                "next_transfer_state_key": self._get_next_transfer_data(picking)["state_key"] or "",
            } for picking in pickings]

            # For optimization purpose, we include the details only when viewing specific picking.
            if picking_id and len(pickings) == 1:
                response = [{
                    **response[0],
                    **self._get_stock_request_detail(pickings)
                }]

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    def _get_next_transfer_data(self, picking) -> int:
        """ There is a next transfer after validate picking of the chain moves. """
        next_transfer_data = {"id": None, "name": "", "state": "", "state_key": ""}
        next_transfers = picking._get_next_transfers()

        next_transfer = next_transfers and next_transfers[-1]
        if next_transfer:
            next_transfer_data["id"] = next_transfer.id
            next_transfer_data["name"] = next_transfer.name
            next_transfer_data["state"] = "Received" if next_transfer.state == 'done' else "Waiting"
            next_transfer_data["state_key"] = next_transfer.state

        return next_transfer_data

    def _get_warehouse_location_name(self, picking) -> str:
        """ Returns complete name of location (including parent location) based on operation type. """
        name = ""
        if picking.picking_type_id.code == 'incoming':
            name = picking.location_dest_id.complete_name
        elif picking.picking_type_id.code == 'outgoing':
            name = picking.location_id.complete_name
        return name

    def _get_stock_request_quantity(self, move) -> float:
        """ Returns quantity based on picking state, either a demand qty or validated qty. """
        picking_state = move.picking_id.state
        if picking_state == 'done':
            return move.quantity
        else:
            return move.product_uom_qty

    def _get_stock_request_detail(self, picking) -> dict:
        """ Currently, there are only two keys which going to be returned:
        - body: a list of dictionaries
        - request_line: a dictionary
        """
        return {
            "body": [
                {
                    "key": "partner_id",
                    "label": "Requester",
                    "value": picking.partner_id.name,
                    "is_highlight": True
                },
                {
                    "key": "request_date",
                    "label": "Request Date",
                    "value": picking.scheduled_date and picking.scheduled_date.strftime('%d-%m-%Y') or "",
                    "is_highlight": False
                },
                {
                    "key": "warehouse_location",
                    "label": "WH Location",
                    "value": self._get_warehouse_location_name(picking),
                    "is_highlight": False
                },
                # {
                #     "key": "remark",
                #     "label": "Remark",
                #     "value": picking.remark or "",
                #     "is_highlight": False
                # },
                {
                    "key": "next_transfer_name",
                    "label": "Stock Receive",
                    "value": self._get_next_transfer_data(picking)["name"] or "",
                    "is_highlight": False
                },
                {
                    "key": "next_transfer_state",
                    "label": "Stock Receive Status",
                    "value": self._get_next_transfer_data(picking)["state"] or "",
                    "is_highlight": False
                },
            ],
            "request_line": {
                "products": [{
                    'id': move.product_id.id, 
                    'image_url': f'/web/image/product.product/{move.product_id.id}/image_1024', 
                    'name': move.product_id.name, 
                    'quantity': self._get_stock_request_quantity(move), 
                    'uom': move.product_uom.name,
                    'move_id': move.id } for move in picking.move_ids
                ],
            }
        }

    def _get_stock_request_domain_filters(self, **payload):
        """ Returns a search domain provided by query parameters `payload`. """

        # by `Internal Transfer` and `Created by`
        domain = [
            ('picking_type_id.code', '=', 'internal'),
            ('create_uid', '=', payload['current_user'].id)
        ]

        # by `Create Date`
        if payload.get('date_from') and payload.get('date_to'):
            domain += [('create_date', '>=', payload['date_from']), ('create_date', '<=', payload['date_to'])]

        # by `Reference` or `Customer Name`
        if payload.get('keyword'):
            domain += ['|', ('name', 'ilike', payload['keyword']), ('partner_id.name', 'ilike', payload['keyword'])]

        return domain

    @validate_jwt
    @http.route('/api/create_stock_request', type="http", auth="none", methods=["post"], csrf=False)
    def create_stock_request(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        request_date = payload.get('request_date')
        # remark = payload.get('remark')
        products = payload.get('products')

        # validation here
        current_user = get_table_model('res.users').search([('id', '=', uid)], limit=1)
        if not current_user:
            return invalid_response_http("Not Found", 'User not found.', status=404)

        if not request_date:
            return invalid_response_http("Bad Request", 'Request Date is required.', status=400)
        
        if not products:
            return invalid_response_http("Bad Request", 'Products are required.', status=400)

        try:
            picking_info, error_msg = self._get_picking_info_from_user(current_user)

            if error_msg:
                return invalid_response_http("Not Found", error_msg, status=404)

            # prepare values to be created
            values = {
                'partner_id': picking_info['partner_id'],
                'scheduled_date': combine_date_with_current_time(request_date),
                'picking_type_id': picking_info['picking_type_id'],
                'location_id': picking_info['location_id'],
                'location_dest_id': picking_info['location_dest_id'],
                # 'remark': remark,
                'move_ids': [
                    Command.create({
                        'location_id': picking_info['location_id'],
                        'product_id': move['product_id'],
                        'name': move['name'],
                        'product_uom_qty': move['product_uom_qty'], 
                    }) for move in self._get_stock_moves(products)
                ]
            }

            picking = get_table_model('stock.picking').create(values)

            response = {
                'id': picking.id, 
                'message': 'Created Successfully'
            }

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/update_stock_request', type="http", auth="none", methods=["post"], csrf=False)
    def update_stock_request(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        if not payload.get('picking_id'):
            return invalid_response_http("Bad Request", "Stock Request ID is required.", status=400)

        picking = get_table_model('stock.picking').search([('id', '=', payload['picking_id'])], limit=1)

        if not picking.exists():
            return invalid_response_http("Not Found", "Stock Request not found.", status=404)

        try:
            # expected fields, with valid values
            fields_to_update = [] #['remark']
            values_to_update = {key: payload[key] for key in fields_to_update if payload.get(key)}

            # prepare stock.move
            stock_moves = self._get_stock_moves(payload.get('products', []))

            # either adding a new one or update the existing one
            request_lines = []
            for move in stock_moves:
                if not move['id']:
                    request_lines.append(
                        Command.create({
                            'location_id': picking.location_id.id,
                            'product_id': move['product_id'],
                            'name': move['name'],
                            'product_uom_qty': move['product_uom_qty'], 
                        })
                    )
                    continue

                # in case for update the existing, we assume the user want to remove if the given quantity is zero
                if move['id'] and not move['product_uom_qty']:
                    line = Command.delete(move['id'])
                else:
                    line = Command.update(
                        move['id'],
                        {
                            'product_id': move['product_id'],
                            'product_uom_qty': move['product_uom_qty'],
                        }
                    )
                
                request_lines.append(line)

            # Prepare values to update `stock.move`
            if request_lines:
                values_to_update = {
                    **values_to_update,
                    **{'move_ids': request_lines},
                }

            # execute an update
            picking.sudo().write(values_to_update)

            response = {
                'id': picking.id, 
                'message': 'Updated Successfully'
            }
            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    def _get_stock_moves(self, product_data) -> list[dict]:
        """ Returns a list of dictionaries representing `stock.move` values.

        :param product_data: a list of dictionaries.
        """
        data_by_product_id = {product['id']: product for product in product_data}        
        product_ids = [_id for _id in data_by_product_id.keys()]

        # orm search in batch for efficiency
        products = get_table_model('product.product').search([('id', 'in', product_ids)])

        stock_moves = []
        for product in products:
            data = data_by_product_id[product.id]
            stock_moves.append({
                'name': (product.display_name or '')[:2000],
                'product_id': data.get('id'),
                'product_uom_qty': data.get('quantity'),
                'id': data.get('move_id'),
            })

        return stock_moves

    def _get_picking_info_from_user(self, current_user) -> tuple:
        """ Returns a dictionary representing `stock.picking` values with error message if there's any.
        
        :param current_user: an instance of `res.user` (logged-in user)
        :return: tuple(picking_info, error_msg)
        """
        error_msg = ""

        partner_id = current_user.partner_id
        if not partner_id:
            error_msg = "User contact not found."

        picking_type_id = current_user.default_picking_type_id
        if not picking_type_id:
            error_msg = "Default operation type not found."

        location_id = current_user.property_warehouse_id.lot_stock_id
        if not location_id:
            error_msg = "Source location not found."

        location_dest_id = current_user.default_transit_location
        if not location_dest_id:
            error_msg = "Default transit location not found."

        if error_msg:
            return {}, error_msg

        picking_info = {
            'partner_id': partner_id.id,
            'picking_type_id': picking_type_id.id, 
            'location_id': location_id.id, 
            'location_dest_id': location_dest_id.id,
        }

        return picking_info, error_msg

    @validate_jwt
    @http.route('/api/confirm_stock_request', type="http", auth="none", methods=["post"], csrf=False)
    def confirm_stock_request(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)
        
        if not payload.get('picking_id'):
            return invalid_response_http("Bad Request", 'Transfer ID is required.', status=400)

        picking = get_table_model('stock.picking').browse(payload['picking_id'])
        if not picking.exists():
            return invalid_response_http("Not Found", "Transfer not found.", status=404)

        if picking.state != 'draft' :
            return invalid_response_http("Bad Request", "Transfer is not in draft state.", status=400) 

        try:
            picking.action_confirm()

            response = {
                'id': picking.id, 
                'message': 'Requested Successfully'
            }

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/accept_stock_request', type="http", auth="none", methods=["post"], csrf=False)
    def accept_stock_request(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)
        
        if not payload.get('picking_id'):
            return invalid_response_http("Bad Request", 'Transfer ID is required.', status=400)

        picking = get_table_model('stock.picking').browse(payload['picking_id'])
        if not picking.exists():
            return invalid_response_http("Not Found", "Transfer not found.", status=404)

        if picking.state != 'assigned' :
            return invalid_response_http("Bad Request", "Transfer is not ready to receive.", status=400) 

        try:
            picking.button_validate()

            response = {
                'id': picking.id, 
                'message': 'Received Successfully'
            }

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/cancel_stock_request', type="http", auth="none", methods=["post"], csrf=False)
    def cancel_stock_request(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        if not payload.get('picking_id'):
            return invalid_response_http("Bad Request", 'Transfer ID is required.', status=400)

        picking = get_table_model('stock.picking').browse(payload['picking_id'])
        if not picking.exists():
            return invalid_response_http("Not Found", "Transfer not found.", status=404)

        invalid_state = picking.state if picking.state in ('done', 'cancel') else None
        if invalid_state == 'done':
            return invalid_response_http("Bad Request", f"You cannot cancel Stock Request that has been set to \'Done\'.", status=400) 
        elif invalid_state == 'cancel':
            return invalid_response_http("Bad Request", f"Stock Request is ready cancelled.", status=400) 

        try:
            picking.action_cancel()

            response = {
                'id': picking.id, 
                'message': 'Cancelled Successfully'
            }

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
