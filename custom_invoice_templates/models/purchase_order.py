from odoo import fields, models

class PurchaseOrderInherit(models.Model):
    _inherit = "purchase.order"

    khr_currency_id = fields.Many2one('res.currency', string='Khmer Riel', required=True, tracking=True,
                                readonly=True, default=lambda self: self.env['res.currency'].search([('name', '=', 'KHR')]))
    usd_currency_id = fields.Many2one('res.currency', string='USD', required=True, tracking=True,
                                readonly=True, default=lambda self: self.env['res.currency'].search([('name', '=', 'USD')]))