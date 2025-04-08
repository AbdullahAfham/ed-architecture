from odoo import models, fields


class DeviceInfo(models.Model):
    _name = 'device.info'
    _description = 'Device Information'

    name = fields.Char(string='Device Name')
    os = fields.Char(string='OS')
    os_version = fields.Char(string='OS Version')
    model = fields.Char(string='Model')
    device_uuid = fields.Char(string='Device UUID', required=True)
    user_id = fields.Many2one('res.users', string='User', required=True)
