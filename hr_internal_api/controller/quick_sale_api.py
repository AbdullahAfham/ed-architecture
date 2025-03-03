from odoo import http, Command
from odoo.http import request
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    valid_response, invalid_response, valid_response_http, invalid_response_http,\
    _get_selection_string_value, _combine_date_with_current_time

import json
import logging

_logger = logging.getLogger(__name__)


class QuickSaleAPI(http.Controller):

    @validate_jwt
    @http.route('/api/create_quick_sale', type="http", auth="none", methods=["post"], csrf=False)
    def create_quick_sale(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        partner_id = payload.get('partner_id')
        date_order = payload.get('date_order')
        warehouse_id = payload.get('warehouse_id')
        date_deliver = payload.get('date_deliver')
        pricelist_id = payload.get('pricelist_id')
        payment_term_id = payload.get('payment_term_id')
        products = payload.get('products')

        # validation here
        employee = get_table_model('hr.employee').search([('user_id', '=', uid)], limit=1)
        if not employee:
            return invalid_response_http("Not Found", 'Employee not found.', status=404)
        
        if not partner_id:
            return invalid_response_http("Bad Request", 'Customer is required.', status=400)

        quick_sale_type = get_table_model('sale.order.type').search([('code', '=', 'quick')], limit=1)
        if not quick_sale_type:
            return invalid_response_http("Not Found", 'Quick Sale Type not found.', status=404)
        
        if not date_order or not date_deliver:
            return invalid_response_http("Bad Request", 'Order Date and Delivery Date are required.', status=400)
        
        default_warehouse = employee.user_id.property_warehouse_id
        if not default_warehouse:
            return invalid_response_http("Not Found", 'The default warehouse is not defined.', status=404)
        
        if warehouse_id != default_warehouse.id:
            return invalid_response_http("Bad Request", 'The default warehouse should not be modified in Quick Sale.', status=400)
        
        try:
            values = {
                'partner_id': partner_id,
                'date_order': _combine_date_with_current_time(date_order),
                'warehouse_id': default_warehouse.id,
                'commitment_date': _combine_date_with_current_time(date_deliver),
                'pricelist_id': pricelist_id,
                'employee_id': employee.id,
                'payment_term_id': payment_term_id,
                'company_id': employee.company_id.id,
                'type_id': quick_sale_type.id,
                'order_line': [
                    Command.create({
                        'product_id': product['id'],
                        'product_uom_qty': product['quantity'], 
                        'sale_type': 'sale',
                    }) for product in products
                ]
            }
            quick_sale = get_table_model('sale.order').create(values)

            # response = {
            #     'id': order.id, 
            #     'message': 'Created Successfully'
            # }
            
            response = self._prepare_quick_sales_response(quick_sale)
            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
    
    @validate_jwt
    @http.route('/api/update_quick_sale/<int:quick_sale_id>', type="http", auth="none", methods=["post"], csrf=False)
    def update_quick_sale(self, uid, quick_sale_id, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        quick_sale = get_table_model('sale.order').browse(quick_sale_id)
        if not quick_sale.exists():
            return invalid_response_http("Not Found", "Quick Sale not found.", status=404)

        date_order, date_deliver = payload.get('date_order'), payload.get('date_deliver')
        
        try:
            # expected fields
            fields_to_update = ['partner_id', 'warehouse_id', 'pricelist_id', 'payment_term_id']

            # and only fields with valid values
            values_to_update = {key: payload[key] for key in fields_to_update if payload.get(key)}

            if date_order:
                date_order = _combine_date_with_current_time(date_order)
                values_to_update.update({'date_order': date_order})
            
            if date_deliver:
                date_deliver = _combine_date_with_current_time(date_deliver)
                values_to_update.update({'commitment_date': date_deliver})

            quick_sale_type = get_table_model('sale.order.type').search([('code', '=', 'quick')], limit=1)
            if not quick_sale_type:
                return invalid_response_http("Not Found", 'Quick Sale Type not found.', status=404)  
            
            # Because of `_compute_sale_type_id` will be invoked when `partner_id` changed
            # This will ensure the `type_id` wouldn't change
            values_to_update.update({'type_id': quick_sale_type.id})

            # Either adding a new one or update the existing one
            order_lines = []
            for product in payload.get('products', []):
                if not product.get('order_line_id'):
                    line = Command.create({
                        'product_id': product['id'],
                        'product_uom_qty': product['quantity'],
                        'sale_type': 'sale',
                    })
                    order_lines.append(line)
                    continue
                
                # in case for update the existing, we assume the user want to remove if the given quantity is zero
                if product['order_line_id'] and not product['quantity']:
                    line = Command.delete(product['order_line_id'])
                else:
                    line = Command.update(
                        product['order_line_id'],
                        {
                            'product_id': product['id'],
                            'product_uom_qty': product['quantity'],
                        }
                    )
                
                order_lines.append(line)

            # Prepare values to update `sale.order.line`
            if order_lines:
                values_to_update = {
                    **values_to_update,
                    **{'order_line': order_lines},
                }

            # execute an update
            quick_sale.sudo().write(values_to_update)

            response = {
                'id': quick_sale.id, 
                'message': 'Updated Successfully'
            }
            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
    
    @validate_jwt
    @http.route('/api/cancel_quick_sale', type="http", auth="none", methods=["post"], csrf=False)
    def cancel_quick_sale(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        if not payload.get('quick_sale_id'):
            return invalid_response_http("Bad Request", 'Quick Sale ID is required.', status=400)
        
        try:
            quick_sale = get_table_model('sale.order').search([('id', '=', payload['quick_sale_id'])], limit=1)
            if not quick_sale:
                return invalid_response_http("Not Found", 'Quick Sale not found.', status=404)  
            
            if quick_sale.state == 'sale':
                return invalid_response_http("Bad Request", 'Sale has been confirmed, and cancellation is not allowed.', status=400)

            quick_sale.sudo().write({'state': 'cancel'})

            response = {
                'id': quick_sale.id, 
                'message': 'You have successfully canceled your order.'
            }
            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/quick_sale/payment', type="http", auth="none", methods=["post"], csrf=False)
    def quick_sale_payment(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        # NOTE: we may include any `context` key in `payload` if needed

        if not payload.get('quick_sale_id'):
            return invalid_response_http("Bad Request", 'Quick Sale ID is required.', status=400)

        quick_sale = get_table_model('sale.order').browse(payload['quick_sale_id'])
        if not quick_sale.exists():
            return invalid_response_http("Not Found", "Quick Sale not found.", status=404)
        
        try:
            # ----------------------------------------------
            # SALE ORDER
            # ----------------------------------------------
            if quick_sale.state == 'draft':
                quick_sale.action_confirm()

            # ----------------------------------------------
            # STOCK DELIVERY
            # ----------------------------------------------

            # `picking_ids` should be available after confirmed
            quick_sale.picking_ids.filtered(lambda picking: picking.state == 'assigned').button_validate()

            # ----------------------------------------------
            # INVOICE
            # ----------------------------------------------
            if not quick_sale.invoice_ids:
                create_invoice_wizard = get_table_model('sale.advance.payment.inv')\
                    .with_context(active_ids=quick_sale.ids)\
                    .create({
                        'advance_payment_method': 'delivered'
                    })
                create_invoice_wizard._check_amount_is_positive()
                create_invoice_wizard.create_invoices()

                # `invoice_ids` should be available now
                quick_sale.invoice_ids.filtered(lambda invoice: invoice.state == 'draft').action_post()

            # ----------------------------------------------
            # PAYMENT
            # ----------------------------------------------
            payments = payload.get('payments', [])
            if not payments:
                return valid_response_http(data={'message': 'Confirmed Successfully'}, status=200)
            
            payment_info = self._prepare_payment_info(payload)
            valid_payments = self._validate_payment_data(payments, **payment_info)

            for payment_data in valid_payments:
                # create wizard programmatically
                payment_register_wizard = get_table_model('account.payment.register')\
                    .with_context(active_model='account.move', active_ids=quick_sale.invoice_ids.ids)\
                    .create(payment_data)

                # make payment
                payment_register_wizard._create_payments()

            return valid_response_http(data={'message': 'Payment Successful'}, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
        
    def _validate_payment_data(self, payments, **payment_info) -> list[dict]:
        """ Validate and prepare data for `account.payment.register` """
        valid_payments = []
        for payment in payments:
            # get journal
            journal = get_table_model('account.journal').browse(payment['journal_id'])

            if journal.type not in ('bank', 'cash', 'credit'):
                return invalid_response_http("Bad Request", 'Invalid Journal Type.', status=400)

            # `payment_method_line_id` field in wizard is expecting record from `account.payment.method.line`
            available_payment_method_lines = journal._get_available_payment_method_lines(payment_type='inbound')
            if not available_payment_method_lines:
                return invalid_response_http("Bad Request", 'Selected payment method is not available.', status=400)
            
            # prepare valid payment data
            valid_payments.append({
                **payment_info,
                'journal_id': journal.id,
                'payment_method_line_id': available_payment_method_lines[-1].id,
                'amount': payment['amount'],
            })
        
        return valid_payments
    
    def _prepare_payment_info(self, payload: dict) -> dict:
        """ Payment info which can be used for all payments. """
        payment_info = {}

        if payload.get('payment_date'):
            payment_info.update({'payment_date': payload['payment_date']})

        if payload.get('memo'):
            payment_info.update({'communication': payload['memo']})

        return payment_info

    @validate_jwt
    @http.route([
        '/api/get_quick_sales', 
        '/api/get_quick_sales/<int:quick_sale_id>'], type="http", auth="none", methods=["get"], csrf=False
    )
    def get_quick_sales(self, uid, quick_sale_id=None, **payload):
        try:
            current_user = get_table_model('res.users').search([('id', '=', uid)])
            if not current_user:
                return invalid_response_http("Not Found", 'User not found.', status=404)
            
            # current user is `Created by` or `Employee` of sale.order, and it has a type of Quick Sale.
            domain = [
                '&', '|',
                ('create_uid', '=', uid),
                ('employee_id', 'in', current_user.employee_ids.ids),
                ('type_id.code', '=', 'quick'),
            ]

            if quick_sale_id:
                domain += [('id', '=', quick_sale_id)]
            elif payload.get('keyword'):
                domain += [('name', 'ilike', payload['keyword'])]

            # Add datetime filter
            date_from = payload.get('date_from')
            date_to = payload.get('date_to')
            if date_from:
                domain += [('create_date', '>=', date_from)]
            if date_to:
                domain += [('create_date', '<=', date_to)]

            quick_sales = get_table_model('sale.order').search(domain, limit=120, order="create_date desc")
            
            response = self._prepare_quick_sales_response(quick_sales)
            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
    
    @staticmethod
    def _prepare_quick_sales_response(quick_sales) -> list[dict]:
        """ Prepare the expected response

        :param quick_sales: sale.order recordset.
        :return: A list of dictionaries.
        """
        return [{
            "order_id": sale.id,
            "order_ref": sale.name,
            "partner_id": sale.partner_id.id,
            "name_en": sale.partner_id.khmer_name or sale.partner_id.name,
            "name_km": sale.partner_id.name,
            "dms_code": sale.partner_id.dms_code or "",
            "date_order": sale.date_order and sale.date_order.strftime('%Y-%m-%d') or "",
            "date_deliver": sale.commitment_date and sale.commitment_date.strftime('%Y-%m-%d') or "",
            "warehouse_id": sale.warehouse_id.id,
            "pricelist_id": sale.pricelist_id.id,
            "payment_term_id": sale.payment_term_id.id,
            "create_date": sale.create_date and sale.create_date.strftime('%Y-%m-%d') or "",
            "payment_state": _get_selection_string_value(sale, 'payment_state'),
            "delivery_state": _get_selection_string_value(sale.picking_ids and sale.picking_ids[-1], 'state'),
            "state": _get_selection_string_value(sale, 'state'),
            "body": [
                {
                    "key": "partner_id",
                    "label": "Customer",
                    "value": sale.partner_id.name,
                    "is_highlight": True
                },
                {
                    "key": "dms_code",
                    "label": "DMS code",
                    "value": sale.partner_id.dms_code or "",
                    "is_highlight": False
                },
                {
                    "key": "address",
                    "label": "Address",
                    "value": " ".join(sale.partner_id._display_address(without_company=True).split()),    # remove white-space
                    "is_highlight": False
                },
                {
                    "key": "phone",
                    "label": "Phone",
                    "value": sale.partner_id.phone or "",
                    "is_highlight": False
                },
                {
                    "key": "date_order",
                    "label": "Order Date",
                    "value": sale.date_order and sale.date_order.strftime('%d-%m-%Y') or "",
                    "is_highlight": False
                },
                {
                    "key": "commitment_date",
                    "label": "Delivery Date",
                    "value": sale.commitment_date and sale.commitment_date.strftime('%d-%m-%Y') or "",
                    "is_highlight": False
                },
                {
                    "key": "warehouse_id",
                    "label": "Warehouse",
                    "value": sale.warehouse_id.name or "",
                    "is_highlight": False
                },
                {
                    "key": "pricelist_id",
                    "label": "Pricelist",
                    "value": sale.pricelist_id.name or "",
                    "is_highlight": False
                },
                {
                    "key": "payment_term_id",
                    "label": "Payment Terms",
                    "value": sale.payment_term_id.name or "",
                    "is_highlight": False
                },
            ],
            "order_line": {
                "products": [{
                    'id': line.product_id.id, 
                    'image_url': f'/web/image/product.product/{line.product_id.id}/image_1024', 
                    'name': line.product_id.name, 
                    'quantity': line.product_uom_qty, 
                    'uom': line.product_uom.name,
                    'unit_price': line.price_unit,
                    'subtotal': line.price_subtotal,
                    'order_line_id': line.id } for line in sale.order_line
                ],
                "subtotal": sale.amount_untaxed,
                "tax": sale.amount_tax,
                "total": sale.amount_total
            }
        } for sale in quick_sales]

    @validate_jwt
    @http.route('/api/get_warehouses', type="http", auth="none", methods=["get"], csrf=False)
    def get_warehouses(self, uid, **payload):
        try:
            current_user = get_table_model('res.users').browse(uid)

            if not current_user:
                return invalid_response_http("Not Found", 'User not found.', status=404)
            
            # We expect the `Default Warehouse` showing before `Allowed Warehouses`
            available_warehouses = current_user.property_warehouse_id | current_user.allow_warehouse_ids
            
            response = [{
                'id': warehouse.id,
                'name': warehouse.name,
                'code': warehouse.code,
                'company': {
                    'id': warehouse.company_id.id, 
                    'name': warehouse.company_id.name
                },
            } for warehouse in available_warehouses]
            return valid_response_http(data=response, status=200)
        
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/get_pricelist', type="http", auth="none", methods=["get"], csrf=False)
    def get_pricelist(self, uid, **payload):
        try:
            domain = [('available_in_mobile', '=', True)]
            
            pricelists = get_table_model('product.pricelist').search(domain)

            response = [{
                'id': pricelist.id,
                'name': pricelist.name,
                'company': {
                    'id': pricelist.company_id.id, 
                    'name': pricelist.company_id.name
                },
            } for pricelist in pricelists]

            return valid_response_http(data=response, status=200)
        
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/get_payment_terms', type="http", auth="none", methods=["get"], csrf=False)
    def get_payment_terms(self, uid, **payload):
        try:
            domain = []
            payment_terms = get_table_model('account.payment.term').search(domain)
            
            response = [{
                'id': payment_term.id,
                'name': payment_term.name,
                'company': {
                    'id': payment_term.company_id.id, 
                    'name': payment_term.company_id.name
                },

            } for payment_term in payment_terms]
            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/get_products', type="http", auth="none", methods=["get"], csrf=False)
    def get_products(self, uid, **payload):
        try:
            current_user = get_table_model('res.users').search([('id', '=', uid)])
            if not current_user:
                return invalid_response_http("Not Found", 'User not found.', status=404)

            domain = [
                ('sale_ok', '=', True), 
                # ('active', '=', True), 
                # ('is_storable', '=', True),
                '|',
                ('company_id', '=', False),
                ('company_id', 'in', current_user.company_ids.ids),
            ]

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
                'image_url': f'/web/image/product.product/{product.id}/image_1024',
                'internal_reference': product.default_code,
            } for product in products]
            return valid_response_http(data=response, status=200)
        
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/get_payment_methods', type="http", auth="none", methods=["get"], csrf=False)
    def get_payment_methods(self, uid, **payload):
        try:
            current_user = get_table_model('res.users').browse(uid)

            if not current_user:
                return invalid_response_http("Not Found", 'User not found.', status=404)
            
            response = [{
                'id': journal.id,
                'name': journal.name,
                'code': journal.code,
                'type': _get_selection_string_value(journal, 'type'),
            } for journal in current_user.allow_journal_ids]
            return valid_response_http(data=response, status=200)
        
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
