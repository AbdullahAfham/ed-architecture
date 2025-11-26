from odoo import models

class PurchaseOrder(models.Model):
    # We EXTEND existing purchase.order model and ADD mail.alias.mixin
    _inherit = ['purchase.order', 'mail.alias.mixin']

    def _alias_get_creation_values(self):
        # Optional: adjust default values when PO created from email
        values = super()._alias_get_creation_values()
        return values
