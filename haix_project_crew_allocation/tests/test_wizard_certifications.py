# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import Command
from odoo.tests import Form, new_test_user, tagged

from odoo.addons.project_crew_allocation.tests.common import MON, TUE, AllocationCommon


@tagged("post_install", "-at_install")
class TestWizardCertifications(AllocationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Survey = cls.env["survey.survey"]
        cls.nr35, cls.nr10 = Survey.create(
            [
                {
                    "title": "NR35",
                    "certification": True,
                    "scoring_type": "scoring_with_answers",
                },
                {
                    "title": "NR10",
                    "certification": True,
                    "scoring_type": "scoring_with_answers",
                },
            ]
        )
        cls.not_certification = Survey.create({"title": "Satisfaction"})

        def give(employee, survey, date_start, date_end):
            cls.env["hr.resume.line"].create(
                {
                    "employee_id": employee.id,
                    "name": survey.title,
                    "display_type": "certification",
                    "survey_id": survey.id,
                    "date_start": date_start,
                    "date_end": date_end,
                }
            )

        year_ago = MON - timedelta(days=365)
        give(cls.emp_a, cls.nr35, year_ago, False)
        give(cls.emp_a, cls.nr10, year_ago, MON + timedelta(days=365))
        give(cls.emp_b, cls.nr35, year_ago, TUE)
        # Expires in the middle of the period: not valid for all of it
        give(cls.emp_c, cls.nr35, year_ago, MON)

    def _employees(self, certifications, date_to=MON):
        wizard = (
            self.env["project.task.allocation.wizard"]
            .with_context(default_task_id=self.task_1.id)
            .create(
                {
                    "date_from": MON,
                    "date_to": date_to,
                    "show_unavailable": True,
                    "certification_ids": [Command.set(certifications.ids)],
                }
            )
        )
        # Only the employees of the test, whatever else the database holds
        test_employees = self.emp_a | self.emp_b | self.emp_c
        return wizard, wizard.line_ids.employee_id & test_employees

    def test_no_certification_filter(self):
        _wizard, employees = self._employees(self.env["survey.survey"])
        self.assertEqual(employees, self.emp_a | self.emp_b | self.emp_c)

    def test_one_certification(self):
        _wizard, employees = self._employees(self.nr35)
        self.assertEqual(employees, self.emp_a | self.emp_b | self.emp_c)

    def test_all_certifications_required(self):
        _wizard, employees = self._employees(self.nr35 | self.nr10)
        self.assertEqual(employees, self.emp_a)

    def test_valid_for_the_whole_period(self):
        _wizard, employees = self._employees(self.nr35, date_to=TUE)
        self.assertEqual(employees, self.emp_a | self.emp_b)

    def test_changing_certifications_rebuilds_lines(self):
        wizard, _employees = self._employees(self.nr35 | self.nr10)
        wizard.certification_ids = [Command.unlink(self.nr10.id)]
        employees = wizard.line_ids.employee_id & (self.emp_a | self.emp_b | self.emp_c)
        self.assertEqual(employees, self.emp_a | self.emp_b | self.emp_c)

    def test_form_filters_on_the_fly(self):
        """Picking certifications on screen rebuilds the list at once."""
        form = Form(
            self.env["project.task.allocation.wizard"].with_context(
                default_task_id=self.task_1.id
            )
        )
        form.date_from = MON
        form.date_to = MON
        form.show_unavailable = True
        test_employees = self.emp_a | self.emp_b | self.emp_c

        def listed():
            employees = self.env["hr.employee"]
            for index in range(len(form.line_ids)):
                with form.line_ids.edit(index) as line:
                    employees |= line.employee_id
            return employees & test_employees

        self.assertEqual(listed(), test_employees)
        form.certification_ids.add(self.nr35)
        form.certification_ids.add(self.nr10)
        self.assertEqual(listed(), self.emp_a)
        form.certification_ids.remove(id=self.nr10.id)
        self.assertEqual(listed(), test_employees)

    def test_internal_user_reads_only_certifications(self):
        user = new_test_user(
            self.env,
            login="haix_internal_user",
            groups="base.group_user",
        )
        surveys = self.env["survey.survey"].with_user(user).search([])
        self.assertIn(self.nr35, surveys)
        self.assertNotIn(self.not_certification, surveys)
