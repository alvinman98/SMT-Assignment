from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    advance_payment_id = fields.Many2one('account.cash.advance', string="Payments")
    settlement_payment_id = fields.Many2one('account.cash.settlement', string="Payment Settlement")
    settlement_payment_sett_id = fields.Many2one('account.cash.advance', string="Payment Advance Settlement")
    move_ids = fields.One2many('account.cash.settlement', 'move_id', string='Move Entry')
