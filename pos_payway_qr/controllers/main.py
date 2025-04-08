# coding: utf-8
import logging
import json
import pprint
from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class PosPayWayQRController(http.Controller):
    _webhook_url = '/pos_payway_qr/notification'

    @http.route(_webhook_url, type='http', auth='none', csrf=False)
    def notification(self, **data):
        if not data:
            data = request.get_json_data()
        _logger.info("Notification received from PayWay QR API with data:\n%s", pprint.pformat(data))

        payment_method_sudo = request.env['pos.payment.method'].sudo().search([('use_payment_terminal', '=', 'payway_qr')], limit=1)
        if payment_method_sudo and data:
            tran_id = data.get('tran_id', False)
            if tran_id:
                payment_method_sudo._retrieve_payway_qr_session_id(data)
            else:
                _logger.error(_('received a message from PayWay QR API but not Success.'))
        else:
            _logger.error(_('received a message for a pos payment provider not registered.'))
        return 'OK'  # Acknowledge the notification.
