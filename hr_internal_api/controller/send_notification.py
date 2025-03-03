import firebase_admin
from firebase_admin import credentials, messaging
from odoo.addons.hr_internal_api.controller.helper import get_table_model
import logging
import os

parent_path = os.path.dirname(__file__).split('/hr_internal_api/controller')[0]
file_path = '/hr_internal_api/data/yh-group-prod-firebase-adminsdk-production.json'

cred = credentials.Certificate(parent_path + file_path)
# logging.info(parent_path + file_path)

firebase_admin.initialize_app(cred)


def send_notification(title, body, device_token, user_id, link=None):
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=device_token,
        )

        response = messaging.send(message)

        logging.info('Successfully sent message')
        logging.info(response)

        notification_model = get_table_model('mobile.notification')
        notification_model.create({
            'title': title,
            'message': body,
            'user_id': user_id,
            'is_read': False,
            'link': link,
        })
    except Exception as e:
        logging.info('Error sending message')
        logging.info(e)
        return False


def send_notification_multicast(title, body, device_tokens, user_ids, link=None):
    try:
        message = messaging.MulticastMessage(
            device_tokens,
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
        )

        # logging.warning(f'device_tokens: {device_tokens}')
        logging.warning(f'Send message: {message}')

        response = messaging.send_multicast(message)
        logging.info('Successfully sent message')
        logging.info(response)

        notification_model = get_table_model('mobile.notification')
        for user_id in user_ids:
            notification_model.create({
                'title': title,
                'message': body,
                'user_id': user_id,
                'is_read': False,
                'link': link,
            })
    except Exception as e:
        logging.info('Error sending message')
        logging.info(e)
        return False
