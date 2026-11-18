# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    allocation_block_overlap = fields.Boolean(
        string="Block Overlapping Allocations",
        default=True,
        help="When enabled, an employee cannot have two overlapping "
        "allocations. When disabled, overlaps are allowed and flagged.",
    )
