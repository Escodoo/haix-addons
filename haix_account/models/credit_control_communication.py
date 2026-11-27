# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from markupsafe import Markup

from odoo import _, models
from odoo.tools.misc import format_date


class CreditControlCommunication(models.Model):
    _inherit = "credit.control.communication"

    def _send_communications_by_email(self):
        """Keep the reminder history on the customer, not only on each run."""
        res = super()._send_communications_by_email()
        for comm in self:
            lines = comm.credit_control_line_ids
            body = Markup("<p>%s</p><ul>%s</ul>") % (
                _(
                    "Payment reminder sent to %(contact)s (%(level)s).",
                    contact=comm.contact_address_id.display_name,
                    level=comm.policy_level_id.display_name,
                ),
                Markup("").join(
                    Markup("<li>%s</li>")
                    % _(
                        "%(invoice)s, due on %(date)s",
                        invoice=line.invoice_id.display_name,
                        date=format_date(self.env, line.date_due),
                    )
                    for line in lines
                ),
            )
            comm.partner_id.commercial_partner_id.message_post(body=body)
        return res
