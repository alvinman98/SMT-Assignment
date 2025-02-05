from odoo import models, fields, api, _


class CashSettlementLine(models.Model):
    _name = 'account.cash.settlement.line'
    _description = 'Cash Settlement Line'

    product_id = fields.Many2one('product.product', string='Product')
    product_id2 = fields.Many2one('product.product', string='Product')
    name = fields.Char(string='Description')
    account_id = fields.Many2one('account.account', string='Account Expense')
    analytic_distribution = fields.Json(string='Analytic')
    amount_expense = fields.Float(string='Expense Amount')
    settlement_id = fields.Many2one('account.cash.settlement', string='Cash Settlement')
    date_trans = fields.Date(string='Date Transaction')
    currency = fields.Many2one('res.currency', string='Currency')
    value = fields.Float(string='Value', compute='_compute_value', store=True)
    cash_out = fields.Float(string='Cash Advance Out', compute='_compute_cash_out', store=True)
    rate = fields.Float(string='Rate')

    @api.onchange('product_id', 'settlement_id')  
    def _onchange_product(self):  
        """Handle changes to the product_id and settlement_id fields."""
        if self.settlement_id:  
            if self.product_id:  
                accounts = self.product_id.product_tmpl_id._get_product_accounts()  
                self.account_id = accounts.get('expense', False)  
                self.name = self.product_id.name

    @api.onchange('product_id2', 'settlement_id')  
    def _onchange_product_id2(self):  
        if self.product_id2:  
            accounts = self.product_id2.product_tmpl_id._get_product_accounts()  
            self.account_id = accounts.get('expense', False)  
            self.name = self.product_id2.name  
            self.settlement_id = self.settlement_id.id

    def detail_product(self):  
        """Open the detail product form view."""
        view = self.env.ref('smt_cash_advance.view_detail_product_form')  
        return {  
            'name': _('Detail Product '),  
            'type': 'ir.actions.act_window',  
            'view_mode': 'form',  
            'res_model': 'account.cash.settlement.line',  
            'views': [(view.id, 'form')],  
            'view_id': view.id,  
            'target': 'new',  
            'res_id': self.id,  
        }

    @api.depends('value', 'rate')  
    def _compute_cash_out(self):  
        """Compute the cash out amount based on value and rate."""
        for record in self:  
            record.cash_out = record.value * record.rate if record.value and record.rate else 0.0
            record.amount_expense = record.cash_out
