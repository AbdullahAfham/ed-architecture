
from odoo import api, fields, models, _
from datetime import date, datetime, time, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
import pandas as pd


class UpdateAttendance(models.TransientModel):
    _name = "update.attendance.wizard"
    _description = "Update Attendance Wizard"

    date = fields.Date(string='Date', required=True, default=lambda self: fields.Date.to_string((datetime.now())))
    date_from = fields.Date(string='Start Date', required=True, help="Start date",
                            default=lambda self: fields.Date.to_string(
                                (datetime.now().replace(day=1))))
    date_to = fields.Date(string='End Date', required=True, help="End date",
                          default=lambda self: fields.Date.to_string(
                              (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True, readonly=True,
                                 default=lambda self: self.env.company)
    employee_id = fields.Many2one('hr.employee', string="Employee")
    state = fields.Selection([('choose', 'choose'), ('get', 'get')], default='choose')
    

    def go_back(self):
        self.state = 'choose'
        return {
            'name': 'Update Attendance Status',
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new'
        }    

    def action_update_attendance(self):
        hr_attendance_obj = self.env['hr.attendance']
        for d in pd.date_range(self.date_from, self.date_to).tolist():
            hr_attendance_obj.manual_update_attendance_status(d.date(), self.employee_id)
        return True


