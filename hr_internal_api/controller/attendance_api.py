from odoo import http
from odoo.http import request
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model, valid_response_http, \
    invalid_response_http
from pytz import timezone
import pytz


class AttendanceAPI(http.Controller):

    # get current user attendances
    @validate_jwt
    @http.route('/api/get_user_attendances', type="http", auth="none", methods=["get"], csrf=False)
    def get_user_attendances(self, uid, **payload):
        try:
            attendance_model = get_table_model('hr.attendance')
            attendances = attendance_model.search([('employee_id.user_id', '=', uid)])

            present = 0
            absent = 0
            missed_fp = 0
            holiday = 0
            cancel = 0
            val = []
            for attendance in attendances:
                if attendance.state == 'presence':
                    present += 1
                elif attendance.state == 'absence':
                    absent += 1
                elif attendance.state == 'missed':
                    missed_fp += 1
                elif attendance.state == 'holiday':
                    holiday += 1
                elif attendance.state == 'cancel':
                    cancel += 1

                val.append({
                    'id': attendance.id,
                    'employee_id': {
                        'id': attendance.employee_id.id,
                        'name': attendance.employee_id.name,
                    },
                    'date': attendance.punching_day.strftime("%d-%m-%Y") if attendance.punching_day else '',
                    'check_in': attendance.check_in,
                    'check_out': attendance.check_out,
                    'break_in': attendance.break_in,
                    'break_out': attendance.break_out,
                    'worked_hours': attendance.worked_hours,
                    'status': attendance.state,
                    'create_date': attendance.create_date,
                    'create_uid': attendance.create_uid.id,
                    'write_date': attendance.write_date,
                    'write_uid': attendance.write_uid.id,
                })

            data = {
                'present': present,
                'absent': absent,
                'missed_fp': missed_fp,
                'holiday': holiday,
                'cancel': cancel,
                'attendances': val
            }

            return valid_response_http(data=data, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # get current user attendances by date format: yyyy-mm-dd (attendance of the whole day)
    @validate_jwt
    @http.route('/api/get_user_attendances_by_date/<string:date>', type="http", auth="none", methods=["get"],
                csrf=False)
    def get_user_attendances_by_date(self, uid, date, **payload):
        try:
            attendance_model = get_table_model('hr.attendance')
            attendances = attendance_model.search([('employee_id.user_id', '=', uid)])
            user_id = get_table_model('res.users').browse(uid)
            local_tz = pytz.timezone(user_id.tz or 'GMT')
            attendances = attendances.filtered(
                lambda r: r.punching_day and r.punching_day.strftime("%Y-%m-%d") == date)
            val = []
            for attendance in attendances:
                check_in = local_tz.localize(attendance.check_in, is_dst=None)
                val.append({
                    'id': attendance.id,
                    'employee_id': {
                        'id': attendance.employee_id.id,
                        'name': attendance.employee_id.name,
                    },
                    'date': attendance.punching_day.strftime("%d-%m-%Y") if attendance.punching_day else '',
                    'check_in': check_in,
                    'check_out': attendance.check_out,
                    'break_in': attendance.break_in,
                    'break_out': attendance.break_out,
                    'worked_hours': attendance.worked_hours,
                    'status': attendance.state,
                    'create_date': attendance.create_date,
                    'create_uid': attendance.create_uid.id,
                    'write_date': attendance.write_date,
                    'write_uid': attendance.write_uid.id,
                })
            return valid_response_http(data=val, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # get current user attendances by year-month (attendance of the whole month)
    @validate_jwt
    @http.route('/api/get_user_attendances_by_month_year/<string:month_year>', type="http", auth="none",
                methods=["get"], csrf=False)
    def get_user_attendances_by_month_year(self, uid, month_year, **payload):
        try:
            attendance_model = get_table_model('hr.attendance')
            attendances = attendance_model.search([('employee_id.user_id', '=', uid)])
            attendances = attendances.filtered(
                lambda r: r.punching_day and r.punching_day.strftime("%Y-%m") == month_year)

            # get timezone of current employee user
            # tz = attendances.mapped('employee_id.tz')
            # timezone = pytz.timezone(tz[0]) if tz else request.env.user.tz
            # if not timezone:
            #     return invalid_response_http('Timezone not found.', status=400)

            present = 0
            time_off = 0
            absent = 0
            missed = 0
            holiday = 0
            weekend = 0
            cancel = 0
            val = []
            for attendance in attendances:
                if attendance.state == 'presence':
                    present += 1
                elif attendance.state == 'absence':
                    absent += 1
                elif attendance.state == 'time_off':
                    time_off += 1
                elif attendance.state == 'holiday':
                    holiday += 1
                elif attendance.state == 'weekend':
                    weekend += 1
                elif attendance.state == 'missed':
                    missed += 1

                val.append({
                    'id': attendance.id,
                    'employee_id': {
                        'id': attendance.employee_id.id,
                        'name': attendance.employee_id.name,
                    },
                    'date': attendance.punching_day.strftime("%d-%m-%Y") if attendance.punching_day else '',
                    'check_in': attendance.check_in,
                    'check_out': attendance.check_out,
                    'break_in': attendance.break_in,
                    'break_out': attendance.break_out,
                    'worked_hours': attendance.worked_hours,
                    'status': attendance.state,
                    'create_date': attendance.create_date,
                    'create_uid': attendance.create_uid.id,
                    'write_date': attendance.write_date,
                    'write_uid': attendance.write_uid.id,
                })

            data = {
                'present': present,
                'absent': absent,
                'missed_fp': missed,
                'holiday': holiday,
                'cancel': cancel,
                "header": [
                    {
                        "key": "presence",
                        "label": "Present",
                        "value": str(present)
                    },
                    {
                        "key": "absence",
                        "label": "Absent",
                        "value": str(absent)
                    },
                    {
                        "key": "time_off",
                        "label": "On Leave",
                        "value": str(time_off)
                    },
                    {
                        "key": "holiday",
                        "label": "Holiday",
                        "value": str(holiday)
                    },
                    {
                        "key": "weekend",
                        "label": "Weekend",
                        "value": str(weekend)
                    },
                    {
                        "key": "missed",
                        "label": "Missing",
                        "value": str(missed)
                    },
                ],
                'attendances': val
            }
            return valid_response_http(data=data, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    @validate_jwt
    @http.route('/api/attendance', type="http", auth="none", methods=["get"], csrf=False)
    def get_user_attendances(self, uid, **payload):
        try:
            leave_model = get_table_model('hr.attendance')

            domain = [('employee_id.user_id', '=', uid)]
            if payload.get('start_date'):
                domain.append(('punching_day', '>=', payload.get('start_date')))
            if payload.get('end_date'):
                domain.append(('punching_day', '<=', payload.get('end_date')))

            attendances = leave_model.search(domain)

            present = 0
            absent = 0
            missed_fp = 0
            holiday = 0
            cancel = 0
            val = []

            for attendance in attendances:
                if attendance.state == 'presence':
                    present += 1
                elif attendance.state == 'absence':
                    absent += 1
                elif attendance.state == 'missed':
                    missed_fp += 1
                elif attendance.state == 'holiday':
                    holiday += 1
                elif attendance.state == 'cancel':
                    cancel += 1

                val.append({
                    'id': attendance.id,
                    'employee_id': {
                        'id': attendance.employee_id.id,
                        'name': attendance.employee_id.name,
                    },
                    'date': attendance.punching_day.strftime("%d-%m-%Y") if attendance.punching_day else '',
                    'check_in': attendance.check_in,
                    'check_out': attendance.check_out,
                    'break_in': attendance.break_in,
                    'break_out': attendance.break_out,
                    'worked_hours': attendance.worked_hours,
                    'status': attendance.state,
                    'create_date': attendance.create_date,
                    'create_uid': attendance.create_uid.id,
                    'write_date': attendance.write_date,
                    'write_uid': attendance.write_uid.id,
                })

            data = {
                'present': present,
                'absent': absent,
                'missed_fp': missed_fp,
                'holiday': holiday,
                'cancel': cancel,
                'attendances': val
            }
            return valid_response_http(data=data, status=200)

        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)
