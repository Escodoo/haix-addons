# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _haix_is_return_date_editor_only(self):
        """Sales user allowed to change return dates, without stock rights."""
        self.ensure_one()
        return self.has_group(
            "haix_stock.group_rental_return_date"
        ) and not self.has_group("stock.group_stock_user")
