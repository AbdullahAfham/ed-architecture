# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from datetime import datetime, timedelta
from odoo.osv.expression import AND
import pytz

class PosDetails(models.TransientModel):
    _inherit = 'pos.details.wizard'

    report_type = fields.Selection(selection=[
        ('product', 'Product'),
        ('category', 'Category'),
        # ('both', 'Both'),
    ], required=True, default='product', string='Report Type')

    # def generate_report(self):
    #     data = {'date_start': self.start_date, 'date_stop': self.end_date, 'config_ids': self.pos_config_ids.ids,
    #             'report_type': self.report_type}
    #     return self.env.ref('point_of_sale.sale_details_report').report_action([], data=data)


class ReportSaleDetails(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'

    @api.model
    def _get_report_values(self, docids, data=None):
        return super(ReportSaleDetails, self.sudo())._get_report_values(docids, data)

    # @api.model
    # def _get_report_values(self, docids, data=None):
    #     data = dict(data or {})
    #     data.update({
    #         'session_ids': data.get('session_ids') or docids,
    #         'config_ids': data.get('config_ids'),
    #         'date_start': data.get('date_start'),
    #         'date_stop': data.get('date_stop')
    #     })
    #     configs = self.env['pos.config'].browse(data['config_ids'])
    #     data.update(self.get_sale_details(data['date_start'], data['date_stop'], configs.ids, data['session_ids'],
    #                                       data['report_type']))
    #     return data

    # @api.model
    # def get_sale_details(self, date_start=False, date_stop=False, config_ids=False, session_ids=False,
    #                      report_type=False):
    #     data = super(ReportSaleDetails, self).get_sale_details(date_start, date_stop, config_ids, session_ids)
    #     domain = [('state', 'in', ['paid', 'invoiced', 'done'])]
    #
    #     if (session_ids):
    #         domain = AND([domain, [('session_id', 'in', session_ids)]])
    #     else:
    #         if date_start:
    #             date_start = fields.Datetime.from_string(date_start)
    #         else:
    #             # start by default today 00:00:00
    #             user_tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
    #             today = user_tz.localize(fields.Datetime.from_string(fields.Date.context_today(self)))
    #             date_start = today.astimezone(pytz.timezone('UTC'))
    #
    #         if date_stop:
    #             date_stop = fields.Datetime.from_string(date_stop)
    #             # avoid a date_stop smaller than date_start
    #             if (date_stop < date_start):
    #                 date_stop = date_start + timedelta(days=1, seconds=-1)
    #         else:
    #             # stop by default today 23:59:59
    #             date_stop = date_start + timedelta(days=1, seconds=-1)
    #
    #         domain = AND([domain,
    #                       [('date_order', '>=', fields.Datetime.to_string(date_start)),
    #                        ('date_order', '<=', fields.Datetime.to_string(date_stop))]
    #                       ])
    #
    #         if config_ids:
    #             domain = AND([domain, [('config_id', 'in', config_ids)]])
    #
    #     orders = self.env['pos.order'].search(domain)
    #
    #     user_currency = self.env.company.currency_id
    #
    #     payments = []
    #     payment_data = {}
    #     payment_ids = self.env["pos.payment"].search([('pos_order_id', 'in', orders.ids)])
    #     for payment_id in payment_ids:
    #         name = payment_id.payment_method_id.name
    #
    #         if name in payment_data:
    #             payment_data[name]['total'] += payment_id.amount
    #             payment_data[name]['khr'] += payment_id.khr
    #         else:
    #             payment_data.update({
    #                 name: {
    #                     'name': name,
    #                     'total': payment_id.amount,
    #                     'khr': payment_id.khr,
    #                 }
    #             })
    #     if payment_data:
    #         payments = list(payment_data.values())
    #
    #     # self.env.cr.execute("""
    #     #             SELECT method.name, sum(amount) total, sum(khr) khr
    #     #             FROM pos_payment AS payment,
    #     #                  pos_payment_method AS method
    #     #             WHERE payment.payment_method_id = method.id
    #     #                 AND payment.id IN %s
    #     #             GROUP BY method.name
    #     #         """, (tuple(payment_ids),))
    #     # payments = self.env.cr.dictfetchall()
    #
    #     for payment in payments:
    #         if 'KHR' in payment['name']:
    #             total = payment['total']
    #             payment['total'] = payment['khr']
    #             payment['khr'] = total
    #     data["payments"] = payments
    #
    #     # payment_ids = self.env["pos.payment"].search([('pos_order_id', 'in', orders.ids)])
    #     # payments_khr = {}
    #     # if payment_ids:
    #     #     for payment in payment_ids:
    #     #         if payment.khr:
    #     #             if "Cash KHR" in payments_khr:
    #     #                 payments_khr["Cash KHR"]=payments_khr["Cash KHR"]+round(payment.khr, 100)
    #     #             else:
    #     #                 payments_khr.update({
    #     #                     "Cash KHR": round(payment.khr, 100)
    #     #                 })
    #     #         else:
    #     #             if payment.name in payments_khr:
    #     #                 payments_khr[payment.name]=payments_khr[payment.name]+payment.amount
    #     #             else:
    #     #                 payments_khr.update({
    #     #                     payment.name: payment.amount
    #     #                 })
    #
    #     products = data["products"]
    #     categ_ids = {}
    #     for product in products:
    #         product_id = self.env['product.product'].browse(product['product_id'])
    #         name = product_id.pos_categ_id.name
    #         total = product['price_unit'] * product['quantity']
    #         discount = product['discount'] != 0 and total * (product['discount'] / 100) or 0
    #         if name in categ_ids:
    #             categ_ids[name]['products'] += [product]
    #             categ_ids[name]['quantity'] += product['quantity']
    #             categ_ids[name]['discount'] += discount
    #             categ_ids[name]['price'] += total
    #             categ_ids[name]['total'] += (total - discount)
    #         else:
    #             categ_ids.update({
    #                 name: {
    #                     'name': name,
    #                     'categ_id': product_id.pos_categ_id.id,
    #                     'products': [product],
    #                     'quantity': product['quantity'],
    #                     'price': total,
    #                     'discount': discount,
    #                     'total': total - discount,
    #                 }
    #             })
    #     category_ids = list(categ_ids.values())
    #
    #     products_sold = {}
    #     taxes = {}
    #     for order in orders:
    #         currency = order.session_id.currency_id
    #         for line in order.lines:
    #             key = (line.product_id, line.price_unit, line.discount)
    #             products_sold.setdefault(key, 0.0)
    #             products_sold[key] += line.qty
    #
    #             if line.tax_ids_after_fiscal_position:
    #                 line_taxes = line.tax_ids_after_fiscal_position.sudo().compute_all(line.price_unit, currency,
    #                                                                                    line.qty,
    #                                                                                    product=line.product_id,
    #                                                                                    partner=line.order_id.partner_id or False)
    #                 for tax in line_taxes['taxes']:
    #                     taxes.setdefault(tax['id'],
    #                                      {'name': tax['name'], 'tax_amount': 0.0, 'base_amount': 0.0, 'tax_total': 0.0})
    #                     taxes[tax['id']]['tax_amount'] += tax['amount']
    #                     taxes[tax['id']]['base_amount'] += tax['base']
    #                     taxes[tax['id']]['tax_total'] += (tax['base'] + tax['amount'])
    #             else:
    #                 taxes.setdefault(0,
    #                                  {'name': _('No Taxes'), 'tax_amount': 0.0, 'base_amount': 0.0, 'tax_total': 0.0})
    #                 taxes[0]['base_amount'] += line.price_subtotal_incl
    #
    #     order_data = [{
    #         'date': order.date_order + timedelta(hours=7),
    #         'order_name': order.name,
    #         'name': order.pos_reference,
    #         'session_name': order.session_id.config_id.name,
    #         'subtotal': round(order.amount_total - order.amount_tax, user_currency.decimal_places),
    #         'vat': round(order.amount_tax, user_currency.decimal_places),
    #         'total': round(order.amount_total, user_currency.decimal_places),
    #     } for order in orders]
    #
    #     subtotal = round(sum(order["subtotal"] for order in order_data), user_currency.decimal_places)
    #     vat = round(sum(order["vat"] for order in order_data), user_currency.decimal_places)
    #     total = round(sum(order["total"] for order in order_data), user_currency.decimal_places)
    #
    #     total_discount = round(
    #         sum(product["discount"] / 100 * product["price_unit"] * product["quantity"] for product in products),
    #         user_currency.decimal_places)
    #     total_qty = round(sum(product["quantity"] for product in products), user_currency.decimal_places)
    #
    #     sessions = False
    #     if config_ids:
    #         sessions = [self.env['pos.config'].browse(config_id).name for config_id in config_ids]
    #
    #     currency_khr = self.env['res.currency'].search([('name', '=', "KHR")], limit=1)
    #     currency_usd = self.env['res.currency'].search([('name', '=', "USD")], limit=1)
    #
    #     data.update({
    #         'taxes': list(taxes.values()),
    #         'products': sorted([{
    #             'product_id': product.id,
    #             'product_name': product.name,
    #             'code': product.default_code,
    #             'quantity': qty,
    #             'price_unit': price_unit,
    #             'total': (1 - (discount or 0.0) / 100.0) * price_unit * qty,
    #             'discount_percent': discount,
    #             'discount': discount != 0 and price_unit * ((discount or 0.0) / 100.0) or 0,
    #             'uom': product.uom_id.name
    #         } for (product, price_unit, discount), qty in products_sold.items()], key=lambda l: l['product_name']),
    #         "now": datetime.now().strftime('%d/%m/%Y'),
    #         # "payments_khr": payments_khr.items(),
    #         "subtotal": subtotal,
    #         "vat": vat,
    #         "total": total,
    #         "total_wo_tax": round(total - vat, user_currency.decimal_places),
    #         "total_discount": total_discount,
    #         "total_qty": total_qty,
    #         "sessions": sessions,
    #         "category_ids": category_ids,
    #         "order_number": len(orders.ids),
    #         "currency_khr": currency_khr,
    #         "currency_usd": currency_usd,
    #         "report_type": report_type,
    #         "grand_total": total_discount + data["total_paid"],
    #         'orders': sorted(order_data, key=lambda l: (l['session_name'], l['date'])),
    #     })
    #     return data
    #
