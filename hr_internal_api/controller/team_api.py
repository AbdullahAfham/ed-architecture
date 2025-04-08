from odoo import http
from odoo.http import request, content_disposition
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    valid_response, invalid_response, valid_response_http, invalid_response_http

import base64


class TeamAPI(http.Controller):

    @validate_jwt
    @http.route('/api/get_employee_team', type="http", auth="none", methods=["get"], csrf=False)
    def get_employee_team(self, uid, **payload):
        try:
            user_employee = get_table_model('hr.employee').search([('user_id', '=', uid)])
            if not user_employee:
                return invalid_response_http(type='Not Found', message='Current Employee not found', status=404)
            
            employees = get_table_model('hr.employee').search([('department_id', '=', user_employee.department_id.id)])

            response = [{
                "id": employee.id,
                "name": employee.name,
                "role": employee.job_id.name,
                "department": employee.department_id.name,
                # "project": employee.project_id.name if employee.project_id else "",
                "image_url": f'/api/get_employee_image/{employee.id}',
            } for employee in employees]

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    @validate_jwt
    @http.route('/api/get_employee_image/<int:employee_id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_employee_image(self, uid, employee_id, **payload):
        try:
            employee = get_table_model('hr.employee').browse(employee_id)

            if not employee:
                return invalid_response_http(type='Not Found', message='Employee not found', status=404)

            image_bytes = base64.b64decode(employee.avatar_128)

            httpheaders = [
                ('Content-Type', ' image/jpeg'),
                ('Content-Length', len(image_bytes)),
                ('Content-Disposition', content_disposition('image.jpg')),
            ]

            return request.make_response(image_bytes, headers=httpheaders)
        
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)
