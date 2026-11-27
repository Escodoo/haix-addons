# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    haix_unique_number = fields.Char(
        string="Unique Number",
        readonly=True,
        copy=False,
        index=True,
        help="Number given by the system when the product is created. It never "
        "changes, even if the name or the internal reference change.",
    )
    haix_asset_type = fields.Selection(
        [
            ("rental_equipment", "Rental Equipment"),
            ("assembly_supply", "Assembly Supply"),
        ],
        string="Asset Type",
        help="Assembly supplies (screws, clamps) go to the job site with the "
        "equipment, but are not charged as rental nor as indemnity.",
    )
    haix_requires_inspection = fields.Boolean(
        string="Requires Inspection",
        help="When it comes back from a rental, the item goes to the Inspection "
        "location and is not available until it is released.",
    )
    haix_indemnity_value = fields.Monetary(
        string="Indemnity Value",
        help="Value charged when the item is not returned. Also used as the "
        "value of the shipping invoice.",
    )
    haix_used_sale_value = fields.Monetary(string="Used Sale Value")
    haix_supplier_value = fields.Monetary(string="Supplier Value")
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
        for template in self:
            variants = template.product_variant_ids
            template.haix_qty_inspection = sum(variants.mapped("haix_qty_inspection"))
            template.haix_qty_maintenance = sum(variants.mapped("haix_qty_maintenance"))

    _sql_constraints = [
        (
            "haix_unique_number_uniq",
            "unique(haix_unique_number)",
            "The unique number must be unique.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if not vals.get("haix_unique_number"):
                vals["haix_unique_number"] = sequence.next_by_code(
                    "haix.product.unique.number"
                )
        return super().create(vals_list)
