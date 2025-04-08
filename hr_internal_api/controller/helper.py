from odoo import http, SUPERUSER_ID
from odoo.http import request, Response
from odoo.tools import frozendict

from werkzeug.exceptions import (HTTPException, BadRequest, Forbidden, NotFound, Unauthorized)
from datetime import datetime

import werkzeug.wrappers
import json
import functools
import jwt
import logging
import pytz
import base64

_logger = logging.getLogger(__name__)

STATUS_COLORS = {
    'Blue': '88CED9',
    'Yellow': 'FDD37D',
    'Green': '93D3A1',
    'Grey': 'E9E9E9',
    'Red': 'EB979F',
}


def valid_response_http(data, status=200):
    """Valid Response
    This will be return when the http request was successfully processed."""
    return Response(
        status=status,
        content_type="application/json; charset=utf-8",
        response=json.dumps(data, default=datetime.isoformat),
    )


def invalid_response_http(type, message=None, status=401):
    """Invalid Response
    This will be the return value whenever the server runs into an error
    either from the client or the server."""
    # return json.dumps({})
    return Response(
        status=status,
        content_type="application/json; charset=utf-8",
        response=json.dumps(
            {
                "type": type,
                "message": str(message)
                if str(message)
                else "wrong arguments (missing validation)",
            },
            default=datetime.isoformat,
        ),
    )


def valid_response(data, status=200):
    """Valid Response
    This will be return when the json request was successfully processed."""
    return data


def invalid_response(type, message=None, status=401):
    """Invalid Response
    This will be the return value whenever the server runs into an error
    either from the client or the server."""
    body = {
        "internal": True,
        "type": type,
        "message": str(message) if str(message) else "wrong arguments (missing validation)",
        "http_status": status
    }
    if status == 400:
        raise BadRequest(body)
    elif status == 403:
        raise Forbidden(body)
    elif status == 401:
        raise Unauthorized(body)
    else:
        raise NotFound(body)


def bad_request_response(message, data=None):
    body = {
        "internal": True,
        "type": "Bad Request",
        "message": str(message) if str(message) else "wrong arguments (missing validation)",
        "data": data,
        "http_status": 400
    }
    raise werkzeug.exceptions.BadRequest(body)


def validate_token(function):
    @functools.wraps(function)
    def wrap_validate_token(self, *args, **kwargs):
        """."""
        client_token = request.httprequest.headers.get("Authorization")
        if not client_token:
            return invalid_response(
                "Client Token not found", "Missing Token in request header", 401
            )

        secret = request.env['ir.config_parameter'].sudo().get_param('internal.api.key')
        key = "Bearer " + secret

        if client_token != key:
            return invalid_response("Token Error", "Access Token seems to have expired or invalid", 401)

        user = request.env['res.users'].sudo().browse(SUPERUSER_ID).exists()
        if not user:
            user = request.env['res.users'].sudo().search([], limit=1)
        request.env.user = user
        request.env.company = user.company_id
        request.website = request.env['website'].get_current_website()
        return function(self, *args, **kwargs)

    return wrap_validate_token


def get_table_model(table_name: str):
    """return a table model for accessing database

    Arguments:
        table_name {str} -- specify table name

    Returns:
        model -- table model
    """
    return http.request.env[table_name].sudo()


# Validate whether jwt is valid or not
def validate_register_jwt(function):
    @functools.wraps(function)
    def wrap_validate_jwt(self, *args, **kwargs):
        token = request.httprequest.headers.get("registerToken")
        PRIVATE_KEY = request.env['ir.config_parameter'].sudo().get_param('internal.server.private.key')
        if not token:
            return invalid_response("Register Token Error", "Missing Register Token", 401)
        try:
            jwt_token = token.split()[1]
            decoded = jwt.decode(jwt_token, PRIVATE_KEY, algorithms='HS256')
        except jwt.exceptions.ExpiredSignatureError:
            return invalid_response(
                "Register Token Error", "Register Token is expired", 401
            )
        except jwt.exceptions.InvalidTokenError:
            return invalid_response(
                "Register Token Error", "Register Token is invalid", 401
            )
        except jwt.exceptions.DecodeError:
            return invalid_response(
                "Register Token Error", "Register Token is error while decoding", 401
            )
        except:
            return invalid_response(
                "Register Token Error", "Register Token is invalid", 401
            )

        user = request.env['res.users'].sudo().browse(SUPERUSER_ID).exists()
        if not user:
            user = request.env['res.users'].sudo().search([], limit=1)
        request.env.user = user
        request.env.company = user.env.company.search([], limit=1)
        return function(self, *args, **kwargs, phone=decoded['phone'], password=decoded['password'], ip=decoded['ip'],
                        application_id=decoded['application_id'], name=decoded['name'])

    return wrap_validate_jwt


# Validate whether jwt is valid or not
def validate_pw_jwt(function):
    @functools.wraps(function)
    def wrap_validate_jwt(self, *args, **kwargs):
        token = request.httprequest.headers.get("resetToken")
        PRIVATE_KEY = request.env['ir.config_parameter'].sudo().get_param('internal.server.private.key')
        if not token:
            return invalid_response("Reset Token Error", "Missing Reset Token", 401)
        try:
            jwt_token = token.split()[0]
            decoded = jwt.decode(jwt_token, PRIVATE_KEY, algorithms='HS256')
        except jwt.exceptions.ExpiredSignatureError:
            return invalid_response(
                "Reset Token Error", "Reset Token is expired", 401
            )
        except jwt.exceptions.InvalidTokenError:
            return invalid_response(
                "Reset Token Error", "Reset Token is invalid", 401
            )
        except jwt.exceptions.DecodeError:
            return invalid_response(
                "Reset Token Error", "Reset Token is error while decoding", 401
            )
        except:
            return invalid_response(
                "Reset Token Error", "Reset Token is invalid", 401
            )

        user = request.env['res.users'].sudo().browse(decoded['user_id'])
        request.uid = user.id
        request.env.user = user
        request.env.company = user.env.company.search([], limit=1)
        return function(self, *args, **kwargs, uid=decoded['user_id'], code=decoded['code'])

    return wrap_validate_jwt


# Validate whether jwt is valid or not
def validate_jwt(function):
    @functools.wraps(function)
    def wrap_validate_jwt(self, *args, **kwargs):
        token = request.httprequest.headers.get("Authorization").replace("Bearer ", "") \
            if request.httprequest.headers.get("Authorization") else None
        PRIVATE_KEY = request.env['ir.config_parameter'].sudo().get_param('internal.server.private.key')

        if not token:
            return invalid_response_http("Access Token Error", "Missing Access Token", 401)
        try:
            jwt_token = token.split()[0]

            # check jwt token if blacklisted
            blacklist = get_table_model('blacklist.token')
            if blacklist.check_token(jwt_token):
                return invalid_response_http(
                    "Access Token Error", "Access Token is invalid", 401
                )

            decoded = jwt.decode(jwt_token, PRIVATE_KEY, algorithms='HS256')
            # check jwt token expired
            if decoded['exp'] < datetime.now().timestamp():
                return invalid_response_http(
                    "Access Token Error", "Access Token is expired", 401
                )
        except jwt.exceptions.ExpiredSignatureError:
            return invalid_response_http(
                "Access Token Error", "Access Token is expired", 401
            )
        except jwt.exceptions.InvalidTokenError:
            return invalid_response_http(
                "Access Token Error", "Access Token is invalid", 401
            )
        except jwt.exceptions.DecodeError:
            return invalid_response_http(
                "Access Token Error", "Access Token is error while decoding", 401
            )
        except:
            return invalid_response_http(
                "Access Token Error", "Access Token is invalid", 401
            )

        # check jwt token expired
        if decoded['exp'] < datetime.now().timestamp():
            return invalid_response(
                "Access Token Error", "Access Token is expired", 401
            )

        user = request.env['res.users'].sudo().browse(decoded['user_id'])
        context = request.context.copy()
        if user.lang:
            context.update({
                'lang': user.lang,
                'tz': user.tz
            })
        request._context = frozendict(context)
        request.env.uid = user.id
        request.env.user = user
        request.env.company = user.company_id
        if not user.company_id:
            request.env.company = user.env.company.search([], limit=1)
        request.website = request.env['website'].get_current_website()
        return function(self, *args, **kwargs, uid=decoded['user_id'])

    return wrap_validate_jwt


# -------------------------------------------------------------------------
# UTILITIES FUNCTIONS
# -------------------------------------------------------------------------


def get_selection_string_value(record, selection_field: str) -> str:
    """
    This function will return a possible value of selection field from given `record`.
    In case the field not found, an empty string is returned.

    :param record: an object
    :param selection_field (str): selection field name
    :return: a string value correspond to the selection key.
    """
    selection_key = getattr(record, selection_field, None)

    if not selection_key:
        return ""
    
    return dict(record._fields[selection_field]._description_selection(request.env)).get(selection_key, "")

def combine_date_with_current_time(date: str, format=None) -> datetime:
    """ Parse a provided `date` string with current time.

    :params `date`: string date to be parsed
    :params `format`: the default format is `%Y-%m-%d`
    :return `datetime` object
    """
    format = "%Y-%m-%d"
    return datetime.combine(
        datetime.strptime(date, format), datetime.now().time()
    )

def convert_to_target_timezone(dt, target_timezone, str_format=None):
    """ Convert a given datetime object to target timezone.
    Returns datetime object or string representation if `str_format` is provided. 
    """
    if not isinstance(dt, datetime):
        return False
    if isinstance(target_timezone, str):
        target_timezone = pytz.timezone(target_timezone)

    aware_datetime = dt.astimezone(target_timezone)
    if str_format:
        aware_datetime = aware_datetime.strftime(str_format)
    return aware_datetime

def upload_attachments(files: list, res_id: int, res_model: str) -> list:
    """ Create `ir.attachment` from provided `files` and link them to Resource ID and Model. """
    attachment_sudo = get_table_model('ir.attachment')
    is_internal_user = request.env.user._is_internal()

    attachment_ids = []
    for file in files:
        attachment = attachment_sudo._from_request_file(
            file, mimetype='TRUST' if is_internal_user else 'GUESS'
        )
        attachment.res_id = res_id
        attachment.res_model = res_model
        attachment_ids.append(attachment.id)

    return attachment_ids

def serve_attachment(attachment_id: int):
    """ Serves the `ir.attachment` as an HTTP response. """
    attachment = get_table_model('ir.attachment').search([('id', '=', attachment_id)], limit=1)

    if not attachment:
        return invalid_response_http(type="Not Found", message="Attachment not found", status=404)

    mimetype = attachment.mimetype
    if mimetype not in ['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'application/pdf']:
        return invalid_response_http(type="Bad Request", message="Attachment type not supported", status=400)

    decoded_data = base64.b64decode(attachment.datas)
    http_headers = [
        ('Content-Type', mimetype),
        ('Content-Length', len(decoded_data)),
    ]

    return request.make_response(decoded_data, headers=http_headers)
