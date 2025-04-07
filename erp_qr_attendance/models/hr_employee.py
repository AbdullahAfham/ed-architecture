from odoo import fields, models, api

class HrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'

    last_check_in = fields.Datetime(
        related='last_attendance_id.check_in', store=True,
        groups="hr_attendance.group_hr_attendance_user,hr.group_hr_user", tracking=False)
    last_check_out = fields.Datetime(
        related='last_attendance_id.check_out', store=True,
        groups="hr_attendance.group_hr_attendance_user,hr.group_hr_user", tracking=False)