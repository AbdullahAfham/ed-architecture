# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    @api.depends('previous_statement_id', 'previous_statement_id.balance_end_real')
    def _compute_starting_balance(self):
        for statement in self.sorted(key=lambda s: s.date):
            if statement.journal_type == 'cash' and statement.pos_session_id:
                statement.balance_start = statement.balance_start or 0.0
            else:
                if statement.previous_statement_id.balance_end_real != statement.balance_start:
                    statement.balance_start = statement.previous_statement_id.balance_end_real
                else:
                    # Need default value
                    statement.balance_start = statement.balance_start or 0.0

    def _check_balance_end_real_same_as_computed(self):
        for stmt in self:
            if stmt.journal_type == 'cash' and (stmt.journal_id.currency_id.name == "KHR"):
                for line in stmt.line_ids:
                    if (line.payment_ref == _("Cash difference observed during the counting (Loss)")) or (
                            line.payment_ref == _("Cash difference observed during the counting (Profit)")):
                        line.unlink()
                stmt.write({'balance_end_real': stmt.balance_end})
        return super(AccountBankStatement, self)._check_balance_end_real_same_as_computed()
