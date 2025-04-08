# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api

class PosPayment(models.Model):
    _inherit = "pos.payment"

    khr = fields.Float(string='Amount KHR', help="Total amount of the payment in KHR.")

    # def _payment_fields(self, order, ui_paymentline):
    #     result = super(PosOrder, self)._payment_fields(order, ui_paymentline)
    #     result['khr'] = ui_paymentline.get("khr", 0.0)
    #     payment_method_id = self.env['pos.payment.method'].browse(ui_paymentline['payment_method_id']).exists()
    #     exchange_rate = order.session_id.config_id.exchange_rate
    #     if payment_method_id and ("KHR" in payment_method_id.name):
    #         result['amount'] = round(ui_paymentline['amount'] / exchange_rate, 4)
    #     return result
