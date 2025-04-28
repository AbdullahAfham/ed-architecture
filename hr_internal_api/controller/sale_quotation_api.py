from odoo import http, Command
from odoo.http import request, content_disposition
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    valid_response, invalid_response, valid_response_http, invalid_response_http,\
    get_selection_string_value, combine_date_with_current_time

from datetime import datetime
import json


class SaleQuotationAPI(http.Controller):

    @validate_jwt
    @http.route('/api/create_sale_quotation', type="http", auth="none", methods=["post"], csrf=False)
    def create_sale_quotation(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        partner_id = payload.get('partner_id')
        date_order = payload.get('date_order')
        date_deliver = payload.get('date_deliver')
        # type_id = payload.get('type_id')
        products = payload.get('products')

        # validation here
        employee = get_table_model('hr.employee').search([('user_id', '=', uid)], limit=1)
        if not employee:
            return invalid_response_http("Not Found", 'Employee not found.', status=404)
        
        if not partner_id:
            return invalid_response_http("Bad Request", 'Customer is required.', status=400)
        
        # normal_sale_type = get_table_model('sale.order.type').search([('code', '=', 'normal')], limit=1)
        # if not normal_sale_type:
        #     return invalid_response_http("Not Found", 'Normal Sale Type not found.', status=404)  
        
        try:
            # combine a given `date` with current `time`
            date_order = datetime.combine(
                datetime.strptime(date_order, '%Y-%m-%d'), datetime.now().time()
            )
            date_deliver = datetime.combine(
                datetime.strptime(date_deliver, '%Y-%m-%d'), datetime.now().time()
            )
            
            values = {
                'partner_id': partner_id,
                'date_order': date_order,
                'commitment_date': date_deliver,
                # 'employee_id': employee.id,
                'company_id': employee.company_id.id,
                # 'type_id': normal_sale_type.id,
                'order_line': [
                    Command.create({
                        'product_id': product['id'],
                        'product_uom_qty': product['quantity'], 
                    }) for product in products
                ]
            }
            sale_quotation = get_table_model('sale.order').create(values)

            # response = {
            #     'id': order.id, 
            #     'message': 'Created Successfully'
            # }
            
            response = self._prepare_sale_quotation_response(sale_quotation)
            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/confirm_sale_quotation', type="http", auth="none", methods=["post"], csrf=False)
    def confirm_sale_quotation(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        if not payload.get('sale_quotation_id'):
            return invalid_response_http("Bad Request", 'Sale Quotation ID is required.', status=400)

        sale_quotation = get_table_model('sale.order').search([('id', '=', payload['sale_quotation_id'])], limit=1)
        if not sale_quotation.exists():
            return invalid_response_http("Not Found", "Sale Quotation not found.", status=404)
        
        try:
            # Confirm Sale
            if sale_quotation and sale_quotation.state == 'draft':
                sale_quotation.action_confirm()

            response = {
                'id': sale_quotation.id, 
                'message': 'Confirm Successfully'
            }
            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
    
    @validate_jwt
    @http.route('/api/update_sale_quotation/<int:sale_quotation_id>', type="http", auth="none", methods=["post"], csrf=False)
    def update_sale_quotation(self, uid, sale_quotation_id, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        sale_quotation = get_table_model('sale.order').browse(sale_quotation_id)
        if not sale_quotation.exists():
            return invalid_response_http("Not Found", "Sale Quotation not found.", status=404)

        date_order, date_deliver = payload.get('date_order'), payload.get('date_deliver')
        
        try:
            # expected fields
            fields_to_update = ['partner_id', 'warehouse_id', 'pricelist_id', 'payment_term_id']

            # and only fields with valid values
            values_to_update = {key: payload[key] for key in fields_to_update if payload.get(key)}

            if date_order:
                date_order = combine_date_with_current_time(date_order)
                values_to_update.update({'date_order': date_order})
            
            if date_deliver:
                date_deliver = combine_date_with_current_time(date_deliver)
                values_to_update.update({'commitment_date': date_deliver})

            # normal_sale_type = get_table_model('sale.order.type').search([('code', '=', 'normal')], limit=1)
            # if not normal_sale_type:
            #     return invalid_response_http("Not Found", 'Normal Sale Type not found.', status=404)  
            
            # Because of `_compute_sale_type_id` will be invoked when `partner_id` changed
            # This will ensure the `type_id` wouldn't change
            # values_to_update.update({'type_id': normal_sale_type.id})

            # Either adding a new one or update the existing one
            order_lines = []
            for product in payload.get('products', []):
                if not product.get('order_line_id'):
                    line = Command.create({
                        'product_id': product['id'],
                        'product_uom_qty': product['quantity'],
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
            sale_quotation.sudo().write(values_to_update)

            response = {
                'id': sale_quotation.id, 
                'message': 'Updated Successfully'
            }
            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/cancel_sale_quotation', type="http", auth="none", methods=["post"], csrf=False)
    def cancel_sale_quotation(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        if not payload.get('sale_quotation_id'):
            return invalid_response_http("Bad Request", 'Sale Quotation ID is required.', status=400)
        
        try:
            sale_quotation = get_table_model('sale.order').search([('id', '=', payload['sale_quotation_id'])], limit=1)
            if not sale_quotation:
                return invalid_response_http("Not Found", 'Sale Quotation not found.', status=404)  
            
            if sale_quotation.state == 'sale':
                return invalid_response_http("Bad Request", 'Sale has been confirmed, and cancellation is not allowed.', status=400)

            sale_quotation.sudo().write({'state': 'cancel'})

            response = {
                'id': sale_quotation.id, 
                'message': 'You have successfully canceled your order.'
            }
            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route([
        '/api/get_sale_quotation', 
        '/api/get_sale_quotation/<int:sale_quotation_id>'], type="http", auth="none", methods=["get"], csrf=False
    )
    def get_sale_quotation(self, uid, sale_quotation_id=None, **payload):
        try:
            current_user = get_table_model('res.users').search([('id', '=', uid)])
            if not current_user:
                return invalid_response_http("Not Found", 'User not found.', status=404)

            # current user is `Created by` or `Employee` of sale.order, and it has a type of Normal Order.
            domain = [
                # '&', '|',
                ('create_uid', '=', uid),
                # ('employee_id', 'in', current_user.employee_ids.ids),
                # ('type_id.code', '=', 'normal'),
            ]

            if sale_quotation_id:
                domain += [('id', '=', sale_quotation_id)]
            elif payload.get('keyword'):
                domain += [('name', 'ilike', payload['keyword'])]

            # Add datetime filter
            date_from = payload.get('date_from')
            date_to = payload.get('date_to')
            if date_from:
                domain += [('create_date', '>=', date_from)]
            if date_to:
                domain += [('create_date', '<=', date_to)]

            sale_quotations = get_table_model('sale.order').search(domain, limit=120, order="create_date desc")
            
            response = self._prepare_sale_quotation_response(sale_quotations)
            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
   
    def _prepare_sale_quotation_response(self, sale_quotations) -> list[dict]:
        """ Prepare the expected response

        :param sale_quotations: sale.order recordset.
        :return: A list of dictionaries.
        """
        return [{
            "order_id": sale.id,
            "order_ref": sale.name,
            "partner_id": sale.partner_id.id,
            "name_en": sale.partner_id.khmer_name or sale.partner_id.name,
            "name_km": sale.partner_id.name,
            "dms_code": "",
            "date_order": sale.date_order and sale.date_order.strftime('%Y-%m-%d') or "",
            "date_deliver": sale.commitment_date and sale.commitment_date.strftime('%Y-%m-%d') or "",
            "warehouse_id": sale.warehouse_id.id,
            "pricelist_id": sale.pricelist_id.id,
            "payment_term_id": sale.payment_term_id.id,
            "create_date": sale.create_date and sale.create_date.strftime('%Y-%m-%d') or "",
            "payment_state": get_selection_string_value(sale, 'payment_state'),
            "delivery_state": get_selection_string_value(sale.picking_ids and sale.picking_ids[-1], 'state'),
            "state": get_selection_string_value(sale, 'state'),
            "currency": {
                'id': sale.currency_id.id,
                'name': sale.currency_id.name,
                'rate': sale.currency_id.rate,
                'symbol': sale.currency_id.symbol,
            },
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
                    "value": "",
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
                    'unit_price': sale.currency_id.format(line.price_unit),
                    'subtotal': sale.currency_id.format(line.price_subtotal),
                    'order_line_id': line.id } for line in sale.order_line
                ],
                "subtotal": sale.currency_id.format(sale.amount_untaxed),
                "tax": sale.currency_id.format(sale.amount_tax),
                "exchange_rate": sale.currency_id.format(sale.exchange_rate),
                "total": sale.amount_total,
                "display_total": sale.currency_id.format(sale.amount_total),
                "display_secondary_total": self._get_secondary_total(sale) or "",
            }
        } for sale in sale_quotations]

    def _get_secondary_total(self, sale) -> str:
        main_currency = sale.currency_id.name
        if main_currency == 'USD':
            return sale.khr_currency_id.format(sale.amount_total_khr)
        elif main_currency == 'KHR':
            return sale.usd_currency_id.format(sale.amount_total_usd)

    @validate_jwt
    @http.route('/api/sale_pdf_report/<int:order_id>', type="http", auth="none", methods=["get"], csrf=False)
    def download_sale_quotation_pdf(self, order_id):
        try:
            sale_order = get_table_model('sale.order').browse(order_id)
            if not sale_order.exists():
                return invalid_response_http("Not Found", "Sale Quotation not found.", status=404)
            pdf_content = request.env['ir.actions.report'].sudo()._render_qweb_pdf('sale.action_report_saleorder', [order_id])[0]
            pdf_http_headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', len(pdf_content)),
                ('Content-Disposition', content_disposition(f'SaleQuotation_{sale_order.name}.pdf'))
            ]
            return request.make_response(pdf_content, headers=pdf_http_headers)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
