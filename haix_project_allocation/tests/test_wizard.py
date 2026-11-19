# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime, timedelta

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import FRI, MON, TUE, WED, AllocationCommon

NEXT_MON = MON + timedelta(days=7)


@tagged("post_install", "-at_install")
class TestWizard(AllocationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["project.task.allocation.wizard"]
        cls.Allocation = cls.env["project.task.allocation"]
        cls.env.company.allocation_block_overlap = True

    def _wizard(self, date_from, date_to, shifts=None, task=None, **vals):
        values = {"date_from": date_from, "date_to": date_to}
        if shifts is not None:
            values["shift_ids"] = [Command.set(shifts.ids)]
        values.update(vals)
        return self.Wizard.with_context(
            default_task_id=(task or self.task_1).id
        ).create(values)

    def _line(self, wizard, employee):
        return wizard.line_ids.filtered(lambda line: line.employee_id == employee)

    def _run(self, date_from, date_to, employees, shifts=None, **vals):
        """Select ``employees`` only, confirm and return the created allocations."""
        wizard = self._wizard(date_from, date_to, shifts, show_unavailable=True, **vals)
        for line in wizard.line_ids:
            line.selected = line.employee_id in employees
        before = self.Allocation.search([])
        wizard.action_confirm()
        return self.Allocation.search([]) - before

    # 6.1 - task

    def test_open_from_task(self):
        action = self.task_1.action_open_allocation_wizard()
        self.assertEqual(action["res_model"], "project.task.allocation.wizard")
        self.assertEqual(action["context"]["default_task_id"], self.task_1.id)
        self._alloc(self.emp_a, MON, self.shift_morning)
        self.assertEqual(self.task_1.allocation_count, 1)
        self.assertEqual(self.task_1.allocated_employee_ids, self.emp_a)
        smart = self.task_1.action_view_allocations()
        self.assertEqual(smart["res_model"], "project.task.allocation")

    # 6.2 - wizard

    def test_defaults(self):
        wizard = self.Wizard.with_context(default_task_id=self.task_1.id).create({})
        self.assertEqual(wizard.shift_ids, self.shift_morning | self.shift_afternoon)
        if "planned_date_start" not in self.task_1._fields:
            self.assertEqual(wizard.date_from, fields.Date.context_today(wizard))
            self.assertEqual(wizard.date_to, fields.Date.context_today(wizard))
            return
        self.task_1.write(
            {
                "planned_date_start": datetime(2026, 11, 24, 12, 0),
                "planned_date_end": datetime(2026, 11, 26, 18, 0),
            }
        )
        wizard = self.Wizard.with_context(default_task_id=self.task_1.id).create({})
        self.assertEqual((wizard.date_from, wizard.date_to), (TUE, WED + timedelta(1)))

    def test_09_multi_day_counts(self):
        self.assertEqual(len(self._run(MON, WED, self.emp_a)), 6)
        self.assertEqual(len(self._run(MON, WED, self.emp_b, self.shift_afternoon)), 3)
        self.assertEqual(len(self._run(FRI, NEXT_MON, self.emp_c)), 4)
        self.assertEqual(len(self._run(FRI, NEXT_MON, self.emp_c, self.shift_night)), 4)

    def test_10_atomic_conflict(self):
        self._alloc(self.emp_a, MON, self.shift_morning, task=self.task_2)
        count = self.Allocation.search_count([])
        with self.assertRaisesRegex(UserError, "Field A"):
            self._run(MON, MON, self.emp_a | self.emp_b, self.shift_morning)
        self.assertEqual(self.Allocation.search_count([]), count)

    def test_08_11_lines_scope(self):
        company_b = self.env["res.company"].create({"name": "Company B"})
        other = self.env["hr.employee"].create(
            {
                "name": "Other company",
                "company_id": company_b.id,
                "allocation_eligible": True,
            }
        )
        wizard = self._wizard(MON, MON, show_unavailable=True)
        self.assertIn(self.emp_a, wizard.line_ids.employee_id)
        self.assertNotIn(self.emp_office, wizard.line_ids.employee_id)
        self.assertNotIn(other, wizard.line_ids.employee_id)

    def test_hide_unavailable_and_order(self):
        self._alloc(self.emp_b, MON, self.shift_morning, task=self.task_2)
        self._alloc(self.emp_b, MON, self.shift_afternoon, task=self.task_2)
        self._alloc(self.emp_c, MON, self.shift_morning, task=self.task_2)
        wizard = self._wizard(MON, MON)
        self.assertNotIn(self.emp_b, wizard.line_ids.employee_id)
        wizard.show_unavailable = True
        # Other field employees may exist in the database: compare only ours
        ours = wizard.line_ids.sorted("sequence").filtered(
            lambda line: line.employee_id in self.emp_a | self.emp_b | self.emp_c
        )
        self.assertEqual(
            ours.mapped("status"),
            ["available", "partial", "allocated"],
        )

    def test_14_team_preselect(self):
        team = self.env["project.allocation.team"].create(
            {
                "name": "Team A",
                "member_ids": [
                    Command.link(self.emp_a.id),
                    Command.link(self.emp_b.id),
                ],
            }
        )
        self._alloc(self.emp_b, MON, self.shift_morning, task=self.task_2)
        wizard = self._wizard(MON, MON, team_id=team.id, show_unavailable=True)
        self.assertTrue(self._line(wizard, self.emp_a).selected)
        self.assertFalse(self._line(wizard, self.emp_b).selected)
        self.assertFalse(self._line(wizard, self.emp_c).selected)
        self.assertTrue(self._line(wizard, self.emp_a).is_team_member)
        self._line(wizard, self.emp_c).selected = True
        wizard.action_confirm()
        created = self.Allocation.search([("employee_id", "=", self.emp_c.id)])
        self.assertEqual(len(created), 2)
        self.assertEqual(created.team_id, team)
        self.assertFalse(self.emp_c.allocation_team_id)

    def test_already_allocated_not_duplicated(self):
        self._alloc(self.emp_a, MON, self.shift_morning)
        wizard = self._wizard(MON, MON, show_unavailable=True)
        line = self._line(wizard, self.emp_a)
        self.assertTrue(line.already_allocated)
        self.assertTrue(line.selected)
        for other in wizard.line_ids - line:
            other.selected = False
        wizard.action_confirm()
        allocations = self.Allocation.search(
            [("employee_id", "=", self.emp_a.id), ("task_id", "=", self.task_1.id)]
        )
        self.assertEqual(
            allocations.shift_id, self.shift_morning | self.shift_afternoon
        )
        self.assertEqual(len(allocations), 2)

    def test_preselected_employees(self):
        wizard = self.Wizard.with_context(
            default_task_id=self.task_1.id,
            default_employee_ids=[self.emp_c.id],
        ).create({"date_from": MON, "date_to": MON})
        self.assertEqual(wizard.line_ids.filtered("selected").employee_id, self.emp_c)

    def test_archived_shift_not_default(self):
        old = self._alloc(self.emp_a, MON, self.shift_afternoon)
        self.shift_afternoon.action_archive()
        wizard = self.Wizard.with_context(default_task_id=self.task_1.id).create({})
        self.assertEqual(wizard.shift_ids, self.shift_morning)
        old.invalidate_recordset()
        self.assertTrue(old.date_start)
        self.assertEqual(old.shift_id.name, "Afternoon")

    def test_full_day_button(self):
        wizard = self._wizard(MON, MON, self.shift_night)
        wizard.action_full_day()
        self.assertEqual(wizard.shift_ids, self.shift_morning | self.shift_afternoon)

    def test_nothing_to_create(self):
        wizard = self._wizard(MON, MON)
        wizard.line_ids.selected = False
        with self.assertRaises(UserError):
            wizard.action_confirm()
