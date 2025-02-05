from odoo import models, fields, api, _
from odoo.exceptions import UserError

class CashAdvance(models.Model):
    _name = 'account.cash.advance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Cash Advance'

    name = fields.Char(string="Transaction Number", copy=False, default='New')
    request_type = fields.Selection([('travel', 'Travel'), ('other', 'Other')], string="Request Type")
    payment_type = fields.Selection([('cash_advance', 'Cash Advance'), ('self_pay', 'Self Pay')], string="Payment Type")
    date_request = fields.Date(string="Request Date")
    date_request_payment = fields.Date(string="Due Date Payment")
    date_approve = fields.Date(string="Approve Date")
    employee_id = fields.Many2one('hr.employee', string="Employee Request")
    employee_pos = fields.Many2one('hr.job', string="Job Position")
    period_travelling = fields.Integer(string="Period of Travelling (days)", compute="_compute_period_travelling", store=True)
    start_travel = fields.Date(string="Start Travel Date")
    end_travel = fields.Date(string="End Travel Date")
    destination = fields.Char(string="Destination")
    purpose = fields.Char(string="Purpose")
    currency_id = fields.Many2one('res.currency', string="Currency")
    total_requested = fields.Monetary(string="Total Requested Amount", compute="_compute_total_requested", store=True)
    total_approved = fields.Float(string="Total Amount Approved")
    line_ids = fields.One2many('account.cash.advance.line', 'advance_id', string="Cash Advance Lines")
    payment_ids = fields.One2many('account.move', 'advance_payment_id', string="Payment")
    settlement_ids = fields.One2many('account.cash.settlement', 'advance_id', string="Settlements")
    settlement_payment_sett_ids = fields.One2many('account.move', 'settlement_payment_sett_id', string="Payment Settlement")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    reg_payment_ids = fields.One2many('cash.advance.payment', 'advance_id', string="Register Payment")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('direct_approved', 'Manager Approved'),
        ('accounting_approved', 'Accounting Approved'),
        ('payment', 'Payment'),
        ('rejected', 'Rejected'),
        ('done', 'Done'),
    ], string="Status", default="draft")

    def _compute_total_requested(self):
        """Compute the total requested amount from the cash advance lines."""
        for record in self:
            record.total_requested = sum(line.amount_requested for line in record.line_ids)

    @api.depends('total_approved')
    def _compute_date_approve(self):
        """Compute the approval date based on the total approved amount."""
        for record in self:
            record.date_approve = fields.Date.today() if record.total_approved else False

    @api.depends('start_travel', 'end_travel')
    def _compute_period_travelling(self):
        """Compute the period of travelling in days."""
        for record in self:
            if record.start_travel and record.end_travel:
                if record.end_travel < record.start_travel:
                    raise UserError(_('End Travel must be higher than Start Travel'))
                record.period_travelling = (record.end_travel - record.start_travel).days + 1
            else:
                record.period_travelling = 0

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """Update the job position based on the selected employee."""
        self.employee_pos = self.employee_id.job_id.id if self.employee_id else False

    def action_confirm(self):
        """Confirm the cash advance."""
        for record in self:
            record.state = 'direct_approved'

    def action_approve(self):
        """Approve the cash advance based on payment type."""
        for record in self:
            record.state = 'direct_approved' if record.payment_type == 'self_pay' else 'accounting_approved'

    def action_reject(self):
        """Reject the cash advance."""
        for record in self:
            record.state = 'rejected'

    def action_pay_advance(self):
        """Open the cash advance payment form."""
        view = self.env.ref('smt_cash_advance.cash_advance_payment_form_view')
        return {
            'name': ('Pay Cash Advance'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'cash.advance.payment',
            'views': [(view.id, 'form')],
            'target': 'new',
            'res_id': self.reg_payment_ids and self.reg_payment_ids[0].id or False,
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Create a new cash advance record."""
        for vals in vals_list:
            emp_id = vals.get('employee_id', self.env.user.employee_ids.id)
            existing_advances = self.search([
                ('state', 'not in', ['done', 'rejected']),
                ('employee_id', '=', emp_id),
                ('request_type', '!=', False)
            ])
            if existing_advances and vals.get('payment_type', False):
                raise UserError(_('You cannot create new advance before settlement outstanding advance'))

            # Create Sequence
            sequence_code = f"{vals.get('request_type')}.advance.sequence"
            vals['name'] = self.env['ir.sequence'].next_by_code(sequence_code) or 'New'

        return super(CashAdvance, self).create(vals_list)

    def unlink(self):
        """Delete the cash advance record if in draft or rejected state."""
        for advance in self:
            if advance.state not in ('draft', 'rejected'):
                raise UserError(_('You cannot delete an advance which is not draft or rejected.'))
        return super(CashAdvance, self).unlink()
