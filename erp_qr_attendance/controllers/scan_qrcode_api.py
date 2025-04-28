import base64
import json

from odoo import http, _, fields
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model, valid_response_http, \
    invalid_response_http, valid_response, invalid_response, STATUS_COLORS
from odoo.http import request
from odoo.tools.float_utils import float_compare
from datetime import datetime, timedelta
from pytz import timezone, utc
import werkzeug.wrappers

import logging

_logger = logging.getLogger(__name__)

SCAN_TYPES = {
    'check_in': "Check In",
    'break_out': "Break Out",
    'break_in': "Break In",
    'check_out': "Check Out",
}

class ScanQrcodeAPI(http.Controller):

    # get scan type for attendance
    @validate_jwt
    @http.route('/api/get_attendance_scan_type', type="http", auth="none", methods=["get"], csrf=False)
    def get_attendance_scan_type(self, uid, **payload):
        # if not payload:
        #     payload = json.loads(request.httprequest.data)
        date = payload.get('date')
        if not date:
            date = fields.Date.today()
        dayofweek = date.weekday()
        employee = get_table_model('hr.employee').search([('user_id', '=', uid)], limit=1)
        contract = get_table_model('hr.contract').search([('employee_id', '=', employee.id),
                                                          ('state', '=', 'open')], limit=1)
        attendance_id = get_table_model('hr.attendance').search(
            [('employee_id', '=', employee.id), ('punching_day', '=', date)], limit=1)
        attendance_ids = employee.resource_calendar_id.attendance_ids
        print(f"=== attendance_id: {attendance_id} {attendance_id.break_out}")
        # if not attendance_id:
        #     default = 'check_in'
        # elif attendance_id.punch_in:
        #     default = 'break_out'
        # elif attendance_id.break_out:
        #     default = 'break_in'
        # elif attendance_id.break_in:
        #     default = 'check_out'
        # elif attendance_id.punch_out:
        #     default = 'check_out'

        if not attendance_id:
            default = 'check_in'
        elif attendance_id.punch_in and not attendance_id.break_out:
            default = 'break_out'
        elif attendance_id.break_out and not attendance_id.break_in:
            default = 'break_in'
        elif attendance_id.break_in and not attendance_id.punch_out:
            default = 'check_out'
        else:
            default = 'check_out'
        try:
            response_data = {
                'scan_types': SCAN_TYPES,
                'default': default,
            }
            return valid_response_http(data=response_data, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # get scan type for overtime
    @validate_jwt
    @http.route('/api/get_overtime_scan_type', type="http", auth="none", methods=["get"], csrf=False)
    def get_overtime_scan_type(self, uid, **payload):
        try:
            scan_qr_attendance_model = get_table_model('scan.qr.overtime')
            scan_types = {
                'ot_in': "Overtime In",
                'ot_out': "Overtime Out",
            }
            response_data = {
                'scan_types': scan_types,
                "default": 'ot_in'
            }
            return valid_response_http(data=response_data, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # get scan qr for attendance
    @validate_jwt
    @http.route('/api/get_attendance_scan_logs', type="http", auth="none", methods=["get"], csrf=False)
    def get_attendance_scan_logs(self, uid, **payload):
        try:
            scan_qr_attendance_model = get_table_model('scan.qr.attendance')
            logs = scan_qr_attendance_model.search([('user_id', '=', uid)])
            val = []
            for log in logs:
                val.append({
                    'id': log.id,
                    'scan_type': log.scan_type,
                    'scan_time': log.scan_time,
                    'late_state': log.late_state,
                    'late': log.late,
                })
            
            qr_info = {
                'id': self.id,
                'name': self.name,
                'project_id': self.project_id,
                'longitude': self.longitude,
                'latitude': self.latitude,
                'radius': self.radius,
            }
            
            response_data = {
                'qr_info': qr_info,
                'date': 'Today',
                'scan_list': 'list',
                'scan_types': SCAN_TYPES,
                'default_scan_type': 'check_in',
            }
            return valid_response_http(data=response_data, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # get scan qr for overtime
    @validate_jwt
    @http.route('/api/get_overtime_scan_logs', type="http", auth="none", methods=["get"], csrf=False)
    def get_overtime_scan_logs(self, uid, **payload):
        try:
            scan_qr_overtime_model = get_table_model('scan.qr.overtime')
            logs = scan_qr_overtime_model.search([('user_id', '=', uid)])
            val = []
            for log in logs:
                val.append({
                    'id': log.id,
                    'scan_type': log.scan_type,
                    'scan_time': log.scan_time,
                    'late_state': log.late_state,
                    'late': log.late,
                })
            # response_data = {
            #     # 'date': date,
            #     'data': val,
            # }
            return valid_response_http(data=val, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)


    # create scan qr attendance
    @validate_jwt
    @http.route('/api/create_scan_qr_attendance', type="http", auth="none", methods=["post"], csrf=False)
    def create_scan_qr_attendance(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        scan_qr_attendance_model = get_table_model('scan.qr.attendance')
        erp_qr_generate_model = get_table_model('erp.qr.generate')
        employee = get_table_model('hr.employee').search([('user_id', '=', uid)], limit=1)
        if not employee:
            return invalid_response_http(type='Not Found', message='Employee not found', status=404)

        qr_id = payload.get('qr_id')
        if not qr_id:
            return invalid_response_http(type='Bad Request', message='QR should not be null.', status=400)

        scan_type = payload.get('scan_type')
        scan_time = payload.get('scan_time')
        if not scan_type or not scan_time:
            return invalid_response_http(type='Bad Request', message='Scan Type and Time should not be null.', status=400)

        latitude = payload.get('latitude')
        longitude = payload.get('longitude')
        if not latitude or not longitude:
            return invalid_response_http(type='Bad Request', message='Lat/Lon should not be null.', status=400)

        # Datetime get from payload is the actual, so need to deduct 7 hours for UTC
        scan_time_in_utc = datetime.strptime(scan_time, '%d-%m-%Y %H:%M:%S') - timedelta(hours=7)

        _logger.warning(f'=== {request.env.user.name} scans {scan_type} at {scan_time_in_utc}')

        # Get QR object
        qr_id = erp_qr_generate_model.browse(int(qr_id))

        # prepare value for create
        val = {
            'user_id': uid,
            'employee_id': employee.id,
            'date': fields.Date().today(),
            'location_id': qr_id.location_id.id if qr_id.location_id else False,
            'project_id': qr_id.project_id.id if qr_id.project_id else False,
            'qr_id': qr_id.id if qr_id else False,
            'scan_type': scan_type,
            'scan_time': scan_time_in_utc,
            'latitude': float(latitude),
            'longitude': float(longitude),
            'late_state': 'good',
            'late': 0.0,
            'status': 'new',
        }

        # validate distance
        distance = qr_id.get_distance(float(latitude), float(longitude))
        if distance > qr_id.radius:
            return invalid_response_http(type='Bad Request', message='Your current location is out of range.', status=400)

        try:
            scan_qr_attendance_model.create(val)
        except Exception as e:
            return invalid_response_http(type='Bad Request', message=str(e), status=400)

        res = {
            'message': 'Submit Request Success',
        }
        return valid_response_http(data=res, status=201)

    # create scan qr overtime
    @validate_jwt
    @http.route('/api/create_scan_qr_overtime', type="http", auth="none", methods=["post"], csrf=False)
    def create_scan_qr_overtime(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        scan_qr_overtime_model = get_table_model('scan.qr.overtime')
        erp_qr_generate_model = get_table_model('erp.qr.generate')
        employee = get_table_model('hr.employee').search([('user_id', '=', uid)], limit=1)

        if not employee:
            return invalid_response_http(type='Not Found', message='Employee not found', status=404)

        qr_id = payload.get('qr_id')
        if not qr_id:
            return invalid_response_http(type='Bad Request', message='QR should not be null.', status=400)

        latitude = payload.get('latitude')
        longitude = payload.get('longitude')
        if not latitude or not longitude:
            return invalid_response_http(type='Bad Request', message='Lat/Lon should not be null.', status=400)

        scan_type = payload.get('scan_type')
        scan_time = payload.get('scan_time')
        if not scan_type or not scan_time:
            return invalid_response_http(type='Bad Request', message='Scan Type and Time should not be null.', status=400)

        # Datetime get from payload is the actual, so need to deduct 7 hours for UTC
        scan_time_in_utc = datetime.strptime(scan_time, '%d-%m-%Y %H:%M:%S') - timedelta(hours=7)

        # Get QR object
        qr_id = erp_qr_generate_model.browse(int(qr_id))

        # prepare value for create
        val = {
            'user_id': uid,
            'employee_id': employee.id,
            'date': fields.Date().today(),
            'location_id': qr_id.location_id.id if qr_id.location_id else False,
            'project_id': qr_id.project_id.id if qr_id.project_id else False,
            'qr_id': qr_id.id if qr_id else False,
            'scan_type': scan_type,
            'scan_time': scan_time_in_utc,
            'longitude': float(longitude),
            'latitude': float(latitude),
            'late_state': 'good',
            'late': 0.0,
            'status': 'new',
        }

        # validate distance
        distance = qr_id.get_distance(float(latitude), float(longitude))
        if distance > qr_id.radius:
            return invalid_response_http(type='Bad Request', message='Your current location is out of range.', status=400)

        try:
            scan_qr = scan_qr_overtime_model.create(val)
        except Exception as e:
            return invalid_response_http(type='Bad Request', message=str(e), status=400)

        # return response
        res = {
            'id': scan_qr.id,
            'message': 'Submit Request Success',
            'name': scan_qr.employee_id.name
        }

        return valid_response_http(data=res, status=201)

    # scan attendance
    @validate_jwt
    @http.route('/api/scan_attendance', type="json", auth="none", methods=["post"], csrf=False)
    def scan_attendance(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        uuid = payload.get('uuid')
        latitude = payload.get('latitude')
        longitude = payload.get('longitude')

        # get current scan time
        scan_time = datetime.now() + timedelta(hours=7)

        # for dev purpose, to input scan_time manually
        # if payload.get('scan_time', False):
        #     scan_time = datetime.strptime(payload.get('scan_time'), '%Y-%m-%d %H:%M:%S')

        # to get current date correctly, aware scan_time is needed (+7 hours)
        current_date = scan_time.date()

        user_tz = request.env.user.tz or request.env.context.get('tz')
        qr_id = get_table_model('erp.qr.generate').search([('qr_code_uuid', '=', uuid)])
        user = get_table_model('res.users').search([('id', '=', uid)])

        employee = get_table_model('hr.employee').search([('user_id', '=', uid)], limit=1)
        if not employee:
            return invalid_response(type='Not Found', message='Employee not found', status=404)

        # validate distance
        distance = qr_id.get_distance(float(latitude), float(longitude))
        if distance > qr_id.radius and user.restrict_location:
            return invalid_response(type='Bad Request', message="Your current location is out of range.", status=400)

        resource_calendar = qr_id.resource_calendar_id or employee.resource_calendar_id
        if not resource_calendar:
            return invalid_response(type='Not Found', message="Working Schedule not found.", status=404)

        # prepare scan logs
        logs = get_table_model('scan.qr.attendance').search([
            ('user_id', '=', uid), 
            ('date', '=', current_date),
            ('status', '=', 'done')])
        
        scan_list = [{
            'id': log.id,
            'scan_type': log.scan_type,
            'scan_time': log.scan_time.astimezone(timezone(user_tz)),   # `scan_time` was stored as UTC, so need to display based on User Timezone
            'late_state': log.late_state,
            'late': log.late,
        } for log in logs]

        # +-----------------------------------------------------------------------------+
        # |     Below is logic to identify for which Scan Type should be returned.      |
        # +-----------------------------------------------------------------------------+

        attendances = get_table_model('hr.attendance').search([
            ('employee_id', '=', employee.id),
            ('punching_day', '=', current_date)])

        is_morning_done = attendances.filtered(lambda x: x.day_period == 'morning' and x.check_in != False and x.check_out != False)
        is_afternoon_done = attendances.filtered(lambda x: x.day_period == 'afternoon' and x.check_in != False and x.check_out != False)

        # whether the current scan time far from `Work to` of morning
        end_of_morning = resource_calendar._is_end_of_session(scan_time, 'morning')

        # check_in: when no attendances for current_date yet and found that current scan is not ended yet for morning session 
        if not attendances and not end_of_morning:
            default_scan_type = 'check_in'

        # break_out: 
        # - when morning attendance not yet `check_out`
        elif attendances.filtered(lambda x: x.day_period == 'morning' and x.check_out == False):
            default_scan_type = 'break_out'
        
        # break_in: 
        # - when morning attendance has already done the scan, but not having the afternoon attendance yet.
        # - when found that current scan is ended for morning session and no attendances for current_date yet.
        # (case for employee start working in the afternoon only)
        elif is_morning_done and not attendances.filtered(lambda x: x.day_period == 'afternoon') or (end_of_morning and not attendances):
            default_scan_type = 'break_in'

        # check_out: 
        # - when afternoon attendance not yet `check_out` 
        # - when afternoon attendance has already done the scan.
        elif attendances.filtered(lambda x: x.day_period == 'afternoon' and x.check_out == False) or is_afternoon_done:
            default_scan_type = 'check_out'

        # +---------------------+
        # |         END         |
        # +---------------------+
        
        response_data = {
            'qr_info': qr_id.get_qr_info(),
            'date': current_date,
            'scan_list': scan_list,
            'scan_types': SCAN_TYPES,
            'default_scan_type': default_scan_type,
            'message': 'Make sure you are inside the correct range location',
        }
        _logger.info(f'===scan_attendance: {response_data}')
        return valid_response(data=response_data, status=200)
    
    # scan overtime
    @validate_jwt
    @http.route('/api/scan_overtime', type="json", auth="none", methods=["post"], csrf=False)
    def scan_overtime(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        uuid = payload.get('uuid')
        latitude = payload.get('latitude')
        longitude = payload.get('longitude')

        # get objects
        user_tz = request.env.user.tz or request.env.context.get('tz')
        date_today = fields.Date().today()
        qr_id = get_table_model('erp.qr.generate').search([('qr_code_uuid', '=', uuid)])
        logs = get_table_model('scan.qr.overtime').search([('user_id', '=', uid), ('date', '=', date_today)])

        # validate distance
        distance = qr_id.get_distance(float(latitude), float(longitude))
        if distance > qr_id.radius:
            return invalid_response(type='Bad Request', message="Your current location is out of range.", status=400)

        scan_list = []
        is_overtime_in = False
        is_overtime_out = False
        default_scan_type = 'ot_in'

        for log in logs:
            if log.scan_type == 'ot_in':
                is_overtime_in = True
            
            if log.scan_type == 'ot_out':
                is_overtime_out = True
            
            # Now `scan_time` was stored as UTC, so need to display based on User Timezone
            user_scan_time = log.scan_time.astimezone(timezone(user_tz))

            scan_list.append({
                'id': log.id,
                'scan_type': log.scan_type,
                'scan_time': user_scan_time,
                'late_state': log.late_state,
                'late': log.late,
            })

        # default scan_type
        if not logs:
            default_scan_type = 'ot_in'

        if is_overtime_in and not is_overtime_out:
            default_scan_type = 'ot_out'
        
        if is_overtime_in and is_overtime_out:
            default_scan_type = 'ot_out'
            # raise werkzeug.exceptions.BadRequest("You already done scan overtime for today!")
        
        scan_type = {
            'ot_in': "Overtime In",
            'ot_out': "Overtime Out",
        }
        
        response_data = {
            'qr_info': qr_id.get_qr_info(),
            'date': date_today,
            'scan_list': scan_list,
            'scan_type': scan_type,
            'default_scan_type': default_scan_type,
            'message': 'Make sure you are inside the correct range location',
        }
        return valid_response(data=response_data, status=200)
    