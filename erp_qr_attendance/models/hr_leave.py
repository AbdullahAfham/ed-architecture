from odoo import fields, models, api

class HrLeaveInherit(models.Model):
    _inherit = 'hr.leave'

    attendance_id = fields.Many2one('hr.attendance', string='Attendance')

class HrLeaveTypeInherit(models.Model):
    _inherit = 'hr.leave.type'

    attendance_state = fields.Selection([
        ('annual_leave', 'AL'),
        ('sick_leave', 'SL'),
        ('maternity_leave', 'ML'),
        ('special_leave', 'SP'),
        ('unpaid_leave', 'L'),
        ('absence', 'Absent'),
        ('missed', 'Missed Scan'),
        ('time_off', 'Time Off'),
    ], string='Attendance Status', default=False, help='Attendance State for Leave Type')