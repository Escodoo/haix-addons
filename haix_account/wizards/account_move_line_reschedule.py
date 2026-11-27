# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date


class AccountMoveLineReschedule(models.TransientModel):
    _name = "account.move.line.reschedule"
    _description = "Reschedule Expected Payment Date"

    line_ids = fields.Many2many(
        comodel_name="account.move.line", string="Receivables and Payables"
    )
    expected_payment_date = fields.Date(required=True)
    reason = fields.Char(required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_model") == "account.move.line":
            lines = self.env["account.move.line"].browse(
                self.env.context.get("active_ids", [])
            )
            res["line_ids"] = [(6, 0, lines.ids)]
        return res

    def action_reschedule(self):
        self.ensure_one()
        lines = self.line_ids.filtered(
            lambda line: line.parent_state == "posted"
            and line.account_type in ("asset_receivable", "liability_payable")
            and not line.reconciled
        )
        if not lines:
            raise UserError(_("Select open receivables or payables of posted entries."))
        for line in lines:
            line.move_id.message_post(
                body=Markup("<p>%s</p><p>%s</p>")
                % (
                    _(
                        "Expected payment date rescheduled: %(old)s → %(new)s "
                        "(original due date %(due)s).",
                        old=format_date(self.env, line.expected_payment_date),
                        new=format_date(self.env, self.expected_payment_date),
                        due=format_date(self.env, line.date_maturity),
                    ),
                    _("Reason: %(reason)s", reason=self.reason),
                )
            )
        lines.write({"expected_payment_date": self.expected_payment_date})
        return {"type": "ir.actions.act_window_close"}
