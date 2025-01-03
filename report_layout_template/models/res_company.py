# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    khmer_name = fields.Char(string='Khmer Name', required=False, store=True, readonly=False)
    khmer_address = fields.Char(string='Khmer Address')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    khmer_name = fields.Char(string='Khmer Name', required=False, store=True, readonly=False)
    khmer_address = fields.Char(string='Khmer Address')
    is_customer = fields.Boolean(string="Is Customer")
    is_vendor = fields.Boolean(string="Is Vendor")


class BaseDocumentLayout(models.TransientModel):
    _inherit = 'base.document.layout'

    khmer_name = fields.Char(related='company_id.khmer_name', readonly=True)
    khmer_address = fields.Char(related='company_id.khmer_address', readonly=True)
    street = fields.Char(related='company_id.street', readonly=True)
    city = fields.Char(related='company_id.city', readonly=True)
