# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import new_test_user, tagged
from odoo.tools.misc import format_date

from .common import MON, TUE, AllocationCommon


@tagged("post_install", "-at_install")
class TestAvailabilityWizard(AllocationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["project.allocation.availability.wizard"]
        cls.team = cls.env["project.allocation.team"].create(
            {"name": "Team A", "member_ids": [Command.link(cls.emp_a.id)]}
        )

    def _line(self, wizard, employee):
        return wizard.line_ids.filtered(lambda line: line.employee_id == employee)

    def test_lines_and_texts(self):
        allocation = self._alloc(self.emp_a, MON, self.shift_morning)
        wizard = self.Wizard.create({"date_from": MON, "date_to": MON})
        self.assertEqual(wizard.shift_ids, self.shift_morning | self.shift_afternoon)
        line = self._line(wizard, self.emp_a)
        weekday = format_date(self.env, MON, date_format="EEE")
        self.assertEqual(line.status, "partial")
        self.assertEqual(
            line.free_shifts_text, f"{weekday} {self.shift_afternoon.name}"
        )
        self.assertEqual(
            line.allocated_shifts_text, f"{weekday} {self.shift_morning.name}"
        )
        self.assertEqual(line.free_hours, 4.0)
        self.assertEqual(line.employee_team_id, self.team)
        self.assertEqual(line.allocated_team_ids, allocation.team_id)
        self.assertEqual(line.allocated_project_ids, self.project)
        self.assertEqual(self._line(wizard, self.emp_b).status, "available")
        self.assertNotIn(self.emp_office, wizard.line_ids.employee_id)

    def test_shows_every_status_in_order(self):
        self._alloc(self.emp_b, MON, self.shift_morning)
        self._alloc(self.emp_b, MON, self.shift_afternoon, task=self.task_2)
        wizard = self.Wizard.create({"date_from": MON, "date_to": MON})
        self.assertIn(self.emp_b, wizard.line_ids.employee_id)
        statuses = wizard.line_ids.sorted("sequence").mapped("status")
        order = ["available", "partial", "allocated", "absent"]
        self.assertEqual(statuses, sorted(statuses, key=order.index))

    def test_team_filter(self):
        wizard = self.Wizard.create(
            {"date_from": MON, "date_to": MON, "team_id": self.team.id}
        )
        self.assertEqual(wizard.line_ids.employee_id, self.emp_a)

    def test_department_filter(self):
        department = self.env["hr.department"].create({"name": "Field"})
        self.emp_c.department_id = department
        wizard = self.Wizard.create(
            {"date_from": MON, "date_to": MON, "department_id": department.id}
        )
        self.assertEqual(wizard.line_ids.employee_id, self.emp_c)

    def test_allocate_action_context(self):
        wizard = self.Wizard.create({"date_from": MON, "date_to": TUE})
        action = self._line(wizard, self.emp_a).action_allocate()
        self.assertEqual(action["res_model"], "project.task.allocation.wizard")
        context = action["context"]
        self.assertEqual(context["default_employee_ids"], [self.emp_a.id])
        self.assertEqual(
            (context["default_date_from"], context["default_date_to"]),
            ("2026-11-23", "2026-11-24"),
        )
        self.assertEqual(context["default_shift_ids"], wizard.shift_ids.ids)
        allocate = (
            self.env["project.task.allocation.wizard"]
            .with_context(**context)
            .create({"task_id": self.task_1.id})
        )
        self.assertEqual(allocate.line_ids.filtered("selected").employee_id, self.emp_a)

    def test_timeline_action_domain(self):
        inside = self._alloc(self.emp_a, MON, self.shift_morning)
        outside = self._alloc(self.emp_a, TUE, self.shift_morning)
        wizard = self.Wizard.create({"date_from": MON, "date_to": MON})
        action = wizard.action_open_timeline()
        found = self.env["project.task.allocation"].search(action["domain"])
        self.assertIn(inside, found)
        self.assertNotIn(outside, found)

    def test_reader_without_hr_rights(self):
        self._alloc(self.emp_a, MON, self.shift_morning)
        reader = new_test_user(
            self.env,
            login="availability_reader",
            groups="base.group_user,haix_project_allocation.group_allocation_user",
        )
        wizard = self.Wizard.with_user(reader).create(
            {"date_from": MON, "date_to": MON}
        )
        self.assertEqual(self._line(wizard, self.emp_a).status, "partial")
