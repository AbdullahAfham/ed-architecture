from odoo import http, SUPERUSER_ID
from odoo.http import request, content_disposition
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model, valid_response_http, \
    invalid_response_http


class PayslipAPI(http.Controller):

    @validate_jwt
    @http.route('/api/payslip', type="http", auth="none", methods=["get"], csrf=False)
    def get_user_payslip(self, uid, **payload):
        try:
            payslip_model = get_table_model('hr.payslip')

            domain = [
                ('employee_id.user_id', '=', uid),
                ('state', 'in', ['done', 'paid'])
            ]
            if payload.get('date_from'):
                domain.append(('date_from', '>=', payload.get('date_from')))
            if payload.get('date_to'):
                domain.append(('date_to', '<=', payload.get('date_to')))

            payslips = payslip_model.search(domain, order='date_from desc')

            vals = []
            for payslip in payslips:
                val = {
                    "id": payslip.id,
                    "name": payslip.name,
                    "reference": payslip.number,
                    'employee_id': {
                        'id': payslip.employee_id.id,
                        'name': payslip.employee_id.name,
                    },
                    "date_from": payslip.date_from.strftime('%Y-%m-%d') or "",
                    "date_to": payslip.date_to.strftime('%Y-%m-%d') or "",
                    'basic_wage': payslip.contract_id.wage,
                    "state": payslip.state,
                    "struct": payslip.struct_id.name,
                    "contract": payslip.contract_id.name,
                }

                vals.append(val)
            return valid_response_http(data=vals, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    @validate_jwt
    @http.route('/api/payslip/<int:id>', type="http", auth="none", methods=["get"], csrf=False)
    def get_payslip(self, uid, id, **payload):
        try:
            payslip = get_table_model('hr.payslip').search([('id', '=', id)])

            if payslip.employee_id.user_id.id != uid:
                return invalid_response_http(
                    type="Unauthorized",
                    message="You are not authorized to access this payslip",
                    status=401
                )

            if payslip:
                details = []
                payslip_lines = payslip.line_ids

                for line in payslip_lines:
                    details.append({
                        "id": line.id,
                        "name": line.name,
                        "total": line.total,
                    })

                basic = payslip.basic_wage
                net = payslip.net_wage

                val = {
                    "id": payslip.id,
                    "name": payslip.name,
                    "basic_wage": basic,
                    "net_wage": net,
                    "date_from": payslip.date_from.strftime("%Y-%m-%d") or "",
                    "date_to": payslip.date_to.strftime("%Y-%m-%d") or "",
                    "state": payslip.state,
                    "details": details,
                }
                return valid_response_http(data=val, status=200)
            else:
                return invalid_response_http(type="Not Found", message="No payslip found", status=404)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    @validate_jwt
    @http.route("/api/payslip/download/<int:id>", type="http", auth="none", methods=["get"], csrf=False)
    def download_user_payslip(self, uid, id, **payload):
        try:
            payslip = get_table_model('hr.payslip').search([('id', '=', id)])

            if payslip.employee_id.user_id.id != uid:
                return invalid_response_http(
                    type="Unauthorized",
                    message="You are not authorized to access this payslip",
                    status=401
                )

            if payslip:
                report_sudo = request.env.ref('hr_payroll_community.action_report_payslip').with_user(SUPERUSER_ID)

                if hasattr(payslip, 'company_id'):
                    report_sudo = report_sudo.with_company(payslip.company_id)

                pdf_content, _ = report_sudo._render_qweb_pdf(report_sudo.id, payslip.ids)

                filename = payslip.name + '.pdf'
                reportHttpHeaders = [
                    ('Content-Type', 'application/pdf'),
                    ('Content-Length', len(pdf_content)),
                    ('Content-Disposition', content_disposition(filename))
                ]

                return request.make_response(pdf_content, headers=reportHttpHeaders)
            else:
                return invalid_response_http(type="Not Found", message="No payslip found", status=404)

        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)
