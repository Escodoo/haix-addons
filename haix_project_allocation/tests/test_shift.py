# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import MON, SAT, TZ, AllocationCommon, utc


@tagged("post_install", "-at_install")
class TestShift(AllocationCommon):
    def test_groups_exist(self):
        group_user = self.env.ref("haix_project_allocation.group_allocation_user")
        group_manager = self.env.ref("haix_project_allocation.group_allocation_manager")
        self.assertIn(
            self.env.ref("project.group_project_user"), group_user.implied_ids
        )
        self.assertIn(group_user, group_manager.implied_ids)
        self.assertEqual(group_user.category_id, group_manager.category_id)

    def test_seed_shifts(self):
        self.assertEqual(self.shift_morning.source, "calendar")
        self.assertEqual(self.shift_morning.day_period, "morning")
        self.assertEqual(self.shift_afternoon.source, "calendar")
        self.assertEqual(self.shift_afternoon.day_period, "afternoon")
        self.assertTrue(self.shift_morning.in_full_day)
        self.assertTrue(self.shift_afternoon.in_full_day)
        self.assertFalse(self.shift_night.in_full_day)
        self.assertFalse(self.shift_oncall.in_full_day)
        self.assertEqual(self.shift_night.source, "fixed")
        self.assertEqual(
            (self.shift_night.hour_start, self.shift_night.hour_end), (19.0, 23.0)
        )
        self.assertEqual(
            (self.shift_oncall.hour_start, self.shift_oncall.hour_end), (7.0, 19.0)
        )
        self.assertFalse(self.shift_night.crosses_midnight)

    def test_fixed_interval(self):
        # 19:00 local = 22:00 UTC; 23:00 local = 02:00 UTC of the next day
        self.assertEqual(
            self.shift_night._get_fixed_interval(MON, TZ),
            (datetime(2026, 11, 23, 22, 0), datetime(2026, 11, 24, 2, 0)),
        )
        # fixed shifts do not depend on the working schedule
        self.assertEqual(
            self.shift_night._get_fixed_interval(SAT, TZ),
            (utc(SAT, "19:00"), utc(SAT, "23:00")),
        )

    def test_overnight_shift(self):
        overnight = self.env["project.allocation.shift"].create(
            {
                "name": "Overnight",
                "source": "fixed",
                "hour_start": 22.0,
                "hour_end": 6.0,
            }
        )
        self.assertTrue(overnight.crosses_midnight)
        self.assertEqual(
            overnight._get_fixed_interval(MON, TZ),
            (datetime(2026, 11, 24, 1, 0), datetime(2026, 11, 24, 9, 0)),
        )

    def test_invalid_shifts(self):
        Shift = self.env["project.allocation.shift"]
        with self.assertRaises(ValidationError):
            Shift.create({"name": "No period", "source": "calendar"})
        with self.assertRaises(ValidationError):
            Shift.create(
                {
                    "name": "Empty",
                    "source": "fixed",
                    "hour_start": 8.0,
                    "hour_end": 8.0,
                }
            )
        with self.assertRaises(ValidationError):
            Shift.create(
                {
                    "name": "Out of range",
                    "source": "fixed",
                    "hour_start": 8.0,
                    "hour_end": 25.0,
                }
            )
