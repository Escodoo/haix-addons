# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import Command
from odoo.tests import tagged

from .common import MON, SAT, TUE, WED, AllocationCommon, utc

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestAvailability(AllocationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.full_day = cls.shift_morning | cls.shift_afternoon

    def _avail(self, employee, date_from, date_to, shifts):
        return employee._get_allocation_availability(date_from, date_to, shifts)[
            employee.id
        ]

    def _approved_leave(self, employee, start, end):
        return self.env["resource.calendar.leaves"].create(
            {
                "name": "Approved",
                "resource_id": employee.resource_id.id if employee else False,
                "calendar_id": self.calendar.id,
                "date_from": start,
                "date_to": end,
            }
        )

    def test_05_statuses(self):
        result = self._avail(self.emp_a, MON, MON, self.full_day)
        self.assertEqual(result["status"], "available")
        self.assertEqual(
            result["free_shifts"],
            [(MON, self.shift_morning.id), (MON, self.shift_afternoon.id)],
        )
        self.assertEqual(result["work_hours"], 8.0)
        self.assertEqual(result["free_hours"], 8.0)

        morning = self._alloc(self.emp_a, MON, self.shift_morning)
        result = self._avail(self.emp_a, MON, MON, self.full_day)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["allocated_shifts"], [(MON, self.shift_morning.id)])
        self.assertEqual(result["free_shifts"], [(MON, self.shift_afternoon.id)])
        self.assertEqual(result["free_hours"], 4.0)
        self.assertEqual(result["allocation_ids"], morning)
        self.assertIn("Assembly", result["detail"])
        self.assertEqual(
            self._avail(self.emp_a, MON, MON, self.shift_afternoon)["status"],
            "available",
        )

        self._alloc(self.emp_a, MON, self.shift_afternoon, task=self.task_2)
        self.assertEqual(
            self._avail(self.emp_a, MON, MON, self.full_day)["status"], "allocated"
        )

    def test_05_approved_leave(self):
        self._approved_leave(self.emp_a, utc(MON, "00:00"), utc(MON, "23:59"))
        result = self._avail(self.emp_a, MON, MON, self.full_day)
        self.assertEqual(result["status"], "absent")
        self.assertEqual(result["detail"], "Time off")

    def test_05_half_day_leave(self):
        self._approved_leave(self.emp_a, utc(TUE, "13:00"), utc(TUE, "17:00"))
        result = self._avail(self.emp_a, TUE, TUE, self.full_day)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["free_shifts"], [(TUE, self.shift_morning.id)])
        self.assertEqual(result["absent_shifts"], [(TUE, self.shift_afternoon.id)])

    def test_05_pending_leave(self):
        leave_type = self.env["hr.leave.type"].create(
            {"name": "Test leave", "requires_allocation": "no"}
        )
        self.env["hr.leave"].create(
            {
                "name": "Pending",
                "employee_id": self.emp_a.id,
                "holiday_status_id": leave_type.id,
                "request_date_from": WED,
                "request_date_to": WED,
            }
        )
        result = self._avail(self.emp_a, WED, WED, self.full_day)
        self.assertEqual(result["status"], "absent")
        self.assertEqual(result["detail"], "Pending time off")

    def test_5a_night_with_leave(self):
        self._approved_leave(self.emp_a, utc(MON, "00:00"), utc(MON, "23:59"))
        result = self._avail(self.emp_a, MON, MON, self.shift_night)
        self.assertEqual(result["status"], "absent")

    def test_06_public_holiday(self):
        self._approved_leave(False, utc(MON, "00:00"), utc(MON, "23:59"))
        employees = self.emp_a | self.emp_b
        result = employees._get_allocation_availability(MON, MON, self.full_day)
        for employee in employees:
            self.assertEqual(result[employee.id]["status"], "absent")
            self.assertEqual(result[employee.id]["detail"], "Public holiday")

    def test_07_saturday(self):
        result = self._avail(self.emp_a, SAT, SAT, self.full_day)
        self.assertEqual(result["status"], "absent")
        self.assertEqual(result["work_shifts"], [])
        self.assertEqual(result["detail"], "Outside working hours")

    def test_08_not_eligible_excluded(self):
        employees = self.emp_a | self.emp_office
        result = employees._get_allocation_availability(MON, MON, self.full_day)
        self.assertEqual(set(result), {self.emp_a.id})

    def test_15a_two_teams_allocated(self):
        team_a, team_b = self.env["project.allocation.team"].create(
            [{"name": "Team A"}, {"name": "Team B"}]
        )
        self._alloc(self.emp_b, MON, self.shift_morning, team_id=team_a.id)
        self._alloc(
            self.emp_b, MON, self.shift_afternoon, task=self.task_2, team_id=team_b.id
        )
        self.assertEqual(
            self._avail(self.emp_b, MON, MON, self.full_day)["status"], "allocated"
        )

    def test_multi_day_text_and_order(self):
        self._alloc(self.emp_a, TUE, self.shift_afternoon)
        result = self._avail(self.emp_a, MON, TUE, self.full_day)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(
            result["free_shifts"],
            [
                (MON, self.shift_morning.id),
                (MON, self.shift_afternoon.id),
                (TUE, self.shift_morning.id),
            ],
        )

    def test_overnight_next_day(self):
        Shift = self.env["project.allocation.shift"]
        overnight = Shift.create(
            {
                "name": "Overnight",
                "source": "fixed",
                "hour_start": 22.0,
                "hour_end": 6.0,
            }
        )
        early = Shift.create(
            {"name": "Early", "source": "fixed", "hour_start": 3.0, "hour_end": 5.0}
        )
        self._alloc(self.emp_a, MON, overnight)
        self.assertEqual(
            self._avail(self.emp_a, TUE, TUE, early)["status"], "allocated"
        )
        self.assertEqual(
            self._avail(self.emp_a, TUE, TUE, self.shift_morning)["status"],
            "available",
        )

    def test_archived_ignored(self):
        self._alloc(self.emp_a, MON, self.shift_morning).action_archive()
        self.assertEqual(
            self._avail(self.emp_a, MON, MON, self.full_day)["status"], "available"
        )

    def test_merged_attendances_keep_shifts(self):
        # 08-12 and 12-16 touch: the core merges them into one interval
        calendar = self.env["resource.calendar"].create(
            {
                "name": "No lunch",
                "tz": "America/Sao_Paulo",
                "attendance_ids": [
                    Command.create(
                        {
                            "name": "Morning",
                            "dayofweek": "0",
                            "hour_from": 8.0,
                            "hour_to": 12.0,
                            "day_period": "morning",
                        }
                    ),
                    Command.create(
                        {
                            "name": "Afternoon",
                            "dayofweek": "0",
                            "hour_from": 12.0,
                            "hour_to": 16.0,
                            "day_period": "afternoon",
                        }
                    ),
                ],
            }
        )
        self.emp_c.resource_calendar_id = calendar
        self.assertEqual(
            self.emp_c._get_shift_interval(MON, self.shift_afternoon),
            (utc(MON, "12:00"), utc(MON, "16:00")),
        )
        result = self._avail(self.emp_c, MON, MON, self.full_day)
        self.assertEqual(len(result["free_shifts"]), 2)
        self.assertEqual(result["work_hours"], 8.0)

    # 5.2 - performance

    def _make_employees(self, count, calendars):
        return self.env["hr.employee"].create(
            [
                {
                    "name": f"Perf {index}",
                    "allocation_eligible": True,
                    "resource_calendar_id": calendars[index % len(calendars)].id,
                }
                for index in range(count)
            ]
        )

    def test_query_count(self):
        calendars = [self.calendar, self.calendar.copy({"name": "Second"})]
        small = self._make_employees(2, calendars)
        large = self._make_employees(30, calendars)
        for employee in (small | large)[::3]:
            self._alloc(employee, MON, self.shift_morning)

        def count(employees):
            self.env.invalidate_all()
            before = self.env.cr.sql_log_count
            employees._get_allocation_availability(MON, SAT, self.full_day)
            return self.env.cr.sql_log_count - before

        small_count = count(small)
        large_count = count(large)
        _logger.info(
            "Availability queries: %s for 2 employees, %s for 30 employees",
            small_count,
            large_count,
        )
        self.assertLessEqual(large_count, small_count + 2)
        self.assertLessEqual(large_count, 25)
