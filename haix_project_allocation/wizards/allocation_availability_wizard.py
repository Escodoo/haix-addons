# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, _, api, fields, models
from odoo.tools.misc import format_date

from .task_allocation_wizard import AVAILABILITY_STATUS, STATUS_ORDER

# Up to a week the weekday is enough to identify a day
WEEKDAY_ONLY_MAX_DAYS = 7


class ProjectAllocationAvailabilityWizard(models.TransientModel):
    _name = "project.allocation.availability.wizard"
    _description = "Available in Period"

    def _default_shift_ids(self):
        return self.env["project.allocation.shift"].search([("in_full_day", "=", True)])

    date_from = fields.Date(
        string="From", required=True, default=fields.Date.context_today
    )
    date_to = fields.Date(string="To", required=True, default=fields.Date.context_today)
    shift_ids = fields.Many2many(
        comodel_name="project.allocation.shift",
        relation="project_allocation_availability_wizard_shift_rel",
        column1="wizard_id",
        column2="shift_id",
        string="Shifts",
        required=True,
        default=_default_shift_ids,
    )
    team_id = fields.Many2one(
        comodel_name="project.allocation.team",
        string="Team",
        help="Only list the members of this team.",
    )
    department_id = fields.Many2one(comodel_name="hr.department")
    line_ids = fields.One2many(
        comodel_name="project.allocation.availability.wizard.line",
        inverse_name="wizard_id",
        string="Employees",
        compute="_compute_line_ids",
        store=True,
    )

    @api.depends("date_from", "date_to", "shift_ids", "team_id", "department_id")
    def _compute_line_ids(self):
        for wizard in self:
            commands = [Command.clear()]
            if (
                wizard.shift_ids
                and wizard.date_from
                and wizard.date_to
                and wizard.date_from <= wizard.date_to
            ):
                commands += [
                    Command.create(vals) for vals in wizard._prepare_line_vals()
                ]
            wizard.line_ids = commands

    def _get_employees(self):
        domain = [
            ("allocation_eligible", "=", True),
            ("company_id", "in", self.env.companies.ids),
        ]
        if self.team_id:
            domain.append(("allocation_team_id", "=", self.team_id.id))
        if self.department_id:
            domain.append(("department_id", "=", self.department_id.id))
        return self.env["hr.employee"].search(domain)

    def _format_shifts(self, keys):
        """Readable list of (day, shift id), e.g. 'Mon Afternoon, Tue Morning'."""
        days = (self.date_to - self.date_from).days + 1
        date_format = "EEE" if days <= WEEKDAY_ONLY_MAX_DAYS else "EEE dd/MM"
        names = {shift.id: shift.name for shift in self.shift_ids}
        return ", ".join(
            f"{format_date(self.env, day, date_format=date_format)} {names[shift_id]}"
            for day, shift_id in keys
        )

    def _prepare_line_vals(self):
        employees = self._get_employees()
        availability = employees._get_allocation_availability(
            self.date_from, self.date_to, self.shift_ids
        )
        rows = []
        for employee in employees:
            info = availability[employee.id]
            allocations = info["allocation_ids"]
            rows.append(
                (
                    (STATUS_ORDER[info["status"]], employee.name or ""),
                    {
                        "employee_id": employee.id,
                        "status": info["status"],
                        "free_shifts_text": self._format_shifts(info["free_shifts"]),
                        "allocated_shifts_text": self._format_shifts(
                            info["allocated_shifts"]
                        ),
                        "free_hours": info["free_hours"],
                        "detail": info["detail"],
                        "allocated_team_ids": [Command.set(allocations.team_id.ids)],
                        "allocated_project_ids": [
                            Command.set(allocations.project_id.ids)
                        ],
                    },
                )
            )
        rows.sort(key=lambda row: row[0])
        return [dict(vals, sequence=index) for index, (_key, vals) in enumerate(rows)]

    def action_open_timeline(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Team Planning"),
            "res_model": "project.task.allocation",
            "view_mode": "list,form",
            "domain": [
                ("allocation_date", ">=", self.date_from),
                ("allocation_date", "<=", self.date_to),
            ],
        }


class ProjectAllocationAvailabilityWizardLine(models.TransientModel):
    _name = "project.allocation.availability.wizard.line"
    _description = "Available in Period Line"
    _order = "sequence, id"

    wizard_id = fields.Many2one(
        comodel_name="project.allocation.availability.wizard",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer()
    employee_id = fields.Many2one(comodel_name="hr.employee", required=True)
    employee_team_id = fields.Many2one(
        related="employee_id.allocation_team_id", string="Team"
    )
    status = fields.Selection(AVAILABILITY_STATUS)
    free_shifts_text = fields.Char(string="Free Shifts")
    allocated_shifts_text = fields.Char(string="Allocated Shifts")
    free_hours = fields.Float()
    detail = fields.Char()
    allocated_team_ids = fields.Many2many(
        comodel_name="project.allocation.team",
        relation="project_allocation_availability_line_team_rel",
        column1="line_id",
        column2="team_id",
        string="Allocated By",
    )
    allocated_project_ids = fields.Many2many(
        comodel_name="project.project",
        relation="project_allocation_availability_line_project_rel",
        column1="line_id",
        column2="project_id",
        string="Allocated On",
    )

    def action_allocate(self):
        self.ensure_one()
        wizard = self.wizard_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Allocate Team"),
            "res_model": "project.task.allocation.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_employee_ids": [self.employee_id.id],
                "default_date_from": fields.Date.to_string(wizard.date_from),
                "default_date_to": fields.Date.to_string(wizard.date_to),
                "default_shift_ids": wizard.shift_ids.ids,
            },
        }
