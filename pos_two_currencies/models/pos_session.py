# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, Command
from odoo.exceptions import AccessError, UserError, ValidationError
from markupsafe import Markup, escape
from collections import defaultdict
from odoo.tools.image import image_data_uri
from odoo.tools import float_is_zero, float_compare, convert

class PosSessionInherit(models.Model):
    _inherit = 'pos.session'

    cash_register_balance_end_real_khr = fields.Monetary(
        string="Ending Balance (KHR)",
        readonly=True)
    cash_register_balance_start_khr = fields.Monetary(
        string="Starting Balance (KHR)",
        readonly=True)
    cash_register_total_entry_encoding_khr = fields.Monetary(
        compute='_compute_cash_balance',
        string='Total Cash Transaction (KHR)',
        readonly=True)
    cash_register_balance_end_khr = fields.Monetary(
        compute='_compute_cash_balance',
        string="Theoretical Closing Balance (KHR)",
        help="Opening balance summed to all cash transactions.",
        readonly=True)
    cash_register_difference_khr = fields.Monetary(
        compute='_compute_cash_balance',
        string='Before Closing Difference (KHR)',
        help="Difference between the theoretical closing balance and the real closing balance.",
        readonly=True)
    cash_journal_khr_id = fields.Many2one('account.journal', compute='_compute_cash_journal', string='Cash Journal (KHR)', store=True)
    # Total Cash In/Out
    cash_real_transaction_usd = fields.Monetary(string='Transaction (USD)', readonly=True)
    cash_real_transaction_khr = fields.Monetary(string='Transaction (KHR)', readonly=True)
    open_employee_id = fields.Many2one('hr.employee', string='Opened by Cashier')
    close_employee_id = fields.Many2one('hr.employee', string='Closed by Cashier')

    def _get_discount_account(self, tax_ids=None):
        if tax_ids:
            tax = self.env['account.tax'].browse(tax_ids).exists()
            discount_account = tax.mapped('discount_account_id')
            if discount_account:
                return discount_account
        return self.company_id and self.company_id.account_discount_pos_id or None

    def _prepare_discount_line(self, order_line):
        """ Derive from order_line the order date, income account, amount and taxes information.

        These information will be used in accumulating the amounts for sales and tax lines.
        """
        def get_income_account(order_line):
            product = order_line.product_id
            income_account = product.with_company(order_line.company_id)._get_product_accounts()['income'] or self.config_id.journal_id.default_account_id
            if not income_account:
                raise UserError(_('Please define income account for this product: "%s" (id:%d).',
                                  product.name, product.id))
            return order_line.order_id.fiscal_position_id.map_account(income_account)

        company_domain = self.env['account.tax']._check_company_domain(order_line.order_id.company_id)
        tax_ids = order_line.tax_ids_after_fiscal_position.filtered_domain(company_domain)
        price_include = any(tax.price_include for tax in tax_ids)

        sign = -1 if order_line.qty >= 0 else 1
        price_unit = sign * order_line.price_unit

        # The 'is_refund' parameter is used to compute the tax tags. Ultimately, the tags are part
        # of the key used for summing taxes. Since the POS UI doesn't support the tags, inconsistencies
        # may arise in 'Round Globally'.
        check_refund = lambda x: x.qty * x.price_unit < 0
        is_refund = check_refund(order_line)

        # price = price_unit
        # if not order_line.is_discount_vat:
        tax_data = tax_ids.compute_all(price_unit=price_unit, quantity=abs(order_line.qty), currency=self.currency_id, is_refund=is_refund, fixed_multiplicator=sign)
        price = tax_data['total_excluded']
        tax_amount = sum(tax['amount'] for tax in tax_data['taxes']) or 0.0
        if order_line.is_discount_vat:
            tax_amount = tax_amount * (order_line.discount or 0.0) / 100.0

        price = price * (order_line.discount or 0.0) / 100.0

        return {
            'date_order': order_line.order_id.date_order,
            'income_account_id': get_income_account(order_line).id,
            'amount': price,
            'tax_amount': tax_amount,
            'is_discount_vat': order_line.is_discount_vat,
            'tax_ids': tax_ids.ids,
        }

    def _accumulate_amounts(self, data):
        data = super()._accumulate_amounts(data)
        amounts = lambda: {'amount': 0.0, 'amount_converted': 0.0}
        discount_account = self._get_discount_account()
        if discount_account:
            sales = data['sales'] if 'sales' in data else defaultdict(amounts)
            for order in self._get_closed_orders():
                if not order.is_invoiced:
                    for order_line in order.lines.filtered(lambda line: line.discount and line.discount != 0.0):
                        discount_line = self._prepare_discount_line(order_line)
                        # Combine Discount sales/refund lines
                        sale_key = (
                            # account
                            discount_line['income_account_id'],
                            # sign
                            1 if discount_line['amount'] < 0 else -1,
                            tuple(),
                            tuple(),
                        )

                        # Combine Discount lines
                        discount_key = (
                            # account
                            discount_account.id,
                            # sign reversed from sale
                            -1 if discount_line['amount'] < 0 else 1,
                            tuple(),
                            tuple(),
                        )
                        # sales/refund lines for discount
                        sales[sale_key] = self._update_amounts(sales[sale_key], {'amount': -discount_line['amount']}, discount_line['date_order'], round=False)
                        sales[sale_key].setdefault('tax_amount', 0.0)

                        # discount lines
                        sales[discount_key] = self._update_amounts(sales[discount_key], {'amount': discount_line['amount']}, discount_line['date_order'], round=False)
                        sales[discount_key].setdefault('tax_amount', 0.0)

                        discount_account_line = self._get_discount_account(discount_line['tax_ids'])
                        if discount_account_line and discount_line.get('is_discount_vat', False):
                            tax_amount = discount_line['tax_amount']
                            discount_line_key = (
                                # account
                                discount_account_line.id,
                                # sign reversed from sale
                                -1 if tax_amount < 0 else 1,
                                tuple((tax_id, False, False) for tax_id in discount_line['tax_ids']),
                                tuple(),
                            )
                            sales[discount_line_key] = self._update_amounts(sales[discount_line_key], {'amount': tax_amount}, discount_line['date_order'], round=False)
                            sales[discount_line_key].setdefault('tax_amount', 0.0)
            data.update({'sales': sales})

        if self.company_id.anglo_saxon_accounting:
            stock_expense = defaultdict(amounts)
            global_session_pickings = self.picking_ids.filtered(lambda p: not p.pos_order_id)
            if global_session_pickings:
                stock_moves = self.env['stock.move'].sudo().search([
                    ('picking_id', 'in', global_session_pickings.ids),
                    ('company_id.anglo_saxon_accounting', '=', True),
                    ('product_id.categ_id.property_valuation', '=', 'real_time'),
                    ('product_id.type', '=', 'product'),
                ])
                for move in stock_moves:
                    exp_key = move.product_id._get_product_accounts()['expense']
                    signed_product_qty = move.product_qty
                    if move._is_in():
                        signed_product_qty *= -1
                    amount = signed_product_qty * move.product_id._compute_average_price(0, move.quantity, move)

                    for bom in move.bom_line_id.bom_id:
                        if bom.product_tmpl_id and bom.product_tmpl_id.product_variant_id and bom.type != 'phantom':
                            continue
                        exp_key = bom.product_tmpl_id.product_variant_id._get_product_accounts()['expense']
                    stock_expense[exp_key] = self._update_amounts(stock_expense[exp_key], {'amount': amount}, move.picking_id.date, force_company_currency=True)
            data.update({'stock_expense': stock_expense})
        return data

    # Override Parent Method
    def _prepare_line(self, order_line):
        """ Derive from order_line the order date, income account, amount and taxes information.

        These information will be used in accumulating the amounts for sales and tax lines.
        """
        def get_income_account(order_line):
            product = order_line.product_id
            income_account = product.with_company(order_line.company_id)._get_product_accounts()['income'] or self.config_id.journal_id.default_account_id
            if not income_account:
                raise UserError(_('Please define income account for this product: "%s" (id:%d).',
                                  product.name, product.id))
            return order_line.order_id.fiscal_position_id.map_account(income_account)

        company_domain = self.env['account.tax']._check_company_domain(order_line.order_id.company_id)
        tax_ids = order_line.tax_ids_after_fiscal_position.filtered_domain(company_domain)
        sign = -1 if order_line.qty >= 0 else 1
        # Custom Code
        price_unit = sign * order_line.price_unit
        # End Custom Code
        price = price_unit * (1 - (order_line.discount or 0.0) / 100.0)
        # The 'is_refund' parameter is used to compute the tax tags. Ultimately, the tags are part
        # of the key used for summing taxes. Since the POS UI doesn't support the tags, inconsistencies
        # may arise in 'Round Globally'.
        check_refund = lambda x: x.qty * x.price_unit < 0
        is_refund = check_refund(order_line)

        # Custom Code
        tax_data = tax_ids.compute_all(price_unit=price_unit, quantity=abs(order_line.qty), currency=self.currency_id, is_refund=is_refund, fixed_multiplicator=sign)
        # tax_data = tax_ids.compute_all(price_unit=price if order_line.is_discount_vat else price_unit, quantity=abs(order_line.qty), currency=self.currency_id, is_refund=is_refund, fixed_multiplicator=sign)
        # End Custom Code

        taxes = tax_data['taxes']
        # For Cash based taxes, use the account from the repartition line immediately as it has been paid already
        for tax in taxes:
            tax_rep = self.env['account.tax.repartition.line'].browse(tax['tax_repartition_line_id'])
            tax['account_id'] = tax_rep.account_id.id

        # Custom Code
        date_order = order_line.order_id.date_order
        # End Custom Code
        taxes = [{'date_order': date_order, **tax} for tax in taxes]
        return {
            'date_order': date_order,
            'income_account_id': get_income_account(order_line).id,
            'amount': order_line.price_subtotal,
            'taxes': taxes,
            'base_tags': tuple(tax_data['base_tags']),
        }

    @api.depends('config_id', 'payment_method_ids')
    def _compute_cash_journal(self):
        for session in self:
            cash_payment_methods = session.payment_method_ids.filtered('is_cash_count')
            cash_payment_method_usd = cash_payment_methods.filtered(lambda pm: "KHR" not in pm.name)
            cash_payment_method_khr = cash_payment_methods.filtered(lambda pm: "KHR" in pm.name)

            session.cash_journal_id = cash_payment_method_usd[:1].journal_id if cash_payment_method_usd else False
            session.cash_journal_khr_id = cash_payment_method_khr[:1].journal_id if cash_payment_method_khr else False

    @api.model_create_multi
    def create(self, vals_list):
        sessions = super().create(vals_list)
        for session in sessions.filtered(lambda s: s.config_id and s.config_id.session_sequence_id):
            session.name = session.config_id.session_sequence_id.next_by_id()

        return sessions

    def _get_balancing_close_default_account(self, balance=0):
        propoerty_account = self.env['ir.property']._get('property_account_receivable_id', 'res.partner')
        if not float_is_zero(balance, precision_rounding=0.01):
            cash_journal_id = self.cash_journal_id
            if cash_journal_id:
                if balance < 0.0:
                    propoerty_account = cash_journal_id.loss_account_id
                else:
                    propoerty_account = cash_journal_id.profit_account_id
        return propoerty_account or self.env['account.account']

    def _close_session_action(self, amount_to_balance):
        # NOTE This can't handle `bank_payment_method_diffs` because there is no field in the wizard that can carry it.
        default_account = self._get_balancing_account()
        if not float_is_zero(amount_to_balance, precision_rounding=0.01):
            cash_journal_id = self.cash_journal_id
            if cash_journal_id:
                if amount_to_balance < 0.0:
                    default_account = cash_journal_id.loss_account_id
                else:
                    default_account = cash_journal_id.profit_account_id

        wizard = self.env['pos.close.session.wizard'].create({
            'amount_to_balance': amount_to_balance,
            'account_id': default_account.id,
            'account_readonly': not self.env.user.has_group('account.group_account_readonly'),
            'message': _(
                "There is a difference between the amounts to post and the amounts of the orders, it is probably caused by taxes or accounting configurations changes.")
        })
        return {
            'name': _("Force Close Session"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'pos.close.session.wizard',
            'res_id': wizard.id,
            'target': 'new',
            'context': {**self.env.context, 'active_ids': self.ids, 'active_model': 'pos.session'},
        }

    def try_cash_in_out(self, _type, amount, reason, extras, amount_khr=0.0):
        sign = 1 if _type == 'in' else -1
        sessions = self.filtered('cash_journal_id')
        if not sessions:
            raise UserError(_("There is no cash payment method for this PoS Session"))

        if amount != 0:
            self.env['account.bank.statement.line'].create([
                {
                    'pos_session_id': session.id,
                    'journal_id': session.cash_journal_id.id,
                    'amount': sign * amount,
                    'date': fields.Date.context_today(self),
                    'payment_ref': '-'.join([session.name, extras['translatedType'], reason]),
                }
                for session in sessions
            ])
        if amount_khr != 0:
            self.env['account.bank.statement.line'].create([
                {
                    'pos_session_id': session.id,
                    'journal_id': session.cash_journal_khr_id.id,
                    'amount': sign * amount_khr,
                    'date': fields.Date.context_today(self),
                    'payment_ref': '-'.join([session.name, extras['translatedType'], reason]),
                }
                for session in sessions
            ])

    @api.depends('payment_method_ids', 'order_ids', 'cash_register_balance_start', 'cash_register_balance_start_khr')
    def _compute_cash_balance(self):
        for session in self:
            cash_payment_methods = session.payment_method_ids.filtered('is_cash_count')
            cash_payment_method = cash_payment_methods.filtered(lambda pm: "KHR" not in pm.name)[:1]
            statement_line_ids = session.sudo().statement_line_ids
            cash_journal_id = session.sudo().cash_journal_id
            statement_line_usd_ids = statement_line_ids.filtered(lambda sl: sl.journal_id == cash_journal_id)
            statement_line_khr_ids = statement_line_ids - statement_line_usd_ids

            if cash_payment_method:
                total_cash_payment = 0.0
                # last_session = session.search([('config_id', '=', session.config_id.id), ('id', '<', session.id)], limit=1)
                result = self.env['pos.payment']._read_group(
                    [('session_id', '=', session.id), ('payment_method_id', '=', cash_payment_method.id)],
                    aggregates=['amount:sum'])
                total_cash_payment = result[0][0] or 0.0
                if session.state == 'closed':
                    session.cash_register_total_entry_encoding = session.cash_real_transaction_usd + total_cash_payment
                else:
                    session.cash_register_total_entry_encoding = sum(
                        statement_line_usd_ids.mapped('amount')) + total_cash_payment

                # session.cash_register_balance_end = last_session.cash_register_balance_end_real + session.cash_register_total_entry_encoding
                session.cash_register_balance_end = session.cash_register_balance_start + session.cash_register_total_entry_encoding
                session.cash_register_difference = session.cash_register_balance_end_real - session.cash_register_balance_end
            else:
                session.cash_register_total_entry_encoding = 0.0
                session.cash_register_balance_end = 0.0
                session.cash_register_difference = 0.0

            # Cash KHR
            cash_payment_method_khr = cash_payment_methods.filtered(lambda pm: "KHR" in pm.name)[:1]
            if cash_payment_method_khr:
                total_cash_payment_khr = 0.0
                result = self.env['pos.payment']._read_group(
                    [('session_id', '=', session.id), ('payment_method_id', '=', cash_payment_method_khr.id)],
                    aggregates=['amount:sum'])
                total_cash_payment_khr = result[0][0] or 0.0
                if session.state == 'closed':
                    session.cash_register_total_entry_encoding_khr = session.cash_real_transaction_khr + total_cash_payment_khr
                else:
                    currency_id = self.env['res.currency'].search([('name', '=', "KHR")], limit=1)
                    date = fields.Date.context_today(session)
                    statement_amount = currency_id._convert(sum(statement_line_khr_ids.mapped('amount')),
                                                            session.currency_id, session.company_id, date, True)
                    session.cash_register_total_entry_encoding_khr = statement_amount + total_cash_payment_khr

                # session.cash_register_balance_end_khr = last_session.cash_register_balance_end_real + session.cash_register_total_entry_encoding
                session.cash_register_balance_end_khr = session.cash_register_balance_start_khr + session.cash_register_total_entry_encoding_khr
                session.cash_register_difference_khr = session.cash_register_balance_end_real_khr - session.cash_register_balance_end_khr
            else:
                session.cash_register_total_entry_encoding_khr = 0.0
                session.cash_register_balance_end_khr = 0.0
                session.cash_register_difference_khr = 0.0

    def get_closing_control_data(self):
        res = super(PosSessionInherit, self).get_closing_control_data()
        if 'default_cash_details' in res and res['default_cash_details']:
            current_open = self.cash_register_balance_start

            orders = self._get_closed_orders()
            payments = orders.payment_ids.filtered(lambda p: p.payment_method_id.type != "pay_later")
            cash_payment_method_ids = self.payment_method_ids.filtered(lambda pm: pm.type == 'cash')
            cash_payment_method_usd_ids = cash_payment_method_ids.filtered(lambda pm: "KHR" not in pm.name)
            cash_payment_method_khr_ids = cash_payment_method_ids.filtered(lambda pm: "KHR" in pm.name)

            # Cash USD
            default_cash_payment_method_id = cash_payment_method_usd_ids[0] if cash_payment_method_usd_ids else None
            total_default_cash_payment_amount = sum(
                payments.filtered(lambda p: p.payment_method_id == default_cash_payment_method_id).mapped(
                    'amount')) if default_cash_payment_method_id else 0
            # Cash KHR
            default_cash_payment_method_khr_id = cash_payment_method_khr_ids[0] if cash_payment_method_khr_ids else None
            total_default_cash_payment_amount_khr = sum(
                payments.filtered(lambda p: p.payment_method_id == default_cash_payment_method_khr_id).mapped(
                    'amount')) if default_cash_payment_method_khr_id else 0

            other_payment_method_ids = self.payment_method_ids - default_cash_payment_method_id if default_cash_payment_method_id else self.payment_method_ids
            other_payment_method_ids = other_payment_method_ids - default_cash_payment_method_khr_id if default_cash_payment_method_khr_id else other_payment_method_ids

            last_session = self.search([('config_id', '=', self.config_id.id), ('id', '!=', self.id)], limit=1)
            statement_line_ids = self.sudo().statement_line_ids
            cash_journal_id = self.sudo().cash_journal_id
            statement_line_usd_ids = statement_line_ids.filtered(lambda sl: sl.journal_id == cash_journal_id)

            cash_in_count = 0
            cash_out_count = 0
            cash_in_out_list = []
            for cash_move in statement_line_usd_ids.sorted('create_date'):
                if cash_move.amount > 0:
                    cash_in_count += 1
                    name = f'Cash in {cash_in_count}'
                else:
                    cash_out_count += 1
                    name = f'Cash out {cash_out_count}'
                cash_in_out_list.append({
                    'name': cash_move.payment_ref if cash_move.payment_ref else name,
                    'amount': cash_move.amount
                })

            amount_usd = (current_open + total_default_cash_payment_amount + sum(statement_line_usd_ids.mapped('amount')))
            res['default_cash_details'] = {
                'name': default_cash_payment_method_id.name,
                'amount': amount_usd,
                'opening': current_open,
                'payment_amount': total_default_cash_payment_amount,
                'moves': cash_in_out_list,
                'id': default_cash_payment_method_id.id
            } if default_cash_payment_method_id else None

            statement_line_khr_ids = statement_line_ids - statement_line_usd_ids

            currency_id = self.env['res.currency'].search([('name', '=', "KHR")], limit=1)
            date = fields.Date.context_today(self)

            cash_in_count_khr = 0
            cash_out_count_khr = 0
            cash_in_out_list_khr = []
            for cash_move in statement_line_khr_ids.sorted('create_date'):
                if cash_move.amount > 0:
                    cash_in_count_khr += 1
                    name = f'Cash in {cash_in_count_khr}'
                else:
                    cash_out_count_khr += 1
                    name = f'Cash out {cash_out_count_khr}'
                cash_in_out_list_khr.append({
                    'name': cash_move.payment_ref if cash_move.payment_ref else name,
                    'amount': currency_id._convert(cash_move.amount, self.currency_id, self.company_id, date, True),
                })
            current_open_khr = self.cash_register_balance_start_khr
            statement_amount = currency_id._convert(sum(statement_line_khr_ids.mapped('amount')), self.currency_id, self.company_id, date, True)
            amount_khr = (current_open_khr + total_default_cash_payment_amount_khr + statement_amount)

            amount_khr_currency = self.currency_id._convert(amount_khr, currency_id, self.company_id, date, True)
            current_open_khr_currency = self.currency_id._convert(current_open_khr, currency_id, self.company_id, date, True)
            total_default_cash_payment_amount_khr_currency = self.currency_id._convert(total_default_cash_payment_amount_khr, currency_id, self.company_id, date, True)

            res['default_cash_details_khr'] = {
                'name': default_cash_payment_method_khr_id.name,
                'amount': amount_khr_currency,
                'opening': current_open_khr_currency,
                'payment_amount': total_default_cash_payment_amount_khr_currency,
                'moves': cash_in_out_list_khr,
                'id': default_cash_payment_method_khr_id.id
            } if default_cash_payment_method_khr_id else None

            res['other_payment_methods'] = [{
                'name': pm.name,
                'amount': sum(orders.payment_ids.filtered(lambda p: p.payment_method_id == pm).mapped('amount')),
                'number': len(orders.payment_ids.filtered(lambda p: p.payment_method_id == pm)),
                'id': pm.id,
                'type': pm.type,
            } for pm in other_payment_method_ids]
        return res

    def action_pos_session_open(self):
        # we only open sessions that haven't already been opened
        for session in self.filtered(lambda session: session.state == 'opening_control'):
            now = fields.Datetime.now()
            values = {}
            if not session.start_at:
                values['start_at'] = now
            if session.config_id.cash_control and not session.rescue:
                # last_session = self.search([('config_id', '=', session.config_id.id), ('id', '!=', session.id)], limit=1)
                # session.cash_register_balance_start = last_session.cash_register_balance_end_real  # defaults to 0 if lastsession is empty
                session.cash_register_balance_start = 0
                session.cash_register_balance_start_khr = 0
            else:
                values['state'] = 'opened'
            session.write(values)
        return True

    def post_closing_cash_details(self, counted_cash, counted_cash_khr=0.0, cashier_name=None, employee_id=None):
        res = super(PosSessionInherit, self).post_closing_cash_details(counted_cash)
        if res.get('successful', False) and self.cash_journal_khr_id:
            currency_id = self.env['res.currency'].search([('name', '=', "KHR")], limit=1)
            date = fields.Date.context_today(self)
            self.cash_register_balance_end_real_khr = currency_id._convert(counted_cash_khr, self.currency_id, self.company_id, date, True)

            if employee_id:
                employee = self.env['hr.employee'].browse(employee_id)
                if employee:
                    self.close_employee_id = employee.id
                    self.message_post(body=f'Closed by Cashier: {employee.name}')
            if cashier_name:
                self.message_post(body=f'Closed by Cashier: {cashier_name}')

        return res

    def _post_cash_khr_details_message(self, state, difference, notes):
        message = ""
        currency_id = self.env['res.currency'].search([('name', '=', "KHR")], limit=1)
        if not currency_id:
            currency_id = self.currency_id
        if difference:
            message = f"{state} difference: " \
                      f"{currency_id.symbol + ' ' if currency_id.position == 'before' else ''}" \
                      f"{currency_id.round(difference)} " \
                      f"{currency_id.symbol if currency_id.position == 'after' else ''}" + Markup('<br/>')
        if notes:
            message += escape(notes).replace('\n', Markup('<br/>'))
        if message:
            self.message_post(body=message)

    def _post_statement_difference(self, amount, is_opening, cash_khr=0.0):
        super(PosSessionInherit, self)._post_statement_difference(amount, is_opening)
        if cash_khr:
            currency_id = self.env['res.currency'].search([('name', '=', "KHR")], limit=1)
            date = self.statement_line_ids.sorted()[-1:].date or fields.Date.context_today(self)
            amount = self.currency_id._convert(cash_khr, currency_id, self.company_id, date, True)
            # amount = cash_khr

            if self.config_id.cash_control:
                st_line_vals = {
                    'journal_id': self.cash_journal_khr_id.id,
                    'amount': amount,
                    'date': date,
                    'pos_session_id': self.id,
                }

            if amount < 0.0:
                if not self.cash_journal_khr_id.loss_account_id:
                    raise UserError(
                        _('Please go on the %s journal and define a Loss Account. This account will be used to record cash difference.',
                          self.cash_journal_khr_id.name))

                st_line_vals['payment_ref'] = _("Cash (KHR) difference observed during the counting (Loss)") + (_(' - opening') if is_opening else _(' - closing'))
                if not is_opening:
                    st_line_vals['counterpart_account_id'] = self.cash_journal_khr_id.loss_account_id.id
            else:
                # self.cash_register_difference  > 0.0
                if not self.cash_journal_khr_id.profit_account_id:
                    raise UserError(
                        _('Please go on the %s journal and define a Profit Account. This account will be used to record cash difference.',
                          self.cash_journal_khr_id.name))

                st_line_vals['payment_ref'] = _("Cash (KHR) difference observed during the counting (Profit)") + (_(' - opening') if is_opening else _(' - closing'))
                if not is_opening:
                    st_line_vals['counterpart_account_id'] = self.cash_journal_khr_id.profit_account_id.id

            self.env['account.bank.statement.line'].create(st_line_vals)

    def _create_account_move(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        """ Create account.move and account.move.line records for this session.

        Side-effects include:
            - setting self.move_id to the created account.move record
            - reconciling cash receivable lines, invoice receivable lines and stock output lines
        """
        account_move = self.env['account.move'].create({
            'journal_id': self.config_id.journal_id.id,
            'date': fields.Date.context_today(self),
            'ref': self.name,
        })
        self.write({'move_id': account_move.id})

        data = {'bank_payment_method_diffs': bank_payment_method_diffs or {}}
        data = self._accumulate_amounts(data)
        data = self._create_non_reconciliable_move_lines(data)
        data = self._create_bank_payment_moves(data)
        data = self._create_pay_later_receivable_lines(data)
        data = self._create_cash_statement_lines_and_cash_move_lines(data)
        data = self._create_invoice_receivable_lines(data)
        data = self._create_stock_output_lines(data)
        if balancing_account and amount_to_balance:
            data = self._create_balancing_line(data, balancing_account, amount_to_balance)

        return data

    def _revalidate_session(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        for record in self:
            cash_difference_before_statements = record.cash_register_difference
            if not self.env.context.get('journal_only', False) and record.update_stock_at_closing:
                record._create_picking_at_end_of_session()
                record._get_closed_orders().filtered(lambda o: not o.is_total_cost_computed)._compute_total_cost_at_session_closing(record.picking_ids.move_ids)
            try:
                with record.env.cr.savepoint():
                    # record.move_id.line_ids.unlink() # Delete all existing move lines
                    # record.move_id.state = 'draft'
                    # data = {'bank_payment_method_diffs': bank_payment_method_diffs or {}}
                    # data = record._accumulate_amounts(data)
                    # data = record._create_non_reconciliable_move_lines(data)
                    # data = record._create_invoice_receivable_lines(data)
                    # data = record._create_stock_output_lines(data)
                    data = record.with_company(record.company_id).with_context(check_move_validity=False, skip_invoice_sync=True)._create_account_move(balancing_account, amount_to_balance, bank_payment_method_diffs)
            except AccessError as e:
                raise e

            balance = sum(record.move_id.line_ids.mapped('balance'))
            try:
                with record.move_id._check_balanced({'records': record.move_id.sudo()}):
                    pass
            except UserError:
                record.env.cr.rollback()
                balancing_account = record._get_balancing_close_default_account(amount_to_balance)
                if not balancing_account:
                    # If there is no balancing account, we force select Profit/Loss account
                    balancing_account = record.sudo().env['account.account'].browse(36)
                return record._revalidate_session(balancing_account, balance, bank_payment_method_diffs)

            record.sudo()._post_statement_difference(cash_difference_before_statements, False)
            if record.move_id.line_ids:
                record.move_id.sudo().with_company(record.company_id)._post()
                #We need to write the price_subtotal and price_total here because if we do it earlier the compute functions will overwrite it here /account/models/account_move_line.py _compute_totals
                for dummy, amount_data in data['sales'].items():
                    record.env['account.move.line'].browse(amount_data['move_line_id']).sudo().with_company(record.company_id).write({
                        'price_subtotal': abs(amount_data['amount_converted']),
                        'price_total': abs(amount_data['amount_converted']) + abs(amount_data['tax_amount']),
                    })
                # Set the uninvoiced orders' state to 'done'
                record.env['pos.order'].search([('session_id', '=', record.id), ('state', '=', 'paid')]).write({'state': 'done'})
            else:
                record.move_id.sudo().unlink()
            record.sudo().with_company(record.company_id)._reconcile_account_move_lines(data)

    def _validate_session(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        bank_payment_method_diffs = bank_payment_method_diffs or {}
        self.ensure_one()
        data = {}
        sudo = self.user_has_groups('point_of_sale.group_pos_user')

        statement_line_ids = self.sudo().statement_line_ids
        cash_journal_id = self.sudo().cash_journal_id
        statement_line_usd_ids = statement_line_ids.filtered(lambda sl: sl.journal_id == cash_journal_id)
        statement_line_khr_ids = statement_line_ids - statement_line_usd_ids
        currency_id = self.env['res.currency'].search([('name', '=', "KHR")], limit=1)
        date = fields.Date.context_today(self)

        if self.order_ids.filtered(lambda o: o.state != 'cancel') or statement_line_ids:
            self.cash_real_transaction_usd = sum(statement_line_usd_ids.mapped('amount')) or 0
            statement_amount = currency_id._convert(sum(statement_line_khr_ids.mapped('amount')),
                                                    self.currency_id, self.company_id, date, True)
            self.cash_real_transaction_khr = statement_amount or 0
            self.cash_real_transaction = self.cash_real_transaction_usd + self.cash_real_transaction_khr
            if self.state == 'closed':
                raise UserError(_('This session is already closed.'))
            self._check_if_no_draft_orders()
            self._check_invoices_are_posted()
            cash_difference_before_statements = self.cash_register_difference
            cash_khr_difference_before_statements = self.cash_register_difference_khr
            if self.update_stock_at_closing:
                self._create_picking_at_end_of_session()
                self._get_closed_orders().filtered(lambda o: not o.is_total_cost_computed)._compute_total_cost_at_session_closing(self.picking_ids.move_ids)
            try:
                with self.env.cr.savepoint():
                    data = self.with_company(self.company_id).with_context(check_move_validity=False, skip_invoice_sync=True)._create_account_move(balancing_account, amount_to_balance, bank_payment_method_diffs)
            except AccessError as e:
                if sudo:
                    data = self.sudo().with_company(self.company_id).with_context(check_move_validity=False, skip_invoice_sync=True)._create_account_move(balancing_account, amount_to_balance, bank_payment_method_diffs)
                else:
                    raise e

            balance = sum(self.move_id.line_ids.mapped('balance'))
            try:
                with self.move_id._check_balanced({'records': self.move_id.sudo()}):
                    pass
            except UserError:
                # Creating the account move is just part of a big database transaction
                # when closing a session. There are other database changes that will happen
                # before attempting to create the account move, such as, creating the picking
                # records.
                # We don't, however, want them to be committed when the account move creation
                # failed; therefore, we need to roll back this transaction before showing the
                # close session wizard.
                self.env.cr.rollback()

                amount_authorized_diff = self.config_id.amount_authorized_diff if self.config_id.set_maximum_difference else False
                balancing_account = self._get_balancing_close_default_account(balance)
                # If balancing amount within the limit, we close the session automatically
                if balancing_account and amount_authorized_diff and amount_authorized_diff > abs(balance):
                    return self._validate_session(balancing_account, balance, bank_payment_method_diffs)

                return self._close_session_action(balance)

            self.sudo()._post_statement_difference(cash_difference_before_statements, is_opening=False, cash_khr=cash_khr_difference_before_statements)

            if self.move_id.line_ids:
                self.move_id.sudo().with_company(self.company_id)._post(soft=False)
                #We need to write the price_subtotal and price_total here because if we do it earlier the compute functions will overwrite it here /account/models/account_move_line.py _compute_totals
                for dummy, amount_data in data['sales'].items():
                    self.env['account.move.line'].browse(amount_data['move_line_id']).sudo().with_company(self.company_id).write({
                        'price_subtotal': abs(amount_data['amount_converted']),
                        'price_total': abs(amount_data['amount_converted']) + abs(amount_data['tax_amount']),
                    })
                # Set the uninvoiced orders' state to 'done'
                self.env['pos.order'].search([('session_id', '=', self.id), ('state', '=', 'paid')]).write({'state': 'done'})
            else:
                self.move_id.sudo().unlink()
            self.sudo().with_company(self.company_id)._reconcile_account_move_lines(data)
        else:
            self.sudo()._post_statement_difference(self.cash_register_difference, False, cash_khr=self.cash_register_difference_khr)

        self.write({'state': 'closed'})
        return True

    # Override Parent Method
    def update_closing_control_state_session(self, notes, notesUSD, notesKHR):
        # Prevent closing the session again if it was already closed
        if self.state == 'closed':
            raise UserError(_('This session is already closed.'))
        # Prevent the session to be opened again.
        self.write({'state': 'closing_control', 'stop_at': fields.Datetime.now(), 'closing_notes': notes})
        self._post_cash_details_message('Closing', self.cash_register_difference, notesUSD or notes)
        self._post_cash_khr_details_message('Closing', self.cash_register_difference_khr, notesKHR or notes)

    def set_cashbox_pos(self, cashbox_value: int, notes: str, cashbox_value_khr=0.0, notesUSD="", notesKHR="", employee_id=None):
        self.state = 'opened'
        self.opening_notes = notes
        self.cash_register_balance_start = cashbox_value

        currency_id = self.env['res.currency'].search([('name', '=', "KHR")], limit=1)
        date = fields.Date.context_today(self)
        if cashbox_value_khr != 0:
            cashbox_value_khr = currency_id._convert(cashbox_value_khr, self.currency_id, self.company_id, date, True)

        self.cash_register_balance_start_khr = cashbox_value_khr or 0.0

        if employee_id:
            employee = self.env['hr.employee'].browse(employee_id)
            if employee:
                self.open_employee_id = employee.id
                self.message_post(body=f'Opened by Cashier: {employee.name}')

        # difference = cashbox_value - self.cash_register_balance_start
        # difference_khr = cashbox_value_khr - self.cash_register_balance_start_khr
        # self.sudo()._post_statement_difference(difference, True, difference_khr)
        #
        # self._post_cash_details_message('Opening', difference, notesUSD or notes)
        # self._post_cash_khr_details_message('Opening', difference_khr, notesKHR or notes)

    def _create_combine_account_payment(self, payment_method, amounts, diff_amount):
        date = fields.Date.context_today(self)
        if payment_method and payment_method.journal_id:
            currency_id = payment_method.journal_id.currency_id
            if currency_id.name == "KHR":
                if 'amount' in amounts:
                    amounts['amount'] = self.currency_id._convert(amounts['amount'], currency_id, self.company_id,
                                                                  date,
                                                                  True)
                    # amounts['amount'] = amounts['amount'] * self.config_id.exchange_rate
                if diff_amount:
                    diff_amount = self.currency_id._convert(diff_amount, currency_id, self.company_id, date, True)
                    # diff_amount = diff_amount * self.config_id.exchange_rate

        outstanding_account = payment_method.outstanding_account_id or self.company_id.account_journal_payment_debit_account_id
        destination_account = self._get_receivable_account(payment_method)

        if float_compare(amounts['amount'], 0, precision_rounding=self.currency_id.rounding) < 0:
            # revert the accounts because account.payment doesn't accept negative amount.
            outstanding_account, destination_account = destination_account, outstanding_account

        account_payment = self.env['account.payment'].create({
            'date': date,
            'amount': abs(amounts['amount']),
            'journal_id': payment_method.journal_id.id,
            'force_outstanding_account_id': outstanding_account.id,
            'destination_account_id':  destination_account.id,
            'ref': _('Combine %s POS payments from %s', payment_method.name, self.name),
            'pos_payment_method_id': payment_method.id,
            'pos_session_id': self.id,
            'company_id': self.company_id.id,
        })

        diff_amount_compare_to_zero = self.currency_id.compare_amounts(diff_amount, 0)
        if diff_amount_compare_to_zero != 0:
            self._apply_diff_on_account_payment_move(account_payment, payment_method, diff_amount)

        account_payment.action_post()
        return account_payment.move_id.line_ids.filtered(lambda line: line.account_id == account_payment.destination_account_id)

    def _create_split_account_payment(self, payment, amounts):
        payment_method = payment.payment_method_id
        date = fields.Date.context_today(self)
        if not payment_method.journal_id:
            return self.env['account.move.line']
        if payment_method.journal_id:
            currency_id = payment_method.journal_id.currency_id
            if currency_id.name == "KHR":
                if 'amount' in amounts:
                    amounts['amount'] = self.currency_id._convert(amounts['amount'], currency_id, self.company_id,
                                                                  date,
                                                                  True)
                    # amounts['amount'] = amounts['amount'] * self.config_id.exchange_rate
        outstanding_account = payment_method.outstanding_account_id or self.company_id.account_journal_payment_debit_account_id
        accounting_partner = self.env["res.partner"]._find_accounting_partner(payment.partner_id)
        destination_account = accounting_partner.property_account_receivable_id

        if float_compare(amounts['amount'], 0, precision_rounding=self.currency_id.rounding) < 0:
            # revert the accounts because account.payment doesn't accept negative amount.
            outstanding_account, destination_account = destination_account, outstanding_account

        account_payment = self.env['account.payment'].create({
            'date': date,
            'amount': abs(amounts['amount']),
            'partner_id': payment.partner_id.id,
            'journal_id': payment_method.journal_id.id,
            'force_outstanding_account_id': outstanding_account.id,
            'destination_account_id': destination_account.id,
            'ref': _('%s POS payment of %s in %s', payment_method.name, payment.partner_id.display_name, self.name),
            'pos_payment_method_id': payment_method.id,
            'pos_session_id': self.id,
        })
        account_payment.action_post()
        return account_payment.move_id.line_ids.filtered(lambda line: line.account_id == account_payment.destination_account_id)

    def _get_combine_statement_line_vals(self, journal_id, amount, payment_method):
        if payment_method and payment_method.journal_id:
            currency_id = payment_method.journal_id.currency_id
            date = fields.Date.context_today(self)
            if currency_id.name == "KHR":
                amount = self.currency_id._convert(amount, currency_id, self.company_id, date, True)
                # amount = amount * self.config_id.exchange_rate
        return super(PosSessionInherit, self)._get_combine_statement_line_vals(journal_id, amount, payment_method)

    def _get_split_statement_line_vals(self, statement, amount, payment):
        payment_method = payment.payment_method_id
        if payment_method and payment_method.journal_id:
            currency_id = payment_method.journal_id.currency_id
            date = fields.Date.context_today(self)
            if currency_id.name == "KHR":
                amount = self.currency_id._convert(amount, currency_id, self.company_id, date, True)
                # amount = amount * self.config_id.exchange_rate
        return super(PosSessionInherit, self)._get_split_statement_line_vals(statement, amount, payment)

    # TODO: Check Cashier Access right
    # def _get_pos_ui_hr_employee(self, params):
    #     employees = self.env['hr.employee'].search_read(**params['search_params'])
    #     employee_ids = [employee['id'] for employee in employees]
    #     user_ids = [employee['user_id'] for employee in employees if employee['user_id']]
    #     admin_ids = self.env['res.users'].browse(user_ids).filtered(lambda user: user.has_group('base.group_erp_manager')).mapped('id')
    #
    #     employees_barcode_pin = self.env['hr.employee'].browse(employee_ids).get_barcodes_and_pin_hashed()
    #     bp_per_employee_id = {bp_e['id']: bp_e for bp_e in employees_barcode_pin}
    #     for employee in employees:
    #         if employee['user_id'] and employee['user_id'] in admin_ids:
    #             employee['role'] = 'admin'
    #         elif employee['id'] in self.config_id.advanced_employee_ids.ids:
    #             employee['role'] = 'manager'
    #         else:
    #             employee['role'] = 'cashier'
    #         employee['barcode'] = bp_per_employee_id[employee['id']]['barcode']
    #         employee['pin'] = bp_per_employee_id[employee['id']]['pin']
    #     return employees
