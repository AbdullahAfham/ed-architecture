from odoo import http, _, SUPERUSER_ID
from odoo.http import request
from odoo.exceptions import UserError, AccessDenied

from .helper import validate_token, validate_pw_jwt, validate_jwt, \
    get_table_model, \
    valid_response, invalid_response, valid_response_http, invalid_response_http

from odoo.addons.resource.models.utils import float_to_time
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.addons.web.controllers.home import ensure_db, Home
from odoo.addons.phone_validation.tools import phone_validation

import requests
import jwt
import json
import base64

from random import choice
from string import digits
from datetime import timedelta, datetime, timezone

# from twilio.rest import Client

defaultUserPassword = 'Odoo!234%^ERP@Int`'


def phone_format(number):
    return phone_validation.phone_format(
        number, None, None,
        force_format='INTERNATIONAL',
        raise_exception=False
    )


class AuthSignupMobile(Home):
    @http.route()
    def web_login(self, *args, **kw):
        ensure_db()
        response = super(AuthSignupMobile, self).web_login(*args, **kw)
        response.qcontext.update(self.get_auth_signup_config())
        if request.httprequest.method == 'GET' and request.session.uid and request.params.get('redirect'):
            # Redirect if already logged in and redirect param is present
            return http.redirect_with_hash(request.params.get('redirect'))
        return response

    @http.route('/api/signup', type='json', auth='public', methods=["POST"], csrf=False)
    def mobile_auth_signup(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()
        if not qcontext.get('token') and not qcontext.get('signup_enabled'):
            return

        if 'error' not in qcontext and request.httprequest.method == 'POST':
            if self.check_user_exist(qcontext):
                message = _("Signup Error")
                if 'email' in kw:
                    message = _("Email Already Exist.")
                if 'phone' in kw:
                    message = _("Phone Already Exist.")
                return invalid_response(type="Create User error", message=message, status=403)
            try:
                self.do_signup(qcontext)
                if qcontext.get('token'):
                    User = request.env['res.users']
                    user_sudo = User.sudo().search(
                        User._get_login_domain(qcontext.get('login')), order=User._get_login_order(), limit=1
                    )
                    template = request.env.ref('auth_signup.mail_template_user_signup_account_created',
                                               raise_if_not_found=False)
                    if user_sudo and template:
                        template.sudo().send_mail(user_sudo.id, force_send=True)
                partner_id = request.env['res.partner'].sudo().search([("email", '=', kw['login'])], limit=1)
                if not partner_id.env.company:
                    partner_id.env.company = partner_id.env.company.search([], limit=1)
                if 'phone' in kw:
                    phone = "".join(s for s in kw['phone'].split(" "))
                    partner_id.write({"phone": phone_format(phone)})
                user = False
                login = kw.get("login", False)
                if not login:
                    email = kw.get("email", False)
                    phone = kw.get("phone", False)
                    phone = phone_format(phone)
                    if email:
                        user = get_table_model('res.users').search([('email', '=', email)], limit=1)
                    elif phone:
                        user = get_table_model('res.users').search([('phone', '=', phone)], limit=1)
                else:
                    user = get_table_model('res.users').search([('login', '=', login)], limit=1)
                if user:
                    user.write({'verification_code': '111111'})
                    to_be_encoded = {
                        'user_id': user.id
                    }
                    PRIVATE_KEY = request.env['ir.config_parameter'].sudo().get_param('internal.server.private.key')
                    token = jwt.encode(to_be_encoded, PRIVATE_KEY, algorithm='HS256').decode('utf-8')
                    return valid_response({"accessToken": token})
                return invalid_response(type="Create User error", message="user refernece error", status=403)
            except UserError as e:
                qcontext['error'] = e.args[0]
            except (SignupError, AssertionError) as e:
                if request.env["res.users"].sudo().search([("login", "=", qcontext.get("login"))]):
                    qcontext["error"] = _("Another user is already registered using this email address.")
                else:
                    qcontext['error'] = _("Could not create a new account.")
        if 'error' in qcontext:
            return invalid_response(type="Create User error", message=qcontext['error'], status=403)

    def get_auth_signup_config(self):
        """retrieve the module config (which features are enabled) for the login page"""

        get_param = request.env['ir.config_parameter'].sudo().get_param
        return {
            'signup_enabled': request.env['res.users']._get_signup_invitation_scope() == 'b2c',
            'reset_password_enabled': get_param('auth_signup.reset_password') == 'True',
        }

    def get_auth_signup_qcontext(self):
        """ Shared helper returning the rendering context for signup and reset password """
        qcontext = request.params.copy()
        qcontext.update(self.get_auth_signup_config())
        if not qcontext.get('token') and request.httprequest.headers.get("token"):
            qcontext['token'] = request.httprequest.headers.get("token")
        if qcontext.get('token'):
            try:
                # retrieve the user info (name, login or email) corresponding to a signup token
                token_infos = request.env['res.partner'].sudo().signup_retrieve_info(qcontext.get('token'))
                for k, v in token_infos.items():
                    qcontext.setdefault(k, v)
            except:
                qcontext['error'] = _("Invalid signup token")
                qcontext['invalid_token'] = True
        return qcontext

    def do_signup(self, qcontext):
        """ Shared helper that creates a res.partner out of a token """
        values = {key: qcontext.get(key) for key in ('login', 'name', 'password')}
        if not values:
            raise UserError(_("The form was not properly filled in."))
        if values.get('password') != qcontext.get('confirm_password'):
            raise UserError(_("Passwords do not match; please retype them."))
        supported_lang_codes = [code for code, _ in request.env['res.lang'].get_installed()]
        lang = request.context.get('lang', '').split('_')[0]
        if lang in supported_lang_codes:
            values['lang'] = lang
        self._signup_with_values(qcontext.get('token'), values)
        request.env.cr.commit()

    def _signup_with_values(self, token, values):
        user = request.env['res.users'].sudo()
        company = request.env.company or request.env.company.search([("id", "=", 1)], limit=1)
        if not user.env.company:
            user.env.company = company
        db, login, password = user.mobile_signup(values, token)
        request.env.cr.commit()  # as authenticate will use its own cursor we need to commit the current transaction
        uid = request.session.authenticate(db, login, password)
        if not uid:
            raise SignupError(_('Authentication Failed.'))

    def check_user_exist(self, values):
        email = values.get("email", False)
        phone = values.get("phone", False)
        partner_id = get_table_model('res.partner')
        if email:
            partner_id = partner_id.search(['&', ('user_ids', '!=', False), ('email', '=', email)],
                                           limit=1)
        elif phone:
            phone = phone_format(phone)
            partner_id = partner_id.search(['&', ('user_ids', '!=', False), ('phone', '=', phone)],
                                           limit=1)
        return partner_id and len(partner_id) != 0 or False

    def send_email(self, email):
        code = '1111'
        # code = ''.join(choice(digits) for i in range(4))
        user = get_table_model('res.users').search([('email', '=', email)], limit=1)
        if user:
            if not user.env.company:
                user.env.company = user.env.company.search([], limit=1)
            user.write({'verification_code': code})
            template = request.env.ref('internal_api.verification_code_email')
            try:
                assert template._name == 'mail.template'
                template_values = {
                    'email_to': '${object.email|safe}',
                    'email_cc': False,
                    'auto_delete': True,
                    'partner_to': False,
                    'scheduled_date': False,
                }
            except:
                return "Template Not found"

            if not template.env.company:
                template.env.company = template.env.company.search([], limit=1)
            template.write(template_values)
            template.send_mail(user.id, force_send=True, raise_exception=True)
            return code
        else:
            return "user Not Found"

    # def send_sms(self, phone):
    #     account_sid = request.env['ir.config_parameter'].sudo().get_param('twilio.account_sid') or False
    #     auth_token = request.env['ir.config_parameter'].sudo().get_param('twilio.auth_token') or False
    #     twilio_phone = request.env['ir.config_parameter'].sudo().get_param('twilio.twilio_phone') or False
    #     code = '2222'
    #     # code = ''.join(choice(digits) for i in range(4))
    #     user = False
    #     if phone.startswith('+'):
    #         user = get_table_model('res.users').search([('phone', '=', phone_format(phone))], limit=1)
    #     if user:
    #         try:
    #             if not user.env.company:
    #                 user.env.company = user.env.company.search([], limit=1)
    #             user.write({'verification_code': code})
    #             body = "Your Huione Life code is " + code
    #             client = Client(account_sid, auth_token)
    #             # message = client.messages.create(
    #             #     body=body,
    #             #     from_=twilio_phone,
    #             #     to=send_to
    #             # )
    #             return code
    #         except Exception as e:
    #             message = _(str(e) + ", Please contact to administrator.")
    #             return message
    #     else:
    #         return "user Not Found"
    #
    # @validate_token
    # @http.route('/mobile/send_code', type="json", auth="none", methods=["POST", "GET"], csrf=False)
    # def send_code(self, **payload):
    #     if not payload:
    #         payload = json.loads(request.httprequest.data)
    #     email = payload.get('email', False)
    #     phone = payload.get('phone', False)
    #     is_exist = self.check_user_exist(payload)
    #     code = False
    #     message = _("Sending code failed")
    #     if email:
    #         if not is_exist:
    #             message = _("Email Not Found!")
    #         else:
    #             code = self.send_email(email)
    #     elif phone:
    #         if not is_exist:
    #             message = _("Phone number Not Found!")
    #         else:
    #             if phone.startswith('+'):
    #                 code = self.send_sms(phone)
    #             else:
    #                 message = _("Phone number missing Country code")
    #     if code:
    #         return valid_response(data='success', status=200)
    #     return invalid_response(type="Sending code failed", message=message, status=403)


# #############END###########

class InternalAPI(http.Controller):

    @http.route('/api/login', type="json", auth="none", methods=["post"], csrf=False)
    def get_jwt_token(self, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)
        
        login = payload.get("login", False)
        phone = payload.get("phone", False)
        
        if not login:
            email = payload.get("email", False)
            user = False
            if email:
                user = get_table_model('res.users').search([('email', '=', email)], limit=1)
            elif phone:
                user = get_table_model('res.users').search([('phone', '=', phone_format(phone))], limit=1)
            
            if user:
                login = user.login
            else:
                return invalid_response(type="Login error", message="Email or Phone not found", status=403)
        
        password = payload.get("password", False)
        code = payload.get("code", False)
        os = payload.get("os", False)
        osVersion = payload.get("os_version", False)
        model = payload.get("model", False)
        name = payload.get("name", False)
        device_uuid = payload.get("device_uuid", False)
        
        try:
            uid = False
            if password:
                credential = {'login': login, 'password': password, 'type': 'password'}
                auth_info = request.session.authenticate(request.db, credential)
            
            elif code and user:
                if str(code) == user.verification_code:
                    user.write({"status": 'verified'})
                    uid = user.id
                    utc_now = datetime.now(timezone.utc)
                    to_be_encoded = {
                        'code': str(code),
                        'user_id': uid,
                        'exp': utc_now + timedelta(days=30)
                    }

                    if user.restrict_device and user.device_uuid and user.device_uuid != device_uuid:
                        message = _("Wrong device login, please make sure you are using same device")
                        return invalid_response(type="Login error", message=message, status=401)
                    else:
                        user.device_id = get_table_model('device.info').create({
                            'os': os,
                            'os_version': osVersion,
                            'model': model,
                            'name': name,
                            'device_uuid': device_uuid,
                            'user_id': user.id
                        })
                    user.device_uuid = device_uuid
                    PRIVATE_KEY = request.env['ir.config_parameter'].sudo().get_param('internal.server.private.key')
                    encoded_jwt = jwt.encode(to_be_encoded, base64.b64decode(PRIVATE_KEY), algorithm='HS256')
                    return valid_response({"accessToken": encoded_jwt})
            
            if auth_info:
                utc_now = datetime.now(timezone.utc)
                to_be_encoded = {
                    'user_id': auth_info['uid'],
                    'exp': utc_now + timedelta(days=30)
                }
                user = get_table_model('res.users').browse(auth_info['uid'])

                if user.restrict_device and user.device_uuid and user.device_uuid != device_uuid:
                    message = _("Wrong device login, please make sure you are using same device")
                    return invalid_response(type="Login error", message=message, status=401)
                else:
                    user.device_id = get_table_model('device.info').create({
                        'os': os,
                        'os_version': osVersion,
                        'model': model,
                        'name': name,
                        'device_uuid': device_uuid,
                        'user_id': user.id
                    })
                    user.device_uuid = user.device_id.device_uuid

                PRIVATE_KEY = request.env['ir.config_parameter'].sudo().get_param('internal.server.private.key')
                encoded_jwt = jwt.encode(to_be_encoded, PRIVATE_KEY, algorithm='HS256')
                return valid_response({"accessToken": encoded_jwt})
            else:
                message = _("Wrong Verification Code")
        except AccessDenied as e:
            request.update_env(user=SUPERUSER_ID)
            if e.args == AccessDenied().args:
                message = _("Wrong Username/password")
                return invalid_response(type="Login error", message=message, status=401)
            else:
                message = e.args[0]
        return invalid_response(type="Login error", message=message, status=403)

    @validate_jwt
    @http.route('/api/logout', type="http", auth="none", methods=["post"], csrf=False)
    def logout(self, uid, **payload):
        token = request.httprequest.headers.get("Authorization").replace("Bearer ", "")

        if not token:
            return invalid_response_http(type="Logout error", message="Token not found", status=403)
        
        # save token to blacklist
        response = get_table_model('blacklist.token').create({'token': token, 'user_id': uid})
        
        return valid_response_http(data={"message": "You have successfully logged out."}, status=200)

    @http.route('/api/register_otp', type='json', auth='public', methods=["POST"], csrf=False)
    def register_otp(self, **payload):
        users = get_table_model('res.users')
        if not payload:
            payload = json.loads(request.httprequest.data)
        phone = payload.get("phone", False)
        user_id = users.search([('active', '=', True), ('phone', '=', phone), ('login', '=', phone)])
        if user_id:
            return invalid_response_http(type="Sending error", message="User already exist, please login instead", status=403)
        code = self.send_sms_plasgate(phone)
        if code:
            user_id = users.create({
                'active': False,
                'login': phone,
                'name': phone,
                'phone': phone,
                'password': defaultUserPassword,
                'verification_code': code,
                'status': 'unverified'})
            return valid_response(data='success', status=200)
        else:
            message = "Please contact to our support team."
            return invalid_response_http(type="Sending code failed", message=message, status=400)

    def send_sms_plasgate(self, phone):
        phone = phone

        code = ''.join(choice(digits) for i in range(6))
        text = "Your OTP code for CHAIN is " + code + ". DO NOT SHARE THIS CODE WITH ANYONE!"
        if not phone:
            phone = '85510741281'

        # for debug mode / develop mode
        debugPhones = ['85592455357', '855886004776', '855965986168','85510741281']
        if phone in debugPhones:
            print('call debug phone to match OTP : 123456')
            return '123456'

        private = "ltEQdtfcEoTDgwcK14f9yoGCPW3XoEHezi5S30m9yYzk4g8baCDFUeNJjqS8fq0-3V1_U5BLxRVxbO-b9qriug"
        url = "https://cloudapi.plasgate.com/rest/send?private_key=" + private
        headers = {
            'X-Secret': '$5$rounds=535000$lZT9q2jbk6FafTQD$4mROUYzDHSlBlHWCKIO8PsLL4L8qbFZWAE1c1kY1dg3',
            'Content-Type': 'application/json'
        }

        payload = json.dumps({
            "sender": "SMS Info",
            "to": phone,
            "content": text,
            "dlr": "yes",
            "dlr_method": "GET",
            "dlr_level": 2,
            "dlr_url": "http://example.com/callback"
        })

        response = requests.request("POST", url, headers=headers, data=payload)

        print(response.text)

        if response:
            return code
        else:
            return False

    @http.route('/api/verify_register_otp', type="http", auth="public", methods=["POST", "GET"], csrf=False)
    def verify_register_otp(self, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)
        code = payload.get('code', False)
        phone = payload.get('phone', False)
        user = get_table_model('res.users').search([('login', '=', phone), ('phone', '=', phone), ('active', '=', False)])
        if str(code) == user.verification_code:
            user_id = user.id
            return valid_response({"user_id": user_id}, status=200)
        else:
            message = _("Wrong Verification code")
        return invalid_response_http(type="Wrong Verification code", message=message, status=400)

    @http.route('/api/get_customer_url', type="http", auth="public", methods=["POST", "GET"], csrf=False)
    def get_customer_url(self, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)
        uuid = payload.get('uuid', False)
        customer_code = payload.get('customer_code', False)
        if uuid:
            customer_id = get_table_model('erp.mobile.company').search([('uuid', '=', uuid), ('active', '=', True)])
        if customer_code:
            customer_id = get_table_model('erp.mobile.company').search([('customer_code', '=', customer_code), ('active', '=', True)])

        if customer_id:
            base_url = customer_id.base_url
            return valid_response_http({"base_url": base_url}, status=200)
        else:
            message = _("Customer not found!")
        return invalid_response_http(type="Customer not found!", message=message, status=400)

    @http.route('/api/register_user', type="http", auth="public", methods=["POST", "GET"], csrf=False)
    def register_user(self, **payload):
        users = get_table_model('res.users')
        if not payload:
            payload = json.loads(request.httprequest.data)
        id = payload.get('id', False)
        name = payload.get('name', False)
        password = payload.get('password', False)

        if id is False:
            return invalid_response_http(type='User', message='User not found', status=400)

        user = users.browse(id)
        if not user:
            return invalid_response_http(type="User", message='User not found.', status=400)

        try:
            # call reset password

            # admin access to update user data
            user.write({
                'name': name,
                'active': True
            })

            user.password = password

            return valid_response_http({"user_id": id}, status=200)

        except Exception as e:
            print(e)
            return invalid_response_http(type='User', message='Something went wrong', status=400)


    @validate_token
    @validate_jwt
    @http.route('/api/verify_otp', type="json", auth="none", methods=["POST", "GET"], csrf=False)
    def verify_otp(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)
        code = payload.get('code', False)
        login = payload.get('login', False)
        user = get_table_model('res.users').search([('login', '=', login)])
        if str(code) == user.verification_code:
            user.status = 'verified'
            return valid_response(data='success', status=200)
        else:
            message = _("Wrong Verification code")
        return invalid_response(type="Wrong Verification code", message=message, status=401)

    # @validate_token
    @validate_jwt
    @http.route('/api/change_password', type="http", auth="none", methods=["post"], csrf=False)
    def change_password(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)
        login = payload.get("username", False)
        if not login:
            login = get_table_model('res.users').browse(uid).login
        old_password = payload.get("old_password", False)
        new_password = payload.get("new_password", False)
        try:
            uid = request.session.authenticate(request.session.db, login, old_password)
            user = request.env(user=uid)['res.users'].browse(uid)
            if user:
                user.change_password(old_password, new_password)
            return valid_response_http(data={"message": "Password Changed Successfully"}, status=200)
        except AccessDenied as e:
            if e.args == AccessDenied().args:
                message = _("Wrong Username/password")
            else:
                message = e.args[0]
        return invalid_response_http(type="Change password error", message=message, status=403)

    @validate_token
    @validate_pw_jwt
    @http.route('/api/reset_password', type="json", auth="none", methods=["post"], csrf=False)
    def reset_password(self, uid, code, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)
        password = payload.get("password", False)
        if password:
            try:
                user = get_table_model('res.users').browse(uid)
                if not user.env.company:
                    user.env.company = user.env.company.search([], limit=1)
                if str(code) == user.verification_code:
                    user.write({'password': password})
                    return valid_response(data='success', status=200)
                else:
                    message = _("Wrong JWT Token")
            except Exception as e:
                message = _(str(e) + ", Please contact to administrator.")
        else:
            message = _("No Password Provided")
        return invalid_response(type="Reset Password Error", message=message, status=403)

    # @validate_token
    @validate_jwt
    @http.route('/api/update_profile_picture', type="http", auth="none", methods=["post"], csrf=False)
    def update_profile_picture(self, uid, **payload):
        file = payload.get("file", False)
        user = get_table_model('res.users').browse(uid)
        # web_base_url = get_table_model('ir.config_parameter').get_param('web.base.url')
        code = ''.join(choice(digits) for i in range(14))
        # url_big = str(web_base_url) + "/web/image?model=res.users&field=image_1920&id=" + str(
        #     user.id) + "&unique=" + code
        try:
            if user and file:
                if not user.env.company:
                    user.env.company = user.env.company.search([], limit=1)
                user.write({"image_1920": base64.b64encode(file.read())})
                user.write({"profile_unique": code})
                # return valid_response_http({"url": url_big}, status=200)
                return valid_response_http(data={"image_data": user.image_1920.decode('utf-8')}, status=200)
            else:
                message = _("Username Not Found. Please contact to administrator.")
        except Exception:
            message = _("Error during update profile picture. Please contact to administrator.")
        return invalid_response_http(type="Update Profile error", message=message, status=403)

    @validate_jwt
    @http.route('/api/update_user_language', type="http", auth="none", methods=["patch"], csrf=False)
    def update_user_info(self, uid, **payload):
        try:
            if not payload:
                payload = json.loads(request.httprequest.data)

            user = get_table_model('res.users').browse(uid)
            if not user:
                return invalid_response_http(type="Update User's info error",
                                             message='User not found. Please contact to administrator.', status=404)

            lang = payload.get('lang') or 'en_US'
            active_langs = get_table_model('res.lang').search([('active', '=', True)])
            if lang and lang not in active_langs.mapped('code'):
                return invalid_response_http(type="Update User's info error", message='Language is not activate',
                                             status=400)

            user.write({'lang': lang})

            return valid_response_http(data={'message': 'Update successfully'}, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # @validate_token
    @validate_jwt
    @http.route('/api/get_user_profile', type="http", auth="none", methods=["get"], csrf=False)
    def get_user_profile(self, uid, **payload):
        user = get_table_model('res.users').browse(uid)
        partner_id = user.partner_id
        employee = get_table_model('hr.employee').search([('user_id', '=', user.id)], limit=1)

        # contract = get_table_model('hr.contract').search([('employee_id', '=', employee.id), ('state', '=', 'open')], limit=1)
        attendance_ids = employee.resource_calendar_id.attendance_ids
        morning_attendance = attendance_ids.filtered(lambda x: x.day_period == 'morning')
        afternoon_attendance = attendance_ids.filtered(lambda x: x.day_period == 'afternoon')

        if partner_id.email:
            email = partner_id.email
        else:
            email = partner_id.login
        
        try:
            val = {
                "name": user.name,
                "gender": partner_id.title and partner_id.title.name or '',
                "phone": partner_id.phone,
                "address": partner_id.street,
                "role": employee and employee.job_id.name or '',
                "email": email,
                "login": user.login,
                "device_token": user.device_token,
                "status": user.status,
                "lang": user.lang,
                "tz": user.tz,
                "image_data": f'/api/get_employee_image/{employee.id}',
                "can_create_batch_ot": employee and employee.can_create_batch_ot or False,

                "morning_work_hours": {
                    "hour_from": morning_attendance and str(float_to_time(morning_attendance[0].hour_from)) or "",
                    "hour_to": morning_attendance and str(float_to_time(morning_attendance[0].hour_to)) or ""
                },
                "afternoon_work_hours": {
                    "hour_from": afternoon_attendance and str(float_to_time(afternoon_attendance[0].hour_from)) or "",
                    "hour_to": afternoon_attendance and str(float_to_time(afternoon_attendance[0].hour_to)) or ""
                },
                "modules": [module.key for module in user.mobile_module_ids],
            }
            return valid_response_http(data={"user": val}, status=200)
        
        except:
            message = _("Error during get data model. Please contact to administrator.")
        
        return invalid_response_http(type="Getting User Profile Error", message=message, status=403)

    # update device token for push notification (mobile)
    @validate_jwt
    @http.route('/api/update_device_token', type="json", auth="none", methods=["post"], csrf=False)
    def update_device_token(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)
        device_token = payload.get("device_token", False)
        user = get_table_model('res.users').browse(uid)
        if user:
            user.write({"device_token": device_token})
            return valid_response(data='success', status=200)
        else:
            message = _("Username Not Found. Please contact to administrator.")
        return invalid_response(type="Update Device Token error", message=message, status=403)

    @validate_jwt
    @http.route('/api/get_user_employee_detail', type="http", auth="none", methods=["get"], csrf=False)
    def get_user_employee_detail(self, uid, **payload):
        try:
            employee = get_table_model('hr.employee').search([('user_id', '=', uid)])
            if employee:
                val = [
                    {
                        "title": "General",
                        "items": [
                            {
                                "label": "Name",
                                "value": employee.name or ''
                            },
                            {
                                "label": "Position",
                                "value": employee.job_id.name or ''
                            },
                            {
                                "label": "Department",
                                "value": employee.department_id.name or ''
                            },
                            {
                                "label": "Phone Number",
                                "value": employee.work_phone or ''
                            },
                            {
                                "label": "Work Email",
                                "value": employee.work_email or ''
                            },
                            {
                                "label": "Working Time",
                                "value": self.get_employee_working_time(employee) or ''
                            },
                            {
                                "label": "Start Working Day",
                                "value": ''
                            },
                        ]
                    },
                    {
                        "title": "Work Information",
                        "items": [
                            {
                                "label": "Working Address",
                                "value": employee.address_id.name or ''
                            },
                            {
                                "label": "Working Hours",
                                "value": employee.resource_calendar_id.name or ''
                            }
                        ]
                    },

                    {
                        "title": "Private Information",
                        "items": [
                            {
                                "label": "Basic Salary",
                                "value":  0.0
                            },
                            # {
                            #     "label": "Contract Start Date",
                            #     "value": employee.contract_id.date_start.strftime(
                            #         "%Y-%m-%d") if employee.contract_id.date_start else ''
                            # },
                            # {
                            #     "label": "Contract End Date",
                            #     "value": employee.contract_id.date_end.strftime(
                            #         "%Y-%m-%d") if employee.contract_id.date_end else ''
                            # },
                            # {
                            #     "label": "Bank Name",
                            #     "value": employee.bank_name_id.name or ''
                            # },
                            # {
                            #     "label": "Bank Account Number",
                            #     "value": employee.bank_account_num or ''
                            # },
                            # {
                            #     "label": "Bank Account Name",
                            #     "value": employee.bank_account_holder_name or ''
                            # }
                        ]
                    }]

                return valid_response_http(data=val, status=200)
            else:
                return invalid_response_http("Not Found", message="No employee found", status=404)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    @validate_jwt
    @http.route('/api/get_company_info', type="http", auth="none", methods=["get"], csrf=False)
    def get_company_info(self, uid, **payload):
        try:
            employee = get_table_model('hr.employee').search([('user_id', '=', uid)])
            if not employee:
                return invalid_response_http("Not Found", message="No employee found", status=404)
            company = employee.company_id

            val = [{
                "name": company.name or '',
                "logoUrl": f'/api/get_company_image/{company.id}',
                "address": company.street or '',
                "phone": company.phone or '',
                "email": company.email or '',
                "website": company.website or '',
            }]
            return valid_response_http(data=val, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    @http.route('/api/get_company_image/<int:company_id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_company_image(self, company_id, **payload):
        company = get_table_model('res.company').browse(company_id)
        if not company:
            return invalid_response_http("Not Found", message="No company found", status=404)

        image = base64.b64decode(company.logo)

        http_headers = [
            ('Content-Type', 'image/jpeg'),
            ('Content-Length', len(image)),
        ]

        return request.make_response(image, headers=http_headers)

    @staticmethod
    def get_employee_working_time(employee):
        if employee and employee.contract_id and employee.contract_id.resource_calendar_id:
            morning_start = float_to_time(employee.contract_id.resource_calendar_id.attendance_ids.filtered(
                lambda x: x.day_period == 'morning')[0].hour_from).strftime('%I:%M%p')
            afternoon_end = float_to_time(employee.contract_id.resource_calendar_id.attendance_ids.filtered(
                lambda x: x.day_period == 'afternoon')[0].hour_to).strftime('%I:%M%p')
            return f'{morning_start} to {afternoon_end}'
        return ''
