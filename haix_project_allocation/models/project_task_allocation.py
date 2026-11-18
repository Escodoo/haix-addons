# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_date, format_datetime

# Dates are computed from the day and the shift. When they are written (by
# the timeline view), they are translated into a new day instead.
DATE_FIELDS = {"date_start", "date_end"}
# Fields that can change which allocations overlap
CONFLICT_FIELDS = {"employee_id", "allocation_date", "shift_id", "active"}


class ProjectTaskAllocation(models.Model):
    _name = "project.task.allocation"
    _description = "Task Allocation"
    _inherit = ["mail.thread"]
    _order = "allocation_date, date_start, employee_id"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        required=True,
        index=True,
        tracking=True,
        check_company=True,
        domain="[('allocation_eligible', '=', True), "
        "('company_id', 'in', allowed_company_ids)]",
    )
    task_id = fields.Many2one(
        comodel_name="project.task",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
        check_company=True,
    )
    project_id = fields.Many2one(related="task_id.project_id", store=True, index=True)
    partner_id = fields.Many2one(related="task_id.partner_id", store=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        compute="_compute_company_id",
        store=True,
        index=True,
        help="Company of the task or, for tasks shared between companies, "
        "of the employee.",
    )
    allocation_date = fields.Date(
        string="Day",
        required=True,
        index=True,
        tracking=True,
        default=fields.Date.context_today,
    )
    shift_id = fields.Many2one(
        comodel_name="project.allocation.shift",
        string="Shift",
        required=True,
        index=True,
        tracking=True,
        ondelete="restrict",
    )
    date_start = fields.Datetime(
        string="Start",
        compute="_compute_dates",
        store=True,
        index=True,
    )
    date_end = fields.Datetime(string="End", compute="_compute_dates", store=True)
    duration_hours = fields.Float(
        string="Hours",
        compute="_compute_duration_hours",
        store=True,
    )
    team_id = fields.Many2one(
        comodel_name="project.allocation.team",
        string="Team",
        index=True,
        tracking=True,
        check_company=True,
        help="Team the employee was allocated by. Defaults to the employee's "
        "team and does not change when the employee changes team.",
    )
    note = fields.Text()
    has_conflict = fields.Boolean(readonly=True, copy=False)
    conflict_allocation_ids = fields.Many2many(
        comodel_name="project.task.allocation",
        relation="project_task_allocation_conflict_rel",
        column1="allocation_id",
        column2="conflict_id",
        string="Conflicting Allocations",
        compute="_compute_conflict_allocation_ids",
    )
    warning_message = fields.Char(compute="_compute_warning_message")
    color = fields.Integer()
    active = fields.Boolean(default=True)

    @api.depends("employee_id.name", "task_id.name")
    def _compute_name(self):
        for allocation in self:
            allocation.name = (
                f"{allocation.employee_id.name} - {allocation.task_id.name}"
                if allocation.employee_id and allocation.task_id
                else False
            )

    @api.depends("task_id.company_id", "employee_id.company_id")
    def _compute_company_id(self):
        for allocation in self:
            allocation.company_id = (
                allocation.task_id.company_id or allocation.employee_id.company_id
            )

    # The working schedule is deliberately not a dependency: changing it must
    # not move allocations already scheduled.
    @api.depends("employee_id", "allocation_date", "shift_id")
    def _compute_dates(self):
        for allocation in self:
            interval = None
            if (
                allocation.employee_id
                and allocation.allocation_date
                and allocation.shift_id
            ):
                interval = allocation.employee_id._get_shift_interval(
                    allocation.allocation_date, allocation.shift_id
                )
            allocation.date_start, allocation.date_end = interval or (False, False)

    @api.depends("date_start", "date_end", "shift_id")
    def _compute_duration_hours(self):
        for allocation in self:
            if not (allocation.date_start and allocation.date_end):
                allocation.duration_hours = 0.0
            elif allocation.shift_id.source == "calendar":
                calendar = allocation.employee_id._get_allocation_calendar()
                allocation.duration_hours = calendar.get_work_hours_count(
                    allocation.date_start, allocation.date_end, compute_leaves=False
                )
            else:
                delta = allocation.date_end - allocation.date_start
                allocation.duration_hours = delta.total_seconds() / 3600

    @api.depends("employee_id", "date_start", "date_end", "active")
    def _compute_conflict_allocation_ids(self):
        overlaps = self._get_overlapping()
        for allocation in self:
            allocation.conflict_allocation_ids = overlaps[allocation.id]

    @api.depends("employee_id", "date_start", "date_end")
    def _compute_warning_message(self):
        allocations = self.filtered(
            lambda a: a.employee_id and a.date_start and a.date_end
        )
        (self - allocations).warning_message = False
        if not allocations:
            return
        absences = allocations.employee_id._get_absence_intervals(
            min(allocations.mapped("date_start")),
            max(allocations.mapped("date_end")),
        )
        labels = {
            "leave": _("time off"),
            "pending_leave": _("time off pending approval"),
            "public_holiday": _("a public holiday"),
        }
        for allocation in allocations:
            kinds = []
            for start, end, label in absences.get(allocation.employee_id.id, []):
                overlaps = start < allocation.date_end and allocation.date_start < end
                if overlaps and labels[label] not in kinds:
                    kinds.append(labels[label])
            allocation.warning_message = (
                _(
                    "%(employee)s has %(absences)s during this allocation.",
                    employee=allocation.employee_id.name,
                    absences=", ".join(kinds),
                )
                if kinds
                else False
            )

    @api.constrains("employee_id", "allocation_date", "shift_id")
    def _check_shift(self):
        for allocation in self:
            if not allocation.date_start:
                raise ValidationError(
                    _(
                        "%(employee)s does not work in the %(shift)s shift on "
                        "%(date)s.",
                        employee=allocation.employee_id.name,
                        shift=allocation.shift_id.name,
                        date=format_date(self.env, allocation.allocation_date),
                    )
                )

    @api.constrains("employee_id", "allocation_date", "shift_id", "active")
    def _check_overlap(self):
        to_check = self.filtered(
            lambda a: (a.company_id or self.env.company).allocation_block_overlap
        )
        overlaps = to_check._get_overlapping()
        for allocation in to_check:
            others = overlaps[allocation.id]
            if not others:
                continue
            other = others[0]
            tz = allocation.employee_id._get_allocation_tz()
            raise ValidationError(
                _(
                    "%(employee)s is already allocated to %(task)s from "
                    "%(start)s to %(end)s.",
                    employee=allocation.employee_id.name,
                    task=other.task_id.display_name,
                    start=format_datetime(self.env, other.date_start, tz=tz),
                    end=format_datetime(self.env, other.date_end, tz=tz),
                )
            )

    def _get_overlapping(self):
        """Return {allocation id: active allocations of the same employee
        whose period overlaps}, using a single search for the recordset."""
        result = {allocation.id: self.browse() for allocation in self}
        allocations = self.filtered(
            lambda a: a.active and a.employee_id and a.date_start and a.date_end
        )
        if not allocations:
            return result
        candidates = self.search(
            [
                ("employee_id", "in", allocations.employee_id.ids),
                ("date_start", "<", max(allocations.mapped("date_end"))),
                ("date_end", ">", min(allocations.mapped("date_start"))),
            ]
        )
        by_employee = defaultdict(list)
        for candidate in candidates:
            by_employee[candidate.employee_id.id].append(candidate)
        for allocation in allocations:
            result[allocation.id] = self.browse(
                [
                    other.id
                    for other in by_employee[allocation.employee_id.id]
                    if other.id != allocation.id
                    and other.date_start < allocation.date_end
                    and allocation.date_start < other.date_end
                ]
            )
        return result

    def _get_overlapping_union(self):
        overlapping = self.browse()
        for others in self._get_overlapping().values():
            overlapping |= others
        return overlapping

    def _refresh_conflicts(self):
        """Update the conflict flag of these allocations and their neighbours."""
        affected = self | self._get_overlapping_union()
        overlaps = affected._get_overlapping()
        for allocation in affected:
            has_conflict = bool(overlaps[allocation.id])
            if allocation.has_conflict != has_conflict:
                # Not a CONFLICT_FIELDS write: does not trigger a new refresh
                allocation.write({"has_conflict": has_conflict})

    @api.model
    def _get_local_day(self, employee, value):
        """Day of ``value`` (naive UTC) in the employee schedule timezone."""
        tz = pytz.timezone(employee._get_allocation_tz())
        moment = pytz.utc.localize(fields.Datetime.to_datetime(value))
        return moment.astimezone(tz).date()

    @api.model_create_multi
    def create(self, vals_list):
        Employee = self.env["hr.employee"]
        for vals in vals_list:
            date_start = vals.pop("date_start", None)
            vals.pop("date_end", None)
            employee = Employee.browse(vals.get("employee_id"))
            if date_start and employee and not vals.get("allocation_date"):
                vals["allocation_date"] = self._get_local_day(employee, date_start)
            if employee and not vals.get("team_id"):
                vals["team_id"] = employee.allocation_team_id.id
        allocations = super().create(vals_list)
        allocations._refresh_conflicts()
        return allocations

    def write(self, vals):
        if DATE_FIELDS & set(vals):
            vals = dict(vals)
            date_start = vals.pop("date_start", None)
            vals.pop("date_end", None)
            if date_start:
                # Timeline drag: keep the shift, move to the day of the new start
                for allocation in self:
                    employee = (
                        self.env["hr.employee"].browse(vals["employee_id"])
                        if vals.get("employee_id")
                        else allocation.employee_id
                    )
                    day = self._get_local_day(employee, date_start)
                    allocation.write(dict(vals, allocation_date=day))
                return True
            if not vals:
                # Timeline resize: the shift sets the end, nothing to change
                return True
        if not CONFLICT_FIELDS & set(vals):
            return super().write(vals)
        before = self._get_overlapping_union()
        result = super().write(vals)
        (self | before).exists()._refresh_conflicts()
        return result

    def unlink(self):
        neighbours = self._get_overlapping_union() - self
        result = super().unlink()
        neighbours.exists()._refresh_conflicts()
        return result
