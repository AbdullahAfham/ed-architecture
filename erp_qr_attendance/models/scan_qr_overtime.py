from odoo import models, fields
import logging
from math import sin, cos, sqrt, atan2, radians

_logger = logging.getLogger(__name__)


class ScanQrOvertime(models.Model):
    _name = 'scan.qr.overtime'
    _order = 'date desc'
    _description = "Scan QR Overtime"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    display_name = fields.Char('Display Name')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    user_id = fields.Many2one('res.users', string='User')
    date = fields.Date(string='Date')
    location_id = fields.Many2one('res.partner', string='Working Address')
    project_id = fields.Many2one('project.project', string="Project Code")
    qr_id = fields.Many2one('erp.qr.generate', string="QR Code")
    scan_type = fields.Selection([('ot_in', 'Overtime In'),
                                  ('ot_out', 'Overtime Out')], string='Punching Type')
    scan_time = fields.Datetime(string='Punching Time')
    longitude = fields.Float(string="Geo Longitude", copy=False, digits=(10, 14))
    latitude = fields.Float(string="Geo Latitude", copy=False, digits=(10, 14))
    late = fields.Float('Late')
    late_state = fields.Selection([('good', 'Good'),
                                   ('late', 'Late'),
                                   ('missed', 'Missed')], string='Late State')
    status = fields.Selection([('done', 'Done'),
                               ('new', 'New'),
                               ('skip', 'Skipped')], string='Status')
    description = fields.Html(string="Description")

    def get_distance(self, lat, lon):
        # Approximate radius of earth in km
        R = 6373.0

        qr_lat = radians(self.latitude)
        qr_lon = radians(self.longitude)
        user_lat = radians(lat)
        user_lon = radians(lon)

        dlat = user_lat - qr_lat
        dlon = user_lon - qr_lon

        a = sin(dlat / 2) ** 2 + cos(qr_lat) * cos(user_lat) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        distance = R * c

        distance_in_meter = distance * 1000

        return distance_in_meter

    def create(self, val):
        res = super(ScanQrOvertime, self).create(val)
        res.update_overtime_request()

        return res

    def update_overtime_request(self):
        for rec in self:
            hr_overtime = self.env['hr.overtime'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('date_from', '>=', rec.date),
            ], limit=1)

            if hr_overtime:
                hr_overtime.update_overtime_request()
