import json
import logging

from odoo import http, _
from odoo.addons.hr_internal_api.controller.helper import validate_token, validate_pw_jwt, validate_jwt, \
    get_table_model, \
    valid_response, invalid_response, valid_response_http, invalid_response_http
from odoo.http import request
from datetime import datetime, timedelta
from pytz import timezone

_logger = logging.getLogger(__name__)

class AttendanceScanAPI(http.Controller):

    @validate_jwt
    @http.route('/api/create_scan_attendance', type='json', auth='none', methods=['POST'], csrf=False)
    def create_scan_attendance(self, uid, **payload):
        print("=== [process] create_scan_attendance ===")
        if not payload:
            payload = json.loads(request.httprequest.data)

        tz = request.httprequest.cookies.get('tz') or 'Asia/Bangkok'
        scan_attendance_model = get_table_model('scan.qr.attendance')
        hr_attendance_model = get_table_model('hr.attendance')
        employee = get_table_model('hr.employee').search([('user_id', '=', uid)], limit=1)

        if not employee:
            return invalid_response(type='Not Found', message='Employee not found', status=404)

        location_id = payload.get('location_id')
        scan_type = payload.get('scan_type')
        description = payload.get('description')
        latitude = payload.get('latitude')
        longitude = payload.get('longitude')
        # scan_time = payload.get('scan_time')
        
        if not location_id and employee.restrict_location:
            return invalid_response(type='Bad Request', message='Location ID should not be null.', status=400)
        if not scan_type:
            return invalid_response(type='Bad Request', message='Scan Type should not be null.', status=400)

        location = get_table_model('erp.qr.generate').search([('id', '=', location_id)], limit=1)
        if not location and employee.restrict_location:
            return invalid_response(type='Not Found', message='Work Location not found', status=404)
        
        if location.resource_calendar_id:
            resource_calendar_id = location.resource_calendar_id
        else:
            resource_calendar_id = employee.resource_calendar_id

        user_tz = request.env.user.tz or request.env.context.get('tz')
        scan_time = datetime.now()
        date_today = datetime.now().astimezone(timezone(user_tz)).strftime('%Y-%m-%d')

        # === debuging error
        overtime_model = get_table_model('hr.attendance.overtime')
        overtime = overtime_model.search([
            ('employee_id', '=', employee.id),
            ('date', '=', date_today),
            ('adjustment', '=', False)
        ], limit=1)
        # print("=== overtime: ", overtime)

        if overtime:
            overtime.write({
                'duration': overtime.duration + 0.0,
                'duration_real': overtime.duration_real + 0.0,
            })
        else:
            overtime_model.create({
                'employee_id': employee.id,
                'date': date_today,
                'duration': 0.0,
                'duration_real': 0.0,
                'adjustment': False,
            })
        # === end debuging ===

        # for dev purpose, to input scan_time manually
        # if payload.get('scan_time', False):
        #     scan_time = datetime.strptime(payload.get('scan_time'), '%Y-%m-%d %H:%M:%S')
        #     date_today = scan_time.date()
        #     scan_time = scan_time - timedelta(hours=7)

        attendance = hr_attendance_model.search([
            ('employee_id', '=', employee.id), 
            ('punching_day', '=', date_today)
        ], limit=1, order='create_date desc')
        print(f"=== attendance: {attendance}")

        if attendance:
            # Change default fields (check_in, check_out) to a new fields to avoid conflict:
            # last_check_time = attendance.check_out or attendance.check_in
            last_check_time = attendance.punch_out or attendance.punch_in
            print(f"=== last_check_time: {last_check_time}")

            # find difference in minutes
            if last_check_time:
                time_delta = scan_time - last_check_time
                total_seconds = time_delta.total_seconds()
                minutes = total_seconds / 60

                # TODO: refactor
                checkin_delay = int(request.env['ir.config_parameter'].sudo().get_param('erp_qr_attendance.employee_checkin_delay_in_mn', default=10))
                if minutes < checkin_delay:
                    last_check_time_str = str((last_check_time + timedelta(hours=7)).time())
                    msg = _(f"You already scanned at {last_check_time_str}.")
                    return invalid_response(type='Bad Request', message=msg, status=400)

        scan_attendance_val = {
            'user_id': uid,
            'employee_id': employee.id,
            'resource_calendar_id': resource_calendar_id.id,
            'date': date_today,
            'scan_type': scan_type,
            'scan_time': scan_time,
            'latitude': latitude,
            'longitude': longitude,
            'description': description,
            'late_state': 'good',
            'late': 0.0,
            'status': 'new',
        }

        try:
            scan_attendance_model.create(scan_attendance_val)
            return valid_response(data={'message': 'Submit Request Success'}, status=200)
        except Exception as e:
            _logger.error(e)
            return invalid_response(type='Bad Request', message=str(e), status=400)

    @validate_jwt
    @http.route('/api/check_scan_location', type='json', auth='none', methods=['POST'], csrf=False)
    def check_scan_location(self, uid, **payload):
        print("=== [process] check_scan_location ===")
        if not payload:
            payload = json.loads(request.httprequest.data)

        scan_location = self.get_scan_location(uid, payload.get('latitude'), payload.get('longitude'))
        employee = get_table_model('hr.employee').search([('user_id', '=', uid)], limit=1)

        if scan_location['distance'] > scan_location['radius']:
            if employee.restrict_location:
                return invalid_response(type='Bad Request', message='Your current location is out of range.', status=400)
            else:
                return valid_response(
                    data={'message': "You're out of Range! Input your reference"}, status=200)

        return valid_response(
            data={
                'location_id': scan_location['location_id'],
                'location_name': scan_location['location_name'],
            },
            status=200
        )

    @validate_jwt
    @http.route('/api/check_scan_location_distance', type='json', auth='none', methods=['POST'], csrf=False)
    def attendance_checking_distance(self, uid, **payload):
        print("=== [process] attendance_checking_distance ===")
        if not payload:
            payload = json.loads(request.httprequest.data)

        scan_location = self.get_scan_location(uid, payload.get('latitude'), payload.get('longitude'))
        if scan_location['distance'] > 1000:
            distance = round(scan_location['distance']/1000, 2)
            distance = str(distance)+"Km"
        else:
            distance = round(scan_location['distance'], 2)
            distance = str(distance) + "m"
        message = "You are " + distance + " from "+scan_location['location_name']
        return valid_response(
            data={
                'location_id': scan_location['location_id'],
                'location_name': scan_location['location_name'],
                'distance': scan_location['distance'],
                'message': message,
            },
            status=200
        )

    @staticmethod
    def get_scan_location(uid, latitude, longitude):
        print("=== [process] get_scan_location ===")
        erp_qr_generates = get_table_model('erp.qr.generate').search([])
        employee = get_table_model('hr.employee').search([('user_id', '=', uid)], limit=1)
        if not erp_qr_generates:
            return invalid_response(type='Bad Request', message='Location not found.', status=404)

        if not employee:
            return invalid_response(type='Not Found', message='Employee not found', status=404)

        if not latitude or not longitude:
            return invalid_response(type='Bad Request', message='Lat/Lon should not be null.', status=400)

        scan_locations = []

        for erp_qr_generate in erp_qr_generates:
            scan_locations.append({
                'location_id': erp_qr_generate.id,
                'location_name': erp_qr_generate.name,
                'distance': erp_qr_generate.get_distance(float(latitude), float(longitude)),
                'radius': erp_qr_generate.radius,
            })

        # get the nearest location
        scan_location = min(scan_locations, key=lambda x: x['distance'])

        return scan_location
