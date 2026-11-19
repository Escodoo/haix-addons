# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import MON, AllocationCommon


@tagged("post_install", "-at_install")
class TestSubstitute(AllocationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["project.task.allocation.substitute.wizard"]
        cls.team_a = cls.env["project.allocation.team"].create(
            {"name": "Team A", "member_ids": [Command.link(cls.emp_a.id)]}
        )
        cls.env.company.allocation_block_overlap = True
        cls.project_2 = cls.env["project.project"].create({"name": "Site 2"})
        cls.task_site_2 = cls.env["project.task"].create(
            {"name": "Scaffolding", "project_id": cls.project_2.id}
        )
        cls.origin = cls._alloc(cls.emp_a, MON, cls.shift_afternoon)

    def _wizard(self, substitute, **vals):
        wizard = self.Wizard.with_context(default_allocation_id=self.origin.id).create(
            dict({"substitute_id": substitute.id}, **vals)
        )
        return wizard

    def _notes(self, record):
        return record.message_ids.filtered(
            lambda message: message.subtype_id == self.env.ref("mail.mt_note")
        ).mapped("body")

    def test_open_from_allocation(self):
        action = self.origin.action_open_substitute_wizard()
        self.assertEqual(
            action["res_model"], "project.task.allocation.substitute.wizard"
        )
        self.assertEqual(action["context"]["default_allocation_id"], self.origin.id)
        wizard = self.Wizard.with_context(
            active_model="project.task.allocation", active_id=self.origin.id
        ).create({})
        self.assertEqual(wizard.allocation_id, self.origin)

    def test_candidates(self):
        self._alloc(self.emp_b, MON, self.shift_afternoon, task=self.task_site_2)
        wizard = self.Wizard.with_context(default_allocation_id=self.origin.id).create(
            {}
        )
        candidates = wizard.line_ids.sorted("sequence")
        self.assertNotIn(self.emp_a, candidates.employee_id)
        self.assertNotIn(self.emp_office, candidates.employee_id)
        # Other field employees may exist in the database: compare only ours
        ours = candidates.filtered(
            lambda line: line.employee_id in self.emp_b | self.emp_c
        )
        self.assertEqual(ours.employee_id.ids, [self.emp_c.id, self.emp_b.id])
        self.assertEqual(ours.mapped("status"), ["available", "allocated"])
        ours[0].action_choose()
        self.assertEqual(wizard.substitute_id, self.emp_c)

    def test_16_simple(self):
        self._wizard(self.emp_b, reason="Sick").action_confirm()
        self.assertEqual(self.origin.employee_id, self.emp_b)
        self.assertEqual(self.origin.task_id, self.task_1)
        self.assertEqual(self.origin.allocation_date, MON)
        self.assertEqual(self.origin.shift_id, self.shift_afternoon)
        self.assertEqual(self.origin.team_id, self.team_a)
        self.assertTrue(self.origin.active)
        self.assertTrue(any("Sick" in body for body in self._notes(self.origin)))

    def test_17_archive_other(self):
        morning_site_2 = self._alloc(
            self.emp_b, MON, self.shift_morning, task=self.task_site_2
        )
        afternoon_site_2 = self._alloc(
            self.emp_b, MON, self.shift_afternoon, task=self.task_site_2
        )
        wizard = self._wizard(self.emp_b, reason="No show")
        self.assertEqual(wizard.substitute_conflict_ids, afternoon_site_2)
        wizard.action_confirm()
        self.assertEqual(self.origin.employee_id, self.emp_b)
        self.assertFalse(afternoon_site_2.active)
        self.assertTrue(morning_site_2.active)
        self.assertFalse(
            self.env["project.task.allocation"].search(
                [("employee_id", "=", self.emp_a.id)]
            )
        )
        for record in (self.origin, afternoon_site_2, self.task_site_2):
            self.assertTrue(
                any("No show" in body for body in self._notes(record)),
                f"No note on {record}",
            )

    def test_18_keep_blocked(self):
        afternoon_site_2 = self._alloc(
            self.emp_b, MON, self.shift_afternoon, task=self.task_site_2
        )
        wizard = self._wizard(self.emp_b, release_mode="keep")
        with self.assertRaises(ValidationError):
            wizard.action_confirm()
        self.assertEqual(self.origin.employee_id, self.emp_a)
        self.assertTrue(afternoon_site_2.active)

    def test_keep_when_not_blocked(self):
        self.env.company.allocation_block_overlap = False
        afternoon_site_2 = self._alloc(
            self.emp_b, MON, self.shift_afternoon, task=self.task_site_2
        )
        self._wizard(self.emp_b, release_mode="keep").action_confirm()
        self.assertEqual(self.origin.employee_id, self.emp_b)
        self.assertTrue(afternoon_site_2.active)
        self.assertTrue(self.origin.has_conflict)
        self.assertTrue(afternoon_site_2.has_conflict)

    def test_same_employee_refused(self):
        with self.assertRaises(ValidationError):
            self._wizard(self.emp_a).action_confirm()

    def test_drag_to_busy_employee(self):
        self._alloc(self.emp_b, MON, self.shift_afternoon, task=self.task_site_2)
        with self.assertRaises(ValidationError):
            self.origin.write({"employee_id": self.emp_b.id})
        self.assertEqual(self.origin.employee_id, self.emp_a)
