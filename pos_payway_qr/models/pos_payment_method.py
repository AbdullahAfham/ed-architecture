# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import requests
import pprint
import base64
import hmac
import hashlib
import json

from .constants import SIGNATURE_KEYS
from odoo import fields, models, api, tools, _
from odoo.exceptions import UserError, AccessError
from odoo.addons.pos_payway_qr.controllers.main import PosPayWayQRController

_logger = logging.getLogger(__name__)
TIMEOUT = 10

def get_payway_qr_session():
    session = requests.Session()
    session.mount('https://', requests.adapters.HTTPAdapter(max_retries=requests.adapters.Retry(
        total=1, # 3 retries
        backoff_factor=2,
        status_forcelist=[202, 500, 502, 503, 504],
        )))
    return session


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _get_payment_terminal_selection(self):
        return super(PosPaymentMethod, self)._get_payment_terminal_selection() + [('payway_qr', 'PayWay QR API')]

    payway_qr_merchant_id = fields.Char(string="Merchant Id", help='Used when connecting to PayWay QR API', copy=False)
    payway_qr_key = fields.Char(string="Public key", help='Used when connecting to PayWay QR API', copy=False)
    payway_qr_test_mode = fields.Selection([
        ('uat', 'UAT'),
        ('sandbox', 'Sandbox'),
        ('production', 'Production'),
    ], string="Test mode", help="Run transactions in the test environment.", default='sandbox')
    payway_qr_webhook_endpoint = fields.Char(string="Webhook URL", compute='_compute_payway_qr_webhook_endpoint', readonly=True)
    payway_qr_latest_response = fields.Json() # used to buffer the latest asynchronous notification from PayWay.
    payway_currency_id = fields.Many2one('res.currency', string='PayWay Currency', domain=lambda self: [('id', 'in', [self.env.ref('base.USD').id, self.env.ref('base.KHR').id])])

    @api.model
    def _load_pos_data_fields(self, config_id):
        params = super()._load_pos_data_fields(config_id)
        params += ['payway_qr_key', 'payway_currency_id']
        return params

    def _is_write_forbidden(self, fields):
        return super(PosPaymentMethod, self)._is_write_forbidden(fields - {'payway_qr_merchant_id', 'payway_qr_key', 'payway_qr_test_mode', 'payway_qr_latest_response'})

    def _payway_qr_api_get_endpoint(self):
        if self.sudo().payway_qr_test_mode == 'production':
            return 'https://checkout.payway.com.kh'
        elif self.sudo().payway_qr_test_mode == 'sandbox':
            return 'https://checkout-sandbox.payway.com.kh'
        else:
            return 'https://pwapp-uat.ababank.com'

    def _compute_payway_qr_webhook_endpoint(self):
        web_base_url = self.get_base_url()
        self.payway_qr_webhook_endpoint = f"{web_base_url}{PosPayWayQRController._webhook_url}"

    def _call_payway_qr(self, endpoint, action, data=None):
        session = get_payway_qr_session()
        endpoint = f"{self._payway_qr_api_get_endpoint()}/api/payment-gateway/v1/{endpoint}"
        try:
            resp = session.request(action, endpoint, json=data, timeout=TIMEOUT)
        except requests.exceptions.RequestException as e:
            return {'error': _("There are some issues between us and PayWay QR API, try again later.%s)", e)}

        if resp.status_code == 200:
            if resp.text:
                return resp.json()
            return {'success': resp.status_code}
        else:
            # return {'error': _("There are some issues between us and PayWay QR API, try again later. %s", resp.json().get('status', {}).get('message', resp.status_code))}
            return {'error': _("There are some issues between us and PayWay QR API, try again later. %s", resp.json().get('status'))}

    def _send_payway_qr_notification(self, data):
        # Send a notification to the point of sale channel to indicate that the transaction are finish
        pos_session_sudo = self.env["pos.session"].browse(int(data.get('pos_session_id', False)))
        if pos_session_sudo:
            pos_session_sudo.config_id._notify('PAYWAY_QR_LATEST_RESPONSE', {
                'config_id': pos_session_sudo.config_id.id
            })

    def get_order_items_base64(self, order_lines):
        key = 0
        item = []
        for order_line in order_lines:
            item.append({})
            price_unit = order_line.get('price_unit', 0)
            discount = order_line.get('discount', 0)
            quantity = order_line.get('quantity', 0)
            item[key]['name'] = order_line.get('product_name', '')
            item[key]['quantity'] = str(quantity)
            item[key]['price'] = "{:.2f}".format(round(price_unit, 2))
            if discount > 0:
                item[key]['discount'] = str(round((price_unit * quantity) * discount / 100, 2))
            key += 1
        return base64.b64encode(json.dumps(item).encode('utf-8')).decode('utf-8')

    def _payway_calculate_signature(self, data, incoming=True, pos_session_id=False):
        """ Compute the signature for the provided data according to the PayWay documentation.

        :param dict data: The data to sign.
        :param bool incoming: Whether the signature must be generated for an incoming (PayWay to
                              Odoo) or outgoing (Odoo to PayWay) communication.
        :return: The calculated signature.
        :rtype: str
        """
        signature_keys = SIGNATURE_KEYS['incoming' if incoming else 'outgoing']
        data_to_sign = [str(data[k]) for k in signature_keys]
        signing_string = ''.join(data_to_sign)

        # pos_session_sudo = pos_session_id and self.env["pos.session"].sudo().browse(int(pos_session_id)) or self.env["pos.session"].sudo()
        secret_key = self.payway_qr_key.encode('utf-8')

        hash_value = hmac.new(secret_key, msg=signing_string.encode('utf-8'), digestmod=hashlib.sha512).digest()
        hash_base64 = base64.b64encode(hash_value).decode('utf-8')
        return hash_base64

    def payway_qr_check_payment_status(self, PosData):
        self.ensure_one()
        endpoint = "payments/check-transaction-2" #check-transaction v2 from PayWay QR API

        lang = self._context.get('lang', 'en')
        tran_id = PosData.get('name', False)
        pos_session_id = PosData.get('pos_session_id', False)
        # pos_session_sudo = self.env["pos.session"].sudo().browse(int(pos_session_id)).exists()
        merchant_id = self.payway_qr_merchant_id

        values = {
            'language': lang,
            'req_time': fields.Datetime.now().strftime("%Y%m%d%H%M%S"),
            'merchant_id': merchant_id,
            'tran_id': tran_id,
        }

        response = self._call_payway_qr(endpoint, 'post', {
            **values,
            'hash': self._payway_calculate_signature(values, incoming=True, pos_session_id=pos_session_id),
        })


        if response.get('data', False):
            data_webhook = response.get('data', {})
            data_webhook['transaction_id'] = tran_id
            data = {'pos_session_id': pos_session_id, 'transaction_id': tran_id, 'data_webhook': data_webhook}
            self.payway_qr_latest_response = data
            return data
        else:
            self._send_payway_qr_notification(
                {'error': _(
                    "There are some issues between us and PayWay QR API, try again later. %s",
                    response.get('status', "Error")
                    )}
                )


    def payway_qr_send_payment_request(self, PosData):
        self.ensure_one()
        endpoint = "payments/purchase"

        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("Only 'group_pos_user' are allowed to fetch token from PayWay QR API"))
        _logger.info('Request to PayWay QR API by user #%d:\n%s', self.env.uid, pprint.pformat(PosData))

        lang = PosData.get('lang', 'en')
        tran_id = PosData.get('name', '')
        amount = PosData.get('total', 0)
        order_lines = PosData.get('order_lines', [])
        is_khr = PosData.get('is_khr', False)
        amount = "{:.0f}".format(amount) if is_khr else "{:.2f}".format(amount)
        pos_session_id = PosData.get('pos_session_id', False)
        # pos_session_sudo = self.env["pos.session"].sudo().browse(int(pos_session_id)).exists()

        merchant_id = self.payway_qr_merchant_id
        values = {
            'req_time': fields.Datetime.now().strftime('%Y%m%d%H%M%S'),
            'merchant_id': merchant_id,
            'tran_id': tran_id,
            'amount': amount,
            'items': self.get_order_items_base64(order_lines),
            'payment_option': '',
            'language': lang,
            'return_url': base64.b64encode(self.payway_qr_webhook_endpoint.encode('utf-8')).decode('utf-8'),
            'cancel_url': '',
            'continue_success_url': '',
            'currency': 'KHR' if is_khr else 'USD',
            'return_params': json.dumps({'pos_session_id': pos_session_id}),
            'lifetime': '3', # 3 minutes
        }

        _logger.warning(f"===payway_qr_send_payment_request values: {values}")

        return self._call_payway_qr(endpoint, 'post', {
            **values,
            'hash': self._payway_calculate_signature(values, incoming=False, pos_session_id=pos_session_id),
        })

    # [DEV] PayWay Doesn't have cancel API
    # def payway_qr_send_payment_cancel(self, data):
    #     if not self.env.user.has_group('point_of_sale.group_pos_user'):
    #         raise AccessError(_("Only 'group_pos_user' are allowed to fetch token from PayWay QR API"))
    #     session_id = data.get('sessionId')
    #     endpoint = f"sessions/{session_id}"
    #     return self._call_payway_qr(endpoint, 'delete')

    def _retrieve_payway_qr_session_id(self, webhook_data):
        # Send a request to confirm the status of the payment
        endpoint = "payments/check-transaction-2" #check-transaction v2 from PayWay QR API

        lang = self._context.get('lang', 'en')
        tran_id = webhook_data.get('tran_id', False)
        return_params = webhook_data.get('return_params', "{}")
        pos_session_id = json.loads(return_params).get('pos_session_id', False)
        # pos_session_sudo = self.env["pos.session"].sudo().browse(int(pos_session_id)).exists()
        merchant_id = self.payway_qr_merchant_id

        values = {
            'language': lang,
            'req_time': fields.Datetime.now().strftime("%Y%m%d%H%M%S"),
            'merchant_id': merchant_id,
            'tran_id': tran_id,
        }

        response = self._call_payway_qr(endpoint, 'post', {
            **values,
            'hash': self._payway_calculate_signature(values, incoming=True, pos_session_id=pos_session_id),
        })

        if response.get('data', False):
            data_webhook = response.get('data', {})
            data_webhook['transaction_id'] = tran_id
            data = {'pos_session_id': pos_session_id, 'transaction_id': tran_id, 'data_webhook': data_webhook}
            self.payway_qr_latest_response = data
            self._send_payway_qr_notification(data)
        else:
            self._send_payway_qr_notification(
                {'error': _(
                    "There are some issues between us and PayWay QR API, try again later. %s",
                    response.get('status', "Error")
                    )}
                )
        return response and response.get('data', False) or {}

    def get_latest_payway_qr_status(self):
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("Only 'group_pos_user' are allowed to get latest transaction status"))

        self.ensure_one()
        latest_response = self.sudo().payway_qr_latest_response
        return latest_response
