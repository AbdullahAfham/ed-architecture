
from odoo import _, _lt, api, fields, models
from datetime import date, datetime, time


class AccountInvoice(models.Model):
    _inherit = "account.move"

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
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    has_active_pricelist = fields.Boolean(compute='_compute_has_active_pricelist')
    show_update_currency = fields.Boolean(string="Has Currency Changed", store=False)  # true if the currency was changed
        

    @api.onchange('invoice_date')
    def onchange_exchange_date(self):
        rate_id = self.env['res.currency.rate'].search([
            ('currency_id', '=', self.khr_currency_id.id),
            ('name', '=', self.invoice_date)
            ], limit=1)
        
        if rate_id:
            self.exchange_rate = rate_id.rate

    @api.depends('company_id')
    def _compute_has_active_pricelist(self):
        for order in self:
            order.has_active_pricelist = bool(self.env['product.pricelist'].search(
                [('company_id', 'in', (False, order.company_id.id)), ('active', '=', True)],
                limit=1,
            ))

    @api.depends('amount_total', 'exchange_rate', 'currency_id')
    def _compute_amount_in_currency(self):
        """Compute amounts in both USD and KHR based on the currency."""
        for order in self:
            if order.currency_id.name == 'USD':
                order.amount_total_khr = order.amount_total * order.exchange_rate
                order.amount_total_usd = order.amount_total
            elif order.currency_id.name == 'KHR':
                order.amount_total_khr = order.amount_total
                order.amount_total_usd = order.amount_total / order.exchange_rate if order.exchange_rate else 0.0
            else:
                order.amount_total_khr = 0.0
                order.amount_total_usd = 0.0

    @api.onchange('currency_id')
    def onchange_currency_pricelist(self):
        # true if the currency was changed
        self.show_update_currency = True

        if self.currency_id:
            pricelist = self.env['product.pricelist'].search([('currency_id', '=', self.currency_id.id)], limit=1)
            self.pricelist_id = pricelist.id if pricelist else False

    @api.depends('currency_id')
    def _compute_is_pricelist_currency(self):
        for order in self:
            order.is_pricelist_khr = order.currency_id.name == 'KHR' if order.currency_id else False
            order.is_pricelist_usd = order.currency_id.name == 'USD' if order.currency_id else False
            
    
    def action_update_price(self):
        self.ensure_one()
        self._recompute_price()
    
        if self.currency_id:
            message = _("Product prices have been recomputed according to pricelist %s.",
                self.currency_id._get_html_link())
        else:
            message = _("Product prices have been recomputed.")
        self.message_post(body=message)

        # set show_update_currency to False
        self.show_update_currency = False

    def _recompute_price(self):
        for line in self.line_ids:
            rate = self.exchange_rate
            if self.currency_id.name == 'KHR':
                line.price_unit = line.price_unit *  rate
            elif self.currency_id.name == 'USD':
                line.price_unit = line.price_unit / rate 
            else:
                line.price_unit = 0.0 