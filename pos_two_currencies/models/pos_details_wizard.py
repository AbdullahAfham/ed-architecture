# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from datetime import datetime, timedelta
from odoo.osv.expression import AND
import pytz

from odoo.exceptions import UserError
from odoo.tools import SQL


class PosDetails(models.TransientModel):
    _inherit = 'pos.details.wizard'

    report_type = fields.Selection(selection=[
        ('product', 'Product'),
        ('category', 'POS Category'),
        ('product_category', 'Product Category'),
        ('all', 'All'),
    ], required=True, default='product', string='Report Type')

    def generate_report(self):
        """ Override """
        data = {'date_start': self.start_date, 'date_stop': self.end_date, 'config_ids': self.pos_config_ids.ids}

        # update new key-value pair
        data['report_type'] = self.report_type
        return self.env.ref('point_of_sale.sale_details_report').report_action([], data=data)


class ReportSaleDetails(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'

    @api.model
    def _get_report_values(self, docids, data=None):
        """ Override

            - get `report_type` value from wizard, and pass to `get_sale_details` method
        """
        data = dict(data or {})
        # initialize data keys with their value if provided, else None
        data.update({
            # If no data is provided it means that the report is called from the PoS, and docids represent the session_id
            'session_ids': data.get('session_ids') or (
                docids if not data.get('config_ids') and not data.get('date_start') and not data.get(
                    'date_stop') else None),
            'config_ids': data.get('config_ids'),
            'date_start': data.get('date_start'),
            'date_stop': data.get('date_stop'),
            'report_type': data.get('report_type'),
        })
        configs = self.env['pos.config'].browse(data['config_ids'])
        data.update(self.get_sale_details(data['date_start'], data['date_stop'], configs.ids, data['session_ids'],
                                          data['report_type']))
        return data

    @api.model
    def get_sale_details(self, date_start=False, date_stop=False, config_ids=False, session_ids=False,
                         report_type='product'):
        """ Serialise the orders of the requested time period, configs and sessions.
        :param date_start: The dateTime to start, default today 00:00:00.
        :type date_start: str.
        :param date_stop: The dateTime to stop, default date_start + 23:59:59.
        :type date_stop: str.
        :param config_ids: Pos Config id's to include.
        :type config_ids: list of numbers.
        :param session_ids: Pos Config id's to include.
        :type session_ids: list of numbers.
        :param report_type: Type of report ('product', 'category', 'product_category', 'all')
        :type report_type: str.
        :returns: dict -- Serialised sales.
        """
        # Special handling for 'all' report type
        if report_type == 'all':
            # Get data for 'category' (POS category)
            pos_data = self.get_sale_details(date_start, date_stop, config_ids, session_ids, 'category')
            # Get data for 'product_category'
            product_data = self.get_sale_details(date_start, date_stop, config_ids, session_ids, 'product_category')

            # Keep both category types separate
            pos_categories = pos_data.get('category_ids', [])
            product_categories = product_data.get('category_ids', [])

            # Update the data structure
            pos_data.update({
                'pos_category_ids': pos_categories,  # Store POS categories here
                'product_category_ids': product_categories,  # Store product categories here
                'report_type': 'all'
            })
            return pos_data

        if (not session_ids):
            date_start, date_stop = self._get_date_start_and_date_stop(date_start, date_stop)

        domain = self._get_domain(date_start, date_stop, config_ids, session_ids)
        orders = self.env['pos.order'].search(domain)

        if config_ids:
            config_currencies = self.env['pos.config'].search([('id', 'in', config_ids)]).mapped('currency_id')
        else:
            config_currencies = self.env['pos.session'].search([('id', 'in', session_ids)]).mapped(
                'config_id.currency_id')
        # If all the pos.config have the same currency, we can use it, else we use the company currency
        if config_currencies and all(i == config_currencies.ids[0] for i in config_currencies.ids):
            user_currency = config_currencies[0]
        else:
            user_currency = self.env.company.currency_id

        total = 0.0
        products_sold = {}
        taxes = {}
        refund_done = {}
        refund_taxes = {}
        for order in orders:
            if user_currency != order.pricelist_id.currency_id:
                total += order.pricelist_id.currency_id._convert(
                    order.amount_total, user_currency, order.company_id, order.date_order or fields.Date.today())
            else:
                total += order.amount_total
            currency = order.session_id.currency_id

            for line in order.lines:
                if line.qty >= 0:
                    products_sold, taxes = self._get_products_and_taxes_dict(line, products_sold, taxes, currency,
                                                                             report_type)
                else:
                    refund_done, refund_taxes = self._get_products_and_taxes_dict(line, refund_done, refund_taxes,
                                                                                  currency, report_type)

        taxes_info = self._get_taxes_info(taxes)
        refund_taxes_info = self._get_taxes_info(refund_taxes)

        # Updated payment processing
        payment_data = {}
        payment_data2 = {}
        payment_ids = self.env["pos.payment"].search([('pos_order_id', 'in', orders.ids)])

        for payment_id in payment_ids:
            payment_method_name = payment_id.payment_method_id.name
            customer_name = payment_id.partner_id.name

            # set groupby `key`
            key = (payment_method_name, customer_name)
            key2 = (payment_method_name,)

            if key in payment_data:
                payment_data[key]['total'] += payment_id.amount
                payment_data[key]['khr'] += payment_id.khr
            else:
                payment_data.update({
                    key: {
                        'name': payment_id.payment_method_id.name,
                        'total': payment_id.amount,
                        'khr': payment_id.khr,
                        'customer_name': payment_id.partner_id.name,
                        'is_customer_account': payment_id.payment_method_id.split_transactions,
                    }
                })

            if key2 in payment_data2:
                payment_data2[key2]['total'] += payment_id.amount
                payment_data2[key2]['khr'] += payment_id.khr
            else:
                payment_data2.update({
                    key2: {
                        'name': payment_id.payment_method_id.name,
                        'total': payment_id.amount,
                        'khr': payment_id.khr,
                        'customer_name': payment_id.partner_id.name,
                        'is_customer_account': payment_id.payment_method_id.split_transactions,
                    }
                })

        if payment_data and payment_data2:
            payments = list(payment_data.values())
            payments_by_payment_method = list(payment_data2.values())
        else:
            payments = []
            payments_by_payment_method = []

        configs = []
        sessions = []
        if config_ids:
            configs = self.env['pos.config'].search([('id', 'in', config_ids)])
            if session_ids:
                sessions = self.env['pos.session'].search([('id', 'in', session_ids)])
            else:
                sessions = self.env['pos.session'].search(
                    [('config_id', 'in', configs.ids), ('start_at', '>=', date_start), ('stop_at', '<=', date_stop)])
        else:
            sessions = self.env['pos.session'].search([('id', 'in', session_ids)])
            for session in sessions:
                configs.append(session.config_id)

        # Prepare products data
        products = []
        refund_products = []
        for category_name, product_list in products_sold.items():
            category_dictionnary = {
                'name': category_name,
                'products': sorted([{
                    'product_id': product.id,
                    'product_name': product.name,
                    'code': product.default_code,
                    'quantity': qty,
                    'price_unit': price_unit,
                    'discount': discount,
                    'uom': product.uom_id.name,
                    'total_paid': product_total,
                    'base_amount': base_amount,
                } for (product, price_unit, discount), (qty, product_total, base_amount) in product_list.items()],
                    key=lambda l: l['product_name']),
            }
            products.append(category_dictionnary)
        products = sorted(products, key=lambda l: str(l['name']))

        for category_name, product_list in refund_done.items():
            category_dictionnary = {
                'name': category_name,
                'products': sorted([{
                    'product_id': product.id,
                    'product_name': product.name,
                    'code': product.default_code,
                    'quantity': qty,
                    'price_unit': price_unit,
                    'discount': discount,
                    'uom': product.uom_id.name,
                    'total_paid': product_total,
                    'base_amount': base_amount,
                } for (product, price_unit, discount), (qty, product_total, base_amount) in product_list.items()],
                    key=lambda l: l['product_name']),
            }
            refund_products.append(category_dictionnary)
        refund_products = sorted(refund_products, key=lambda l: str(l['name']))

        # Calculate totals
        products, products_info = self._get_total_and_qty_per_category(products)
        refund_products, refund_info = self._get_total_and_qty_per_category(refund_products)

        # Process products according to requirements
        # The `products` key in `data` is a list of objects represent:
        # - category name
        # - list of products object
        # - total amount
        # - total quantity
        final_products = []
        category_ids = []

        if products:
            for categ in products:
                # 1). get list of products belong to a category
                final_products.extend(categ["products"])

                # get total of discount and tax correspond to a category
                discount = sum(product["price_unit"] * product["quantity"] * product["discount"] / 100 for product in
                               categ["products"])
                tax = sum(product["price_unit"] * product["quantity"] - product["base_amount"] for product in
                          categ["products"])
                total = categ["total"]
                categ_name = categ["name"]
                qty = categ["qty"]
                price = total + discount

                if categ_name == "Discount":
                    discount = total * -1
                    price = 0
                    total = 0

                # 2). get list of categories
                # As we have overridden `_get_total_and_qty_per_category`
                # now categ["total"] is the tax included amount with discount subtraction.
                category_ids.append({
                    'name': categ_name,
                    'quantity': qty,
                    'price': price,
                    'discount': discount,
                    'total': total,
                })

        currency = {
            'symbol': user_currency.symbol,
            'position': True if user_currency.position == 'after' else False,
            'total_paid': user_currency.round(total),
            'precision': user_currency.decimal_places,
        }

        session_name = False
        if len(sessions) == 1:
            state = sessions[0].state
            date_start = sessions[0].start_at
            date_stop = sessions[0].stop_at
            session_name = sessions[0].name
        else:
            state = "multiple"

        config_names = []
        module_pos_restaurant = False
        for config in configs:
            if not module_pos_restaurant:
                module_pos_restaurant = config.module_pos_restaurant
            config_names.append(config.name)

        discount_number = len(orders.filtered(lambda o: o.lines.filtered(lambda l: l.discount > 0)))
        discount_amount = sum(l._get_discount_amount() for l in orders.lines.filtered(lambda l: l.discount > 0))

        invoiceList = []
        invoiceTotal = 0
        totalPaymentsAmount = 0

        for session in sessions:
            invoiceList.append({
                'name': session.name,
                'invoices': session._get_invoice_total_list(),
            })
            invoiceTotal += session._get_total_invoice()
            totalPaymentsAmount += session.total_payments_amount

        currency_khr = self.env['res.currency'].search([('name', '=', "KHR")], limit=1)
        currency_usd = self.env['res.currency'].search([('name', '=', "USD")], limit=1)

        return {
            'opening_note': sessions[0].opening_notes if len(sessions) == 1 else False,
            'closing_note': sessions[0].closing_notes if len(sessions) == 1 else False,
            'state': state,
            'currency': currency,
            'nbr_orders': len(orders),
            'date_start': date_start,
            'date_stop': date_stop,
            'session_name': session_name or False,
            'config_names': config_names,
            'payments': payments,
            'payments_by_payment_method': payments_by_payment_method,
            'company_name': self.env.company.name,
            'taxes': list(taxes.values()),
            'taxes_info': taxes_info,
            'products': final_products,  # Flattened list of all products
            'products_info': products_info,
            'category_ids': category_ids,
            'pos_category_ids': category_ids,
            'product_category_ids': category_ids,
            'refund_taxes': list(refund_taxes.values()),
            'refund_taxes_info': refund_taxes_info,
            'refund_info': refund_info,
            'refund_products': refund_products,
            'discount_number': discount_number,
            'discount_amount': discount_amount,
            'invoiceList': invoiceList,
            'invoiceTotal': invoiceTotal,
            'total_paid': totalPaymentsAmount,
            'report_type': report_type,
            'currency_khr': currency_khr,
            'currency_usd': currency_usd,
            'currency_precision': user_currency.decimal_places,
            'nbr_customers': module_pos_restaurant and sum(orders.mapped('customer_count')) or 0,
        }

    def _get_products_and_taxes_dict(self, line, products, taxes, currency, report_type='product'):
        key2 = (line.product_id, line.price_unit, line.discount)

        # Define key1 based on report_type
        default_category = _('Not Categorized')
        if line.order_id.config_id and line.order_id.config_id.discount_product_id == line.product_id:
            default_category = _('Discount')

        if report_type == 'product_category':
            # Use product category
            key1 = line.product_id.product_tmpl_id.categ_id.name if line.product_id.product_tmpl_id.categ_id else default_category
        else:
            # Default to POS category (original behavior)
            key1 = line.product_id.product_tmpl_id.pos_categ_ids[0].name if len(
                line.product_id.product_tmpl_id.pos_categ_ids) else default_category

        products.setdefault(key1, {})
        products[key1].setdefault(key2, [0.0, 0.0, 0.0])
        products[key1][key2][0] += line.qty
        products[key1][key2][1] += self._get_product_total_amount(line)
        products[key1][key2][2] += line.price_subtotal

        if line.tax_ids_after_fiscal_position:
            line_taxes = line.tax_ids_after_fiscal_position.sudo().compute_all(
                line.price_unit * (1 - (line.discount or 0.0) / 100.0), currency, line.qty, product=line.product_id,
                partner=line.order_id.partner_id or False)
            base_amounts = {}
            for tax in line_taxes['taxes']:
                taxes.setdefault(tax['id'], {'name': tax['name'], 'tax_amount': 0.0, 'base_amount': 0.0})
                taxes[tax['id']]['tax_amount'] += tax['amount']
                base_amounts[tax['id']] = tax['base']

            for tax_id, base_amount in base_amounts.items():
                taxes[tax_id]['base_amount'] += base_amount
        else:
            taxes.setdefault(0, {'name': _('No Taxes'), 'tax_amount': 0.0, 'base_amount': 0.0})
            taxes[0]['base_amount'] += line.price_subtotal_incl

        return products, taxes

    def _get_total_and_qty_per_category(self, categories):
        """ Override: replace `product['base_amount']` with `product['total_paid']` """
        all_qty = 0
        all_total = 0
        for category_dict in categories:
            qty_cat = 0
            total_cat = 0
            for product in category_dict['products']:
                qty_cat += product['quantity']
                total_cat += product['total_paid']
            category_dict['total'] = total_cat
            category_dict['qty'] = qty_cat
        # IMPROVEMENT: It would be better if the `products` are grouped by pos.order.line.id.
        unique_products = list({tuple(sorted(product.items())): product for category in categories for product in
                                category['products']}.values())
        all_qty = sum([product['quantity'] for product in unique_products])
        all_total = sum([product['total_paid'] for product in unique_products])

        return categories, {'total': all_total, 'qty': all_qty}
