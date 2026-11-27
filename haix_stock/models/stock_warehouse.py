# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    haix_inspection_location_id = fields.Many2one(
        "stock.location",
        string="Inspection Location",
        domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]",
        help="Returned rental items that require inspection are received here.",
    )
    haix_maintenance_location_id = fields.Many2one(
        "stock.location",
        string="Maintenance Location",
        domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]",
    )
