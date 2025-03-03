import base64

from odoo import http, _
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    invalid_response, valid_response_http, invalid_response_http, STATUS_COLORS
from odoo.addons.hr_internal_api.controller.send_notification import send_notification
from odoo.http import request
import json
from datetime import datetime, timedelta
import pytz


class OvertimeAPI(http.Controller):

    # my overtime
    @validate_jwt
    @http.route('/api/overtime', type="http", auth="none", methods=["get"], csrf=False)
    def get_user_overtimes(self, uid, **payload):
        try:
            overtime_model = get_table_model('hr.overtime')

            domain = [('employee_id.user_id', '=', uid)]
            if payload.get('start_date'):
                domain.append(('date_from', '>=', payload.get('start_date')))
            if payload.get('end_date'):
                domain.append(('date_from', '<=', payload.get('end_date')))
            if payload.get('state'):
                states = payload.get('state').split(',')
                domain.append(('state', 'in', states))

            overtimes = overtime_model.search(domain)

            val = [self._prepare_overtime(overtime, uid) for overtime in overtimes]

            # sort the data by 'create_date'
            val.sort(key=lambda x: x.get('create_date'), reverse=True)

            return valid_response_http(data=val, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # my team overtimes
    @validate_jwt
    @http.route('/api/team/overtime', type="http", auth="none", methods=["get"], csrf=False)
    def get_team_overtimes(self, uid, **payload):
        try:
            overtime_model = get_table_model('hr.overtime')

            domain = [('employee_id.parent_id.user_id', '=', uid)]
            if payload.get('start_date'):
                domain.append(('date_from', '>=', payload.get('start_date')))
            if payload.get('end_date'):
                domain.append(('date_from', '<=', payload.get('end_date')))
            if payload.get('state'):
                states = payload.get('state').split(',')
                domain.append(('state', 'in', states))

            overtimes = overtime_model.search(domain)

            val = [self._prepare_overtime(overtime, uid) for overtime in overtimes]
            
            # sort the data by 'create_date'
            val.sort(key=lambda x: x.get('create_date'), reverse=True)

            return valid_response_http(data=val, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    @validate_jwt
    @http.route('/api/overtime/<int:overtime_id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_overtime(self, uid, overtime_id, **payload):
        try:
            overtime_model = get_table_model('hr.overtime')
            overtime = overtime_model.search([('id', '=', overtime_id), ('employee_id.user_id', '=', uid)], limit=1)
            if not overtime:
                return invalid_response_http(type='Not Found', message='Overtime not found', status=404)

            return valid_response_http(data=self._prepare_overtime(overtime, uid), status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    @validate_jwt
    @http.route('/api/overtime', type="http", auth="none", methods=["post"], csrf=False)
    def create_overtime(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        overtime_model = get_table_model('hr.overtime')
        employee_model = get_table_model('hr.employee')

        employee = employee_model.search([('user_id', '=', uid)], limit=1)
        if not employee:
            return invalid_response('Employee not found')

        duration_type = payload.get('duration_type')
        break_hours = payload.get('break_hours')
        date_from = payload.get('date_from')
        date_to = payload.get('date_to')
        type = payload.get('type')
        desc = payload.get('description')
        documents = request.httprequest.files.getlist('documents')

        if not duration_type:
            return invalid_response('Duration type is required')
        if not date_from:
            return invalid_response('Date from is required')
        if not date_to:
            return invalid_response('Date to is required')

        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d %H:%M:%S') - timedelta(hours=7)
            date_to = datetime.strptime(date_to, '%Y-%m-%d %H:%M:%S') - timedelta(hours=7)

            overtime = overtime_model.create({
                'employee_id': employee.id,
                'project_manager_id': employee.parent_id.user_id.id,
                'duration_type': duration_type,
                'break_hours': break_hours,
                'date_from': date_from,
                'date_to': date_to,
                'type': type,
                'desc': desc,
                'state': 'approval',
            })

            if documents:
                attachment_model = get_table_model('ir.attachment')
                for document in documents:
                    attachment_model.create({
                        'name': document.filename,
                        'type': 'binary',
                        'datas': base64.b64encode(document.read()),
                        'res_model': 'hr.overtime',
                        'res_id': overtime.id,
                    })
                        
            title = f"Overtime Request from {overtime.create_uid.name}"
            body = f"Overtime {overtime.name} from {date_from} to {date_to}"
            
            send_to = overtime.project_manager_id  
            if send_to and send_to.device_token:
                send_notification(
                    title=title,
                    body=body,
                    device_token=send_to.device_token,
                    user_id=send_to.id,
                    link='/approve_overtime/%s' % (overtime.id),
                )

            return valid_response_http(data=self._prepare_overtime(overtime, uid), status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/overtime_refuse/<int:overtime_id>', type="http", auth="none", methods=['patch'], csrf=False)
    def overtime_refuse(self, uid, overtime_id, **payload):
        try:
            overtime = get_table_model('hr.overtime').search([('id', '=', overtime_id)])

            if not overtime:
                return invalid_response_http(type='Not Found', message='overtime Request not found', status=404)

            if overtime.state == 'finance_approval':
                return invalid_response_http(
                    type='Bad Request',
                    message='Refuse not allowed as overtime Request has been approved.',
                    status=400)

            overtime.reject()

            return valid_response_http(data={'message': 'Refuse successfully'}, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)
        
    # approve overtime
    @validate_jwt
    @http.route('/api/overtime_approve/<int:overtime_id>', type="http", auth="none", methods=['patch'], csrf=False)
    def overtime_approve(self, uid, overtime_id, **payload):
        try:
            overtime = get_table_model('hr.overtime').search([('id', '=', overtime_id)])

            if not overtime:
                return invalid_response_http(type='Not Found', message='Overtime request not found', status=404)

            if overtime.state != 'approval':
                return invalid_response_http(
                    type='Bad Request',
                    message='Approval not allowed for overtime requests that are not in the Waiting state.',
                    status=400
                )
            
            state = overtime.state
            if state == 'approval':
                overtime.approve()

            return valid_response_http(data={'message': 'Approved successfully'}, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # get overtimes to approve
    @validate_jwt
    @http.route('/api/get_overtime_approve/<int:overtime_id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_overtime_approve(self, uid, overtime_id, **payload):
        try:
            overtime = get_table_model('hr.overtime').search([('id', '=', overtime_id)])

            if not overtime:
                return invalid_response_http(type='Not Found', message='overtime Request not found', status=404)

            val = self._prepare_overtime(overtime, uid)

            return valid_response_http(data=val, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)
 
    # get all states of overtime
    @validate_jwt
    @http.route('/api/overtime/states', type="http", auth="none", methods=["get"], csrf=False)
    def get_overtime_states(self, **payload):
        try:
            state = [
                {'id': 'draft', 'value': 'Draft'},
                {'id': 'approval', 'value': 'Waiting'},
                {'id': 'officer_approval', 'value': 'Manager Approved'},
                {'id': 'finance_approval', 'value': 'Officer Approved'},
                {'id': 'approved', 'value': 'Approved'},
                {'id': 'refused', 'value': 'Refused'},
            ]

            return valid_response_http(data=state, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    @http.route('/api/overtime/document/<int:document_id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_overtime_document(self, document_id, **payload):
        try:
            attachment_model = get_table_model('ir.attachment')
            attachment = attachment_model.search([('id', '=', document_id), ('res_model', '=', 'hr.overtime')])

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

    @staticmethod
    def _make_response(encoded_data, content_type):
        decoded_data = base64.b64decode(encoded_data)
        http_headers = [
            ('Content-Type', content_type),
            ('Content-Length', len(decoded_data)),
        ]
        return request.make_response(decoded_data, headers=http_headers)

    @staticmethod
    def _prepare_overtime(overtime, uid):
        attachment_model = get_table_model('ir.attachment')
        user_tz = request.env.context.get('tz') or 'UTC'

        states = {
            'draft': (_('Draft'), STATUS_COLORS['Blue']),
            'approval': (_('Waiting'), STATUS_COLORS['Yellow']),
            'officer_approval': (_('Manager Approved'), STATUS_COLORS['Yellow']),
            'finance_approval': (_('Officer Approved'), STATUS_COLORS['Yellow']),
            'approved': (_('Approved'), STATUS_COLORS['Green']),
            'refused': (_('Refused'), STATUS_COLORS['Red']),
        }

        attachments = attachment_model.search([('res_model', '=', 'hr.overtime'), ('res_id', '=', overtime.id)])
        documents = [{
            'id': attachment.id,
            'name': attachment.name,
            'url': '/api/overtime/document/{}'.format(attachment.id),
        } for attachment in attachments]

        # check if the current user is the manager of the employee
        can_approve_overtime = (
            overtime.employee_id.parent_id and
            overtime.employee_id.parent_id.user_id.id == uid and
            overtime.state == 'approval'
        )

        return {
            'id': overtime.id,
            'name': overtime.name or '#',
            'employee_id': {
                'id': overtime.employee_id.id,
                'name': overtime.employee_id.name,
            },
            'date_from': overtime.date_from.astimezone(pytz.timezone(user_tz)) if isinstance(overtime.date_from, datetime) else '',
            'date_to': overtime.date_to.astimezone(pytz.timezone(user_tz)) if isinstance(overtime.date_to, datetime) else '',
            'duration_type': overtime.duration_type,
            'days_no_tmp': overtime.days_no_tmp,
            'break_hours': overtime.break_hours,
            'type': overtime.type,
            'description': overtime.desc or '',
            'documents': documents,
            'state': {
                'id': overtime.state,
                'value': states.get(overtime.state)[0],
                'color': states.get(overtime.state)[1],
            },
            'can_approve_overtime': can_approve_overtime,
            'create_date': overtime.create_date,
            'create_uid': overtime.create_uid.id,
            'write_date': overtime.write_date,
            'write_uid': overtime.write_uid.id,
        }
