
from odoo import _, _lt, api, fields, models
from datetime import date, datetime, time


class SaleOrderInherit(models.Model):
    _inherit = "sale.order"

    khr_currency_id = fields.Many2one('res.currency', string='Khmer Riel', required=True, tracking=True,
                                readonly=True, default=lambda self: self.env['res.currency'].search([('name', '=', 'KHR')]))
    usd_currency_id = fields.Many2one('res.currency', string='USD', required=True, tracking=True,
                                readonly=True, default=lambda self: self.env['res.currency'].search([('name', '=', 'USD')]))
    exchange_date = fields.Date('Exchange Date', required=True, default=lambda self: fields.Date.to_string(date.today()))
    exchange_rate = fields.Float('Exchange Rate', required=True, store=True, readonly=True, default=4050.00)
    amount_total_khr = fields.Monetary(string='Total in Riel', compute='_compute_amount_in_currency', store=True)
    amount_total_usd = fields.Monetary(string='Total in USD', compute='_compute_amount_in_currency', store=True)
    is_pricelist_khr = fields.Boolean(compute="_compute_is_pricelist_currency", store=True)
    is_pricelist_usd = fields.Boolean(compute="_compute_is_pricelist_currency", store=True)

    @api.onchange('invoice_date')
    def onchange_exchange_date(self):
        rate_id = self.env['res.currency.rate'].search([
            ('currency_id', '=', self.khr_currency_id.id),
            ('name', '=', self.invoice_date)
            ], limit=1)
        
        if rate_id:
            self.exchange_rate = rate_id.rate

    @api.depends('amount_total', 'exchange_rate', 'pricelist_id.currency_id')
    def _compute_amount_in_currency(self):
        """Compute amounts in both USD and KHR based on the pricelist currency."""
        for order in self:
            if order.pricelist_id.currency_id.name == 'USD':
                order.amount_total_khr = order.amount_total * order.exchange_rate
                order.amount_total_usd = order.amount_total
            elif order.pricelist_id.currency_id.name == 'KHR':
                order.amount_total_khr = order.amount_total
                order.amount_total_usd = order.amount_total / order.exchange_rate if order.exchange_rate else 0.0
            else:
                order.amount_total_khr = 0.0
                order.amount_total_usd = 0.0

    @api.depends('pricelist_id')
    def _compute_is_pricelist_currency(self):
        for order in self:
            order.is_pricelist_khr = order.pricelist_id.currency_id.name == 'KHR' if order.pricelist_id.currency_id else False
            order.is_pricelist_usd = order.pricelist_id.currency_id.name == 'USD' if order.pricelist_id.currency_id else False

    def _prepare_invoice(self):
        value = super(SaleOrderInherit, self)._prepare_invoice()
        
        value['pricelist_id'] = self.pricelist_id.id if self.pricelist_id else False,
        return value