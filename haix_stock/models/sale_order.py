# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    haix_indemnity_product_id = fields.Many2one(
        "product.product",
        string="Indemnified Product",
        readonly=True,
        copy=False,
    )

    def _prepare_procurement_values(self, group_id=False):
        values = super()._prepare_procurement_values(group_id=group_id)
        if self.analytic_distribution:
            values["analytic_distribution"] = self.analytic_distribution
        return values

    def _prepare_new_rental_procurement_values(self, group=False):
        values = super()._prepare_new_rental_procurement_values(group=group)
        if self.start_date:
            values["date_planned"] = fields.Datetime.to_datetime(
                self.start_date
            ).replace(hour=12)
        if self.analytic_distribution:
            values["analytic_distribution"] = self.analytic_distribution
        return values


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _haix_missing_rental_quantities(self):
        """Quantity of each rented product still at the customer with no
        pending return and not yet charged as indemnity."""
        self.ensure_one()
        rental_out = self.warehouse_id.rental_out_location_id
        if not rental_out or not self.procurement_group_id:
            return {}
        moves = self.env["stock.move"].search(
            [
                ("group_id", "=", self.procurement_group_id.id),
                ("state", "!=", "cancel"),
                "|",
                ("location_id", "=", rental_out.id),
                ("location_dest_id", "=", rental_out.id),
            ]
        )
        balance = defaultdict(float)
        for move in moves:
            if move.state == "done":
                qty = move.product_uom._compute_quantity(
                    move.quantity, move.product_id.uom_id
                )
            else:
                qty = move.product_qty
            if move.location_dest_id == rental_out and move.state == "done":
                balance[move.product_id] += qty
            elif move.location_id == rental_out:
                balance[move.product_id] -= qty
        for line in self.order_line.filtered("haix_indemnity_product_id"):
            balance[line.haix_indemnity_product_id] -= line.product_uom_qty
        return {
            product: qty
            for product, qty in balance.items()
            if product.haix_asset_type != "assembly_supply"
            and float_compare(qty, 0.0, precision_rounding=product.uom_id.rounding) > 0
        }

    def action_haix_charge_missing_items(self):
        self.ensure_one()
        indemnity = self.env.ref("haix_stock.product_rental_indemnity")
        missing = self._haix_missing_rental_quantities()
        if not missing:
            raise UserError(
                self.env._(
                    "There are no missing items: everything that was delivered "
                    "came back or still has a return scheduled."
                )
            )
        rental_lines = self.order_line.filtered(
            lambda line: line.product_id.rented_product_id
        )
        lines = []
        for product, qty in missing.items():
            source = rental_lines.filtered(
                lambda line, product=product: line.product_id.rented_product_id
                == product
            )[:1]
            lines.append(
                {
                    "order_id": self.id,
                    "product_id": indemnity.id,
                    "name": self.env._(
                        "Indemnity - %(product)s not returned",
                        product=product.display_name,
                    ),
                    "product_uom_qty": qty,
                    "price_unit": product.haix_indemnity_value,
                    "haix_indemnity_product_id": product.id,
                    "analytic_distribution": source.analytic_distribution or False,
                }
            )
        new_lines = self.env["sale.order.line"].create(lines)
        self.message_post(
            body=self.env._(
                "Indemnity charged for the items not returned: %(items)s",
                items=", ".join(
                    f"{line.product_uom_qty:g} x "
                    f"{line.haix_indemnity_product_id.display_name}"
                    for line in new_lines
                ),
            )
        )
        return True
