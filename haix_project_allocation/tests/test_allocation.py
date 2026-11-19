# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import MON, SAT, TUE, WED, AllocationCommon, utc


@tagged("post_install", "-at_install")
class TestAllocation(AllocationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Team = cls.env["project.allocation.team"]
        cls.team_a = Team.create(
            {"name": "Team A", "member_ids": [Command.link(cls.emp_a.id)]}
        )
        cls.team_b = Team.create(
            {"name": "Team B", "member_ids": [Command.link(cls.emp_b.id)]}
        )
        cls.env.company.allocation_block_overlap = True

    # 4.1 - dates, duration, team, drag

    def test_01_dates_and_duration(self):
        allocation = self._alloc(self.emp_a, MON, self.shift_morning)
        self.assertEqual(allocation.date_start, utc(MON, "08:00"))
        self.assertEqual(allocation.date_end, utc(MON, "12:00"))
        self.assertEqual(allocation.duration_hours, 4.0)
        self.assertEqual(allocation.name, "Field A - Assembly")
        allocation.shift_id = self.shift_afternoon
        self.assertEqual(allocation.date_start, utc(MON, "13:00"))
        self.assertEqual(allocation.date_end, utc(MON, "17:00"))

    def test_5a_night_on_saturday(self):
        allocation = self._alloc(self.emp_a, SAT, self.shift_night)
        self.assertEqual(allocation.date_start, utc(SAT, "19:00"))
        self.assertEqual(allocation.date_end, utc(SAT, "23:00"))
        self.assertEqual(allocation.duration_hours, 4.0)

    def test_5a_overnight_dates(self):
        overnight = self.env["project.allocation.shift"].create(
            {
                "name": "Overnight",
                "source": "fixed",
                "hour_start": 22.0,
                "hour_end": 6.0,
            }
        )
        allocation = self._alloc(self.emp_a, MON, overnight)
        self.assertEqual(allocation.allocation_date, MON)
        self.assertEqual(allocation.date_end, datetime(2026, 11, 24, 9, 0))
        self.assertEqual(allocation.duration_hours, 8.0)

    def test_13_team_default(self):
        self.assertEqual(
            self._alloc(self.emp_a, MON, self.shift_morning).team_id, self.team_a
        )
        explicit = self._alloc(
            self.emp_a, TUE, self.shift_morning, team_id=self.team_b.id
        )
        self.assertEqual(explicit.team_id, self.team_b)
        self.assertFalse(self._alloc(self.emp_c, MON, self.shift_morning).team_id)

    def test_15_team_change_keeps_history(self):
        allocation = self._alloc(self.emp_a, MON, self.shift_morning)
        self.team_b.member_ids = [Command.link(self.emp_a.id)]
        self.assertEqual(self.emp_a.allocation_team_id, self.team_b)
        self.assertEqual(allocation.team_id, self.team_a)

    def test_15a_two_teams_same_day(self):
        morning = self._alloc(
            self.emp_b, MON, self.shift_morning, team_id=self.team_a.id
        )
        afternoon = self._alloc(self.emp_b, MON, self.shift_afternoon, task=self.task_2)
        self.assertEqual(morning.team_id, self.team_a)
        self.assertEqual(afternoon.team_id, self.team_b)
        self.assertFalse(morning.has_conflict or afternoon.has_conflict)

    def test_drag_to_other_day(self):
        allocation = self._alloc(self.emp_a, MON, self.shift_afternoon)
        allocation.write(
            {"date_start": utc(WED, "09:30"), "date_end": utc(WED, "11:00")}
        )
        self.assertEqual(allocation.allocation_date, WED)
        self.assertEqual(allocation.shift_id, self.shift_afternoon)
        self.assertEqual(allocation.date_start, utc(WED, "13:00"))
        self.assertEqual(allocation.date_end, utc(WED, "17:00"))

    def test_drag_same_day_realigns(self):
        allocation = self._alloc(self.emp_a, MON, self.shift_afternoon)
        allocation.write({"date_end": utc(MON, "18:30")})
        self.assertEqual(allocation.date_end, utc(MON, "17:00"))
        allocation.write({"date_start": utc(MON, "14:30")})
        self.assertEqual(allocation.date_start, utc(MON, "13:00"))

    def test_drag_uses_schedule_timezone(self):
        # 01:00 UTC on Tuesday is still Monday 22:00 in Sao Paulo
        allocation = self._alloc(self.emp_a, TUE, self.shift_morning)
        allocation.with_context(tz="Asia/Tokyo").write(
            {"date_start": datetime(2026, 11, 24, 1, 0)}
        )
        self.assertEqual(allocation.allocation_date, MON)

    def test_calendar_change_does_not_move(self):
        allocation = self._alloc(self.emp_a, MON, self.shift_morning)
        other_calendar = self.calendar.copy({"name": "Other", "tz": "UTC"})
        self.emp_a.resource_calendar_id = other_calendar
        self.assertEqual(allocation.date_start, utc(MON, "08:00"))
        self.assertEqual(allocation.date_end, utc(MON, "12:00"))

    # 4.2 - shift and conflict rules

    def test_02_saturday_calendar_shift_fails(self):
        with self.assertRaisesRegex(ValidationError, "Field A"):
            self._alloc(self.emp_a, SAT, self.shift_morning)

    def test_03_overlap_block(self):
        self._alloc(self.emp_a, MON, self.shift_morning)
        with self.assertRaisesRegex(ValidationError, "Field A"):
            self._alloc(self.emp_a, MON, self.shift_morning, task=self.task_2)

    def test_03_overlap_warn_only(self):
        self.env.company.allocation_block_overlap = False
        first = self._alloc(self.emp_a, MON, self.shift_morning)
        second = self._alloc(self.emp_a, MON, self.shift_morning, task=self.task_2)
        self.assertTrue(first.has_conflict)
        self.assertTrue(second.has_conflict)
        self.assertEqual(first.conflict_allocation_ids, second)
        second.action_archive()
        self.assertFalse(first.has_conflict)
        second.action_unarchive()
        self.assertTrue(first.has_conflict)
        second.shift_id = self.shift_afternoon
        self.assertFalse(first.has_conflict)
        self.assertFalse(second.has_conflict)

    def test_conflict_cleared_on_unlink(self):
        self.env.company.allocation_block_overlap = False
        first = self._alloc(self.emp_a, MON, self.shift_morning)
        second = self._alloc(self.emp_a, MON, self.shift_morning, task=self.task_2)
        second.unlink()
        self.assertFalse(first.has_conflict)

    def test_04_morning_and_afternoon(self):
        morning = self._alloc(self.emp_a, MON, self.shift_morning)
        afternoon = self._alloc(self.emp_a, MON, self.shift_afternoon, task=self.task_2)
        self.assertFalse(morning.has_conflict or afternoon.has_conflict)

    def test_oncall_conflicts_with_afternoon(self):
        self._alloc(self.emp_a, MON, self.shift_afternoon)
        with self.assertRaises(ValidationError):
            self._alloc(self.emp_a, MON, self.shift_oncall, task=self.task_2)

    def test_archived_not_conflict(self):
        old = self._alloc(self.emp_a, MON, self.shift_morning)
        old.action_archive()
        new = self._alloc(self.emp_a, MON, self.shift_morning, task=self.task_2)
        self.assertFalse(new.has_conflict)

    def test_batch_create_conflict(self):
        vals = {
            "employee_id": self.emp_a.id,
            "allocation_date": MON,
            "shift_id": self.shift_morning.id,
        }
        with self.assertRaises(ValidationError):
            self.env["project.task.allocation"].create(
                [
                    dict(vals, task_id=self.task_1.id),
                    dict(vals, task_id=self.task_2.id),
                ]
            )

    # 4.3 - absences and warning

    def test_absence_intervals(self):
        leave_type = self.env["hr.leave.type"].create(
            {"name": "Test leave", "requires_allocation": "no"}
        )
        self.env["resource.calendar.leaves"].create(
            {
                "name": "Approved",
                "resource_id": self.emp_a.resource_id.id,
                "calendar_id": self.calendar.id,
                "date_from": utc(MON, "00:00"),
                "date_to": utc(MON, "23:59"),
            }
        )
        self.env["resource.calendar.leaves"].create(
            {
                "name": "Holiday",
                "calendar_id": self.calendar.id,
                "date_from": utc(WED, "00:00"),
                "date_to": utc(WED, "23:59"),
            }
        )
        pending = self.env["hr.leave"].create(
            {
                "name": "Pending",
                "employee_id": self.emp_a.id,
                "holiday_status_id": leave_type.id,
                "request_date_from": TUE,
                "request_date_to": TUE,
            }
        )
        self.assertIn(pending.state, ("confirm", "validate1"))
        employees = self.emp_a | self.emp_b
        absences = employees._get_absence_intervals(
            utc(MON, "00:00"), utc(WED, "23:59")
        )
        labels_a = sorted(label for _start, _end, label in absences[self.emp_a.id])
        labels_b = sorted(label for _start, _end, label in absences[self.emp_b.id])
        self.assertEqual(labels_a, ["leave", "pending_leave", "public_holiday"])
        self.assertEqual(labels_b, ["public_holiday"])

    def test_warning_on_leave(self):
        self.env["resource.calendar.leaves"].create(
            {
                "name": "Approved",
                "resource_id": self.emp_a.resource_id.id,
                "calendar_id": self.calendar.id,
                "date_from": utc(MON, "00:00"),
                "date_to": utc(MON, "23:59"),
            }
        )
        on_leave = self._alloc(self.emp_a, MON, self.shift_morning)
        self.assertTrue(on_leave.warning_message)
        self.assertIn("Field A", on_leave.warning_message)
        self.assertFalse(
            self._alloc(self.emp_a, TUE, self.shift_morning).warning_message
        )
