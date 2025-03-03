from odoo import models, fields, api


class MobileModule(models.Model):
    _name = 'mobile.module'
    _description = 'Mobile Module'

    @api.model
    def _company_get(self):
        return self.env["res.company"].browse(self.env.company.id)

    name = fields.Char(string='Name')
    key = fields.Char(string='key')
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=_company_get,
        track_visibility="onchange",
    )

