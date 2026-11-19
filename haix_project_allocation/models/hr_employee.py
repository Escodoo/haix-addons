# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.tools.misc import format_date

# Absence labels, by precedence when several kinds touch the same shift
ABSENCE_PRECEDENCE = ("public_holiday", "leave", "pending_leave")


def _to_naive_utc(value):
    return value.astimezone(pytz.utc).replace(tzinfo=None)


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
    allocation_ids = fields.One2many(
        comodel_name="project.task.allocation",
        inverse_name="employee_id",
        string="Allocations",
    )

    def action_view_allocations(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "haix_project_allocation.action_project_task_allocation"
        )
        action["domain"] = [("employee_id", "=", self.id)]
        action["context"] = {"default_employee_id": self.id}
        return action

    def _get_allocation_calendar(self):
        """Working schedule used for allocations: the employee's, or the
        company's when the employee has none."""
        self.ensure_one()
        return self.resource_calendar_id or self.company_id.resource_calendar_id

    def _get_allocation_tz(self):
        """Timezone shift hours are expressed in. Never the user's timezone:
        the same shift must give the same hours whoever schedules it."""
        self.ensure_one()
        return self._get_allocation_calendar().tz or self.tz or "UTC"

    def _get_shift_interval(self, day, shift):
        """Return the (start, end) naive UTC datetimes of ``shift`` on ``day``.

        Fixed shifts use their own hours. Working schedule shifts span from
        the first start to the last end of the schedule attendances of that
        day period, or return None when the employee does not work then.
        """
        self.ensure_one()
        tz_name = self._get_allocation_tz()
        if shift.source == "fixed":
            return shift._get_fixed_interval(day, tz_name)
        calendar = self._get_allocation_calendar()
        if not calendar:
            return None
        interval = self._get_calendar_shift_intervals(calendar, day, day, tz_name).get(
            (day, shift.day_period)
        )
        return interval[:2] if interval else None

    @api.model
    def _get_calendar_shift_intervals(self, calendar, date_from, date_to, tz_name):
        """Return {(day, day period): (start, end, hours)} of a working
        schedule between two days, with naive UTC datetimes, in one query.

        A day period spans from its first attendance start to its last
        attendance end; ``hours`` is the sum of its attendances.
        """
        tz = pytz.timezone(tz_name)
        period_start = tz.localize(datetime.combine(date_from, time.min))
        period_end = tz.localize(datetime.combine(date_to, time.max))
        # No ``resources``: a resource without its own schedule would be
        # treated as fully flexible, while we want the fallback calendar.
        intervals = calendar._attendance_intervals_batch(
            period_start, period_end, tz=tz
        )[False]
        result = {}
        for interval_start, _interval_end, attendances in intervals:
            # Touching attendances (e.g. 08-12 and 12-16) come merged into one
            # interval: rebuild each attendance to keep day periods apart.
            day = interval_start.date()
            midnight = datetime.combine(day, time.min)
            for attendance in attendances:
                if attendance.day_period not in ("morning", "afternoon"):
                    continue
                start = tz.localize(midnight + timedelta(hours=attendance.hour_from))
                end = tz.localize(midnight + timedelta(hours=attendance.hour_to))
                hours = (end - start).total_seconds() / 3600
                start, end = _to_naive_utc(start), _to_naive_utc(end)
                key = (day, attendance.day_period)
                if key in result:
                    known_start, known_end, known_hours = result[key]
                    start, end = min(start, known_start), max(end, known_end)
                    hours += known_hours
                result[key] = (start, end, hours)
        return result

    def _get_allocation_availability(self, date_from, date_to, shifts):
        """Return the availability of the field team employees in ``self``
        for each day between ``date_from`` and ``date_to`` and each shift.

        Returns {employee id: {
            work_shifts, allocated_shifts, absent_shifts, free_shifts:
                lists of (day, shift id), in day and shift order,
            work_hours, free_hours: floats,
            status: available | partial | allocated | absent,
            detail: short readable text,
            allocation_ids: allocations touching the requested shifts,
        }}
        """
        employees = self.filtered("allocation_eligible")
        shifts = shifts.sorted()
        days = [
            date_from + timedelta(days=offset)
            for offset in range((date_to - date_from).days + 1)
        ]

        # 1. Shift intervals of each employee: one schedule query per
        # (calendar, timezone), fixed shifts need no query.
        calendar_intervals = {}
        work_items = {}
        for employee in employees:
            calendar = employee._get_allocation_calendar()
            tz_name = employee._get_allocation_tz()
            key = (calendar.id, tz_name)
            if calendar and key not in calendar_intervals:
                calendar_intervals[key] = self._get_calendar_shift_intervals(
                    calendar, date_from, date_to, tz_name
                )
            items = []
            for day in days:
                for shift in shifts:
                    if shift.source == "fixed":
                        start, end = shift._get_fixed_interval(day, tz_name)
                        hours = (end - start).total_seconds() / 3600
                    else:
                        interval = calendar_intervals.get(key, {}).get(
                            (day, shift.day_period)
                        )
                        if not interval:
                            continue
                        start, end, hours = interval
                    items.append((day, shift, start, end, hours))
            work_items[employee.id] = items

        # 2. Absences and allocations: one batch each, over the real span of
        # the shifts (an overnight shift may end on the next day).
        all_items = [item for items in work_items.values() for item in items]
        absences, allocations_per_employee = {}, defaultdict(list)
        if all_items:
            span_start = min(item[2] for item in all_items)
            span_end = max(item[3] for item in all_items)
            absences = employees._get_absence_intervals(span_start, span_end)
            allocations = self.env["project.task.allocation"].search(
                [
                    ("employee_id", "in", employees.ids),
                    ("date_start", "<", span_end),
                    ("date_end", ">", span_start),
                ]
            )
            for allocation in allocations:
                allocations_per_employee[allocation.employee_id.id].append(allocation)

        # 3. Classify each shift: absent, then allocated, then free.
        absence_names = {
            "public_holiday": _("Public holiday"),
            "leave": _("Time off"),
            "pending_leave": _("Pending time off"),
        }
        several_days = len(days) > 1
        result = {}
        for employee in employees:
            info = {
                "work_shifts": [],
                "allocated_shifts": [],
                "absent_shifts": [],
                "free_shifts": [],
                "work_hours": 0.0,
                "free_hours": 0.0,
                "allocation_ids": self.env["project.task.allocation"],
            }
            parts, absence_kinds = [], set()
            for day, shift, start, end, hours in work_items[employee.id]:
                key = (day, shift.id)
                info["work_shifts"].append(key)
                info["work_hours"] += hours
                kinds = {
                    label
                    for absence_start, absence_end, label in absences.get(
                        employee.id, []
                    )
                    if absence_start < end and start < absence_end
                }
                busy = [
                    allocation
                    for allocation in allocations_per_employee[employee.id]
                    if allocation.date_start < end and start < allocation.date_end
                ]
                if kinds:
                    kind = next(k for k in ABSENCE_PRECEDENCE if k in kinds)
                    absence_kinds.add(kind)
                    info["absent_shifts"].append(key)
                    what = absence_names[kind]
                elif busy:
                    info["allocated_shifts"].append(key)
                    for allocation in busy:
                        info["allocation_ids"] |= allocation
                    what = ", ".join(sorted({a.task_id.name for a in busy}))
                else:
                    info["free_shifts"].append(key)
                    info["free_hours"] += hours
                    what = _("free")
                prefix = (
                    format_date(self.env, day, date_format="EEE dd/MM") + " "
                    if several_days
                    else ""
                )
                parts.append(f"{prefix}{shift.name}: {what}")
            info["status"], info["detail"] = self._get_availability_status(
                info, parts, absence_kinds, absence_names
            )
            result[employee.id] = info
        return result

    @api.model
    def _get_availability_status(self, info, parts, absence_kinds, absence_names):
        """Return (status, detail) from the classified shifts."""
        if not info["work_shifts"]:
            return "absent", _("Outside working hours")
        if not info["free_shifts"] and not info["allocated_shifts"]:
            if len(absence_kinds) == 1:
                return "absent", absence_names[absence_kinds.pop()]
            return "absent", "; ".join(parts)
        if not info["free_shifts"]:
            return "allocated", "; ".join(parts)
        if info["allocated_shifts"] or info["absent_shifts"]:
            return "partial", "; ".join(parts)
        return "available", "; ".join(parts)

    def _get_absence_intervals(self, start, end):
        """Return {employee id: [(start, end, label)]} of the absences that
        touch the period, as naive UTC datetimes.

        Labels: ``leave`` (approved time off), ``pending_leave`` (time off
        waiting for approval) and ``public_holiday``.
        """
        result = {employee.id: [] for employee in self}
        if not self:
            return result
        period_start = pytz.utc.localize(start)
        period_end = pytz.utc.localize(end)
        employees_per_calendar = defaultdict(lambda: self.browse())
        for employee in self:
            calendar = employee._get_allocation_calendar()
            if calendar:
                employees_per_calendar[calendar] |= employee
        for calendar, employees in employees_per_calendar.items():
            # sudo: allocation users may not read time off records; only the
            # period and the kind of absence are used
            leaves = calendar.sudo()._leave_intervals_batch(
                period_start, period_end, resources=employees.resource_id
            )
            for employee in employees:
                seen = set()
                for leave_start, leave_end, records in leaves[employee.resource_id.id]:
                    for record in records:
                        label = "leave" if record.resource_id else "public_holiday"
                        item = (
                            leave_start.astimezone(pytz.utc).replace(tzinfo=None),
                            leave_end.astimezone(pytz.utc).replace(tzinfo=None),
                            label,
                        )
                        if item not in seen:
                            seen.add(item)
                            result[employee.id].append(item)
        # sudo: same reason as above
        pending_leaves = (
            self.env["hr.leave"]
            .sudo()
            .search(
                [
                    ("employee_id", "in", self.ids),
                    ("state", "in", ("confirm", "validate1")),
                    ("date_from", "<", end),
                    ("date_to", ">", start),
                ]
            )
        )
        for leave in pending_leaves:
            result[leave.employee_id.id].append(
                (leave.date_from, leave.date_to, "pending_leave")
            )
        return result


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    # Exposed to users without HR rights (e.g. allocation readers)
    allocation_eligible = fields.Boolean(string="Field Team", readonly=True)
    allocation_team_id = fields.Many2one(
        comodel_name="project.allocation.team",
        string="Allocation Team",
        readonly=True,
    )
