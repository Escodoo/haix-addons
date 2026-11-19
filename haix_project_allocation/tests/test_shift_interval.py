# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import tagged

from .common import MON, SAT, TZ, AllocationCommon, utc


@tagged("post_install", "-at_install")
class TestShiftInterval(AllocationCommon):
    def test_calendar_shifts(self):
        self.assertEqual(
            self.emp_a._get_shift_interval(MON, self.shift_morning),
            (utc(MON, "08:00"), utc(MON, "12:00")),
        )
        self.assertEqual(
            self.emp_a._get_shift_interval(MON, self.shift_afternoon),
            (utc(MON, "13:00"), utc(MON, "17:00")),
        )

    def test_calendar_shift_without_work(self):
        self.assertIsNone(self.emp_a._get_shift_interval(SAT, self.shift_morning))

    def test_fixed_shift_ignores_calendar(self):
        self.assertEqual(
            self.emp_a._get_shift_interval(SAT, self.shift_night),
            (utc(SAT, "19:00"), utc(SAT, "23:00")),
        )

    def test_user_tz_does_not_matter(self):
        employee = self.emp_a.with_context(tz="Asia/Tokyo")
        self.assertEqual(employee._get_allocation_tz(), TZ)
        self.assertEqual(
            employee._get_shift_interval(MON, self.shift_morning),
            (utc(MON, "08:00"), utc(MON, "12:00")),
        )

    def test_company_calendar_fallback(self):
        self.env.company.resource_calendar_id = self.calendar
        employee = self.env["hr.employee"].create(
            {"name": "No schedule", "allocation_eligible": True}
        )
        employee.resource_calendar_id = False
        self.assertEqual(employee._get_allocation_calendar(), self.calendar)
        self.assertEqual(
            employee._get_shift_interval(MON, self.shift_afternoon),
            (utc(MON, "13:00"), utc(MON, "17:00")),
        )

    def test_split_morning(self):
        calendar = self.env["resource.calendar"].create(
            {
                "name": "Split morning",
                "tz": TZ,
                "attendance_ids": [
                    Command.create(
                        {
                            "name": "Early",
                            "dayofweek": "0",
                            "hour_from": 8.0,
                            "hour_to": 10.0,
                            "day_period": "morning",
                        }
                    ),
                    Command.create(
                        {
                            "name": "Late",
                            "dayofweek": "0",
                            "hour_from": 10.25,
                            "hour_to": 12.0,
                            "day_period": "morning",
                        }
                    ),
                ],
            }
        )
        self.emp_b.resource_calendar_id = calendar
        self.assertEqual(
            self.emp_b._get_shift_interval(MON, self.shift_morning),
            (utc(MON, "08:00"), utc(MON, "12:00")),
        )
