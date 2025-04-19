from odoo import _, _lt, api, fields, models


class HrEmployee(models.AbstractModel):
    _inherit = "hr.employee"

    spouse_number = fields.Integer('Spouse Number', store=True,
                                   help="This is the number of spouse for calculating in payroll")


class HrEmployeeBase(models.AbstractModel):
    _inherit = "hr.employee.base"

    spouse_number = fields.Integer('Spouse Number', store=True,
                                   help="This is the number of spouse for calculating in payroll")


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    spouse_number = fields.Integer(readonly=True)


class HrContract(models.Model):
    _inherit = 'hr.contract'

    allowance = fields.Float('Allowances', store=True)
    ot_ph = fields.Float('OT PH', store=True)
    ot_working_day = fields.Float('OT Working Day', store=True)
    ot_weekend = fields.Float('OT Weekend', store=True)
    unpaid_num = fields.Float('UNPAID NUM', store=True)
    # first_paid = fields.Float(string="First Paid")


#
# class ResourceCalendar(models.Model):
#     _inherit = 'resource.calendar'
#
#     day_per_month = fields.Integer('Working Day', store=True)
#
#     @api.depends('attendance_ids', 'two_weeks_calendar')
#     def _onchange_day_per_month(self):
#         attendances = self._get_global_attendances()
#         if not attendances:
#             self.day_per_month = 0
#         else:
#             dayofweek = []
#             for attendance in attendances:
#                 if attendance.dayofweek not in dayofweek:
#                     dayofweek.append(attendance.dayofweek)
#             if len(dayofweek) == 5:
#                 self.day_per_month = 22
#             elif len(dayofweek) == 6:
#                 self.day_per_month = 26
#             elif len(dayofweek) == 7:
#                 self.day_per_month = 30
#             else:
#                 self.day_per_month = 0

