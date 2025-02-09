# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json

from odoo import api, fields, models, _
from odoo.tools import float_is_zero, float_round
from odoo.exceptions import UserError, ValidationError
from collections import defaultdict
from datetime import datetime
from odoo.osv.expression import AND

import logging
_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    is_khr = fields.Boolean("Is Paid In KHR?")
    discount_all = fields.Float(string='Discount (%)', digits='Discount')
    order_no = fields.Char(string='Order No')
    origs_order_name = fields.Char(string='Original Order Name')

    @api.model
    def search_paid_order_ids(self, config_id, domain, limit, offset):
        """Search for 'paid' orders that satisfy the given domain, limit and offset."""
        default_domain = [('state', '!=', 'draft'), ('state', '!=', 'cancel')]
        pos_config = self.env['pos.config'].browse(config_id)
        if domain == []:
            real_domain = AND([[['config_id', '=', config_id]], default_domain])
        else:
            real_domain = AND([domain, default_domain])
        orders = self.search(real_domain, limit=limit, offset=offset)
        # We clean here the orders that does not have the same currency.
        # As we cannot use currency_id in the domain (because it is not a stored field),
        # we must do it after the search.
        orders = orders.filtered(lambda order: order.currency_id == pos_config.currency_id)
        orderlines = self.env['pos.order.line'].search(['|', ('refunded_orderline_id.order_id', 'in', orders.ids), ('order_id', 'in', orders.ids)])

        # We will return to the frontend the ids and the date of their last modification
        # so that it can compare to the last time it fetched the orders and can ask to fetch
        # orders that are not up-to-date.
        # The date of their last modification is either the last time one of its orderline has changed,
        # or the last time a refunded orderline related to it has changed.
        orders_info = defaultdict(lambda: datetime.min)
        for orderline in orderlines:
            key_order = orderline.order_id.id if orderline.order_id in orders \
                            else orderline.refunded_orderline_id.order_id.id
            if orders_info[key_order] < orderline.write_date:
                orders_info[key_order] = orderline.write_date
        totalCount = self.search_count(real_domain)
        return {'ordersInfo': list(orders_info.items())[::-1], 'totalCount': totalCount}

    @api.model
    def _order_fields(self, ui_order):
        order_fields = super(PosOrder, self)._order_fields(ui_order)
        order_fields['is_khr'] = ui_order.get('is_khr', False)
        order_fields['discount_all'] = ui_order.get('discount_all', False)
        order_fields['order_no'] = ui_order.get('order_no', False)
        order_fields['origs_order_name'] = ui_order.get('origs_order_name', False)
        name = ui_order.get('order_name', False)

        if name:
            order_fields['name'] = self.check_sequence_store(pos_session_id=ui_order['pos_session_id'], pos_reference=ui_order['name'], name=name)
        return order_fields

    # Override Parent to add costing for kit
    def _compute_total_cost_at_session_closing(self, stock_moves):
        """
        Compute the margin at the end of the session. This method should be called to compute the remaining lines margin
        containing a storable product with a fifo/avco cost method and then compute the order margin
        """
        for order in self:
            # storable Product
            storable_fifo_avco_lines = order.lines.filtered(lambda l: l._is_product_storable_fifo_avco())
            storable_fifo_avco_lines._compute_total_cost(stock_moves)

            # KIT Product
            kit_fifo_avco_lines = order.lines.filtered(lambda l: l._is_product_kit_fifo_avco())
            kit_fifo_avco_lines._compute_kit_total_cost(stock_moves)

    def _export_for_ui(self, order):
        result = super(PosOrder, self)._export_for_ui(order)
        result['is_khr'] = order.is_khr
        result['discount_all'] = order.discount_all
        result['origs_order_name'] = order.origs_order_name
        result['order_no'] = order.order_no
        result['order_name'] = order.name
        return result

    @api.model
    def _get_fields_for_draft_order(self):
        fields = super(PosOrder, self)._get_fields_for_draft_order()
        fields.extend(['is_khr', 'discount_all', 'order_no'])
        return fields

    def _payment_fields(self, order, ui_paymentline):
        result = super(PosOrder, self)._payment_fields(order, ui_paymentline)
        result['khr'] = ui_paymentline.get("khr", 0.0)
        payment_method_id = self.env['pos.payment.method'].browse(ui_paymentline['payment_method_id']).exists()
        exchange_rate = order.session_id.config_id.exchange_rate
        if payment_method_id and ("KHR" in payment_method_id.name):
            result['amount'] = round(ui_paymentline['amount'] / exchange_rate, 4)
        return result

    def _process_payment_lines(self, pos_order, order, pos_session, draft):
        """Create account.bank.statement.lines from the dictionary given to the parent function.

        If the payment_line is an updated version of an existing one, the existing payment_line will first be
        removed before making a new one.
        :param pos_order: dictionary representing the order.
        :type pos_order: dict.
        :param order: Order object the payment lines should belong to.
        :type order: pos.order
        :param pos_session: PoS session the order was created in.
        :type pos_session: pos.session
        :param draft: Indicate that the pos_order is not validated yet.
        :type draft: bool.
        """
        prec_acc = order.currency_id.decimal_places
        exchange_rate = order.session_id.config_id.exchange_rate
        payment_method_ids = pos_session.payment_method_ids.filtered('is_cash_count')
        cash_khr = False
        cash_usd = False
        for payment_method_id in payment_method_ids:
            if "KHR" in payment_method_id.name:
                cash_khr = payment_method_id
            else:
                cash_usd = payment_method_id

        order._clean_payment_lines()
        for payments in pos_order['statement_ids']:
            order.add_payment(self._payment_fields(order, payments[2]))
        order.amount_paid = sum(order.payment_ids.mapped('amount'))
        payment_methods = [payment_method.name for payment_method in order.payment_ids.mapped('payment_method_id')]

        if not draft and not float_is_zero(pos_order['amount_return'], prec_acc):
            cash_payment_method = payment_method_ids[:1]
            if not cash_payment_method:
                raise UserError(_("No cash statement found for this session. Unable to record returned cash."))
            amount_return = float(pos_order['amount_return'])
            amount_return_usd = int(amount_return // 10 * 10)
            amount_return_khr = amount_return - amount_return_usd

            if "KHR" in payment_methods[-1]:
                order.add_payment({
                    'name': _('return KHR'),
                    'pos_order_id': order.id,
                    'amount': -amount_return,
                    'payment_date': fields.Datetime.now(),
                    'payment_method_id': cash_khr.id,
                    'khr': -amount_return * exchange_rate,
                    'is_change': True,
                })
            else:
                order.add_payment({
                    'name': _('return USD'),
                    'pos_order_id': order.id,
                    'amount': -amount_return_usd,
                    'payment_date': fields.Datetime.now(),
                    'payment_method_id': cash_usd.id,
                    'is_change': True,
                })
                if amount_return_khr > 0:
                    order.add_payment({
                        'name': _('return KHR'),
                        'pos_order_id': order.id,
                        'amount': -amount_return_khr,
                        'payment_date': fields.Datetime.now(),
                        'payment_method_id': cash_khr.id,
                        'khr': -amount_return_khr * exchange_rate,
                        'is_change': True,
                    })

    @api.model
    def _amount_line_tax(self, line, fiscal_position_id):
        taxes = line.tax_ids.filtered(lambda t: t.company_id.id == line.order_id.company_id.id)
        taxes = fiscal_position_id.map_tax(taxes)
        if line.is_discount_vat:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
        else:
            price = line.price_unit
        taxes = taxes.compute_all(price, line.order_id.pricelist_id.currency_id, line.qty, product=line.product_id,
                                  partner=line.order_id.partner_id or False)['taxes']
        return sum(tax.get('amount', 0.0) for tax in taxes)

    def action_pos_order_paid(self):
        self.ensure_one()

        # TODO: add support for mix of cash and non-cash payments when both cash_rounding and only_round_cash_method are True
        if not self.config_id.cash_rounding \
                or self.config_id.only_round_cash_method \
                and not any(p.payment_method_id.is_cash_count for p in self.payment_ids):
            total = self.amount_total
        else:
            total = float_round(self.amount_total, precision_rounding=self.config_id.rounding_method.rounding,
                                rounding_method=self.config_id.rounding_method.rounding_method)

        isPaid = float_is_zero(total - self.amount_paid, precision_rounding=self.currency_id.rounding)

        if not isPaid:
            currency = self.currency_id
            diff = currency.round(self.amount_total - self.amount_paid)

            # Dev: Allow Maximum diff is 120R
            if not abs(diff) <= 0.03:
                raise UserError(_("Order %s is not fully paid.", self.name))

        self.write({'state': 'paid'})
        return True

    def get_next_available_sequence(self, sequence_id, start_number, batch_size=100):
        """
        Find the next available sequence number using a batch search approach.

        Args:
            self_sudo: The model instance with sudo privileges
            sequence_id: The sequence record
            start_number: Starting number to search from
            batch_size: How many numbers to check at once

        Returns:
            tuple: (number, name_to_assign) for the first available sequence
        """
        try:
            # Generate a batch of potential names
            batch_numbers = range(start_number, start_number + batch_size)
            name_mapping = {
                num: sequence_id.get_next_char(num)
                for num in batch_numbers
            }

            # Check which names are already taken
            existing_names = self.search_read(
                [('name', 'in', list(name_mapping.values()))],
                ['name']
            )
            taken_names = {record['name'] for record in existing_names}

            # Find first available name
            for num in batch_numbers:
                name = name_mapping[num]
                if name not in taken_names:
                    return (num, name)

            # If no names were available in this batch
            raise ValueError(f"No available sequence found in batch of {batch_size} from {start_number}")

        except Exception as e:
            _logger.error(f"Error in sequence generation: {e}")
            raise

    def check_sequence_store(self, pos_session_id, pos_reference=False, name=False):
        self_sudo = self.sudo()
        if not name:
            name = self_sudo.name
        if not pos_reference:
            pos_reference = self_sudo.pos_reference
        name_to_assign = name
        pos_session = self_sudo.env['pos.session'].browse(pos_session_id)
        if name and pos_reference and pos_session.config_id.sequence_id:
            sequence_id = pos_session.config_id.sequence_id
            # Prevent Duplicate Order Number
            duplicate_id = self_sudo.search([('name', '=', name), ('pos_reference', '!=', pos_reference)])
            if name and duplicate_id and sequence_id.prefix in name:
                parts = name.split(sequence_id.prefix)
                try:
                    number = int(parts[1])
                    number, name_to_assign = self_sudo.get_next_available_sequence(
                        sequence_id,
                        number + 1
                    )
                except Exception as e:
                    _logger.error(e)
        return name_to_assign
