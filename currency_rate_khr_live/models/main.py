# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _

import re
from urllib.request import urlopen
from datetime import datetime, timedelta

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

class ResCompany(models.Model):
    _inherit = 'res.company'

    currency_provider = fields.Selection(selection_add=[
        ('dtc', 'Department of Taxation Cambodia'),
        ('nbc', 'National Bank of Cambodia'),
    ], default='nbc', string='Service Provider')

    def _parse_dtc_data(self, available_currencies):
        ''' This method is used to update the currencies by using ECB service provider.
            Rates are given against EURO
        '''
        today = fields.Date.today()

        available_currency_names = available_currencies.mapped('name')
        rslt = {currency.name: (currency.rate, today) for currency in available_currencies}

        request_url = "https://www.tax.gov.kh/en/exchange-rate"
        try:
            page = urlopen(request_url)
            html = page.read().decode("utf-8")
        except:
            #connection error, the request wasn't successful
            return False

        pattern = "<span.*?>(3|4|5).*?</span.*?>"
        match_results = re.search(pattern, html, re.IGNORECASE)
        if match_results:
            rate_element = match_results.group()
            rate_str = re.sub("<.*?>", "", rate_element)
            rate = rate_str.split(" ")[4]

            if rslt and 'KHR' in available_currency_names:
                rslt['KHR'] = (float(rate), today)
        return rslt

    def _parse_nbc_data(self, available_currencies):
        ''' This method is used to update the currencies by using ECB service provider.
            Rates are given against EURO
        '''
        today = fields.Date.today()
        currency_date = today

        request_url = "https://www.nbc.org.kh/english/economic_research/exchange_rate.php"
        try:
            page = urlopen(request_url)
            html = page.read().decode("utf-8")
        except:
            #connection error, the request wasn't successful
            return False

        pattern = "<font.*?>(3|4|5).*?</font.*?>"
        match_results = re.search(pattern, html, re.IGNORECASE)
        rate_element = match_results.group()
        rate = re.sub("<.*?>", "", rate_element)

        pattern_date = "<font.*?>(\d{4})-(\d{2})-(\d{2})</font.*?>"
        date_results = re.search(pattern_date, html, re.IGNORECASE)
        if date_results:
            date_element = date_results.group()
            date = re.sub("<.*?>", "", date_element)
            currency_date = datetime.strptime(date, '%Y-%m-%d').date()

        available_currency_names = available_currencies.mapped('name')
        rslt = { currency.name: (currency.rate, today) for currency in available_currencies}

        for n in range(int ((currency_date - today).days)):
            rslt2 = rslt.copy()
            date = today + timedelta(n)
            if rslt2 and 'KHR' in available_currency_names:
                rslt2['KHR'] = rslt2['KHR'][0], date
            self._generate_currency_rates(rslt2)

        if rslt and 'KHR' in available_currency_names:
            rslt['KHR'] = (float(rate), currency_date)

        return rslt
