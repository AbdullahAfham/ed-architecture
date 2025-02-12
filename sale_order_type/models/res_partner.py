# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    sale_type = fields.Many2one(
        comodel_name="sale.order.type", string="Sale Order Type", company_dependent=True
    )

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        if default.get('sale_type'):
            return vals_list
        return [dict(vals, sale_type=partner.sale_type) for partner, vals in zip(self, vals_list)]
