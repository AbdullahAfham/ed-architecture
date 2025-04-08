# -*- coding: utf-8 -*-
###################################################################################
#    A part of OpenHRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2018-TODAY Cybrosys Technologies (<https://www.cybrosys.com>).
#    Author: Ijaz Ahammed (<https://www.cybrosys.com>)
#
#    This program is free software: you can modify
#    it under the terms of the GNU Affero General Public License (AGPL) as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
###################################################################################
{
    'name': 'HR Overtime',
    'version': '1.0',
    'summary': 'Manage Employee Overtime',
    'description': """
        Helps you to manage Employee Overtime.
        """,
    'category': 'Generic Modules/Human Resources',
    'author': "",
    'live_test_url': '',
    'company': '',
    'maintainer': '',
    'website': "",
    'depends': [
        'web', 
        'base', 
        'hr', 
        'hr_contract', 
        'hr_attendance', 
        'hr_holidays', 
        'project',
        'mail', 
        'hr_timesheet'
    ],
    'external_dependencies': {
        'python': ['pandas'],
    },
    'data': [
        'security/overtime_security.xml',
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/overtime_request_view.xml',
        'views/overtime_settings_menu.xml',
        'views/overtime_type.xml',
        'views/overtime_batch_request_view.xml',
        'views/hr_contract.xml',
        # 'views/hr_payslip.xml',
        'views/edit_project_view.xml',
        'reports/batch_overtime_template.xml',
        'data/clean_bot_data.xml',
    ],
    'demo': ['data/hr_overtime_demo.xml'],
    'images': ['static/description/banner.png'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
