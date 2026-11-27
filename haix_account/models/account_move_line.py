# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    expected_payment_date = fields.Date(
        compute="_compute_expected_payment_date",
        store=True,
        readonly=False,
        copy=False,
        index=True,
        help="Date the payment is expected. It starts as the due date and can be "
        "rescheduled without changing the original due date. The cash flow "
        "forecast uses this date.",
    )
    is_rescheduled = fields.Boolean(
        compute="_compute_is_rescheduled",
        store=True,
        help="The expected payment date differs from the original due date.",
    )

    @api.depends("date_maturity")
    def _compute_expected_payment_date(self):
        for line in self:
            if not line.expected_payment_date or line.parent_state != "posted":
                line.expected_payment_date = line.date_maturity

    @api.depends("expected_payment_date", "date_maturity")
    def _compute_is_rescheduled(self):
        for line in self:
            line.is_rescheduled = bool(
                line.expected_payment_date
                and line.date_maturity
                and line.expected_payment_date != line.date_maturity
            )

    def _check_due_date_lock(self, vals):
        """The due date of a posted receivable or payable cannot change."""
        if "date_maturity" not in vals or self.env.context.get("skip_due_date_lock"):
            return
        new_date = fields.Date.to_date(vals["date_maturity"])
        for line in self:
            if (
                line.parent_state == "posted"
                and line.account_type in ("asset_receivable", "liability_payable")
                and line.date_maturity
                and line.date_maturity != new_date
            ):
                raise UserError(
                    _(
                        "The due date of %(line)s cannot be changed after the "
                        "entry is posted. Reschedule the expected payment date "
                        "instead.",
                        line=line.display_name,
                    )
                )

    def write(self, vals):
        self._check_due_date_lock(vals)
        return super().write(vals)
