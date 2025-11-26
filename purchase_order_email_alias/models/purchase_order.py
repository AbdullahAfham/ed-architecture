from odoo import models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # Enable e-mail alias support
    def _get_alias_values(self):
        """Return values used for the mail alias linked to purchase.order."""
        return {
            'alias_name': 'purchaseteam',      # alias name
            'alias_model_id': self.env.ref('purchase.model_purchase_order').id,
            'alias_contact': 'everyone',       # anyone can send PO email
        }
