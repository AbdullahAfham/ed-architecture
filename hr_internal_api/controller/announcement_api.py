from odoo import http
from odoo.http import request
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model, valid_response_http, invalid_response_http

import base64


class AnnouncementAPI(http.Controller):

    # get all announcements
    @validate_jwt
    @http.route('/api/get_all_announcements', type="http", auth="none", methods=["get"], csrf=False)
    def get_all_announcements(self, uid, **payload):
        try:
            announcements = get_table_model('hr.announcement').search([('state', '=', 'release')])
            val = [{
                'id': announcement.id,
                'title': announcement.title,
                'description': announcement.description,
                'image': f'/api/get_announcement_image/{announcement.id}',
                'date_release': announcement.date_release,
                'create_uid': announcement.create_uid.id,
            } for announcement in announcements]

            return valid_response_http(data=val, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # get announcement detail
    @validate_jwt
    @http.route('/api/get_announcement_detail/<int:announcement_id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_announcement_detail(self, uid, announcement_id, **payload):
        try:
            announcement = get_table_model('hr.announcement').search([('id', '=', announcement_id)])

            if not announcement:
                return invalid_response_http(type="Not Found", message='Announcement not found', status=404)
            
            val = {
                'id': announcement.id,
                'title': announcement.title,
                'description': announcement.description,
                'image': f'/api/get_announcement_image/{announcement.id}',
                'date_release': announcement.date_release,
                'create_uid': announcement.create_uid.id,
            }
            
            # get attachments
            attachments = get_table_model('ir.attachment').search([
                ('res_model', '=', 'hr.announcement'), 
                ('res_id', '=', announcement.id)],
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
    @http.route('/api/get_announcement_image/<int:announcement_id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_announcement_image(self, announcement_id, **payload):
        # get announcement object
        announcement = get_table_model('hr.announcement').search([('id', '=', announcement_id)])

        if not announcement:
            return invalid_response_http(type="Not Found", message='Announcement not found', status=404)

        if not announcement.image:
            return invalid_response_http(type="Not Found", message='Image not found', status=404)

        # get image
        image = base64.b64decode(announcement.image)
        httpheaders = [
            ('Content-Type', 'image/jpeg'),
            ('Content-Length', len(image)),
        ]

        return request.make_response(image, headers=httpheaders)