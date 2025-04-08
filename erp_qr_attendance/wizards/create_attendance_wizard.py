
from odoo import fields, models, _
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import pandas as pd

class PreCreateAttendance(models.TransientModel):
    _name = "pre.create.attendance.wizard"
    _description = "Pre Create Attendance Wizard"

    date = fields.Date(string='Date', required=True, default=lambda self: fields.Date.to_string((datetime.now())))
    date_from = fields.Date(string='Start Date', required=True, help="Start date",
                            default=lambda self: fields.Date.to_string(
                                (datetime.now().replace(day=1))))
    date_to = fields.Date(string='End Date', required=True, help="End date",
                          default=lambda self: fields.Date.to_string(
                              (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True, readonly=True,
                                 states={'draft': [('readonly', False)]},
                                 default=lambda self: self.env.company)
    state = fields.Selection([('choose', 'choose'), ('get', 'get')], default='choose')
    employee_id = fields.Many2one('hr.employee', string="Employee")

    def go_back(self):
        self.state = 'choose'
        return {
            'name': 'Create Attendance',
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new'
        }

    def action_create_attendance(self):
        att = self.env['hr.attendance']
        for d in pd.date_range(self.date_from, self.date_to).tolist():
            att.manual_pre_create_attendance(d.date(), self.employee_id)
        return True


