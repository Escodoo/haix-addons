# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import tagged

from odoo.addons.project_crew_allocation.tests.common import (
    MON,
    TUE,
    AllocationCommon,
)


@tagged("post_install", "-at_install")
class TestAllocatePeople(AllocationCommon):
    def test_button_label(self):
        arch = self.env.ref("project.view_task_form2")._get_combined_arch()
        button = arch.find(".//button[@name='action_open_allocation_wizard']")
        self.assertEqual(button.get("string"), "Allocate People")

    def _assert_dialog(self, action):
        self.assertEqual(action["name"], "Allocate People")
        self.assertEqual(action["context"]["dialog_size"], "extra-large")

    def test_dialog_from_task(self):
        action = self.task_1.action_open_allocation_wizard()
        self._assert_dialog(action)
        # The task default set by project_crew_allocation is kept
        self.assertEqual(action["context"]["default_task_id"], self.task_1.id)

    def test_dialog_on_reopen(self):
        wizard = (
            self.env["project.task.allocation.wizard"]
            .with_context(default_task_id=self.task_1.id)
            .create({"date_from": MON, "date_to": MON})
        )
        self._assert_dialog(wizard.action_full_day())

    def test_dialog_from_availability(self):
        wizard = self.env["project.allocation.availability.wizard"].create(
            {"date_from": MON, "date_to": TUE}
        )
        wizard.selected_employee_ids = self.emp_a
        action = wizard.action_allocate()
        self._assert_dialog(action)
        self.assertEqual(action["context"]["default_employee_ids"], self.emp_a.ids)

    def test_planning_help(self):
        action = self.env.ref("project_crew_allocation.action_project_task_allocation")
        self.assertIn("Allocate People", action.help)
        self.assertNotIn("Allocate Team", action.help)
