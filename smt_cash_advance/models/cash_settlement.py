from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class CashSettlement(models.Model):
    _name = 'account.cash.settlement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Cash Settlement'

    advance_id = fields.Many2one('account.cash.advance', string="Advance ID")
    name = fields.Char(string="Number", default='New')
    settlement_type = fields.Selection([('travel', 'Travel'), ('other', 'Other')], string="Settlement Type")
    employee_id = fields.Many2one('hr.employee', string='Employee Request')
    move_id = fields.Many2one('account.move', string='Move Entry')
    payment_type = fields.Selection([('cash_advance', 'Cash Advance'), ('self_pay', 'Self Pay')], string="Payment Type")
    date_claim = fields.Date(string="Date Settlement")
    currency_id = fields.Many2one('res.currency', string="Currency")
    line_ids = fields.One2many('account.cash.settlement.line', 'settlement_id', string="Cash Settlement Lines")
    settlement_payment_ids = fields.One2many('account.move', 'settlement_payment_id', string='Payment Settlement')
    total_expense = fields.Float(string="Total Expense", compute="_compute_total")
    total_cash_advance = fields.Monetary(string='Total Cash Advance', compute='_compute_total_cash_advance', store=True, currency_field='currency_id')
    total_approve = fields.Float(string='Total Approve (self pay)', store=True, compute='_compute_total_approve')
    total_pay = fields.Float(string='Total will be pay / return', store=True, compute='_compute_total_pay')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('direct_approved', 'Manager Approved'),
        ('accounting_approved', 'Accounting Approved'),
        ('payment', 'Payment'),
        ('rejected', 'Rejected'),
    ], string="Status", default="draft")
    reg_type = fields.Selection([
        ('register_payment', 'Register Payment'),
        ('return_advance', 'Return Advance')
    ], string='Action')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    reg_payment_ids = fields.One2many('cash.settlement.payment', 'advance_id', string='Register Payment')

    @api.onchange('advance_id')
    def _onchange_advance_id(self):
        """Handle changes to the advance_id field."""
        if self.advance_id and self.advance_id.payment_type == 'cash_advance' and self.advance_id.state != 'paid':
            raise UserError(_('This Number Advance Request must be paid by finance before settlement.'))
        if self.advance_id and self.advance_id.request_type == 'other' and self.advance_id.payment_type == 'cash_advance' and self.advance_id.state != 'paid':
            raise UserError(('This Number Advance Request must be paid by finance before settlement.'))
        if self.advance_id:
            self.payment_type = self.advance_id.payment_type

    @api.depends('line_ids.amount_expense', 'advance_id.total_approved', 'advance_id.payment_type')
    def _compute_total(self):
        """Compute total expenses and cash advances."""
        for record in self:
            record.total_expense = sum(line.amount_expense for line in self.line_ids)
            if self.advance_id.payment_type == 'cash_advance':
                record.total_cash_advance = self.advance_id.total_approved
                record.total_pay = record.total_cash_advance - record.total_expense
            elif self.advance_id.payment_type == 'self_pay':
                record.total_approve = self.advance_id.total_approved
                record.total_pay = record.total_cash_advance - record.total_expense
            else:
                record.total_cash_advance = self.advance_id.total_approved
                record.total_pay = record.total_cash_advance - record.total_expense

    def action_reject_settlement(self):
        """Reject the cash settlement."""
        for record in self:
            record.write({'state': 'rejected'})

    def action_confirm_settlement(self):
        """Confirm the cash settlement."""
        for record in self:
            record.write({'state': 'direct_approved'})

    def action_set_to_draft(self):
        """Set the cash settlement back to draft state."""
        for record in self:
            record.write({'state': 'draft'})

    def action_pay_settlement(self):
        """Initiate payment for the cash settlement."""
        view = self.env.ref('smt_cash_advance.cash_settlement_payment_form_view')
        ids = [r.id for r in self.reg_payment_ids]
        res = {
            'name': _('Pay Cash Settlement'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'cash.settlement.payment',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
        }
        if ids:
            res['res_id'] = ids
        return res

    def action_approve_settlement(self):
        """Approve the cash settlement and create accounting entries."""
        self._update_reg_type()
        move_lines = self._prepare_move_lines()
        move_value = {
            'date': self.date_claim or fields.Date.now(),
            'partner_id': self.advance_id.employee_id.address_home_id and self.advance_id.employee_id.address_home_id.id or False,
            'ref': self.advance_id and self.advance_id.name or False,
            'journal_id': self.env['account.journal'].search([('type', '=', 'general')], limit=1).id,
            'line_ids': move_lines
        }
        move = self.env['account.move'].create(move_value)
        move.action_post()

        if self.total_pay == 0:
            self.write({'state': 'paid', 'move_id': move.id})
            self.advance_id.write({'state': 'done'})
        else:
            self.write({'state': 'accounting_approved', 'move_id': move.id})

        return True

    def _update_reg_type(self):
        """Update the registration type based on total expenses and cash advances."""
        if self.total_expense > self.total_cash_advance:
            self.write({'reg_type': '0'})
        else:
            self.write({'reg_type': '1'})

    def _prepare_move_lines(self):
        """Prepare the move lines for accounting entries."""
        move_lines = []
        journal_id = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
        company_id = self.env.user.company_id
        company_currency = company_id.currency_id
        current_currency = self.advance_id.currency
        prec = company_currency.decimal_places

        for line in self.line_ids:
            amount_expense = line.amount_expense
            amount_expense_converted = current_currency._convert(amount_expense, company_currency, company_id, self.date_claim or fields.Date.today())
            move_line = {
                'name': line.account_id and line.account_id.name or False,
                'partner_id': self.advance_id.employee_id.address_home_id and self.advance_id.employee_id.address_home_id.id or False,
                'account_id': line.account_id.id,
                'amount_currency': amount_expense,
                'currency_id': current_currency and current_currency.id,
                'quantity': 1,
                'analytic_distribution': line.analytic_distribution,
                'debit': amount_expense_converted if float_compare(amount_expense_converted, 0.0, precision_digits=prec) > 0 else 0.0,
                'credit': 0.0 if float_compare(amount_expense_converted, 0.0, precision_digits=prec) > 0 else -amount_expense_converted,
            }
            move_lines.append((0, 0, move_line))

        return move_lines

    @api.model_create_multi
    def create(self, vals_list):
        """Create new cash settlement records."""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New') and vals.get('settlement_type', 'travel') == 'travel':
                sequence_code = 'travel.settlement.sequence' or False
            elif vals.get('name', _('New')) == _('New') and vals.get('settlement_type', 'other') == 'other':
                sequence_code = 'other.settlement.sequence' or False
            vals['name'] = self.env['ir.sequence'].next_by_code(sequence_code) or _('New') or False

        result = super(CashSettlement, self).create(vals)
        return result

    def unlink(self):
        """Delete cash settlement records."""
        for settlement in self:
            if settlement.state not in ('draft', 'rejected'):
                raise UserError(_('You cannot delete a settlement which is not draft or rejected.'))
        return super(CashSettlement, self).unlink()
