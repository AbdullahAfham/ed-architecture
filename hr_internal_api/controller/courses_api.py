import json
from odoo import http
from odoo.http import request
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model, valid_response_http, invalid_response_http

import base64


class CoursesAPI(http.Controller):

    @validate_jwt
    @http.route('/api/get_courses', type="http", auth="none", methods=["get"], csrf=False)
    def get_courses(self, uid, **payload):
        try:

            slide_channel_model = get_table_model('slide.channel')
            print("===========")
            course_ids = slide_channel_model.search([('is_published', '=', True)])
            print("==========courses=======", course_ids)
            val = [{
                'id': course.id,
                'title': course.name,
                'description': course.description or '',
                'image': f'/api/get_course_image/{course.id}',
                'date_release': course.create_date,
                'create_uid': course.create_uid.id,
            } for course in course_ids]

            return valid_response_http(data=val, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    @validate_jwt
    @http.route('/api/get_course_contents/<int:course_id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_course_contents(self, uid, course_id, **payload):
        try:
            contents = get_table_model('slide.slide').search([('channel_id', '=', course_id)])
            if not contents:
                return invalid_response_http(type="Not Found", message='Contents not found', status=404)

            val = []
            for content in contents:
                data = {
                    "id": content.id,
                    "is_category": content.is_category,
                    "name": content.name or '',
                    "content_type": None if content.is_category else content.slide_category
                }
                val.append(data)
            return valid_response_http(data=val, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    @validate_jwt
    @http.route('/api/get_content_detail/<int:content_id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_content_detail(self, uid, content_id, **payload):
        try:
            content = get_table_model('slide.slide').search([('id', '=', content_id)])

            if not content:
                return invalid_response_http(type="Not Found", message='Course not found', status=404)

            if content.slide_type == 'infographic':
                datas = f'/api/get_course_image/{content.id}'
            elif content.slide_type == 'video':
                datas = content.url
            else:
                datas = None

            val = {
                'id': content.id,
                'url': datas,
                'title': content.name,
                'description': content.description,
            }

            # get attachments
            attachments = get_table_model('ir.attachment').search([
                ('res_model', '=', 'slide.slide'),
                ('res_id', '=', content.id)],
            )

            val['attachments'] = [{
                'id': atm.id,
                'name': atm.name,
                # 'datas': atm.datas,
            } for atm in attachments]

            return valid_response_http(data=val, status=200)
        except Exception as e:
            return invalid_response_http(type=type(e).__name__, message=str(e), status=400)

    # get announcement image
    @http.route('/api/get_course_image/<int:course_id>', type="http", auth="none", methods=["get"],
                csrf=False)
    def get_course_image(self, course_id, **payload):
        # get announcement object
        course = get_table_model('slide.channel').search([('id', '=', course_id)])

        if not course_id:
            return invalid_response_http(type="Not Found", message='Course not found', status=404)

        if not course.image_1920:
            return invalid_response_http(type="Not Found", message='Image not found', status=404)

        # get image
        image = base64.b64decode(course.image_1920)
        httpheaders = [
            ('Content-Type', 'image/jpeg'),
            ('Content-Length', len(image)),
        ]

        return request.make_response(image, headers=httpheaders)


    @http.route('/api/get_course_attachment/<int:document_id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_course_attachment(self, document_id, **payload):
        try:
            attachment_model = get_table_model('ir.attachment')
            attachment = attachment_model.search([('id', '=', document_id), ('res_model', '=', 'slide.slide')])

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