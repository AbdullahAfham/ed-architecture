from odoo import fields, models, api, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    verification_code = fields.Char('Verification Code')
