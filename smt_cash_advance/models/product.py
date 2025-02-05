from odoo import api, fields, models


class ProductTemplate(models.Model) :
    _inherit = 'product.template'

    can_be_expensed = fields.Boolean(string="Can be Expensed for Travel Settlement", help="specify whether the product can be selected in an expense.")
    can_be_expensed2 = fields.Boolean(string="Can be Expensed for other Settlement", help="specify whether the product can be selected in an expense.")

    @api.onchange("type")
    def _onchange_type_for_expense(self):
        if self.type not in ['consu', 'service']:
            self.can_be_expensed = False
            self.can_be_expensed2 = False
