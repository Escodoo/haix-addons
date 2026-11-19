# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date

AVAILABILITY_STATUS = [
    ("available", "Available"),
    ("partial", "Partially Available"),
    ("allocated", "Allocated"),
    ("absent", "Absent"),
]
STATUS_ORDER = {
    status: index for index, (status, _label) in enumerate(AVAILABILITY_STATUS)
}


class ProjectTaskAllocationWizard(models.TransientModel):
    _name = "project.task.allocation.wizard"
    _description = "Allocate Team"

    def _get_context_task(self):
        return self.env["project.task"].browse(self.env.context.get("default_task_id"))

    def _default_planned_date(self, field_name):
        task = self._get_context_task()
        if task and field_name in task._fields and task[field_name]:
            return fields.Date.context_today(self, task[field_name])
        return fields.Date.context_today(self)

    def _default_date_from(self):
        return self._default_planned_date("planned_date_start")

    def _default_date_to(self):
        return self._default_planned_date("planned_date_end")

    def _default_shift_ids(self):
        return self.env["project.allocation.shift"].search([("in_full_day", "=", True)])

    task_id = fields.Many2one(comodel_name="project.task", required=True)
    company_id = fields.Many2one(
        comodel_name="res.company", compute="_compute_company_id"
    )
    date_from = fields.Date(string="From", required=True, default=_default_date_from)
    date_to = fields.Date(string="To", required=True, default=_default_date_to)
    shift_ids = fields.Many2many(
        comodel_name="project.allocation.shift",
        relation="project_task_allocation_wizard_shift_rel",
        column1="wizard_id",
        column2="shift_id",
        string="Shifts",
        required=True,
        default=_default_shift_ids,
    )
    team_id = fields.Many2one(
        comodel_name="project.allocation.team",
        string="Team",
        help="Team of the site for these days. Its available members are "
        "selected, and every allocation created gets this team.",
    )
    team_members_only = fields.Boolean()
    show_unavailable = fields.Boolean(
        help="Also list employees who are allocated or absent.",
    )
    employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        relation="project_task_allocation_wizard_employee_rel",
        column1="wizard_id",
        column2="employee_id",
        string="Preselected Employees",
    )
    line_ids = fields.One2many(
        comodel_name="project.task.allocation.wizard.line",
        inverse_name="wizard_id",
        string="Employees",
        compute="_compute_line_ids",
        store=True,
        readonly=False,
    )

    @api.depends("task_id.company_id")
    def _compute_company_id(self):
        for wizard in self:
            wizard.company_id = wizard.task_id.company_id or self.env.company

    @api.depends(
        "task_id",
        "date_from",
        "date_to",
        "shift_ids",
        "team_id",
        "team_members_only",
        "show_unavailable",
        "employee_ids",
    )
    def _compute_line_ids(self):
        for wizard in self:
            commands = [Command.clear()]
            if (
                wizard.task_id
                and wizard.shift_ids
                and wizard.date_from
                and wizard.date_to
                and wizard.date_from <= wizard.date_to
            ):
                commands += [
                    Command.create(vals) for vals in wizard._prepare_line_vals()
                ]
            wizard.line_ids = commands

    def _get_candidate_employees(self):
        domain = [
            ("allocation_eligible", "=", True),
            ("company_id", "=", self.company_id.id),
        ]
        if self.team_id and self.team_members_only:
            domain.append(("allocation_team_id", "=", self.team_id.id))
        return self.env["hr.employee"].search(domain)

    def _get_existing_allocations(self, employees):
        """Allocations of these employees already on this task in the period."""
        return self.env["project.task.allocation"].search(
            [
                ("task_id", "=", self.task_id._origin.id),
                ("employee_id", "in", employees.ids),
                ("allocation_date", ">=", self.date_from),
                ("allocation_date", "<=", self.date_to),
                ("shift_id", "in", self.shift_ids.ids),
            ]
        )

    def _prepare_line_vals(self):
        employees = self._get_candidate_employees()
        availability = employees._get_allocation_availability(
            self.date_from, self.date_to, self.shift_ids
        )
        already = self._get_existing_allocations(employees).employee_id
        preselected = self.employee_ids
        rows = []
        for employee in employees:
            info = availability[employee.id]
            status = info["status"]
            is_member = bool(self.team_id) and (
                employee.allocation_team_id == self.team_id
            )
            selected = (
                employee in already
                or employee in preselected
                or (is_member and status == "available")
            )
            if not (
                self.show_unavailable or status in ("available", "partial") or selected
            ):
                continue
            sort_key = (not is_member, STATUS_ORDER[status], employee.name or "")
            rows.append(
                (
                    sort_key,
                    {
                        "employee_id": employee.id,
                        "selected": selected,
                        "already_allocated": employee in already,
                        "is_team_member": is_member,
                        "status": status,
                        "work_hours": info["work_hours"],
                        "free_hours": info["free_hours"],
                        "detail": info["detail"],
                    },
                )
            )
        rows.sort(key=lambda row: row[0])
        return [dict(vals, sequence=index) for index, (_key, vals) in enumerate(rows)]

    def _prepare_allocation_vals(self, employees):
        """Return (allocation values, conflict descriptions) for one allocation
        per employee, day and shift they work in, skipping existing ones."""
        availability = employees._get_allocation_availability(
            self.date_from, self.date_to, self.shift_ids
        )
        existing = {
            (
                allocation.employee_id.id,
                allocation.allocation_date,
                allocation.shift_id.id,
            )
            for allocation in self._get_existing_allocations(employees)
        }
        shift_names = {shift.id: shift.name for shift in self.shift_ids}
        vals_list, conflicts = [], []
        for employee in employees:
            info = availability.get(employee.id)
            if not info:
                continue
            allocated = set(info["allocated_shifts"])
            for day, shift_id in info["work_shifts"]:
                if (employee.id, day, shift_id) in existing:
                    continue
                if (day, shift_id) in allocated:
                    conflicts.append(
                        f"{employee.name} ({format_date(self.env, day)} "
                        f"{shift_names[shift_id]})"
                    )
                vals = {
                    "task_id": self.task_id.id,
                    "employee_id": employee.id,
                    "allocation_date": day,
                    "shift_id": shift_id,
                }
                if self.team_id:
                    vals["team_id"] = self.team_id.id
                vals_list.append(vals)
        return vals_list, conflicts

    def action_full_day(self):
        self.ensure_one()
        self.shift_ids = self._default_shift_ids()
        return self._reopen()

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Allocate Team"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_confirm(self):
        self.ensure_one()
        employees = self.line_ids.filtered("selected").employee_id
        vals_list, conflicts = self._prepare_allocation_vals(employees)
        if conflicts and self.company_id.allocation_block_overlap:
            raise UserError(
                _(
                    "These employees are already allocated to another task in "
                    "the selected shifts:\n%(conflicts)s",
                    conflicts="\n".join(conflicts),
                )
            )
        if not vals_list:
            raise UserError(
                _(
                    "There is no allocation to create: select at least one "
                    "employee who works in the selected days and shifts."
                )
            )
        allocations = self.env["project.task.allocation"].create(vals_list)
        return {
            "type": "ir.actions.act_window",
            "name": _("Allocations"),
            "res_model": "project.task.allocation",
            "view_mode": "list,form",
            "domain": [("id", "in", allocations.ids)],
        }


class ProjectTaskAllocationWizardLine(models.TransientModel):
    _name = "project.task.allocation.wizard.line"
    _description = "Allocate Team Line"
    _order = "sequence, id"

    wizard_id = fields.Many2one(
        comodel_name="project.task.allocation.wizard",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer()
    employee_id = fields.Many2one(comodel_name="hr.employee", required=True)
    selected = fields.Boolean()
    already_allocated = fields.Boolean(
        help="Already allocated to this task in the period: existing "
        "allocations are kept and not duplicated.",
    )
    is_team_member = fields.Boolean(string="Team Member")
    status = fields.Selection(AVAILABILITY_STATUS)
    work_hours = fields.Float()
    free_hours = fields.Float()
    detail = fields.Char()
