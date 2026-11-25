# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import tagged

from odoo.addons.project_crew_allocation.tests.common import MON, AllocationCommon


@tagged("post_install", "-at_install")
class TestWizardJob(AllocationCommon):
    def test_line_shows_job_position(self):
        job = self.env["hr.job"].create({"name": "Scaffold Assembler"})
        self.emp_a.job_id = job
        wizard = (
            self.env["project.task.allocation.wizard"]
            .with_context(default_task_id=self.task_1.id)
            .create({"date_from": MON, "date_to": MON, "show_unavailable": True})
        )
        line_a = wizard.line_ids.filtered(lambda line: line.employee_id == self.emp_a)
        line_b = wizard.line_ids.filtered(lambda line: line.employee_id == self.emp_b)
        self.assertEqual(line_a.job_id, job)
        self.assertFalse(line_b.job_id)
