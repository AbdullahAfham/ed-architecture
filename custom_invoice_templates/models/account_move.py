
from odoo import _, _lt, api, fields, models
from datetime import date, datetime, time


class AccountInvoice(models.Model):
    _inherit = "account.move"

    def _compute_amount_khr(self):
        for move in self:
            move.amount_total_khr = move.amount_total * move.exchange_rate

    attend_id = fields.Many2one('res.partner', string="Attend", domain="[('parent_id', '=', partner_id)]")
    amount_total_khr = fields.Monetary(
        string='Total in Riel',
        compute='_compute_amount_khr', store=True)


    def _get_quotation_lines(self, name):

        order_id = self.env['sale.order'].search([('name', '=', self.invoice_origin)])

        return order_id