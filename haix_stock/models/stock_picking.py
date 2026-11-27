# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import AccessError

RETURN_DATE_FIELDS = {"scheduled_date", "date_deadline"}


class StockPicking(models.Model):
    _inherit = "stock.picking"

    haix_analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Lease Sheet",
        compute="_compute_haix_analytic_account_id",
        store=True,
        index=True,
    )
    haix_is_rental_return = fields.Boolean(
        string="Rental Return",
        compute="_compute_haix_is_rental_return",
        store=True,
    )

    @api.depends("move_ids.haix_analytic_account_id")
    def _compute_haix_analytic_account_id(self):
        for picking in self:
            picking.haix_analytic_account_id = (
                picking.move_ids.haix_analytic_account_id[:1]
            )

    @api.depends("location_id", "picking_type_id.warehouse_id.rental_out_location_id")
    def _compute_haix_is_rental_return(self):
        for picking in self:
            rental_out = picking.picking_type_id.warehouse_id.rental_out_location_id
            picking.haix_is_rental_return = bool(
                rental_out and picking.location_id == rental_out
            )

    @api.model
    def _haix_raise_return_date_only(self):
        raise AccessError(
            self.env._("You can only change the scheduled date of the rental returns.")
        )

    def write(self, vals):
        if not self.env.su and self.env.user._haix_is_return_date_editor_only():
            if not set(vals).issubset(RETURN_DATE_FIELDS) or self.filtered(
                lambda picking: not picking.haix_is_rental_return
            ):
                self._haix_raise_return_date_only()
        return super().write(vals)

    def action_haix_print_return_slip(self):
        return self.env.ref("haix_stock.action_report_return_slip").report_action(self)
