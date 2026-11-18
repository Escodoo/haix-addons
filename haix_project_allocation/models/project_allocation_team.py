# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ProjectAllocationTeam(models.Model):
    _name = "project.allocation.team"
    _description = "Allocation Team"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True)
    leader_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Usual Leader",
        check_company=True,
    )
    member_ids = fields.One2many(
        comodel_name="hr.employee",
        inverse_name="allocation_team_id",
        string="Members",
        domain=[("allocation_eligible", "=", True)],
        help="Each employee belongs to a single team: adding an employee "
        "here removes them from their previous team.",
    )
    member_count = fields.Integer(compute="_compute_member_count")
    color = fields.Integer()
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)

    def _compute_member_count(self):
        # hr.employee.public: readable by users without HR rights
        counts = {
            team.id: count
            for team, count in self.env["hr.employee.public"]._read_group(
                [("allocation_team_id", "in", self.ids)],
                ["allocation_team_id"],
                ["__count"],
            )
        }
        for team in self:
            team.member_count = counts.get(team.id, 0)
