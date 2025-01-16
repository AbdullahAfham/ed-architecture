
from odoo import _, _lt, api, fields, models
from datetime import date, datetime, time


class AccountInvoice(models.Model):
    _inherit = "account.move"

    khr_currency_id = fields.Many2one('res.currency', string='Khmer Riel', required=True,
                                  readonly=True, default=lambda self: self.env['res.currency'].search([('name', '=', 'KHR')]),
                                      tracking=True)
    exchange_date = fields.Date('Exchange Date', required=True,
                                default=lambda self: fields.Date.to_string(date.today()))
    exchange_rate = fields.Float('Exchange Rate', required=True, store=True, readonly=True,
                                 default=lambda self: self.khr_currency_id.rate)

    @api.onchange('invoice_date')
    def onchange_exchange_date(self):
        rate_id = self.env['res.currency.rate'].search([('currency_id', '=', self.khr_currency_id.id),
                                                            ('name', '=', self.invoice_date)], limit=1)
        if rate_id:
            self.exchange_rate = rate_id.rate