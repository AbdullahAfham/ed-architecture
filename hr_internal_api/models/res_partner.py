import base64
from odoo import fields, models, tools, api, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    verification_code = fields.Char('Verification Code')

    visit_history_ids = fields.One2many(
        comodel_name='visit.history', inverse_name='partner_id', string='Visit History'
    )
    last_visit_date = fields.Datetime(
        compute="_compute_last_visit_date"
    )

    def _compute_last_visit_date(self):
        for partner in self:
            all_visit_date = partner.visit_history_ids.mapped('date')

            if not all_visit_date:
                partner.last_visit_date = False
                continue

            partner.last_visit_date = max(all_visit_date)

