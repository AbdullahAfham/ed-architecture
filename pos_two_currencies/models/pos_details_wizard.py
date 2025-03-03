# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from datetime import datetime, timedelta
from odoo.osv.expression import AND
import pytz

from odoo.exceptions import UserError


class PosDetails(models.TransientModel):
    _inherit = 'pos.details.wizard'

    report_type = fields.Selection(selection=[
        ('product', 'Product'),
        ('category', 'Category'),
        ('both', 'Both'),
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
                         report_type=False):
        """ Override

            - add new parameter to accept `report_type` value
            - override new list of payments object
            - override new list of products object
            - add new list of categories object
        """
        data = super(ReportSaleDetails, self).get_sale_details(date_start, date_stop, config_ids, session_ids)

        domain = [('state', 'in', ['paid', 'invoiced', 'done'])]
        if (session_ids):
            domain = AND([domain, [('session_id', 'in', session_ids)]])
        else:
            if date_start:
                date_start = fields.Datetime.from_string(date_start)
            else:
                # start by default today 00:00:00
                user_tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
                today = user_tz.localize(fields.Datetime.from_string(fields.Date.context_today(self)))
                date_start = today.astimezone(pytz.timezone('UTC'))

            if date_stop:
                date_stop = fields.Datetime.from_string(date_stop)
                # avoid a date_stop smaller than date_start
                if (date_stop < date_start):
                    date_stop = date_start + timedelta(days=1, seconds=-1)
            else:
                # stop by default today 23:59:59
                date_stop = date_start + timedelta(days=1, seconds=-1)

            domain = AND([domain,
                          [('date_order', '>=', fields.Datetime.to_string(date_start)),
                           ('date_order', '<=', fields.Datetime.to_string(date_stop))]
                          ])

            if config_ids:
                domain = AND([domain, [('config_id', 'in', config_ids)]])

        orders = self.env['pos.order'].search(domain)

        user_currency = self.env.company.currency_id

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
            raise UserError(_('There is no Payments in session.'))

        # The `products` key in `data` is a list of objects represent:
        # - category name
        # - list of products object
        # - total amount
        # - total quantity
        products = []
        category_ids = []
        if data["products"]:

            for categ in data["products"]:
                # 1). get list of products belong to a category
                products.extend(categ["products"])

                # get total of discount and tax correspond to a category
                discount = sum(product["price_unit"] * product["quantity"] * product["discount"] / 100 for product in
                               categ["products"])
                tax = sum(product["price_unit"] * product["quantity"] - product["base_amount"] for product in
                          categ["products"])

                # 2). get list of categories
                # As we have overridden `_get_total_and_qty_per_category`
                # now categ["total"] is the tax included amount with discount subtraction.
                category_ids.append({
                    'name': categ["name"],
                    'quantity': categ["qty"],
                    'price': categ["total"] + discount,
                    'discount': discount,
                    'total': categ["total"],
                })

        currency_khr = self.env['res.currency'].search([('name', '=', "KHR")], limit=1)
        currency_usd = self.env['res.currency'].search([('name', '=', "USD")], limit=1)

        data.update({
            "payments": payments,
            "payments_by_payment_method": payments_by_payment_method,
            "products": products,
            "category_ids": category_ids,
            "currency_khr": currency_khr,
            "currency_usd": currency_usd,
            "report_type": report_type,
            "currency_precision": user_currency.decimal_places,
            "nbr_customers": sum(orders.mapped('customer_count')),
        })
        return data

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
