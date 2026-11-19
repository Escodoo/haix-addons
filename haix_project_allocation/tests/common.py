# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date, datetime, time, timedelta

import pytz

from odoo import Command
from odoo.tests.common import TransactionCase

TZ = "America/Sao_Paulo"
MON = date(2026, 11, 23)
TUE = MON + timedelta(days=1)
WED = MON + timedelta(days=2)
FRI = date(2026, 11, 27)
SAT = date(2026, 11, 28)


def utc(day, hhmm, tz_name=TZ):
    """Return the naive UTC datetime of local time ``hhmm`` on ``day``."""
    hour, minute = (int(part) for part in hhmm.split(":"))
    local = pytz.timezone(tz_name).localize(datetime.combine(day, time(hour, minute)))
    return local.astimezone(pytz.utc).replace(tzinfo=None)


class AllocationCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Messages are compared in English, whatever the admin's language
        cls.env = cls.env(
            context=dict(cls.env.context, tracking_disable=True, lang="en_US")
        )
        attendances = []
        for dayofweek in ("0", "1", "2", "3", "4"):
            attendances += [
                Command.create(
                    {
                        "name": f"Morning {dayofweek}",
                        "dayofweek": dayofweek,
                        "hour_from": 8.0,
                        "hour_to": 12.0,
                        "day_period": "morning",
                    }
                ),
                Command.create(
                    {
                        "name": f"Afternoon {dayofweek}",
                        "dayofweek": dayofweek,
                        "hour_from": 13.0,
                        "hour_to": 17.0,
                        "day_period": "afternoon",
                    }
                ),
            ]
        cls.calendar = cls.env["resource.calendar"].create(
            {
                "name": "Field 08-12 13-17",
                "tz": TZ,
                "attendance_ids": attendances,
            }
        )
        Employee = cls.env["hr.employee"]
        field_vals = {
            "resource_calendar_id": cls.calendar.id,
            "allocation_eligible": True,
        }
        cls.emp_a = Employee.create(dict(field_vals, name="Field A"))
        cls.emp_b = Employee.create(dict(field_vals, name="Field B"))
        cls.emp_c = Employee.create(dict(field_vals, name="Field C"))
        cls.emp_office = Employee.create(
            {"name": "Office", "resource_calendar_id": cls.calendar.id}
        )
        cls.project = cls.env["project.project"].create({"name": "Site 1"})
        cls.task_1 = cls.env["project.task"].create(
            {"name": "Assembly", "project_id": cls.project.id}
        )
        cls.task_2 = cls.env["project.task"].create(
            {"name": "Disassembly", "project_id": cls.project.id}
        )
        cls.shift_morning = cls.env.ref("haix_project_allocation.shift_morning")
        cls.shift_afternoon = cls.env.ref("haix_project_allocation.shift_afternoon")
        cls.shift_night = cls.env.ref("haix_project_allocation.shift_night")
        cls.shift_oncall = cls.env.ref("haix_project_allocation.shift_oncall")

    @classmethod
    def _alloc(cls, employee, day, shift, task=None, **vals):
        """Create an allocation of ``employee`` on ``task`` (task_1 by default)."""
        return cls.env["project.task.allocation"].create(
            dict(
                {
                    "employee_id": employee.id,
                    "task_id": (task or cls.task_1).id,
                    "allocation_date": day,
                    "shift_id": shift.id,
                },
                **vals,
            )
        )
