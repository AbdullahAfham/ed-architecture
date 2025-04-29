from odoo import http, Command, _
from odoo.http import request, content_disposition, DEFAULT_MAX_CONTENT_LENGTH
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    valid_response, invalid_response, valid_response_http, invalid_response_http,\
    serve_attachment


class IrAttachmentAPI(http.Controller):

    @validate_jwt
    @http.route(['/api/upload_attachment'], type="http", auth="none", methods=["post"], csrf=False, max_content_length=DEFAULT_MAX_CONTENT_LENGTH)
    def upload_attachment(self, uid, **payload):
        try:
            # validation check
            current_user = get_table_model('res.users').search([('id', '=', uid)], limit=1)
            if not current_user:
                return invalid_response_http("Not Found", 'User not found.', status=404)

            # retrieve the files
            files = request.httprequest.files.getlist('documents')
            if not files:
                return invalid_response_http("Bad Request", "Missing documents.", status=400)

            is_internal_user = request.env.user._is_internal()

            attachment_ids = []
            for file in files:
                attachment = get_table_model('ir.attachment')._from_request_file(
                    file, mimetype='TRUST' if is_internal_user else 'GUESS'
                )
                # attachment.message_post(
                #     body=_("Document uploaded by %(user)s", user=request.env.user.name)
                # )
                attachment_ids.append(attachment.id)

            response = {
                'attachment_ids': attachment_ids,
                'message': 'Uploaded Successfully'
            }

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/get_attachment/<int:attachment_id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_attachment(self, uid, attachment_id, **payload):
        try:
            return serve_attachment(attachment_id)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
