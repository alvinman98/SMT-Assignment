from odoo import models, fields


class CashAdvanceLine(models.Model):
    _name = 'account.cash.advance.line'
    _description = 'Cash Advance Line'

    name = fields.Char(string="Description")
    account_id = fields.Many2one('account.account', string='Account Expense')
    analytic_distribution = fields.Json(string='Analytic')
    amount_requested = fields.Float(string="Requested Amount")
    advance_id = fields.Many2one('account.cash.advance', string="Advance ID")
