# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _push_prepare_move_copy_values(self, move_to_copy, new_date):
        # The rental return comes from a push rule. l10n_br_stock_account only
        # applies the rule fiscal operation on pull rules, so the return would
        # keep the delivery operation copied from the outgoing move.
        values = super()._push_prepare_move_copy_values(move_to_copy, new_date)
        if self.fiscal_operation_id:
            values.update(
                {
                    "fiscal_operation_id": self.fiscal_operation_id.id,
                    "fiscal_operation_line_id": False,
                    "invoice_state": self.invoice_state,
                }
            )
        return values
