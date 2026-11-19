# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    allocation_block_overlap = fields.Boolean(
        related="company_id.allocation_block_overlap",
        readonly=False,
    )
