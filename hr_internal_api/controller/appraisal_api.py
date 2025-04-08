import base64
import json

from odoo import http, _
from odoo.addons.hr_internal_api.controller.helper import validate_jwt, get_table_model,\
    valid_response, invalid_response, valid_response_http, invalid_response_http, STATUS_COLORS
from odoo.http import request

import logging

_logger = logging.getLogger(__name__)


class AppraisalAPI(http.Controller):

    # get current user appraisal
    @validate_jwt
    @http.route('/api/get_user_appraisals', type="http", auth="none", methods=["get"], csrf=False)
    def get_user_appraisals(self, uid, **payload):
        try:
            appraisal_model = get_table_model('hr.appraisal')
            employee_model = get_table_model('hr.employee')

            employee = employee_model.search([('user_id', '=', uid)])
            domain = ['&', '|', ('emp_id.user_id', '=', uid), ('emp_id.parent_id', '=', employee.id), ('state', 'not in', ['cancel', 'new'])]

            appraisals = appraisal_model.search(domain)

            val = []
            for appraisal in appraisals:
                d = {
                    'id': appraisal.id,
                    'employee_id': appraisal.emp_id.name,
                    "date" : appraisal.appraisal_deadline.strftime("%d-%m-%Y") if appraisal.appraisal_deadline else '',
                    "state": appraisal.state.name or 'To Confirm',
                }
                val.append(d)
            data = {
                'appraisals': val
            }

            return valid_response_http(data=data, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)


    # get current user appraisal
    @validate_jwt
    @http.route('/api/get_appraisal_detail', type="http", auth="none", methods=["get"], csrf=False)
    def get_appraisal_detail(self, uid, **payload):
        appraisal_id = payload.get('appraisal_id', False)
        try:
            appraisal_model = get_table_model('hr.appraisal')
            appraisal_note_model = get_table_model('hr.appraisal.note')
            survey_input_model = get_table_model('survey.user_input')
            survey_domain = [('appraisal_id.id', '=', appraisal_id), ('state', '=', 'done')]

            survey_ids = survey_input_model.search(survey_domain)

            surveys = []
            for survey in survey_ids:
                if survey.state == 'new':
                    answer_url = survey.survey_start_url
                    state = 'Not Started Yet'
                elif survey.state == 'done':
                    answer = survey.action_print_answers()
                    answer_url = '%s%s' % (survey.get_base_url(), answer['url'])
                    state = 'Completed'
                elif survey.state == 'in_progress':
                    answer_url = survey.survey_start_url
                    state = 'In Progress'
                else:
                    answer_url = survey.survey_start_url
                    state = 'Not Started Yet'

                d = {
                    'id': survey.id,
                    'name': survey.survey_id.title,
                    'employee_id': survey.appraisal_id.emp_id.name or 'No Name',
                    'partner_id': survey.partner_id.name,
                    'deadline': survey.deadline.strftime("%d-%m-%Y") if survey.deadline else '',
                    'url': answer_url or '',
                    'score': '' if survey.survey_id.scoring_type == 'no_scoring' else survey.scoring_percentage,
                    'state': state,
                }

                surveys.append(d)

            domain = [('id', '=', appraisal_id)]

            appraisal = appraisal_model.search(domain)
            skills = []

            # for skill in appraisal.skill_ids:
            #     skills.append({
            #         'id': skill.id,
            #         "name": skill.skill_id.name,
            #         "level": skill.skill_level_id.name or '',
            #         "progress": skill.level_progress,
            #         "justification": skill.justification or ''
            #     })
            notes = appraisal_note_model.search([])
            rating_option = []
            for note in notes:
                rating_option.append({'sequence': note.sequence, 'name': note.name})


            data = {
                "employee_id": appraisal.emp_id.name,
                "date": appraisal.appraisal_deadline.strftime("%d-%m-%Y") if appraisal.appraisal_deadline else '',
                "state": appraisal.state.name or 'Cancelled',
                "manager_id": appraisal.hr_manager_id[0].name or '',
                "department_id": appraisal.emp_id.department_id.name or '',
                "position": appraisal.emp_id.job_title or '',
                "rating_option": rating_option,
                "final_rating": appraisal.assessment_note.name or '',
                "is_employee_feedback": False,
                "employee_feedback": '',
                "is_manager_feedback": True,
                "manager_feedback": appraisal.final_evaluation or '',
                "surveys": surveys,
                "skills": skills,
            }

            return valid_response_http(data=data, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)

    # Update Final Rating
    @validate_jwt
    @http.route('/api/update_final_rating', type="http", auth="none", methods=["post"], csrf=False)
    def update_final_rating(self, uid, **payload):
        try:
            if not payload:
                payload = json.loads(request.httprequest.data)
            appraisal_id = payload.get('appraisal_id')
            sequence = payload.get('sequence')

            appraisal_model = get_table_model('hr.appraisal')
            employee_model = get_table_model('hr.employee')
            user_model = get_table_model('res.users')
            appraisal_note_model = get_table_model('hr.appraisal.note')
            survey_input_model = get_table_model('survey.user_input')
            domain = [('id', '=', appraisal_id)]


            # check if current user is able to create Batch OT
            appraisal = appraisal_model.search(domain, limit=1)
            # if appraisal.state != 'pending':
            #     return invalid_response_http(type='Bad Request', message='You can not update final for appraisal not in progress', status=403)
            if appraisal.emp_id.user_id.id == uid:
                return invalid_response_http(type='Bad Request', message='You can not update final for yourself', status=400)

            assessment_note = appraisal_note_model.search([('sequence', '=', sequence)], limit=1)
            appraisal.assessment_note = assessment_note.id

            # return response
            data = {
                'id': appraisal.id,
                'message': 'Updated Successfully'
            }

            return valid_response_http(data=data, status=200)
        except Exception as e:
            return invalid_response_http(str(e), status=400)

    # get current survey
    @validate_jwt
    @http.route('/api/get_user_survey', type="http", auth="none", methods=["get"], csrf=False)
    def get_user_survey(self, uid, **payload):
        try:
            survey_input_model = get_table_model('survey.user_input')
            users_model = get_table_model('res.users')
            user_id = users_model.search([('id', '=', uid)])
            domain = [('partner_id', '=', user_id.partner_id.id), ('state', '!=', 'cancel')]

            surveys = survey_input_model.search(domain)

            val = []
            for survey in surveys:
                if survey.state == 'new':
                    state = 'Not Started Yet'
                elif survey.state == 'done':
                    state = 'Completed'
                elif survey.state == 'in_progress':
                    state = 'In Progress'
                else:
                    state = 'Not Started Yet'

                if survey.state == 'done':
                    answer = survey.action_print_answers()
                    start_url = '%s/%s%s' % (survey.get_base_url(), user_id.lang, answer['url'])
                else:
                    # start_url = survey.survey_start_url
                    start_url = '%s/%s/survey/%s/%s' % (survey.get_base_url(), user_id.lang, survey.survey_id.access_token, survey.access_token)

                d = {
                    'id': survey.id,
                    'name': survey.survey_id.title,
                    'employee_id': survey.appraisal_id.emp_id.name or 'No Name',
                    'partner_id': survey.partner_id.name,
                    'deadline': survey.deadline.strftime("%d-%m-%Y") if survey.deadline else '',
                    'start_url': start_url or '',
                    'score': '' if survey.survey_id.scoring_type == 'no_scoring' else survey.scoring_percentage,
                    'state': state,
                }                
                val.append(d)
            
            data = {
                'surveys': val
            }

            return valid_response_http(data=data, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)


    # get current user goals
    @validate_jwt
    @http.route('/api/get_user_goals', type="http", auth="none", methods=["get"], csrf=False)
    def get_user_goals(self, uid, **payload):
        try:
            hr_appraisal_goal_model = get_table_model('hr.appraisal.goal')
            users_model = get_table_model('res.users')
            user_id = users_model.search([('id', '=', uid)])
            domain = ['|', ('employee_id', '=', user_id.employee_id.id), ('manager_id', '=', user_id.employee_id.id)]

            goals = hr_appraisal_goal_model.search(domain)

            val = []
            for goal in goals:
                d = {
                    'id': goal.id,
                    'name': goal.name,
                    'employee_id': goal.employee_id.name or 'No Name',
                    'manager_id': goal.manager_id.name or 'No Name',
                    'deadline': goal.deadline.strftime("%d-%m-%Y") if goal.deadline else '',
                    'progression': goal.progression or '',
                    'progression_option': ['0', '25', '50', '75', '100'],
                }
                val.append(d)
            data = {
                'goals': val
            }

            return valid_response_http(data=data, status=200)
        except Exception as e:
            return invalid_response_http(type(e).__name__, message=str(e), status=400)


    # Update Goal Progression
    @validate_jwt
    @http.route('/api/update_goal_progression', type="http", auth="none", methods=["post"], csrf=False)
    def update_goal_progression(self, uid, **payload):
        try:
            if not payload:
                payload = json.loads(request.httprequest.data)
            goal_id = payload.get('goal_id')
            progression = payload.get('progression')

            hr_appraisal_goal_model = get_table_model('hr.appraisal.goal')
            domain = [('id', '=', goal_id)]

            # check if current user is able to create Batch OT
            goal = hr_appraisal_goal_model.search(domain, limit=1)
            if goal.progression == '100':
                return invalid_response_http(type='Bad Request', message='You can not update Done goal', status=403)
            if goal.employee_id.user_id.id == uid:
                return invalid_response_http(type='Bad Request', message='You can not update Goal for yourself', status=400)

            goal.progression = progression
            # return response
            data = {
                'id': goal.id,
                'message': 'Updated Successfully'
            }

            return valid_response_http(data=data, status=200)
        except Exception as e:
            return invalid_response_http(str(e), status=400)