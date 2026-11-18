# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProjectAllocationShift(models.Model):
    _name = "project.allocation.shift"
    _description = "Allocation Shift"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    source = fields.Selection(
        [
            ("calendar", "Working Schedule"),
            ("fixed", "Fixed Hours"),
        ],
        required=True,
        default="calendar",
        help="Working Schedule: hours come from the employee's working "
        "schedule for the selected day period.\n"
        "Fixed Hours: hours are set on the shift and do not depend on the "
        "working schedule.",
    )
    day_period = fields.Selection(
        [
            ("morning", "Morning"),
            ("afternoon", "Afternoon"),
        ],
        help="Day period of the working schedule used by this shift.",
    )
    hour_start = fields.Float(string="Start Hour")
    hour_end = fields.Float(
        string="End Hour",
        help="When the end hour is lower than or equal to the start hour, "
        "the shift ends on the next day.",
    )
    crosses_midnight = fields.Boolean(compute="_compute_crosses_midnight")
    in_full_day = fields.Boolean(
        string="Part of Full Day",
        help="Selected by the 'Full Day' shortcut when allocating.",
    )
    color = fields.Integer()
    active = fields.Boolean(default=True)

    @api.depends("source", "hour_start", "hour_end")
    def _compute_crosses_midnight(self):
        for shift in self:
            shift.crosses_midnight = (
                shift.source == "fixed" and shift.hour_end <= shift.hour_start
            )

    @api.constrains("source", "day_period", "hour_start", "hour_end")
    def _check_source_fields(self):
        for shift in self:
            if shift.source == "calendar" and not shift.day_period:
                raise ValidationError(
                    _("Shift %(shift)s needs a day period.", shift=shift.name)
                )
            if shift.source != "fixed":
                continue
            if not (0 <= shift.hour_start < 24 and 0 <= shift.hour_end <= 24):
                raise ValidationError(
                    _(
                        "Shift %(shift)s hours must be between 00:00 and 24:00.",
                        shift=shift.name,
                    )
                )
            if shift.hour_start == shift.hour_end:
                raise ValidationError(
                    _(
                        "Shift %(shift)s start and end hours must be different.",
                        shift=shift.name,
                    )
                )

    def _get_fixed_interval(self, day, tz_name):
        """Return the (start, end) naive UTC datetimes of this fixed shift.

        :param day: date the shift starts on
        :param tz_name: timezone the shift hours are expressed in
        """
        self.ensure_one()
        tz = pytz.timezone(tz_name or "UTC")
        midnight = datetime.combine(day, time())
        start = tz.localize(midnight + timedelta(hours=self.hour_start))
        end_midnight = midnight + timedelta(days=1 if self.crosses_midnight else 0)
        end = tz.localize(end_midnight + timedelta(hours=self.hour_end))
        return (
            start.astimezone(pytz.utc).replace(tzinfo=None),
            end.astimezone(pytz.utc).replace(tzinfo=None),
        )
