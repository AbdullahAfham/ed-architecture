from odoo import api, fields, models, _
from datetime import datetime, timedelta, time

import pytz
from dateutil.relativedelta import relativedelta
from odoo.addons.resource.models.utils import float_to_time
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _name = 'hr.attendance'
    _inherit = ['hr.attendance', 'mail.thread', 'mail.activity.mixin']

    punching_day = fields.Date(string='Date')
    check_in = fields.Datetime(string="Check In", default=False, required=False, tracking=True)
    check_out = fields.Datetime(string="Check Out", tracking=True)
    break_out = fields.Datetime(string="Break Out")
    break_in = fields.Datetime(string="Break In")
    punch_break_out = fields.Datetime(string="Scan Break Out", readonly=True)
    punch_break_in = fields.Datetime(string="Scan Break In", readonly=True)
    punch_in = fields.Datetime(string="Scan In", readonly=True)
    punch_out = fields.Datetime(string="Scan Out", readonly=True)
    shift_check_in = fields.Float(string="Shift Checkin", index=True,
                                  help="A specific value of 24:00 is interpreted as 23:59:59.999999.")
    shift_check_out = fields.Float(string="Shift Checkout", index=True,
                                   help="A specific value of 24:00 is interpreted as 23:59:59.999999.")
    shift_break_in = fields.Float(string="Shift Breakin", index=True,
                                  help="A specific value of 24:00 is interpreted as 23:59:59.999999.")
    shift_break_out = fields.Float(string="Shift Breakout", index=True,
                                   help="A specific value of 24:00 is interpreted as 23:59:59.999999.")
    late_num = fields.Integer('Late Count', compute='_compute_late_duration', store=True, readonly=True)
    late_duration = fields.Float('Late Duration', compute='_compute_late_duration', store=True, readonly=True)
    state = fields.Selection([
        ('absence', 'Absent'),
        ('missed', 'Missed Scan'),
        ('annual_leave', 'AL'),
        ('sick_leave', 'SL'),
        ('maternity_leave', 'ML'),
        ('special_leave', 'SP'),
        ('unpaid_leave', 'L'),
        ('time_off', 'Time Off'),
        ('holiday', 'Public Holiday'),
        ('weekend', 'Weekend'),
        ('presence', 'Present'),
        ('cancel', 'Cancelled'),
        ], string='State', required=True, default='absence', tracking=True)
    
    day_period = fields.Selection([
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon')], string='Day Period')
    work_schedule_id = fields.Many2one('resource.calendar', string='Work Schedule', store=True)
    missed_count = fields.Integer('Missed Count', readonly=True)
    project_id = fields.Many2one('project.project', string="Project Code")
    project_manager_id = fields.Many2one('res.users', string="Project Manager", related='project_id.user_id', store=True)

    line_ids = fields.One2many('scan.qr.attendance', 'attendance_id', string='Scan Lines', store=True, readonly=True)
    leave_ids = fields.One2many('hr.leave', 'attendance_id', string='Leaves', store=True, readonly=True)

    def write(self, vals):
        res = super().write(vals)

        # update `check_out` to be the same as mentioning fields
        if any(field in vals for field in ['break_out', 'punch_break_out']):
            scan_time = vals.get('break_out') or vals.get('punch_break_out')
            self.check_out = scan_time

        return res

    # def _is_morning_scan(self):
    #     """ return true for cases that considered to be morning. """

    #     if self.punch_in and not self.punch_break_in:
    #         return True

    # def _is_afternoon_scan(self):
    #     """ return true for cases that considered to be afternoon. """

    #     if self.punch_break_in and not self.punch_in:
    #         return True

    # def _assign_day_period(self, scan_log):
    #     """ 
    #     This table represents which punch type is considered to be `CHECK IN` or `CHECK OUT` for certain day_period.

    #                     CHECK IN            CHECK OUT       
    #                 +-------------------+-------------------+
    #     Morning     |   punch_in        |   punch_break_out |
    #                 +-------------------+-------------------|
    #     Afternoon   |   punch_break_in  |   punch_out       |
    #                 +-------------------+-------------------+

    #     """
    #     for attend in self:
    #         # convert scan time to float
    #         current_scan_time = str((scan_log.scan_time + timedelta(hours=7)).time())
    #         hour, minute, second = current_scan_time.split(':')
    #         current_scan_time_float = float(hour) + float(minute) / 60.0

    #         # in case the user scan check_in from afternoon (no morning session)
    #         scan_for_afternoon = current_scan_time_float > attend.shift_break_out

    #         if attend._is_afternoon_scan() or scan_for_afternoon:
    #             attend.day_period = 'afternoon'
    #         elif attend._is_morning_scan():
    #             attend.day_period = 'morning'
    #         else:
    #             attend.day_period = ''

    def _assign_day_period(self, period=None):
        """ Update day_period in `self` if day_period provided.
        Otherwise, find the matching period of the check_in float time within working schedule.

        :param: day_period: either `morning` or `afternoon`
        :return: None
        """
        if period:
            self.day_period = period

        # day_period in `self` is already set
        if self.check_in and self.day_period:
            return
        
        # to get weekday correctly, aware check_in is needed (+7 hours)
        check_in = self.check_in + timedelta(hours=7)

        # for create attendance manually, either `work_schedule_id` or `calendar_id` need to defined
        calendar = self.work_schedule_id or self.calendar_id

        # find out whether an aware `check_in` is already ended or not
        end_of_morning = calendar._is_end_of_session(check_in, 'morning')
        
        self.day_period = 'afternoon' if end_of_morning else 'morning'

    def action_view(self):
        # search scan logs records
        for attendance in self:
            scan_qr_logs = self.env['scan.qr.attendance'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('date', '=', attendance.punching_day),
            ], order='scan_time desc')
            attendance.line_ids = scan_qr_logs

        action = self.env.ref('erp_qr_attendance.action_scan_qr_attendance')
        result = action.read()[0]
        result.pop('id', None)
        result['context'] = {}
        result['domain'] = [('id', 'in', self.line_ids.ids)]
        line_ids = len(self.line_ids)
        if line_ids == 1:
            res = self.env.ref('erp_qr_attendance.scan_qr_attendance_form_view', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = self.line_ids[0].id
        return result

    def action_view_leaves(self):
        # search leave records
        for attendance in self:
            leaves = self.env['hr.leave'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('date_from', '<=', attendance.punching_day),
                ('date_to', '>=', attendance.punching_day),
            ])
            attendance.leave_ids = leaves
        
        action = self.env.ref('hr_holidays.hr_leave_action_action_approve_department')
        result = action.read()[0]
        result.pop('id', None)
        result['context'] = {}
        result['domain'] = [('id', 'in', self.leave_ids.ids)]        
        if len(self.leave_ids) == 1:
            res = self.env.ref('hr_holidays.hr_leave_view_form_manager', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = self.leave_ids[0].id
        
        return result

    @api.depends('check_in', 'check_out', 'break_in', 'break_out')
    def _compute_worked_hours(self):
        for attendance in self:
            breaktime = timedelta()
            if attendance.break_out and attendance.break_in:
                breaktime = attendance.break_in - attendance.break_out

            if attendance.check_out and attendance.check_in:
                delta = attendance.check_out - attendance.check_in
                if breaktime:
                    delta -= breaktime
                attendance.worked_hours = delta.total_seconds() / 3600.0
            else:
                attendance.worked_hours = False

    @api.depends('check_in', 'check_out', 'break_in', 'break_out')
    def _compute_late_amount(self):
        config_params = self.env['ir.config_parameter'].sudo()
        buffer_minutes = int(config_params.get_param('erp_qr_attendance.late_buffer_duration'))
        checkin_late = config_params.get_param('erp_qr_attendance.is_checkin_late')
        breakout_first = config_params.get_param('erp_qr_attendance.scan_break')
        breakin_late = config_params.get_param('erp_qr_attendance.is_breakin_late')
        checkout_first = config_params.get_param('erp_qr_attendance.is_checkout_early')

        for attendance in self:
            late_num = 0

            if not attendance.employee_id:
                continue

            contract = self.env['hr.contract'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('state', '=', 'open')
                ], limit=1)

            attendance_ids = contract.resource_calendar_id.attendance_ids
            morning_attendance = attendance_ids.filtered(lambda x: x.day_period == 'morning')
            afternoon_attendance = attendance_ids.filtered(lambda x: x.day_period == 'afternoon')

            if morning_attendance and afternoon_attendance:
                if attendance.check_in and checkin_late:
                    late_num += self._calculate_late(
                        attendance.check_in, morning_attendance[0].hour_from, buffer_minutes, 'check_in')
                if attendance.break_out and breakout_first:
                    late_num += self._calculate_late(
                        attendance.break_out, morning_attendance[0].hour_to, buffer_minutes, 'break_out')
                if attendance.break_in and breakin_late:
                    late_num += self._calculate_late(
                        attendance.break_in, afternoon_attendance[0].hour_from, buffer_minutes, 'break_in')
                if attendance.check_out and checkout_first:
                    late_num += self._calculate_late(
                        attendance.check_out, afternoon_attendance[0].hour_to, buffer_minutes, 'check_out')

            attendance.late_num = late_num

    @api.depends('check_in', 'check_out', 'break_in', 'break_out')
    def _compute_late_duration(self):
        for rec in self:
            late_duration = 0.0
            late_count = 0

            scan_qr_logs = self.env['scan.qr.attendance'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('date', '=', rec.punching_day),
            ], order='scan_time desc')

            for line in scan_qr_logs:
                if line.late_state == 'late':
                    if rec.day_period == 'morning' and line.scan_type in ['check_in', 'break_out']:
                        late_duration += line.late
                        late_count += 1
                    elif rec.day_period == 'afternoon' and line.scan_type in ['break_in', 'check_out']:
                        late_duration += line.late
                        late_count += 1

            rec.late_num = late_count
            rec.late_duration = late_duration

            print(f"=== after late_count: {late_count}, late_duration: {late_duration}")

    @staticmethod
    def _calculate_late(scan_time, schedule_hour, buffer_minutes, scan_type):
        scan_time_local = pytz.utc.localize(scan_time) + timedelta(hours=7)
        scan_date = scan_time_local.date()
        schedule_time = timedelta(hours=schedule_hour)
        schedule_datetime = datetime.strptime(str(scan_date) + ' ' + str(schedule_time), '%Y-%m-%d %H:%M:%S')
        schedule_datetime_utc = pytz.utc.localize(schedule_datetime)
        difference = scan_time_local - schedule_datetime_utc

        if scan_type in ['check_in', 'break_in']:
            difference = scan_time_local - schedule_datetime_utc
        elif scan_type in ['check_out', 'break_out']:
            difference = schedule_datetime_utc - scan_time_local
        late_in_minutes = difference.total_seconds() / 60

        return 1 if late_in_minutes > buffer_minutes else 0

    # def create_attendance(self, date, employee, resource_calendar):
    #     # Assign default values for shift times
    #     shift_check_in = shift_check_out = shift_break_in = shift_break_out = 0.0
    #     resource_calendar_id = resource_calendar

    #     domain = [('employee_id', '=', employee.id), ('status', '=', 'new')]

    #     # Handle cross-day shifts
    #     if resource_calendar_id.is_cross_day_shift:
    #         date_now = datetime.now().astimezone(pytz.timezone(employee.tz))
    #         shift_start_hour = min(resource_calendar_id.attendance_ids.mapped("hour_from"), default=0.0)

    #         if date_now.hour < shift_start_hour:
    #             date -= timedelta(days=1)

    #         domain += [
    #             ('scan_time', '>=', datetime.strptime(str(date), '%Y-%m-%d').replace(hour=12, minute=0, second=0)),
    #             ('scan_time', '<=', datetime.strptime(str(date), '%Y-%m-%d').replace(hour=11, minute=59, second=59) + timedelta(days=1))
    #         ]
    #     else:
    #         domain += [('date', '=', date)]

    #     dayofweek = date.weekday()

    #     # Find morning and afternoon shifts for the given weekday
    #     working_hours = resource_calendar_id.attendance_ids.filtered(
    #         lambda att: str(dayofweek) == str(att.dayofweek)
    #     )

    #     morning_shift = working_hours.filtered(lambda att: att.day_period == 'morning')
    #     afternoon_shift = working_hours.filtered(lambda att: att.day_period == 'afternoon')
    #     if morning_shift:
    #         shift_check_in, shift_check_out = morning_shift.hour_from, morning_shift.hour_to
    #     elif afternoon_shift:
    #         shift_check_in, shift_check_out = afternoon_shift.hour_from, afternoon_shift.hour_to

    #     # Find existing attendance records
    #     attendances = self.env['hr.attendance'].search([
    #         ('employee_id', '=', employee.id),
    #         ('punching_day', '=', date)
    #     ])

    #     # flag true if both attendances for morning and afternoon are found
    #     is_done = all([session in attendances.mapped('day_period') for session in ['morning', 'afternoon']])

    #     # true if attendance in the morning is done
    #     is_morning_done = attendances.filtered(lambda x: x.day_period == 'morning' and x.check_in != False and x.check_out != False)
        
    #     # Check if both morning and afternoon attendance already exist
    #     # is_done = all(session in attendances.mapped('day_period') for session in ['morning', 'afternoon'])

    #     # Find attendance to be updated (if necessary)
    #     attendance_rec = None
    #     if not is_done:
    #         attendance_rec = attendances.filtered(lambda x: not x.check_out)

    #     afternoon_attendance = attendances.filtered(lambda x: x.day_period == 'afternoon')
    #     if afternoon_attendance.exists():
    #         # Always update check_out for afternoon attendance
    #         attendance_rec = afternoon_attendance

    #     # Create attendance if not found
    #     if not attendance_rec and not is_done and len(attendances) <= 2:
    #         attendance_rec = self.env['hr.attendance'].create({
    #             'employee_id': employee.id,
    #             'punching_day': date,
    #             'work_schedule_id': resource_calendar_id.id,
    #             'shift_check_in': shift_check_in,
    #             'shift_check_out': shift_check_out,
    #             'shift_break_in': shift_break_in,
    #             'shift_break_out': shift_break_out,
    #             'state': 'absence',
    #         })

    #     # Update attendance record based on day_period
    #     if attendance_rec:
    #         _logger.info(f"=== day_period: {attendance_rec.day_period}")
    #         if attendance_rec.day_period == 'morning':
    #             attendance_rec.write({
    #                 'shift_check_in': morning_shift.hour_from,
    #                 'shift_check_out': morning_shift.hour_to
    #             })
    #         elif attendance_rec.day_period == 'afternoon':
    #             attendance_rec.write({
    #                 'shift_check_in': afternoon_shift.hour_from,
    #                 'shift_check_out': afternoon_shift.hour_to
    #             })

    #     # Fetch scan logs for the employee
    #     scan_logs = self.env['scan.qr.attendance'].search(domain)

    #     # Process scan records
    #     for rec in scan_logs:
    #         if rec.scan_type == 'check_in':
    #             print(f"=== scan type: check_in")
    #             self._process_check_in(rec, attendance_rec)
    #         elif rec.scan_type == 'check_out':
    #             self._process_check_out(rec, attendance_rec)
    #         elif rec.scan_type == 'break_out':
    #             self._process_break_out(rec, attendance_rec)
    #         elif rec.scan_type == 'break_in':
    #             self._process_break_in(rec, attendance_rec)

    #     # determine day_period of attendance
    #     if is_morning_done:
    #         attendance_rec._assign_day_period(period='afternoon')
    #     else:
    #         attendance_rec._assign_day_period()

    #     return attendance_rec



    def create_attendance(self, date, employee, resource_calendar, day_period):
        print(f"=== create_attendance: {date}, {employee.name}, period: {day_period}")
        shift_check_in = shift_check_out = shift_break_in = shift_break_out = 0.0
        resource_calendar_id = resource_calendar

        domain = [('employee_id', '=', employee.id), ('status', '=', 'new')]

        if resource_calendar_id.is_cross_day_shift:
            date_now = datetime.now().astimezone(pytz.timezone(employee.tz))
            shift_start_hour = min(resource_calendar_id.attendance_ids.mapped("hour_from"), default=0.0)

            if date_now.hour < shift_start_hour:
                date -= timedelta(days=1)

            domain += [
                ('scan_time', '>=', datetime.strptime(str(date), '%Y-%m-%d').replace(hour=12, minute=0, second=0)),
                ('scan_time', '<=', datetime.strptime(str(date), '%Y-%m-%d').replace(hour=11, minute=59, second=59) + timedelta(days=1))
            ]
        else:
            domain += [('date', '=', date)]

        dayofweek = date.weekday()

        working_hours = resource_calendar_id.attendance_ids.filtered(
            lambda att: str(dayofweek) == str(att.dayofweek)
        )

        morning_shift = working_hours.filtered(lambda att: att.day_period == 'morning')
        afternoon_shift = working_hours.filtered(lambda att: att.day_period == 'afternoon')

        if day_period == 'morning' and morning_shift:
            shift_check_in, shift_check_out = morning_shift.hour_from, morning_shift.hour_to
        elif day_period == 'afternoon' and afternoon_shift:
            shift_check_in, shift_check_out = afternoon_shift.hour_from, afternoon_shift.hour_to

        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', employee.id),
            ('punching_day', '=', date)
        ])
        print(f"=== attendances: {attendances}")

        attendance_rec = attendances.filtered(lambda a: a.day_period == day_period)
        if not attendance_rec:
            # Assign default check-in/out based on day_period
            check_in = check_out = False
            if day_period == 'morning' and morning_shift:
                check_in = datetime.combine(date, float_to_time(morning_shift.hour_from)) - timedelta(hours=7)
                check_out = datetime.combine(date, float_to_time(morning_shift.hour_to)) - timedelta(hours=7)
                print(f"=== [get] - 'morning' {check_in}, {check_out}")
            elif day_period == 'afternoon' and afternoon_shift:
                check_in = datetime.combine(date, float_to_time(afternoon_shift.hour_from)) - timedelta(hours=7)
                check_out = datetime.combine(date, float_to_time(afternoon_shift.hour_to)) - timedelta(hours=7)
                print(f"=== [get] - 'afternoon' {check_in}, {check_out}")

            attendance_rec = self.env['hr.attendance'].create({
                'employee_id': employee.id,
                'punching_day': date,
                'work_schedule_id': resource_calendar_id.id,
                'shift_check_in': shift_check_in,
                'shift_check_out': shift_check_out,
                'shift_break_in': shift_break_in,
                'shift_break_out': shift_break_out,
                'day_period': day_period,
                'check_in': check_in,
                'check_out': check_out,
                'state': 'absence',
            })

        scan_logs = self.env['scan.qr.attendance'].search(domain)
        print(f"=== logs: {scan_logs}")

        # for rec in scan_logs:
        #     if rec.scan_type == 'check_in':
        #         self._process_check_in(rec, attendance_rec)
        #     elif rec.scan_type == 'check_out':
        #         self._process_check_out(rec, attendance_rec)

        # attendance_rec.day_period = day_period
        # print(f"=== [done] created attendance: {attendance_rec.day_period}")
        # return attendance_rec

        # Process scan records
        for rec in scan_logs:
            if rec.scan_type == 'check_in':
                print(f"=== type: {rec.scan_type}")
                self._process_check_in(rec, attendance_rec)
            elif rec.scan_type == 'check_out':
                print(f"=== type: {rec.scan_type}")
                self._process_check_out(rec, attendance_rec)
            elif rec.scan_type == 'break_out':
                print(f"=== type: {rec.scan_type}")
                self._process_break_out(rec, attendance_rec)
            elif rec.scan_type == 'break_in':
                print(f"=== type: {rec.scan_type}")
                self._process_break_in(rec, attendance_rec)

        attendance_rec.day_period = day_period
        print(f"=== [done] created attendance: {attendance_rec.day_period}")
        return attendance_rec

    @staticmethod
    def _process_check_in(rec, attendance_rec):
        print(f"=== att: {attendance_rec}")
        if not attendance_rec.punch_in and not attendance_rec.punch_out:
            attendance_rec.write({
                # 'check_in': rec.scan_time,
                'punch_in': rec.scan_time,
                'project_id': rec.project_id.id,
                'project_manager_id': rec.project_id.user_id and rec.project_id.user_id.id or False,
                'state': 'missed'
            })
            attendance_rec.update_scan_qr_attendance_status(rec)

        elif not attendance_rec.punch_in and attendance_rec.punch_out:
            if attendance_rec.punch_out > rec.scan_time:
                attendance_rec.write({
                    # 'check_in': rec.scan_time,
                    'punch_in': rec.scan_time,
                    'project_id': rec.project_id.id,
                    'project_manager_id': rec.project_id.user_id and rec.project_id.user_id.id or False,
                    'state': 'presence'
                })
                attendance_rec.update_scan_qr_attendance_status(rec)
            else:
                rec.status = 'skip'

        elif attendance_rec.punch_in and attendance_rec.punch_in > rec.scan_time:
            attendance_rec.write({
                # 'check_in': rec.scan_time,
                'punch_in': rec.scan_time,
                'project_id': rec.project_id.id,
                'project_manager_id': rec.project_id.user_id and rec.project_id.user_id.id or False,
                'state': attendance_rec.check_out and 'presence' or 'missed'
            })
            attendance_rec.update_scan_qr_attendance_status(rec)
        else:
            rec.status = 'skip'

    @staticmethod
    def _process_check_out(rec, attendance_rec):
        scan_date = rec.scan_time.date()
        attendance_date = attendance_rec.punching_day

        # prevent early check_out
        if attendance_rec.work_schedule_id.scan_interval:
            # hour in float
            check_out_hour = attendance_rec.shift_check_out - attendance_rec.work_schedule_id.scan_interval

            # convert scan time to float
            current_scan_time = str((rec.scan_time + timedelta(hours=7)).time())
            hour, minute, second = current_scan_time.split(':')
            current_scan_time_float = float(hour) + float(minute) / 60.0

            if current_scan_time_float < check_out_hour:
                rec.status = 'skip'

                msg = ':'.join(str(timedelta(hours=check_out_hour)).split(':')[:2])
                raise UserError(_(f"Check Out can be scanned from {msg}"))

        if scan_date == attendance_date:
            if attendance_rec.punch_in and not attendance_rec.punch_out:
                if attendance_rec.punch_in < rec.scan_time:
                    attendance_rec.write({
                        'check_out': rec.scan_time,
                        'punch_out': rec.scan_time,
                        'state': 'presence'
                    })
                    attendance_rec.update_scan_qr_attendance_status(rec)
                else:
                    rec.status = 'skip'

            elif attendance_rec.punch_in and attendance_rec.punch_out and attendance_rec.punch_out < rec.scan_time:
                attendance_rec.write({
                    'check_out': rec.scan_time,
                    'punch_out': rec.scan_time,
                    'state': 'presence'
                })
                attendance_rec.update_scan_qr_attendance_status(rec)

            elif not attendance_rec.punch_in and attendance_rec.punch_out and attendance_rec.punch_out < rec.scan_time:
                attendance_rec.write({
                    'check_out': rec.scan_time,
                    'punch_out': rec.scan_time,
                    'state': 'missed'
                })
                attendance_rec.update_scan_qr_attendance_status(rec)

            elif not attendance_rec.punch_in and not attendance_rec.punch_out:
                attendance_rec.write({
                    'check_out': rec.scan_time,
                    'punch_out': rec.scan_time,
                    'state': 'missed'
                })
                attendance_rec.update_scan_qr_attendance_status(rec)
            else:
                rec.status = 'skip'
        else:
            _logger.warning(f'check out between different date -> {scan_date} and {attendance_date}')
            rec.status = 'skip'

    @staticmethod
    def _process_break_out(rec, attendance_rec):
        """ `break_out` is considered to be `check_out` for the morning shift. """

        # prevent early break_out
        if attendance_rec.work_schedule_id.scan_interval:
            # hour in float
            break_out_hour = attendance_rec.shift_break_out - attendance_rec.work_schedule_id.scan_interval

            # convert scan time to float
            current_scan_time = str((rec.scan_time + timedelta(hours=7)).time())
            hour, minute, second = current_scan_time.split(':')
            current_scan_time_float = float(hour) + float(minute) / 60.0

            if current_scan_time_float < break_out_hour:
                rec.status = 'skip'

                msg = ':'.join(str(timedelta(hours=break_out_hour)).split(':')[:2])
                raise UserError(_(f"Break Out can be scanned from {msg}"))
        
        if not attendance_rec.break_out:
            attendance_rec.write({
                'break_out': rec.scan_time,
                'punch_break_out': rec.scan_time,
                'punch_out': rec.scan_time,
                'state': 'presence'
            })
            attendance_rec.update_scan_qr_attendance_status(rec)

        elif attendance_rec.break_out and attendance_rec.break_out < rec.scan_time:
            attendance_rec.write({
                'break_out': rec.scan_time,
                'punch_break_out': rec.scan_time,
                'punch_out': rec.scan_time,
                'state': 'presence'
            })
            attendance_rec.update_scan_qr_attendance_status(rec)
        else:
            rec.status = 'skip'

    @staticmethod
    def _process_break_in(rec, attendance_rec):
        """ `break_in` is considered to be `check_in` for the afternoon shift. """
        if not attendance_rec.break_in:
            attendance_rec.write({
                'break_in': rec.scan_time,
                'punch_break_in': rec.scan_time,
                'punch_in': rec.scan_time,
                'state': 'missed'
            })
            attendance_rec.update_scan_qr_attendance_status(rec)

        elif attendance_rec.break_in and attendance_rec.break_in > rec.scan_time:
            attendance_rec.write({
                'break_in': rec.scan_time,
                'punch_break_in': rec.scan_time,
                'punch_in': rec.scan_time,
                'state': 'missed'
            })
            attendance_rec.update_scan_qr_attendance_status(rec)
        else:
            rec.status = 'skip'

    def update_scan_qr_attendance_status(self, rec):
            rec.status = 'done'

            to_skip_scan_logs = self.env['scan.qr.attendance'].search([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('date', '=', rec.date),
                ('scan_type', '=', rec.scan_type),
            ])
            to_skip_scan_logs.write({'status': 'skip'})

    def update_attendance_status(self):
        date = (datetime.now() + relativedelta(hours=+7)).date()
        _logger.info(f"=== Update Attendance status: {date}")   
        dayofweek = date.weekday()

        employees = self.env['hr.employee'].search([('active', '=', True)])
        _logger.info(f"=== total: {len(employees)}")

        for employee in employees:
            attendances = self._get_employee_attendance(employee, date)
            if not attendances:
                continue
            
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open')
            ], limit=1)
            _logger.info(f"=== contract: {contract}, {employee.name}")

            morning_attendance = attendances.filtered(lambda a: a.day_period == 'morning')[:1]
            afternoon_attendance = attendances.filtered(lambda a: a.day_period == 'afternoon')[:1]
            # _logger.info(f"=== emp: {employee.name}, att: {attendances}")

            # Check if it's a holiday
            if self._holiday_exists(date):
                attendances.write({'state': 'holiday'})
                _logger.info(f"=== holiday applied for {employee.name}")
                continue

            # Check if there are working hours for the day
            working_hours_exists = any(
                attendance.dayofweek == str(dayofweek) for attendance in employee.resource_calendar_id.attendance_ids)            

            # counter for weekdays
            # if not working_hours_exists:
            #     attendances.write({'state': 'weekend'})
            #     _logger.info(f"=== weekend")
            #     continue

            # Check for time off
            time_off = self._time_off_exists(employee, date)
            if time_off:
                attendances.write({'state': time_off.holiday_status_id.attendance_state or 'time_off'})
                _logger.info(f"=== leave: {time_off}, -> time off or leave type")
                continue

            # Check for weekend
            working_hours = self._get_working_hours(employee, dayofweek)
            if not working_hours:
                attendances.write({'state': 'weekend'})
                _logger.info(f"=== no working day: {working_hours}, -> weekend")
                continue

            # Contract validation
            # if not contract or (contract.date_start and contract.date_start > date) or (contract.date_end and contract.date_end < date):
            #     if attendances:
            #         # attendances.write({'state': 'cancel'})
            #         attendances.write({'state': 'absence'})
            #         _logger.info(f"=== {employee.name} -> No valid contract -> absence")
            #     continue

            half_day_leave = self._get_half_day_leave(employee, date)
            is_cross_day = employee.resource_calendar_id.is_cross_day_shift
            is_single_shift = len(working_hours) == 1

            # Handling attendance updates
            if is_single_shift:
                _logger.info("=== single shift")
                attendances.write({'state': self.attendance_single_shift_missing_check(attendances)})
                attendances.filtered(lambda a: a.state == 'missed').write({'missed_count': attendances.missed_count + 1})

            elif is_cross_day:
                _logger.info("=== cross-day shift")
                attendances.write({'state': self.attendance_single_shift_missing_check(attendances)})
                attendances.filtered(lambda a: a.state == 'missed').write({'missed_count': attendances.missed_count + 1})

            elif half_day_leave and len(working_hours) == 2:
                _logger.info("=== half-day leave")
                
                # Determine leave period (morning or afternoon)
                leave_period = 'afternoon' if half_day_leave.request_date_from_period == 'am' else 'morning'
                
                # Fetch the attendance state based on the holiday status of the leave
                leave_state = half_day_leave.holiday_status_id.attendance_state or 'time_off'
                
                # Update attendance state based on the leave period
                if leave_period == 'morning' and morning_attendance:
                    morning_attendance.write({'state': leave_state})
                elif leave_period == 'afternoon' and afternoon_attendance:
                    afternoon_attendance.write({'state': leave_state})

            else:
                _logger.info("=== full-day shift")
                for attendance in [morning_attendance, afternoon_attendance]:
                    if attendance:
                        attendance.write({'state': self.attendance_half_shift_missing_check(attendance)})
                        if attendance.state == 'missed':
                            attendance.write({'missed_count': attendance.missed_count + 1})

    def manual_update_attendance_status(self, date, employees=None):     
        date = date or fields.Date.today()
        _logger.info(f"=== Manual update status: {date}")   
        dayofweek = date.weekday()

        employees = employees or self.env['hr.employee'].search([
            ('active', '=', True),
            ('company_id', '=', self.env.company.id)
        ])
        _logger.info(f"=== total: {len(employees)}")

        for employee in employees:
            attendances = self._get_employee_attendance(employee, date)
            if not attendances:
                continue

            contract = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open')
            ], limit=1)
            _logger.info(f"=== contract: {contract}, {employee.name}")

            morning_attendance = attendances.filtered(lambda a: a.day_period == 'morning')[:1]
            afternoon_attendance = attendances.filtered(lambda a: a.day_period == 'afternoon')[:1]
            # _logger.info(f"=== emp: {employee.name}, att: {attendances}")
            
            # 1. Check if it's a holiday
            if self._holiday_exists(date):
                attendances.write({'state': 'holiday'})
                _logger.info(f"=== holiday applied for {employee.name}")
                continue

            # 2. Check for time off
            time_off = self._time_off_exists(employee, date)
            print("=== time_off: ", time_off)
            if time_off:
                attendances.write({'state': time_off.holiday_status_id.attendance_state or 'time_off'})
                _logger.info(f"=== leave: {time_off}, -> time off or leave type")
                continue

            # 3. Check for weekend
            working_hours = self._get_working_hours(employee, dayofweek)
            if not working_hours:
                attendances.write({'state': 'weekend'})
                _logger.info(f"=== no working day: {working_hours}, -> weekend")
                continue

            # 4. Contract validation
            # if not contract or (contract.date_start and contract.date_start > date) or (contract.date_end and contract.date_end < date):
            #     if attendances:
            #         # attendances.write({'state': 'cancel'})
            #         attendances.write({'state': 'absence'})
            #         _logger.info(f"=== {employee.name} -> No valid contract -> absence")
            #     continue

            half_day_leave = self._get_half_day_leave(employee, date)
            is_cross_day = employee.resource_calendar_id.is_cross_day_shift
            is_single_shift = len(working_hours) == 1

            # Handling attendance updates
            if is_single_shift:
                _logger.info("=== single shift")
                attendances.write({'state': self.attendance_single_shift_missing_check(attendances)})
                attendances.filtered(lambda a: a.state == 'missed').write({'missed_count': attendances.missed_count + 1})

            elif is_cross_day:
                _logger.info("=== cross-day shift")
                attendances.write({'state': self.attendance_single_shift_missing_check(attendances)})
                attendances.filtered(lambda a: a.state == 'missed').write({'missed_count': attendances.missed_count + 1})

            elif half_day_leave and len(working_hours) == 2:
                _logger.info("=== half-day leave")
                
                # Determine leave period (morning or afternoon)
                leave_period = 'afternoon' if half_day_leave.request_date_from_period == 'am' else 'morning'
                
                # Fetch the attendance state based on the holiday status of the leave
                leave_state = half_day_leave.holiday_status_id.attendance_state or 'time_off'
                
                # Update attendance state based on the leave period
                if leave_period == 'morning' and morning_attendance:
                    morning_attendance.write({'state': leave_state})
                elif leave_period == 'afternoon' and afternoon_attendance:
                    afternoon_attendance.write({'state': leave_state})

            else:
                _logger.info("=== full-day shift")
                for attendance in [morning_attendance, afternoon_attendance]:
                    if attendance:
                        attendance.write({'state': self.attendance_half_shift_missing_check(attendance)})
                        if attendance.state == 'missed':
                            attendance.write({'missed_count': attendance.missed_count + 1})

    # def pre_create_attendance(self):
    #     date = (datetime.now() + relativedelta(hours=+7)).date()
    #     _logger.info(f"=== Pre create attendance: {date}")

    #     dayofweek = date.weekday()
    #     employees = self.env['hr.employee'].search([('active', '=', True)])           
    #     holiday = self._holiday_exists(date)

    #     for employee in employees:
    #         shift_check_in = shift_check_out = shift_break_in = shift_break_out = 0.0
    #         attendance_exists = self._attendance_exists(employee, date)
    #         contract = self.env['hr.contract'].search([
    #             ('employee_id', '=', employee.id),
    #             ('state', '=', 'open'),
    #         ], limit=1)

    #         _logger.info(f"=== calender: {employee.name}, {employee.resource_calendar_id}")
                
    #         # attendance_ids = contract.resource_calendar_id.attendance_ids
    #         working_hours = self._get_working_hours(employee, dayofweek)
    #         if attendance_exists:
    #             continue

    #         if len(working_hours) == 2:
    #             for calendar_attendance in employee.resource_calendar_id.attendance_ids.filtered(
    #                     lambda att: str(dayofweek) == str(att.dayofweek)):
    #                 if calendar_attendance.day_period == 'morning':
    #                     shift_check_in = calendar_attendance.hour_from
    #                     shift_break_out = calendar_attendance.hour_to
    #                 elif calendar_attendance.day_period == 'afternoon':
    #                     shift_break_in = calendar_attendance.hour_from
    #                     shift_check_out = calendar_attendance.hour_to
    #         if len(working_hours) == 1:
    #             for calendar_attendance in employee.resource_calendar_id.attendance_ids.filtered(
    #                     lambda att: str(dayofweek) == str(att.dayofweek)):
    #                 shift_check_in = calendar_attendance.hour_from
    #                 shift_check_out = calendar_attendance.hour_to
    #         time_off = self._time_off_exists(employee, date)

    #         working_hours_exists = any(
    #             attendance.dayofweek == str(dayofweek) for attendance in employee.resource_calendar_id.attendance_ids)

    #         # attendance_state = 'absence'
    #         # if not contract:
    #         #     attendance_state = 'cancel'
    #         # elif not working_hours_exists:
    #         #     attendance_state = 'weekend'
    #         # elif time_off:
    #         #     attendance_state = time_off.holiday_status_id.attendance_state \
    #         #         if time_off.holiday_status_id.attendance_state else 'time_off'
    #         # elif holiday:
    #         #     attendance_state = 'holiday'

    #         attendance_state = 'absence'
    #         # if not contract:
    #         #     attendance_state = 'cancel'
    #         if holiday:
    #             attendance_state = 'holiday'
    #         elif time_off:
    #             attendance_state = time_off.holiday_status_id.attendance_state or 'time_off'
    #         elif not working_hours_exists:
    #             attendance_state = 'weekend'

    #         self.env['hr.attendance'].create({
    #             'employee_id': employee.id,
    #             # 'project_id': employee.project_id and employee.project_id.id or False,
    #             # 'project_manager_id': employee.project_id.user_id and employee.project_id.user_id.id or False,
    #             'work_schedule_id': employee.resource_calendar_id and employee.resource_calendar_id.id or False,
    #             'punching_day': date,
    #             'shift_check_in': shift_check_in,
    #             'shift_check_out': shift_check_out,
    #             'shift_break_in': shift_break_in,
    #             'shift_break_out': shift_break_out,
    #             'check_in': False,
    #             'state': attendance_state
    #         })

    def pre_create_attendance(self):
        """
        Automatically generates two attendance records (morning and afternoon)
        based on employee's work schedule.
        """
        user_tz = self.env.user.tz or 'UTC'
        date = fields.Date.today()
        dayofweek = date.weekday()
        employees = self.env['hr.employee'].search([('active', '=', True)])
        holiday = self._holiday_exists(date)

        for employee in employees:
            attendance_exists = self._attendance_exists(employee, date)
            if attendance_exists:
                continue

            calendar = employee.resource_calendar_id
            if not calendar:
                continue

            attendance_ids = calendar.attendance_ids.filtered(
                lambda a: str(a.dayofweek) == str(dayofweek)
            )

            morning_shift = attendance_ids.filtered(lambda a: a.day_period == 'morning')
            afternoon_shift = attendance_ids.filtered(lambda a: a.day_period == 'afternoon')

            # Skip if no shift at all
            if not morning_shift and not afternoon_shift:
                continue

            # Determine attendance state
            attendance_state = 'absence'
            if holiday:
                attendance_state = 'holiday'
            elif not attendance_ids:
                attendance_state = 'weekend'
            elif self._time_off_exists(employee, date):
                attendance_state = 'time_off'
            
            # Convert to UTC
            def local_to_utc(float_hour):
                local_dt = datetime.combine(date, time(int(float_hour), int((float_hour % 1) * 60)))
                return local_dt - timedelta(hours=7)

            # Create morning attendance
            if morning_shift:
                self.env['hr.attendance'].create({
                    'employee_id': employee.id,
                    'punching_day': date,
                    'day_period': 'morning',
                    'work_schedule_id': calendar.id,
                    'shift_check_in': morning_shift[0].hour_from,
                    'shift_check_out': morning_shift[0].hour_to,
                    'check_in': local_to_utc(morning_shift[0].hour_from),
                    'check_out': local_to_utc(morning_shift[0].hour_to),
                    'state': attendance_state,
                })

            # Create afternoon attendance
            if afternoon_shift:
                self.env['hr.attendance'].create({
                    'employee_id': employee.id,
                    'punching_day': date,
                    'day_period': 'afternoon',
                    'work_schedule_id': calendar.id,
                    'shift_check_in': afternoon_shift[0].hour_from,
                    'shift_check_out': afternoon_shift[0].hour_to,
                    'check_in': local_to_utc(afternoon_shift[0].hour_from),
                    'check_out': local_to_utc(afternoon_shift[0].hour_to),
                    'state': attendance_state,
                })

    def manual_pre_create_attendance(self, date, employees=None):
        date = date or fields.Date.today()
        _logger.info(f"=== Manual Pre Create Attendnace: {date}")   
        dayofweek = date.weekday()

        employees = employees or self.env['hr.employee'].search([
            ('active', '=', True),
            ('company_id', '=', self.env.company.id)
        ])
        _logger.info(f"=== total: {len(employees)}")

        holiday = self._holiday_exists(date)

        for employee in employees:
            shift_check_in = shift_check_out = shift_break_in = shift_break_out = 0.0

            if self._attendance_exists(employee, date):
                continue

            contract = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open')
            ], order="date_start desc", limit=1)

            # Get calendar from employee profile
            attendance_ids = self.env['resource.calendar.attendance'].search([
                ('calendar_id', '=', employee.resource_calendar_id.id),
                ('dayofweek', '=', str(dayofweek))
            ])

            if len(attendance_ids) == 2:
                for att in attendance_ids:
                    if att.day_period == 'morning':
                        shift_check_in = att.hour_from
                        shift_break_out = att.hour_to
                    elif att.day_period == 'afternoon':
                        shift_break_in = att.hour_from
                        shift_check_out = att.hour_to
            elif len(attendance_ids) == 1:
                shift_check_in = attendance_ids.hour_from
                shift_check_out = attendance_ids.hour_to

            time_off = self._time_off_exists(employee, date)

            attendance_state = 'absence'
            # if not contract:
            #     attendance_state = 'cancel'
            if holiday:
                attendance_state = 'holiday'
            elif time_off:
                attendance_state = time_off.holiday_status_id.attendance_state or 'time_off'
            elif not attendance_ids:
                attendance_state = 'weekend'
            _logger.info(f"=== create attendance for {employee.name} -> {attendance_state}")

            self.env['hr.attendance'].create({
                'employee_id': employee.id,
                'work_schedule_id': employee.resource_calendar_id.id if employee.resource_calendar_id else False,
                'punching_day': date,
                'shift_check_in': shift_check_in,
                'shift_check_out': shift_check_out,
                'shift_break_in': shift_break_in,
                'shift_break_out': shift_break_out,
                'check_in': False,
                'state': attendance_state
            })

    def create_absent_attendance(self):
        """
        Create absence attendance records for employees who do not have attendance recorded for the current date.
        If an existing attendance record has no `day_period`, update it instead of creating a new one.
        """
        date = (datetime.now() + relativedelta(hours=7)).date()
        _logger.info(f"=== Create Absent Attendance: {date}")
        dayofweek = date.weekday()

        # Fetch active employees
        employees = self.env['hr.employee'].search([('active', '=', True)])           

        for employee in employees:
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open')
            ], limit=1)

            attendances = self._get_employee_attendance(employee, date)
            
            # Get working hours for the current day
            working_hours = employee.resource_calendar_id.attendance_ids.filtered(
                lambda att: str(att.dayofweek) == str(dayofweek)
            )

            # Contract validation
            # if not contract or (contract.date_start and contract.date_start > date) or (contract.date_end and contract.date_end < date):
            #     if attendances:
            #         attendances.write({'state': 'cancel'})
            #     _logger.info(f"=== {employee.name} -> No valid contract -> cancel")
            #     continue
            
            # 1. Check if it's a holiday
            if self._holiday_exists(date):
                attendances.write({'state': 'holiday'})
                _logger.info(f"=== holiday applied for {employee.name}")
                continue

            # 2. Check for time off
            time_off = self._time_off_exists(employee, date)
            if time_off:
                if attendances:
                    attendances.write({'state': time_off.holiday_status_id.attendance_state or 'time_off'})
                _logger.info(f"=== {employee.name} -> On leave: {time_off.holiday_status_id.name}")
                continue

            # 3. Skip if no working hours exist (i.e., weekends)
            if not working_hours:
                if attendances:
                    attendances.write({'state': 'weekend'})
                _logger.info(f"=== {employee.name} has no working hours today -> weekend")
                continue

            no_period_attendances = attendances.filtered(lambda x: not x.day_period)

            # Process morning and afternoon shifts
            for shift in ['morning', 'afternoon']:
                shift_hours = working_hours.filtered(lambda att: att.day_period == shift)
                if not shift_hours or attendances.filtered(lambda x: x.day_period == shift):
                    continue

                shift_data = {
                    'shift_check_in': shift_hours.hour_from,
                    'shift_check_out': shift_hours.hour_to,
                    'state': 'absence',
                    'day_period': shift,
                }

                # Update existing attendance without `day_period`, otherwise create a new record
                if no_period_attendances:
                    no_period_attendances[0].write(shift_data)
                    no_period_attendances = no_period_attendances[1:]
                else:
                    self.env['hr.attendance'].create({
                        'employee_id': employee.id, 
                        'punching_day': date,
                        'work_schedule_id': employee.resource_calendar_id.id, 
                        **shift_data
                    })

    def manual_create_absent_attendance(self, date, employees=None):
        """
        Create absence attendance records for employees who do not have attendance recorded for the current date.
        If an existing attendance record has no `day_period`, update it instead of creating a new one.
        """
        if date:
            date = date
        else:
            date = fields.Date.today()
        _logger.info(f"=== Manual Create Absent Attendance: {date}")
        dayofweek = date.weekday()

        # Check if today is a holiday
        holiday = self._holiday_exists(date)

        employees = employees or self.env['hr.employee'].search([
            ('active', '=', True),
            ('company_id', '=', self.env.company.id)
        ])
        _logger.info(f"=== total: {len(employees)}")

        for employee in employees:
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open')
            ], limit=1)

            attendances = self._get_employee_attendance(employee, date)
            
            # Get working hours for the current day
            working_hours = employee.resource_calendar_id.attendance_ids.filtered(
                lambda att: str(att.dayofweek) == str(dayofweek)
            )

            # 1. Check for holiday
            if holiday:
                if attendances:
                    attendances.write({'state': 'holiday'})
                _logger.info(f"=== Holiday exists, skipping attendance check")
                continue

            # Contract validation
            # if not contract or (contract.date_start and contract.date_start > date) or (contract.date_end and contract.date_end < date):
            #     if attendances:
            #         attendances.write({'state': 'cancel'})
            #     _logger.info(f"=== {employee.name} -> No valid contract -> cancel")
            #     continue

            # Skip if no working hours exist (i.e., weekends)
            if not working_hours:
                if attendances:
                    attendances.write({'state': 'weekend'})
                _logger.info(f"=== {employee.name} has no working hours today -> weekend")
                continue

            # Check for time off
            time_off = self._time_off_exists(employee, date)
            if time_off:
                if attendances:
                    attendances.write({'state': time_off.holiday_status_id.attendance_state or 'time_off'})
                _logger.info(f"=== {employee.name} -> On leave: {time_off.holiday_status_id.name}")
                continue

            no_period_attendances = attendances.filtered(lambda x: not x.day_period)

            # Process morning and afternoon shifts
            for shift in ['morning', 'afternoon']:
                shift_hours = working_hours.filtered(lambda att: att.day_period == shift)
                if not shift_hours or attendances.filtered(lambda x: x.day_period == shift):
                    continue

                shift_data = {
                    'shift_check_in': shift_hours.hour_from,
                    'shift_check_out': shift_hours.hour_to,
                    'state': 'absence',
                    'day_period': shift,
                }

                # Update existing attendance without `day_period`, otherwise create a new record
                if no_period_attendances:
                    no_period_attendances[0].write(shift_data)
                    no_period_attendances = no_period_attendances[1:]
                else:
                    self.env['hr.attendance'].create({
                        'employee_id': employee.id, 
                        'punching_day': date,
                        'work_schedule_id': employee.resource_calendar_id.id, 
                        **shift_data
                    })

    def _holiday_exists(self, date):
        return self.env['resource.calendar.leaves'].search_count([
            ('date_from', '<=', date),
            ('date_to', '>=', date),
            ('resource_id', '=', False),
        ]) > 0

    def _get_holiday(self, date):
        return self.env['resource.calendar.leaves'].search([
            ('date_from', '<=', date),
            ('date_to', '>=', date),
            ('resource_id', '=', False),
        ], limit=1)

    def _attendance_exists(self, employee, date):
        return self.env['hr.attendance'].search_count([
            ('employee_id', '=', employee.id),
            ('punching_day', '=', date)
        ]) > 0

    def _get_employee_attendance(self, employee, date):
        punching_day = date
        if employee.resource_calendar_id.is_cross_day_shift:
            punching_day = fields.Date.to_string(fields.Datetime.from_string(date) - timedelta(days=1))
        return self.env['hr.attendance'].search([
            ('employee_id', '=', employee.id),
            ('punching_day', '=', punching_day),
        ], limit=2)

    def _time_off_exists(self, employee, date):
        return self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ['validate1', 'validate']),
            ('date_from', '<=', date),
            ('date_to', '>=', date),
            ('number_of_days', '>=', 1)
        ], limit=1)

    def _get_half_day_leave(self, employee, date):
        return self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ['validate1', 'validate']),
            ('date_from', '<=', date),
            ('date_to', '>=', date),
            ('number_of_days', '=', 0.5),
        ], limit=1)

    @staticmethod
    def _get_working_hours(employee, dayofweek):
        return employee.resource_calendar_id.attendance_ids.filtered(
            lambda r: r.dayofweek == str(dayofweek)
        )

    @staticmethod
    def attendance_single_shift_missing_check(attendance):
        attendance_fields = [attendance.check_in, attendance.check_out]
        if any(field is False for field in attendance_fields) and not all(
                field is False for field in attendance_fields):
            return 'missed'
        elif all(field for field in attendance_fields):
            return 'presence'
        return attendance.state

    # @staticmethod
    # def attendance_half_shift_missing_check(attendance, day_period):
    #     if day_period == 'morning':
    #         attendance_fields = [attendance.check_in, attendance.break_out]
    #     else:
    #         attendance_fields = [attendance.break_in, attendance.check_out]

    #     if any(field is False for field in attendance_fields):
    #         return 'missed'
    #     elif all(field for field in attendance_fields):
    #         return 'presence'
    #     return attendance.state

    @staticmethod
    def attendance_half_shift_missing_check(attendance):
        """
        This function checks the attendance status based on the check-in and check-out fields.
        
        Conditions:
        1. If both check-in and check-out are blank (None or False), return 'absence'.
        2. If at least one of the check-in or check-out fields is blank (None or False), return 'missed'.
        3. If both check-in and check-out are filled with values, return 'presence'.
        
        Default:
        If none of the above conditions apply, return the current state of the attendance.
        """
        attendance_fields = [attendance.check_in, attendance.check_out]
        
        if not any(field for field in attendance_fields):
            return 'absence'
        elif any(field is False for field in attendance_fields):
            return 'missed'
        elif all(field for field in attendance_fields):
            return 'presence'
        
        return attendance.state
    
    @staticmethod
    def attendance_full_shift_missing_check(attendance):
        attendance_fields = [attendance.check_in, attendance.break_out, attendance.break_in, attendance.check_out]
        if any(field is False for field in attendance_fields) and not all(
                field is False for field in attendance_fields):
            return 'missed'
        elif all(field for field in attendance_fields):
            return 'presence'
        return attendance.state

    def create_missing_scan_time_off(self, working_hour):
        for rec in self:
            config_params = self.env['ir.config_parameter'].sudo()
            missing_create_time_off = config_params.get_param('erp_qr_attendance.missing_create_time_off')
            missing_time_off_type_id = int(config_params.get_param('erp_qr_attendance.missing_time_off_type_id'))

            if not missing_create_time_off or rec.state != 'missed':
                continue

            request_date_from_period = 'pm' if working_hour.day_period == 'afternoon' else 'am'
            time_off_type = self.env['hr.leave.type'].browse(missing_time_off_type_id)
            responsible_id = time_off_type.responsible_id.id if time_off_type.responsible_id else self.env.uid
            date_from = datetime.combine(rec.punching_day, float_to_time(working_hour.hour_from)) - timedelta(hours=7)
            date_to = datetime.combine(rec.punching_day, float_to_time(working_hour.hour_to)) - timedelta(hours=7)

            if responsible_id:
                self = self.with_user(responsible_id)

            if rec.employee_id.resource_calendar_id.is_night_shift:
                if not self.check_in:
                    request_date_from_period = 'am'
                    date_to = date_from + timedelta(hours=4)
                else:
                    request_date_from_period = 'pm'
                    date_from = date_to - timedelta(hours=4)

            existing_leave = self.env['hr.leave'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('request_date_from', '=', rec.punching_day),
                ('request_date_from_period', '=', request_date_from_period),
            ], limit=1)

            if existing_leave:
                continue

            leave_vals = {
                'employee_id': rec.employee_id.id,
                'holiday_status_id': missing_time_off_type_id,
                'date_from': date_from,
                'date_to': date_to,
                'request_date_from': rec.punching_day,
                'request_date_from_period': request_date_from_period,
                'request_unit_half': True,
                'name': 'Missing Scan Time Off',
                'number_of_days': 0.5,
                'number_of_hours_text': 4,
                'attendance_id': rec.id,
                'state': 'confirm',
            }
            leave = self.env['hr.leave'].create(leave_vals)
            leave.action_validate()

    def create_absence_time_off(self, from_working_hour, to_working_hour):
        for rec in self:
            config_params = self.env['ir.config_parameter'].sudo()
            absence_create_time_off = config_params.get_param('erp_qr_attendance.absence_create_time_off')
            absence_time_off_type_id = int(config_params.get_param('erp_qr_attendance.absence_time_off_type_id'))

            if not absence_create_time_off or rec.state != 'absence':
                continue

            time_off_type = self.env['hr.leave.type'].browse(absence_time_off_type_id)
            responsible_id = time_off_type.responsible_id.id if time_off_type.responsible_id else self.env.uid
            date_from = datetime.combine(rec.punching_day, float_to_time(from_working_hour.hour_from)) - timedelta(
                hours=7)
            date_to = datetime.combine(rec.punching_day, float_to_time(to_working_hour.hour_to)) - timedelta(hours=7)

            if responsible_id:
                self = self.with_user(responsible_id)

            existing_leave = self.env['hr.leave'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('request_date_from', '=', rec.punching_day),
            ], limit=1)

            if existing_leave:
                continue

            leave_vals = {
                'employee_id': rec.employee_id.id,
                'holiday_status_id': absence_time_off_type_id,
                'date_from': date_from,
                'date_to': date_to,
                'request_date_from': rec.punching_day,
                'request_date_to': rec.punching_day,
                'request_unit_half': False,
                'name': 'Absence Time Off',
                'number_of_days': 1,
                'number_of_hours_text': 8,
                'attendance_id': rec.id,
                'state': 'confirm',
            }
            leave = self.env['hr.leave'].create(leave_vals)
            leave.action_validate()
