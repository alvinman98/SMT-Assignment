from odoo import models, fields, api
from odoo.tools import float_compare


class CashAdvancePayment(models.Model):  
    _name = 'cash.advance.payment'  
    _description = 'Cash Advance Payment'  

    advance_id = fields.Many2one('account.cash.advance', string="Advance To Pay", required=True, default=lambda self: self._context.get('active_id', False))  
    journal_id = fields.Many2one('account.journal', string="Payment Journal", required=True)  
    amount_paid = fields.Float(string="Payment Amount", required=True, store=True, compute='_compute_amount_paid')  
    currency = fields.Many2one('res.currency', string="Currency")  
    date = fields.Date(string="Payment Date", required=True, default=fields.Date.today)  
    memo = fields.Char('Memo')  
    method_type = fields.Selection([  
        ('manual', 'Manual'),  
        ('checks', 'Checks'),  
    ], string="Payment Method Type", default='manual', required=True)

    @api.depends('advance_id.total_approved')
    def _compute_amount_paid(self):
        """Compute the amount paid based on the advance's total approved amount."""
        for record in self:
            record.amount_paid = record.advance_id.total_approved if record.advance_id else 0.0

    @api.onchange('amount_paid', 'advance_id')
    def _onchange_advance_id(self):
        """Update the amount paid and currency based on the selected advance."""
        if self.advance_id:
            self.amount_paid = self.advance_id.total_approved
            self.currency = self.advance_id.currency_id

    def action_validate_advance_payment(self):
        """Validate the cash advance payment and create accounting entries."""
        self.amount_paid = self.advance_id.total_approved
        move_lines = self._prepare_move_lines()
        move_value = self._prepare_move_value(move_lines)

        created_move_id = self.env['account.move'].create(move_value)  
        created_move_id.action_post()  
        self.advance_id.write({'state': 'paid'})  
        return True

    def _prepare_move_lines(self):
        """Prepare the move lines for accounting entries."""
        move_lines = []
        user = self.env['res.users'].sudo().browse(self._uid)
        company_id = user.company_id
        company_currency = company_id.currency_id
        current_currency = self.advance_id.currency_id
        prec = company_currency.decimal_places

        amount = current_currency._convert(self.amount_paid, company_currency, company_id, self.date or fields.Date.today())

        move_line_1 = {
            'name': self.advance_id and self.advance_id.name or False,
            'partner_id': self.advance_id.employee_id.address_home_id and self.advance_id.employee_id.address_home_id.id or False,
            'account_id': self.advance_id.employee_id.advance_account_id.id,
            'amount_currency': self.amount_paid,
            'currency_id': current_currency and current_currency.id,
            'quantity': 1,
            'debit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
            'credit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
        }
        move_lines.append((0, 0, move_line_1))

        move_line_2 = {
            'name': self.journal_id and self.journal_id.name or False,
            'partner_id': self.advance_id.employee_id.address_home_id and self.advance_id.employee_id.address_home_id.id or False,
            'account_id': self.journal_id.default_account_id.id,
            'amount_currency': -self.amount_paid,
            'currency_id': current_currency and current_currency.id,
            'quantity': 1,
            'debit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else amount,
            'credit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
        }
        move_lines.append((0, 0, move_line_2))

        return move_lines

    def _prepare_move_value(self, move_lines):
        """Prepare the move value for creating an account move."""
        return {
            'date': self.date or fields.Date.now(),
            'partner_id': self.advance_id.employee_id.address_home_id and self.advance_id.employee_id.address_home_id.id or False,
            'ref': self.advance_id and self.advance_id.name or False,
            'journal_id': self.journal_id and self.journal_id.id or False,
            'advance_payment_id': self.advance_id and self.advance_id.id or False,
            'line_ids': move_lines,
        }
