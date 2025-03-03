# -*- coding: utf-8 -*-

from odoo import models, fields, api
try:
  import qrcode
except ImportError:
  qrcode = None
try:
  import base64
except ImportError:
  base64 = None
from io import BytesIO
from math import sin, cos, sqrt, atan2, radians
from random import choice
import string
import uuid

class ERPMobileUsers(models.Model):
    _name = 'erp.mobile.users'
    _description = "ERP Mobile Users List"

    name = fields.Char()
    login = fields.Integer()
    lang = fields.Many2one()
    mobile_account_id = fields.Many2one('erp.mobile.company', 'Company Account')
    partner_id = fields.Many2one('res.partner', 'User')
    parent_id = fields.Many2one('res.partner', 'Company')
    login_date = fields.Datetime(string="Latest authentication")
    state = fields.Selection([('new', 'Never Login'),
                              ('confirm', 'Confirmed')], string='Status', default='new',
                             track_visibility='always')


class ERPMobileCompany(models.Model):
    _name = 'erp.mobile.company'
    # _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']
    _description = "ERP Mobile Company Accounts"

    name = fields.Char()
    customer_code = fields.Char("Customer Code")
    partner_id = fields.Many2one('res.partner', 'Customer')
    login_date = fields.Datetime(string="Start Date")
    company_id = fields.Many2one('res.company', 'Company', readonly=True, help="Company",
                                 default=lambda self: self.env.user.company_id)
    base_url = fields.Char(string="Base URL")
    active = fields.Boolean()
    description = fields.Text('Description')
    mobile_user_ids = fields.One2many('erp.mobile.users', 'mobile_account_id', string="Users")
    state = fields.Selection([('new', 'New'),
                              ('confirm', 'Confirmed')], string='Status', default='new',
                             track_visibility='always')
    qr_code_uuid = fields.Char("UUID")
    qr_code_img = fields.Image("QR Code", max_width=1024, max_height=1024, store=True, copy=False)
    date_localization = fields.Date("Updated On")
    color = fields.Integer('Color Index')
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Favorite'),
    ], default='0', string="Favorite")

    def action_generate_qrcode(self):
        data = str(uuid.uuid4())

        if qrcode and base64:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=3,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image()
            temp = BytesIO()
            img.save(temp, format="PNG")
            qr_image = base64.b64encode(temp.getvalue())

            self.write({'qr_code_img': qr_image, 'qr_code_uuid': data})

    def generate_custom_code(self):
        for rec in self:
            code = ''.join(choice(string.ascii_uppercase) for i in range(6))
            rec.customer_code = code

        return True