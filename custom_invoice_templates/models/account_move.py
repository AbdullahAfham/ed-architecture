
from odoo import _, _lt, api, fields, models
from datetime import date, datetime, time


class AccountInvoice(models.Model):
    _inherit = "account.move"

    attend_id = fields.Many2one('res.partner', string="Attend", domain="[('parent_id', '=', partner_id)]")

    def _get_quotation_lines(self, name):

        order_id = self.env['sale.order'].search([('name', '=', self.invoice_origin)])

        return order_id