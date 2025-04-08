from odoo import http
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model, valid_response_http, \
    invalid_response_http


class NotificationAPI(http.Controller):

    # get current user notifications
    @validate_jwt
    @http.route('/api/get_user_notifications', type="http", auth="none", methods=["get"], csrf=False)
    def get_user_notifications(self, uid, **payload):
        try:
            notification_model = get_table_model('mobile.notification')
            notifications = notification_model.search([('user_id', '=', uid)])
            val = []
            for notification in notifications:
                val.append({
                    'id': notification.id,
                    'title': notification.title,
                    'message': notification.message,
                    'user_id': notification.user_id.id,
                    'is_read': notification.is_read,
                    'link': notification.link or "",
                    'create_date': notification.create_date,
                    'create_uid': notification.create_uid.id,
                    'write_date': notification.write_date,
                    'write_uid': notification.write_uid.id,
                })

            # Sort the data by 'create_date' in descending order
            sorted_vals = sorted(val, key=lambda d: d['create_date'], reverse=True)

            return valid_response_http(data=sorted_vals, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # mark notification as read
    @validate_jwt
    @http.route('/api/update_notification/<int:notification_id>', type="http", auth="none", methods=["patch"],
                csrf=False)
    def update_notification(self, uid, notification_id, **payload):
        try:
            notification_model = get_table_model('mobile.notification')
            notification = notification_model.search([('id', '=', notification_id), ('user_id', '=', uid)])
            if not notification:
                return invalid_response_http(type="Not Found", message='Notification not found', status=400)
            notification.write({'is_read': True})
            return valid_response_http(data={'message': 'Marked as read successfully'}, status=200)

        except Exception as e:
            return invalid_response_http(type=type(e).__name__, message=str(e), status=400)

    # delete notification
    @validate_jwt
    @http.route('/api/delete_notification/<int:notification_id>', type="http", auth="none", methods=["delete"],
                csrf=False)
    def delete_notification(self, uid, notification_id, **payload):
        try:
            notification_model = get_table_model('mobile.notification')
            notification = notification_model.search([('id', '=', notification_id), ('user_id', '=', uid)])
            if not notification:
                return invalid_response_http(type="Not Found", message='Notification not found', status=400)
            notification.unlink()
            return valid_response_http(data={'message': 'Deleted successfully'}, status=200)
        except Exception as e:
            return invalid_response_http(type=type(e).__name__, message=str(e), status=400)
