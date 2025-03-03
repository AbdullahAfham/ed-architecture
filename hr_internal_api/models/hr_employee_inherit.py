from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    can_create_batch_ot = fields.Boolean(string="Can Create Batch OT", default=False)
    restrict_location = fields.Boolean(string="Restrict Location", default=True)
    device_token = fields.Char(related='user_id.device_token', string='Device Token')
    