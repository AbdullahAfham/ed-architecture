# -*- coding: utf-8 -*-

from odoo import fields, models, api

class StockQuantInherit(models.Model):
    _inherit = 'stock.quant'

    standard_price = fields.Float(
        string="Cost", 
        compute="_compute_product_fields", 
        store=True, 
        digits='Product Price', 
        groups="base.group_user"
    )
    default_code = fields.Char(
        string="Internal Reference", 
        compute="_compute_product_fields", 
        store=True
    )

    @api.depends('product_id')
    def _compute_product_fields(self):
        for record in self:
            record.standard_price = record.product_id.standard_price if record.product_id else 0.0
            record.default_code = record.product_id.default_code if record.product_id else ""