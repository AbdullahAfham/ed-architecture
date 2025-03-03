import base64
import json

from odoo import http, _
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model, valid_response_http, \
    invalid_response_http, STATUS_COLORS
from odoo.addons.hr_internal_api.controller.send_notification import send_notification
from odoo.http import request
from odoo.tools.float_utils import float_compare
from datetime import datetime, timedelta
import pytz

import logging

_logger = logging.getLogger(__name__)


class LeaveAPI(http.Controller):

    # get current user leaves
    @validate_jwt
    @http.route('/api/leave', type="http", auth="none", methods=["get"], csrf=False)
    def get_user_leaves(self, uid, **payload):
        try:
            leave_model = get_table_model('hr.leave')

            domain = [('employee_id.user_id', '=', uid)]
            if payload.get('start_date'):
                domain.append(('request_date_from', '>=', payload.get('start_date')))
            if payload.get('end_date'):
                domain.append(('request_date_from', '<=', payload.get('end_date')))
            # split the state parameter by commas to handle multiple states
            if payload.get('state'):
                states = payload.get('state').split(',')
                domain.append(('state', 'in', states))

            leaves = leave_model.search(domain)

            val = [self._prepare_leave(leave, uid) for leave in leaves]
            val.sort(key=lambda x: x.get('create_date'), reverse=True)

            return valid_response_http(data=val, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # get my team leaves
    @validate_jwt
    @http.route('/api/team/leave', type="http", auth="none", methods=["get"], csrf=False)
    def get_my_team_leave(self, uid, **payload):
        try:
            leave_model = get_table_model('hr.leave')
                        
            domain = [('employee_id.parent_id.user_id', '=', uid)]
            if payload.get('start_date'):
                domain.append(('request_date_from', '>=', payload.get('start_date')))
            if payload.get('end_date'):
                domain.append(('request_date_from', '<=', payload.get('end_date')))
            if payload.get('state'):
                states = payload.get('state').split(',')
                domain.append(('state', 'in', states)) 
        
            leaves = leave_model.search(domain)

            val = [self._prepare_leave(leave, uid) for leave in leaves]
            val.sort(key=lambda x: x.get('create_date'), reverse=True)

            return valid_response_http(data=val, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # create leave request
    @validate_jwt
    @http.route('/api/leave', type="http", auth="none", methods=["post"], csrf=False)
    def create_leave(self, uid, **payload):
        try:
            if not payload:
                payload = json.loads(request.httprequest.data)

            employee = get_table_model('hr.employee').search([('user_id', '=', uid)], limit=1)
            if not employee:
                return invalid_response_http(type='Not Found', message='Employee not found', status=404)

            leave_type_id = payload.get('leave_type_id')
            leave_type = get_table_model('hr.leave.type').search([('id', '=', leave_type_id)], limit=1)
            documents = request.httprequest.files.getlist('documents')

            if not leave_type_id:
                return invalid_response_http(type='Bad Request', message='Leave Type cannot be null', status=400)
            if not leave_type:
                return invalid_response_http(type='Not Found', message='Leave Type not found', status=404)
            if not employee.resource_calendar_id:
                return invalid_response_http(type='Bad Request', message='Working Schedule is not set', status=400)

            # get working schedule
            working_schedule = get_table_model('resource.calendar.attendance').search(
                [('calendar_id', '=', employee.resource_calendar_id.id)])
            working_days = dict(working_schedule._fields['dayofweek'].selection)
            working_period = dict(working_schedule._fields['day_period'].selection)

            # validate not null date_from and date_to
            request_date_from, request_date_to = payload.get('date_from'), payload.get('date_to')
            if not request_date_from or not request_date_to:
                return invalid_response_http(type='Bad Request', message='Start Date/End Date cannot be null',
                                             status=400)

            # leave request for half day
            request_unit_half = bool(payload.get('half_day') == 'true')
            request_date_from_period = 'Morning' if payload.get('date_period', 'am') == 'am' else 'Afternoon'

            # request half day, or with specific duration
            if request_unit_half and request_date_from_period:
                # parse requested date from str (both the same as requesting for half day)
                from_datetime = to_datetime = datetime.strptime(request_date_from, "%Y-%m-%d")

                # validate requested date and requested period based on working schedule
                from_weekday = to_weekday = working_schedule.filtered(
                    lambda r: working_days.get(r.dayofweek) == from_datetime.strftime("%A") and working_period.get(
                        r.day_period) == request_date_from_period
                )
            else:
                # parse requested date from str
                from_datetime = datetime.strptime(request_date_from, "%Y-%m-%d")
                to_datetime = datetime.strptime(request_date_to, "%Y-%m-%d")

                # validate both requested date are working days based on working schedule
                from_weekday = working_schedule.filtered(
                    lambda r: working_days.get(r.dayofweek) == from_datetime.strftime("%A"))
                to_weekday = working_schedule.filtered(
                    lambda r: working_days.get(r.dayofweek) == to_datetime.strftime("%A"))

            _logger.warning('===Done Checking Period===')

            if not from_weekday or not to_weekday:
                return invalid_response_http(type='Bad Request',
                                             message='Request Date is not valid based on Working Schedule', status=400)

            # get hours in UTC
            hour_from = min(from_weekday.mapped('hour_from')) - 7.0
            hour_to = max(to_weekday.mapped('hour_to')) - 7.0

            # Now we can set time for `Start Date` and `End Date` which correspond to working schedule/hours
            from_datetime = from_datetime + timedelta(hours=hour_from)
            to_datetime = to_datetime + timedelta(hours=hour_to)

            _logger.warning('===Done Setting Time===')

            # constraint for setting 2 time off on the same day
            leave_model = get_table_model('hr.leave')
            domain = [
                ('date_from', '<', to_datetime.strftime("%Y-%m-%d %H:%M:%S")),
                ('date_to', '>', from_datetime.strftime("%Y-%m-%d %H:%M:%S")),
                ('employee_id', '=', employee.id),
                ('state', 'not in', ['cancel', 'refuse']),
            ]

            # in case of update, not count this `leave_id` which was passed from client side
            leave_id = payload.get('id')
            if leave_id:
                domain.append(('id', '!=', leave_id))

            nb_holidays = leave_model.search_count(domain)
            if nb_holidays:
                return invalid_response_http(
                    type='Bad Request',
                    message='You can not set 2 time off that overlaps on the same day for ''the same employee.',
                    status=400
                )

            _logger.warning('===2 Time Off constraint was passed===')

            # constraint for insufficient duration
            # TODO: This one need to update, as of now it checks for 0.0 days only
            if leave_type.requires_allocation == 'yes':
                mapped_days = leave_type.sudo().get_employees_days([employee.id], from_datetime.date())
                leave_days = mapped_days[employee.id][leave_type.id]

                if float_compare(leave_days['remaining_leaves'], 0.0, precision_digits=2) == 0 or float_compare(
                        leave_days['virtual_remaining_leaves'], 0.0, precision_digits=2) == 0:
                    return invalid_response_http(
                        type='Bad Request',
                        message='The number of remaining time off is not sufficient for this time off type.\n'
                                'Please also check the time off waiting for validation.',
                        status=400)

            _logger.warning('===Insufficient Duration constraint was passed===')

            _logger.info("Time Off (%s) will created on %s to %s", leave_type.name, request_date_from, request_date_to)

            # prepare value for create/edit
            val = {
                'user_id': uid,
                'employee_id': employee.id,
                'holiday_status_id': leave_type.id,
                'date_from': from_datetime,
                'date_to': to_datetime,
                'request_date_from': request_date_from,
                'request_date_to': request_date_to,
                'request_unit_half': bool(payload.get('half_day') == 'true'),
                'request_date_from_period': payload.get('date_period', 'am'),
                'name': payload.get('note'),
            }

            # create or edit leave request
            if not leave_id:
                leave = leave_model.create(val)
            else:
                leave = leave_model.browse(int(leave_id))
                leave.write(val)

            if documents:
                attachment_model = get_table_model('ir.attachment')
                for document in documents:
                    attachment_model.create({
                        'name': document.filename,
                        'type': 'binary',
                        'datas': base64.b64encode(document.read()),
                        'res_model': 'hr.leave',
                        'res_id': leave.id,
                    })

            title = "Leave Request from " + employee.name
            body = leave.holiday_status_id.name + " on " + str(leave.date_from) + ", Reason " + leave.name
            if employee.parent_id:
                send_to = employee.parent_id.user_id
            else:
                send_to = employee.leave_manager_id

            if send_to:
                logging.info('=== Sending sent message.......')
                send_notification(
                    title=title or 'Leave Reqeust',
                    body=leave.name or '',
                    device_token=send_to.device_token,
                    user_id=send_to.id,
                    link='/approve_leave/%s' % (leave.id),
                )
            hr_send_to = leave.holiday_status_id.responsible_id
            if hr_send_to:
                logging.info('==== Sending sent message.......')
                send_notification(
                    title=title or 'Leave Reqeust',
                    body=body or '',
                    device_token=hr_send_to.device_token,
                    user_id=hr_send_to.id,
                    link='/approve_leave/%s' % (leave.id),
                )

            return valid_response_http(data=self._prepare_leave(leave, uid), status=200)

        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    @validate_jwt
    @http.route('/api/leave_refuse/<int:leave_id>', type="http", auth="none", methods=['patch'], csrf=False)
    def leave_refuse(self, uid, leave_id, **payload):
        try:
            leave = get_table_model('hr.leave').search([('id', '=', leave_id)])

            if not leave:
                return invalid_response_http(type='Not Found', message='Leave Request not found', status=404)

            if leave.state in ('validate1', 'validate'):
                return invalid_response_http(type='Bad Request',
                                             message='Refuse not allowed as Leave Request has been approved.',
                                             status=400)

            leave.action_refuse()

            return valid_response_http(data={'message': 'Refuse successfully'}, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)
    
    # approve leave
    @validate_jwt
    @http.route('/api/leave_approve/<int:leave_id>', type="http", auth="none", methods=['patch'], csrf=False)
    def leave_approve(self, uid, leave_id, **payload):
        logging.info('Approve is calling...')
        try:
            leave = get_table_model('hr.leave').search([('id', '=', leave_id)])

            if not leave:
                return invalid_response_http(type='Not Found', message='Leave Request not found', status=404)

            if leave.state not in ('confirm', 'validate1'):
                return invalid_response_http(type='Bad Request',
                                             message='Approve not allowed as Leave Request which is not waiting approval.',
                                             status=400)
            state = leave.state
            if state == 'confirm':
                leave.action_approve()
            if state == 'validate1':
                leave.action_validate()

            return valid_response_http(data={'message': 'Approved successfully'}, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # get leaves to approve
    @validate_jwt
    @http.route('/api/get_leave_approve/<int:leave_id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_leave_approve(self, uid, leave_id, **payload):
        try:
            leave = get_table_model('hr.leave').search([('id', '=', leave_id)])

            if not leave:
                return invalid_response_http(type='Not Found', message='Leave Request not found', status=404)

            val = self._prepare_leave(leave, uid)

            return valid_response_http(data=val, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    @validate_jwt
    @http.route('/api/leave/type', type="http", auth="none", methods=["get"], csrf=False)
    def get_leave_types(self, uid, **payload):
        try:
            employee = get_table_model('hr.employee').search([('user_id', '=', uid)])
            leave_types = get_table_model('hr.leave.type').search([('company_id', '=', employee.company_id.id)])

            val = []
            for leave_type in leave_types:
                mapped_days = leave_type.sudo().get_employees_days([employee.id])
                leave_days = mapped_days[employee.id][leave_type.id]
                remaining = leave_days['remaining_leaves'] > 0.0 and leave_days['virtual_remaining_leaves'] > 0.0

                # `Absent` leave type (id=7 in production)
                is_absent_type = (leave_type.id == 7)

                # all leave types that not require allocation
                no_limit_types = (leave_type.requires_allocation == 'no')

                # leave type requires allocation and has remaining days
                is_remaining_allocation = (leave_type.requires_allocation == 'yes' and remaining == True)

                # get `Total Days` of each leave type
                total_days = 'No Limit' if no_limit_types else leave_days['max_leaves']

                # get `Taken Days` after leave approved
                taken_days = leave_days['leaves_taken']

                # get `Remaining Days` after leave submitted
                remaining_days = 'No Limit' if no_limit_types else leave_days['virtual_remaining_leaves']

                val.append({
                    'id': leave_type.id,
                    'name': leave_type.name,
                    'total_days': total_days,
                    'taken_days': taken_days,
                    'remaining_days': remaining_days,
                    'is_available': bool(is_remaining_allocation or no_limit_types and not is_absent_type),
                })
            return valid_response_http(data=val, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)
    
    @http.route('/api/leave/document/<int:document_id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_leave_document(self, document_id, **payload):
        try:
            attachment_model = get_table_model('ir.attachment')
            attachment = attachment_model.search([('id', '=', document_id), ('res_model', '=', 'hr.leave')])

            if not attachment:
                return invalid_response_http(type='Not Found', message='Document not found', status=404)

            document_type = attachment.mimetype

            if document_type in ['image/jpeg', 'image/png', 'image/gif', 'image/bmp']:
                return self._make_response(attachment.datas, 'image/jpeg')
            elif document_type == 'application/pdf':
                return self._make_response(attachment.datas, 'application/pdf')
            else:
                return invalid_response_http(type='Bad Request', message='Document type not supported', status=400)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # get all states of leave
    @validate_jwt
    @http.route('/api/leave/states', type="http", auth="none", methods=["get"], csrf=False)
    def get_leave_states(self, **payload):
        try:
            states = [
                {'id': 'draft', 'value': 'To Submit'},
                {'id': 'confirm', 'value': 'To Approve'},
                {'id': 'refuse', 'value': 'Refused'},
                {'id': 'validate1', 'value': 'Second Approval'},
                {'id': 'validate', 'value': 'Approved'},
            ]

            return valid_response_http(data=states, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    @staticmethod
    def _make_response(encoded_data, content_type):
        decoded_data = base64.b64decode(encoded_data)
        http_headers = [
            ('Content-Type', content_type),
            ('Content-Length', len(decoded_data)),
        ]
        return request.make_response(decoded_data, headers=http_headers)

    @staticmethod
    def _prepare_leave(leave, uid):
        attachment_model = get_table_model('ir.attachment')
        user_tz = request.env.context.get('tz') or 'UTC'

        states = {
            'draft': (_('Draft'), STATUS_COLORS['Blue']),
            'confirm': (_('Waiting Approval'), STATUS_COLORS['Yellow']),
            'validate1': (_('PM approved'), STATUS_COLORS['Yellow']),
            'validate': (_('HR Approved'), STATUS_COLORS['Green']),
            'refuse': (_('Refuse'), STATUS_COLORS['Red']),
        }

        attachments = attachment_model.search([('res_model', '=', 'hr.leave'), ('res_id', '=', leave.id)])
        documents = [
            {
                'id': attachment.id,
                'name': attachment.name,
                'url': '/api/leave/document/{}'.format(attachment.id),
            } for attachment in attachments
        ]

        # check if the current user is the manager of the employee
        can_approve_leave = (
            leave.employee_id.parent_id and
            leave.employee_id.parent_id.user_id.id == uid and
            leave.state == 'confirm'
        )
    
        return {
            'id': leave.id,
            'employee_id': {
                'id': leave.employee_id.id,
                'name': leave.employee_id.name,
            },
            'holiday_status_id': {
                'id': leave.holiday_status_id.id,
                'name': leave.holiday_status_id.name,
            },
            'date_from': leave.date_from.astimezone(pytz.timezone(user_tz)) or '',
            'date_to': leave.date_to.astimezone(pytz.timezone(user_tz)) or '',
            'number_of_days': leave.number_of_days,
            'request_unit_half': leave.request_unit_half,
            'request_date_from_period': leave.request_date_from_period or 'am',
            'state': {
                'id': leave.state,
                'value': states.get(leave.state)[0],
                'color': states.get(leave.state)[1],
            },
            'note': leave.name or '',
            'document': documents,
            'editable': bool(leave.state == 'confirm'),
            'can_approve_leave': can_approve_leave,
            'approve_date': (leave.approve_date).astimezone(pytz.timezone(user_tz)).isoformat() if leave.approve_date else '',
            'create_date': leave.create_date,
            'create_uid': leave.create_uid.id,
            'write_date': leave.write_date,
            'write_uid': leave.write_uid.id,
        }
