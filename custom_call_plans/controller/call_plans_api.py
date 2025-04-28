from odoo import http, Command
from odoo.http import request
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    valid_response, invalid_response, valid_response_http, invalid_response_http,\
    get_selection_string_value, combine_date_with_current_time, convert_to_target_timezone, upload_attachments

from odoo.tools import html2plaintext, str2bool
from datetime import datetime

import calendar
import json
import pytz
import ast

import logging

_logger = logging.getLogger(__name__)


class CallPlansAPI(http.Controller):
    
    @validate_jwt
    @http.route('/api/create_call_plan', type="http", auth="none", methods=["post"], csrf=False)
    def create_call_plan(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        plan_name = payload.get('plan_name')
        partner_id = payload.get('partner_id')
        plan_type_id = payload.get('plan_type_id')
        date = payload.get('date')
        start_time = payload.get('start_time')
        end_time = payload.get('end_time')
        tag_ids = payload.get('tag_ids', [])
        description = payload.get('description')

        # validation here
        current_user = get_table_model('res.users').search([('id', '=', uid)], limit=1)
        if not current_user:
            return invalid_response_http("Not Found", 'User not found.', status=404)

        if not plan_name:
            return invalid_response_http("Bad Request", 'Plan Topic is required.', status=400)

        if not partner_id:
            return invalid_response_http("Bad Request", 'Customer is required.', status=400)

        if not plan_type_id:
            return invalid_response_http("Bad Request", 'Plan Type is required.', status=400)

        if not date or not start_time or not end_time:
            return invalid_response_http("Bad Request", 'Date and Time are required.', status=400)

        if tag_ids:
            tag_ids = ast.literal_eval(tag_ids) # safely evaluates the string -> list of ids

        try:
            date_start = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M:%S")
            date_stop = datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M:%S")

            # in creation, it expects a naive datetime, also store in utc to avoid timezone conversion issues
            naive_utc_date_start = self._get_naive_utc_datetime(date_start, self._get_default_timezone())
            naive_utc_date_stop = self._get_naive_utc_datetime(date_stop, self._get_default_timezone())

            values = {
                'name': plan_name,
                'partner_id': partner_id,
                'user_id': current_user.id,
                'plan_type_id': plan_type_id,
                'date': datetime.strptime(date, "%Y-%m-%d"),
                'date_start': naive_utc_date_start,
                'date_stop': naive_utc_date_stop,
                'tag_ids': [Command.set(tag_ids)],
                'note': description,
                'company_id': current_user.company_id.id,
            }

            call_plan = get_table_model('call.plans').create(values)

            # Trigger oncahnge to update some fields related to partner
            call_plan._onchange_partner_id()

            # link attachments
            if payload.get('attachment_ids'):
                attachments = get_table_model('ir.attachment').search([
                    ('id', 'in', payload['attachment_ids']),
                    ('res_id', '=', False),
                    ('res_model', '=', False),
                ])
                attachments.write({
                    'res_id': call_plan.id, 'res_model': call_plan._name
                })

            response = {
                'id': call_plan.id, 
                'message': 'Created Successfully'
            }
            return valid_response_http(data=response, status=200)

        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/update_call_plan', type="http", auth="none", methods=["post"], csrf=False)
    def update_call_plan(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        if not payload.get('call_plan_id'):
            return invalid_response_http("Bad Request", "Call Plan ID is required.", status=400)

        call_plan = get_table_model('call.plans').search([('id', '=', payload['call_plan_id'])], limit=1)

        if not call_plan.exists():
            return invalid_response_http("Not Found", "Call Plan not found.", status=404)

        try:
            # expected fields, with valid values
            fields_to_update = ['note']
            values_to_update = {key: payload[key] for key in fields_to_update if payload.get(key)}

            if payload.get('date') and payload.get('start_time') and payload.get('end_time'):
                date_start = datetime.strptime(f"{payload['date']} {payload['start_time']}", "%Y-%m-%d %H:%M:%S")
                date_stop = datetime.strptime(f"{payload['date']} {payload['end_time']}", "%Y-%m-%d %H:%M:%S")

                # it expects a naive datetime, also store in utc to avoid timezone conversion issues
                naive_utc_date_start = self._get_naive_utc_datetime(date_start, self._get_default_timezone())
                naive_utc_date_stop = self._get_naive_utc_datetime(date_stop, self._get_default_timezone())

                values_to_update.update({
                    'date': payload['date'], 
                    'date_start': naive_utc_date_start, 
                    'date_stop': naive_utc_date_stop,
                })

            # execute an update
            call_plan.sudo().write(values_to_update)

            # link attachments
            if payload.get('attachment_ids'):
                attachments = get_table_model('ir.attachment').search([
                    ('id', 'in', payload['attachment_ids']),
                    ('res_id', '=', False),
                    ('res_model', '=', False),
                ])
                attachments.write({
                    'res_id': call_plan.id, 'res_model': call_plan._name
                })

            response = {
                'id': call_plan.id, 
                'message': 'Updated Successfully'
            }

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route([
        '/api/get_call_plans', 
        '/api/get_call_plans/<int:call_plan_id>'], type="http", auth="none", methods=["get"], csrf=False
    )
    def get_call_plans(self, uid, call_plan_id=None, **payload):
        try:
            current_user = get_table_model('res.users').search([('id', '=', uid)], limit=1)

            if not current_user:
                return invalid_response_http("Not Found", 'User not found.', status=404)
            
            timezone = current_user.tz or self._get_default_timezone()
            request.session['timezone'] = timezone  # ensure timezone is consistent in _prepare_call_plan_detail

            # make sure current_user must be included
            payload.update({'current_user': current_user})

            if not call_plan_id:
                domain = self._get_call_plan_domain_filters(**payload)
            else:
                domain = [('id', '=', call_plan_id)]    # view call plans detail

            # determine raw data or grouped data
            groupby = payload.get('groupby', None) if not call_plan_id else None

            # fetch `call.plans` data
            call_plans = self._get_call_plans(domain, groupby)

            # For multiple records.
            if groupby is not None:
                response = []
                for date, plan_type, grouped_data, count in call_plans:
                    response.append({
                        "date": date and date.strftime('%Y-%m-%d') or "None",
                        "plan_type": plan_type.name or "None",
                        "count": count,
                        "data": [self._prepare_call_plan(call_plan) for call_plan in grouped_data]
                    })
            else:
                response = [self._prepare_call_plan(call_plan) for call_plan in call_plans]

            # For optimization purpose, we include the details only when viewing specific record.
            if call_plan_id and len(call_plans) == 1:
                response = [{
                    **response[0],
                    **self._prepare_call_plan_detail(call_plans)
                }]

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    def _prepare_call_plan(self, call_plan):
        """ Prepare `call.plans` data to be returned. """
        partner_employee = call_plan.partner_id.employee_id
        return {
            'id': call_plan.id,
            'name': call_plan.name,
            'name_en': call_plan.partner_id.khmer_name or call_plan.partner_id.name,
            'name_km': call_plan.partner_id.name,
            'phone': call_plan.partner_id.phone or "",
            'profile_url': f'/api/get_employee_image/{partner_employee.id}' if partner_employee else "",
            'date': call_plan.date and call_plan.date.strftime('%Y-%m-%d') or "",
            'plan_type': {
                'id': call_plan.plan_type_id.id,
                'name': call_plan.plan_type_id.name,
                'color': call_plan.plan_type_id.color,
            },
            'date_start': convert_to_target_timezone(call_plan.date_start, self._get_default_timezone(), '%Y-%m-%d %H:%M:%S') or "",
            'date_stop': convert_to_target_timezone(call_plan.date_stop, self._get_default_timezone(), '%Y-%m-%d %H:%M:%S') or "",
            'stage': call_plan.stage_id.name or "",
        }

    def _prepare_call_plan_detail(self, call_plan):
        """ Prepare `call.plans` data for more detail when viewing specific record. """
        next_stage = call_plan._get_next_stage()
        next_stage_id = next_stage.get('id') if next_stage else None
        next_stage_label = f"Move To {next_stage.get('name') if next_stage else call_plan.stage_id.name}"

        return {
            'body': [
                {
                    "key": "partner_id",
                    "label": "Customer",
                    "value": call_plan.partner_id.name,
                    "is_highlight": True
                },
                {
                    "key": "address",
                    "label": "Address",
                    "value": " ".join(call_plan.partner_id._display_address(without_company=True).split()),    # remove white-space
                    "is_highlight": False
                },
                {
                    "key": "phone",
                    "label": "Phone",
                    "value": call_plan.partner_id.phone or "",
                    "is_highlight": False
                },
                {
                    "key": "date",
                    "label": "Date",
                    "value": call_plan.date and call_plan.date.strftime('%d-%m-%Y') or "",
                    "is_highlight": False
                },
                {
                    "key": "date_start",
                    "label": "Day From",
                    "value": convert_to_target_timezone(call_plan.date_start, self._get_default_timezone(), '%Y-%m-%d %H:%M:%S') or "",
                    "is_highlight": False
                },
                {
                    "key": "date_stop",
                    "label": "Day To",
                    "value": convert_to_target_timezone(call_plan.date_stop, self._get_default_timezone(), '%Y-%m-%d %H:%M:%S') or "",
                    "is_highlight": False
                },
                {
                    "key": "tag_ids",
                    "label": "Tags",
                    "value": ", ".join([tag.name for tag in call_plan.tag_ids]),
                    "is_highlight": False
                },
            ],
            "description": html2plaintext(call_plan.note or ""),
            "attachments": [
                f"/api/get_attachment/{attach.id}" for attach in call_plan.attachment_ids
            ],
            "next_stage": {
                "key": "",
                "label": next_stage_label,
                "value": next_stage_id,
                "is_highlight": False
            },
        }

    def _get_call_plan_domain_filters(self, **payload):
        """ Returns a search domain provided by query parameters `payload`. """

        domain = [
            '|', ('create_uid', '=', payload['current_user'].id), ('user_id', '=', payload['current_user'].id)
        ]

        # by `Plan Type`
        if payload.get('plan_type_id'):
            domain += [('plan_type_id', '=', int(payload['plan_type_id']))]

        # by `Date`
        if payload.get('date'):
            if str2bool(payload.get('exclude_day'), False):
                # extract year, month, and casting them to int
                year = int(payload['date'].split("-")[0])
                month = int(payload['date'].split("-")[1])
                
                last_day = calendar.monthrange(year, month)[1]

                from_date = f"{year}-{month:02d}-01"
                to_date = f"{year}-{month:02d}-{last_day}"

                _logger.info(f"Get Call Plans by Month: {from_date} - {to_date}")

                domain += [('date', '>=', from_date), ('date', '<', to_date)]   # use only year-month from `date` (ignore day)
            else:
                _logger.info(f"Get Call Plans on: {payload['date']}")

                domain += [('date', '=', payload['date'])]  # use actual value of `date`

        # by `Create Date`
        if payload.get('date_from') and payload.get('date_to'):
            domain += [('create_date', '>=', payload['date_from']), ('create_date', '<=', payload['date_to'])]

        # by `Name` or `Customer Name`
        if payload.get('keyword'):
            domain += ['|', ('name', 'ilike', payload['keyword']), ('partner_id.name', 'ilike', payload['keyword'])]

        return domain

    def _get_default_timezone(self):
        """ Find the default timezone from the value store in the session. """
        timezone = request.session.get('timezone')
        if not timezone:
            timezone = request.env.context.get('tz') or 'Asia/Phnom_Penh'
            request.session['timezone'] = timezone

        _logger.info(f"Timezone: {timezone}")

        return timezone

    def _get_naive_utc_datetime(self, dt, tz):
        timezone = pytz.timezone(tz)
        aware_datetime = timezone.localize(dt)
        naive_utc_date_start = convert_to_target_timezone(aware_datetime, "UTC").replace(tzinfo=None)
        return naive_utc_date_start

    def _get_call_plans(self, domain, groupby=None):
        """ Returns `call.plans` recordset or a list of tuples containing 
        the group values and aggregated values (`call.plans` recordset and `count`) if groupby is set. 
        """
        if groupby is not None:
            return get_table_model('call.plans')._read_group(
                domain=domain, groupby=['date:day', 'plan_type_id'], aggregates=['id:recordset', '__count']
            )
        else:
            return get_table_model('call.plans').search(
                domain=domain, order="create_date desc"
            )

    @validate_jwt
    @http.route('/api/get_call_plan_stages', type="http", auth="none", methods=["get"], csrf=False)
    def get_call_plan_stages(self, uid, **payload):
        try:
            domain = []
            stages = get_table_model('call.plans.stages').search(domain)

            response = [{'id': stage.id, 'name': stage.name} for stage in stages]

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/get_call_plan_tags', type="http", auth="none", methods=["get"], csrf=False)
    def get_call_plan_tags(self, uid, **payload):
        try:
            domain = []
            tags = get_table_model('call.plans.tags').search(domain)

            response = [{'id': tag.id, 'name': tag.name} for tag in tags]

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/get_call_plan_types', type="http", auth="none", methods=["get"], csrf=False)
    def get_call_plan_types(self, uid, **payload):
        try:
            domain = []
            types = get_table_model('call.plans.types').search(domain)
            
            response = [{'id': type.id, 'name': type.name, 'color': type.color} for type in types]

            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)

    @validate_jwt
    @http.route('/api/update_call_plan_stage', type="http", auth="none", methods=["post"], csrf=False)
    def update_call_plan_stage(self, uid, **payload):
        if not payload:
            payload = json.loads(request.httprequest.data)

        # validation here
        current_user = get_table_model('res.users').search([('id', '=', uid)], limit=1)
        if not current_user:
            return invalid_response_http("Not Found", 'User not found.', status=404)

        if not payload.get('call_plan_id'):
            return invalid_response_http("Bad Request", 'Call Plan ID is required.', status=400)

        if not payload.get('stage_id'):
            return invalid_response_http("Bad Request", 'Stage to move is required.', status=400)

        try:
            call_plan = get_table_model('call.plans').browse(payload['call_plan_id'])

            # update
            call_plan.sudo().write({'stage_id': payload['stage_id']})

            response = {
                'id': call_plan.id, 
                'message': 'Move Stage Successfully'
            }
            return valid_response_http(data=response, status=200)
        except Exception as e:
            return invalid_response_http("Bad Request", str(e), status=400)
