from odoo import _, api, fields, models


class Pricelist(models.Model):
    _inherit = "product.pricelist"

    available_in_mobile = fields.Boolean(string="Available in Mobile")
