# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

RETURN_DATE_FIELDS = {"date", "date_deadline"}


class StockMove(models.Model):
    _inherit = "stock.move"

    haix_analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Lease Sheet",
        compute="_compute_haix_analytic_account_id",
        store=True,
        index=True,
    )

    @api.model
    def _haix_lease_sheet_account(self, distribution):
        """First account of the distribution, preferring the lease sheet plan."""
        if not distribution:
            return self.env["account.analytic.account"]
        account_ids = [
            int(account_id)
            for key in distribution
            for account_id in key.split(",")
            if account_id.isdigit()
        ]
        accounts = self.env["account.analytic.account"].browse(account_ids).exists()
        plan_id = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("haix_stock.lease_sheet_plan_id", 0)
        )
        sheet = accounts.filtered(lambda acc: acc.root_plan_id.id == plan_id)
        return (sheet or accounts)[:1]

    @api.depends("analytic_distribution")
    def _compute_haix_analytic_account_id(self):
        for move in self:
            move.haix_analytic_account_id = self._haix_lease_sheet_account(
                move.analytic_distribution
            )

    def write(self, vals):
        if (
            not self.env.su
            and self.env.user._haix_is_return_date_editor_only()
            and not set(vals).issubset(RETURN_DATE_FIELDS)
        ):
            self.env["stock.picking"]._haix_raise_return_date_only()
        return super().write(vals)

    def _haix_inspection_location(self):
        """Inspection location when this move brings back a rental item that
        must be inspected, otherwise an empty recordset."""
        self.ensure_one()
        warehouse = self.warehouse_id or self.picking_type_id.warehouse_id
        if (
            warehouse
            and warehouse.haix_inspection_location_id
            and warehouse.rental_out_location_id
            and self.location_id == warehouse.rental_out_location_id
            and self.product_id.haix_requires_inspection
        ):
            return warehouse.haix_inspection_location_id
        return self.env["stock.location"]

    def _action_done(self, cancel_backorder=False):
        for move in self.filtered(lambda m: m.state not in ("done", "cancel")):
            inspection = move._haix_inspection_location()
            if inspection and move.location_dest_id != inspection:
                move.location_dest_id = inspection
                move.move_line_ids.location_dest_id = inspection
        return super()._action_done(cancel_backorder=cancel_backorder)
