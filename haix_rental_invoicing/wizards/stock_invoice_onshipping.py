# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockInvoiceOnshipping(models.TransientModel):
    _inherit = "stock.invoice.onshipping"

    def _get_invoice_type(self):
        # The sale_rental "Rental Out" location is internal, so a rental
        # delivery (internal -> internal) would be invoiced as a vendor refund.
        # It stands for the customer site: delivery is an outgoing document and
        # the return an incoming one, like a sale and its return.
        picking = self.env["stock.picking"].browse(
            self.env.context.get("active_ids", [])[:1]
        )
        rental_out = picking.picking_type_id.warehouse_id.rental_out_location_id
        if rental_out:
            if picking.location_dest_id == rental_out:
                return "out_invoice"
            if picking.location_id == rental_out:
                return "out_refund"
        return super()._get_invoice_type()

    def _group_moves(self, moves):
        # A move cancelled at validation (nothing shipped or returned) must not
        # be invoiced.
        return super()._group_moves(moves.filtered(lambda m: m.state != "cancel"))

    def _get_invoice_line_values(self, moves, invoice_values, invoice):
        # stock_picking_invoicing invoices the demand (product_uom_qty). Since
        # Odoo 17 the demand is not updated to the done quantity at validation,
        # so a delivery with more or less than planned (an extra counterweight,
        # a missing guardrail) would be invoiced with the planned quantity.
        values = super()._get_invoice_line_values(moves, invoice_values, invoice)
        if not moves or any(move.state != "done" for move in moves):
            return values
        done = sum(moves.mapped("quantity"))
        quantity = values.get("quantity") or 0.0
        if not quantity or abs(quantity) == done:
            return values
        new_quantity = done if quantity > 0 else -done
        values["quantity"] = new_quantity
        if "fiscal_quantity" in values:
            # same rule as l10n_br_fiscal _compute_fiscal_quantity
            product = fields.first(moves).product_id
            values["fiscal_quantity"] = new_quantity * (product.uot_factor or 1.0)
        return values
