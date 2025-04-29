from odoo import models, api, fields
from datetime import datetime, timedelta
from pytz import timezone
import logging
from odoo.tools import format_datetime

_logger = logging.getLogger(__name__)

class ScanQrAttendance(models.Model):
    _name = 'scan.qr.attendance'
    _order = 'date desc'
    _description = "Scan QR Attendance"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    display_name = fields.Char('Display Name')
    employee_id = fields.Many2one('hr.employee', string='Employee', tracking=True)
    attendance_id = fields.Many2one('hr.attendance', string="Attendance")
    resource_calendar_id = fields.Many2one('resource.calendar', string="Working Schedule", tracking=True)
    user_id = fields.Many2one('res.users', string='User')
    partner_id = fields.Many2one('res.partner', related='user_id.partner_id', string="Employee")
    date = fields.Date(string='Date', tracking=True)
    location_id = fields.Many2one('res.partner', string='Working Address', tracking=True)
    project_id = fields.Many2one('project.project', string="Project Code", tracking=True)
    qr_id = fields.Many2one('erp.qr.generate', string="QR Code")
    scan_type = fields.Selection([('check_in', 'Check In'),
                                  ('check_out', 'Check Out'),
                                  ('break_out', 'Break Out'),
                                  ('break_in', 'Break In')], string='Scan Type', tracking=True)
    scan_time = fields.Datetime(string='Scan Time', tracking=True)
    longitude = fields.Float(string="Geo Longitude", copy=False, digits=(10, 14))
    latitude = fields.Float(string="Geo Latitude", copy=False, digits=(10, 14))
    late = fields.Float('Late', compute='_compute_late', store=True, tracking=True)
    description = fields.Html(string="Description")
    late_state = fields.Selection([
        ('good', 'Good'),
        ('late', 'Late'),
        ('missed', 'Missed')
    ], string='Late State', tracking=True)
    status = fields.Selection([
        ('done', 'Done'),
        ('new', 'New'),
        ('skip', 'Skipped')
    ], string='Status', tracking=True)
    day_period = fields.Selection([
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon')
    ], string='Day Period', store=True)

    def _assign_day_period(self):
        print(f"=== _assign_day_period ===")
        for rec in self:
            rec.day_period = False

            if not rec.scan_time or not rec.resource_calendar_id or not rec.scan_type:
                continue

            # Convert scan time to user's local timezone
            scan_time = rec.scan_time.astimezone(
                timezone(self.env.user.partner_id.tz or 'Asia/Phnom_Penh')).replace(tzinfo=None)
            scan_hour = scan_time.hour + scan_time.minute / 60.0

            # Get morning attendance slots from calendar
            calendar = rec.resource_calendar_id
            morning_attendances = calendar.attendance_ids.filtered(lambda a: a.day_period == 'morning')

            if morning_attendances:
                # Filter for current weekday
                weekday = str(scan_time.weekday())  # Monday = 0
                today_morning = morning_attendances.filtered(lambda a: a.dayofweek == weekday)
                morning_end = today_morning[0].hour_to if today_morning else 12.0
                print(f"=== [get] weekday: {weekday}, morning_end: {morning_end}")
            else:
                print("=== [warn] No morning attendance configured, using default morning_end = 12.0")
                morning_end = 12.0

            # Compare scan time to end of morning
            rec.day_period = 'morning' if scan_hour < morning_end else 'afternoon'
            print(f"=== [done] assigned day_period: {rec.day_period}")

    def name_get(self):
        result = []
        for scan in self:
            result.append((scan.id, _("%(empl_name)s from %(date)s") % {
                'empl_name': scan.employee_id.name,
                'date': format_datetime(self.env, scan.date, dt_format=False),
            }))
        return result

    def create(self, val):
        res = super(ScanQrAttendance, self).create(val)
        # Assign day_period
        res._assign_day_period()
        
        res.compute_scan_qr_attendance_late_status()

        # try to create hr.attendance when scan.qr.attendance is created 
        res.create_attendance()

        return res

    @api.depends('scan_time', 'resource_calendar_id')
    def _compute_late(self):
        config_params = self.env['ir.config_parameter'].sudo()
        buffer_minutes = int(config_params.get_param('erp_qr_attendance.late_buffer_duration'))
        checkin_late = config_params.get_param('erp_qr_attendance.is_checkin_late')
        breakout_first = config_params.get_param('erp_qr_attendance.scan_break')
        breakin_late = config_params.get_param('erp_qr_attendance.is_breakin_late')
        checkout_first = config_params.get_param('erp_qr_attendance.is_checkout_early')

        for rec in self:
            rec.late = 0.0
            rec.late_state = 'good'
            attendance_ids = rec.resource_calendar_id.attendance_ids
            morning_attendance = attendance_ids.filtered(lambda x: x.day_period == 'morning')
            afternoon_attendance = attendance_ids.filtered(lambda x: x.day_period == 'afternoon')

            if morning_attendance and afternoon_attendance and rec.scan_time:
                scan_time = rec.scan_time.astimezone(
                    timezone(self.env.user.partner_id.tz or 'GMT')).replace(tzinfo=None)
                scan_date = scan_time.date()

                if rec.scan_type == 'check_in' and checkin_late:
                    schedule_time = timedelta(hours=morning_attendance[0].hour_from)
                elif rec.scan_type == 'break_out' and breakout_first:
                    schedule_time = timedelta(hours=morning_attendance[0].hour_to)
                elif rec.scan_type == 'break_in' and breakin_late:
                    schedule_time = timedelta(hours=afternoon_attendance[0].hour_from)
                elif rec.scan_type == 'check_out' and checkout_first:
                    schedule_time = timedelta(hours=afternoon_attendance[0].hour_to)
                else:
                    continue

                schedule_datetime = datetime.strptime(str(scan_date) + ' ' + str(schedule_time), '%Y-%m-%d %H:%M:%S')
                rec.late = self.calculate_late_in_hours(scan_time, schedule_datetime, rec.scan_type)
                rec.late_state = 'late' if rec.late * 60 > buffer_minutes else 'good'

    def create_attendance(self):
        for rec in self:
            self.env['hr.attendance'].create_attendance(
                date=rec.date,
                employee=rec.employee_id,
                resource_calendar=rec.resource_calendar_id,
                day_period=rec.day_period
            )

    def compute_scan_qr_attendance_late_status(self):
        config_params = self.env['ir.config_parameter'].sudo()
        buffer_minutes = int(config_params.get_param('erp_qr_attendance.late_buffer_duration'))
        checkin_late = config_params.get_param('erp_qr_attendance.is_checkin_late')
        breakout_first = config_params.get_param('erp_qr_attendance.scan_break')
        breakin_late = config_params.get_param('erp_qr_attendance.is_breakin_late')
        checkout_first = config_params.get_param('erp_qr_attendance.is_checkout_early')

        for rec in self:
            employee = self.env['hr.employee'].search([('active', '=', True)], limit=1)

            attendance_ids = employee.resource_calendar_id.attendance_ids
            morning_attendance = attendance_ids.filtered(lambda x: x.day_period == 'morning')
            afternoon_attendance = attendance_ids.filtered(lambda x: x.day_period == 'afternoon')

            if morning_attendance and afternoon_attendance and rec.scan_time:
                scan_time = self.scan_time.astimezone(
                    timezone(self.env.user.partner_id.tz or 'GMT')).replace(tzinfo=None)
                scan_date = scan_time.date()

                if rec.scan_type == 'check_in' and checkin_late:
                    schedule_time = timedelta(hours=morning_attendance[0].hour_from)
                elif rec.scan_type == 'break_out' and breakout_first:
                    schedule_time = timedelta(hours=morning_attendance[0].hour_to)
                elif rec.scan_type == 'break_in' and breakin_late:
                    schedule_time = timedelta(hours=afternoon_attendance[0].hour_from)
                elif rec.scan_type == 'check_out' and checkout_first:
                    schedule_time = timedelta(hours=afternoon_attendance[0].hour_to)
                else:
                    continue

                schedule_datetime = datetime.strptime(str(scan_date) + ' ' + str(schedule_time), '%Y-%m-%d %H:%M:%S')
                rec.late = self.calculate_late_in_hours(scan_time, schedule_datetime, rec.scan_type)
                rec.late_state = 'late' if rec.late * 60 > buffer_minutes else 'good'

    @staticmethod
    def calculate_late_in_hours(scan_time, schedule_time, scan_type):        
        difference = scan_time - schedule_time
        if scan_type in ['check_in', 'break_in']:
            difference = scan_time - schedule_time
        elif scan_type in ['check_out', 'break_out']:
            difference = schedule_time - scan_time

        late_in_hour = difference.total_seconds() / 3600
        return max(late_in_hour, 0)
