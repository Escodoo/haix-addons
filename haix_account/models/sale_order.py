# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    measurement_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Measurement Approver",
        tracking=True,
        help="Contact at the job site who receives and approves the measurement "
        "report.",
    )
    billing_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Billing Contact",
        tracking=True,
        help="Contact who receives the invoice and the payment reminders. It can "
        "belong to a company other than the customer of the job site.",
    )
