from odoo import models, fields


class HRemployee(models.Model):
    _inherit = 'hr.employee'

    advance_account_id = fields.Many2one("account.account", string="Advance Account")
    advance_payable_account_id = fields.Many2one("account.account", string="Advance Account Payable")
    advance_receivable_account_id = fields.Many2one("account.account", string="Advance Account Receivable")


class HrEmployeePublic(models.Model) :
    _inherit = 'hr.employee.public'

    advance_account_id = fields.Many2one("account.account", readonly=True)
    advance_payable_account_id = fields.Many2one("account.account", readonly=True)
    advance_receivable_account_id = fields.Many2one("account.account", readonly=True)
