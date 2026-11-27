# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import time

from odoo import fields, models

# Rental dates are plain dates; at midnight UTC they show up the day before in
# Brazil, so they are scheduled at noon.
RENTAL_TIME = time(12, 0)


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _push_prepare_move_copy_values(self, move_to_copy, new_date):
        res = super()._push_prepare_move_copy_values(move_to_copy, new_date)
        line = move_to_copy.sale_line_id
        if (
            line.rental_type == "new_rental"
            and line.end_date
            and res.get("location_id")
            == move_to_copy.warehouse_id.rental_out_location_id.id
        ):
            res["date"] = fields.Datetime.to_datetime(line.end_date).replace(
                hour=RENTAL_TIME.hour
            )
        return res
