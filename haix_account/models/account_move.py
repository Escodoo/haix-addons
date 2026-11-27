# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _check_vendor_bill_purchase(self):
        """A vendor bill must come from a purchase order."""
        if self.env.context.get(
            "skip_vendor_bill_purchase_check"
        ) or self.env.user.has_group("haix_account.group_vendor_bill_without_purchase"):
            return
        for move in self:
            if move.move_type != "in_invoice":
                continue
            if not move.invoice_line_ids.purchase_line_id:
                raise UserError(
                    _(
                        "The vendor bill %(bill)s is not linked to a purchase "
                        "order. Create the bill from the purchase order or ask a "
                        "user allowed to post vendor bills without a purchase "
                        "order.",
                        bill=move.display_name,
                    )
                )

    def _post(self, soft=True):
        self._check_vendor_bill_purchase()
        return super()._post(soft=soft)
