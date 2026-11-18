# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    allocation_eligible = fields.Boolean(
        string="Field Team",
        help="Field team employees can be allocated to tasks and appear in "
        "the availability screen.",
    )
    allocation_team_id = fields.Many2one(
        comodel_name="project.allocation.team",
        string="Allocation Team",
        index=True,
        tracking=True,
        check_company=True,
        domain="[('company_id', 'in', [company_id, False])]",
        help="Usual team of the employee. Each employee belongs to a single team.",
    )


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    # Exposed to users without HR rights (e.g. allocation readers)
    allocation_eligible = fields.Boolean(string="Field Team", readonly=True)
    allocation_team_id = fields.Many2one(
        comodel_name="project.allocation.team",
        string="Allocation Team",
        readonly=True,
    )
