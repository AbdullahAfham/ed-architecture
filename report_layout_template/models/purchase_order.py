
from odoo import _, _lt, api, fields, models
from datetime import date, datetime, time


class PurchaseOrderInherit(models.Model):
    _inherit = "purchase.order"

    khr_currency_id = fields.Many2one('res.currency', string='Khmer Riel', required=True, tracking=True,
                                readonly=True, default=lambda self: self.env['res.currency'].search([('name', '=', 'KHR')]))
    exchange_date = fields.Date('Exchange Date', required=True, default=lambda self: fields.Date.to_string(date.today()))
    exchange_rate = fields.Float('Exchange Rate', required=True, store=True, readonly=True, default=4050.00)
    amount_total_khr = fields.Monetary(string='Total in Riel', compute='_compute_amount_khr', store=True)
        
    @api.onchange('invoice_date')
    def onchange_exchange_date(self):
        rate_id = self.env['res.currency.rate'].search([
            ('currency_id', '=', self.khr_currency_id.id),
            ('name', '=', self.invoice_date)
            ], limit=1)
        
        if rate_id:
            self.exchange_rate = rate_id.rate

    @api.depends('amount_total', 'exchange_rate')
    def _compute_amount_khr(self):
        for order in self:
            order.amount_total_khr = order.amount_total * order.exchange_rate
 

