# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

class PosPayment(models.Model):
    _inherit = "pos.payment"

    khr = fields.Float(string='Amount KHR', help="Total amount of the payment in KHR.")

    def _export_for_ui(self, payment):
        result = super(PosPayment, self)._export_for_ui(payment)
        result['khr'] = payment.khr
        return result
