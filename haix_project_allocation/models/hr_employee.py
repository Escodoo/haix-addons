# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime, time

import pytz

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
        tz = pytz.timezone(tz_name)
        day_start = tz.localize(datetime.combine(day, time.min))
        day_end = tz.localize(datetime.combine(day, time.max))
        # No ``resources``: a resource without its own schedule would be
        # treated as fully flexible, while we want the fallback calendar.
        intervals = calendar._attendance_intervals_batch(
            day_start,
            day_end,
            domain=[("day_period", "=", shift.day_period)],
            tz=tz,
        )[False]
        if not intervals:
            return None
        start = min(interval[0] for interval in intervals)
        end = max(interval[1] for interval in intervals)
        return (
            start.astimezone(pytz.utc).replace(tzinfo=None),
            end.astimezone(pytz.utc).replace(tzinfo=None),
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
