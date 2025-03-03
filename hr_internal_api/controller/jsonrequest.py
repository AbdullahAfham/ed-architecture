import logging
from odoo.http import SessionExpiredException, serialize_exception
import json
from odoo.http import JsonRPCDispatcher
from werkzeug.exceptions import (HTTPException, BadRequest, Forbidden,
                                 NotFound, Unauthorized)


_handle_error = JsonRPCDispatcher.handle_error  # original json handle_error method

_logger = logging.getLogger(__name__)

def handle_error(self, exc):
    """
    Handle any exception that occurred while dispatching a request to
    a `type='json'` route. Also handle exceptions that occurred when
    no route matched the request path, that no fallback page could
    be delivered and that the request ``Content-Type`` was json.

    :param exc Exception: the exception that occurred.
    :returns: an HTTP error response
    :rtype: Response
    """
    request_id = self.jsonrequest.get('id')
    try:
        data = exc.description
        if isinstance(data,dict) and data.get('internal',False):
            data.pop('internal')
            return self.request.make_json_response({'jsonrpc': '2.0', 'id': request_id, 'error': data}, status=data.get('http_status', 200))
    except:
        pass

    try:
        return _handle_error(self, exc)
    except Exception:
        error = {
            'code': 200,  # this code is the JSON-RPC level code, it is
                          # distinct from the HTTP status code. This
                          # code is ignored and the value 200 (while
                          # misleading) is totally arbitrary.
            'message': "Odoo Server Error",
            'data': serialize_exception(exc),
        }
        if isinstance(exc, NotFound):
            error['http_status'] = 404
            error['code'] = 404
            error['message'] = "404: Not Found"
        elif isinstance(exc, SessionExpiredException):
            error['code'] = 100
            error['message'] = "Odoo Session Expired"
        elif isinstance(exc, Unauthorized):
            error['http_status'] = 401
            error['code'] = 401
            error['message'] = "Unauthorized"
        elif isinstance(exc, Forbidden):
            error['http_status'] = 403
            error['code'] = 403
            error['message'] = "Forbidden"
        elif isinstance(exc, BadRequest):
            error['http_status'] = 400
            error['code'] = 400
            error['message'] = "Bad Request"
        return self.request.make_json_response({'jsonrpc': '2.0', 'id': request_id, 'result': error}, status=error.get('code', 200))

JsonRPCDispatcher.handle_error = handle_error