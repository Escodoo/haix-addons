# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    haix_qty_inspection = fields.Float(
        string="In Inspection",
        compute="_compute_haix_qty_inspection_maintenance",
        digits="Product Unit of Measure",
    )
    haix_qty_maintenance = fields.Float(
        string="In Maintenance",
        compute="_compute_haix_qty_inspection_maintenance",
        digits="Product Unit of Measure",
    )

    def _compute_haix_qty_inspection_maintenance(self):
        warehouses = self.env["stock.warehouse"].search([])
        inspection = warehouses.haix_inspection_location_id
        maintenance = warehouses.haix_maintenance_location_id
        for product in self:
            product.haix_qty_inspection = (
                product.with_context(location=inspection.ids).qty_available
                if inspection
                else 0.0
            )
            product.haix_qty_maintenance = (
                product.with_context(location=maintenance.ids).qty_available
                if maintenance
                else 0.0
            )
