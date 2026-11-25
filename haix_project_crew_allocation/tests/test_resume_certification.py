# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestResumeCertification(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env["hr.employee"].create({"name": "Field Worker"})
        cls.nr35 = cls.env["survey.survey"].create(
            {
                "title": "NR35",
                "certification": True,
                "scoring_type": "scoring_with_answers",
                "certification_validity_months": 24,
            }
        )
        cls.nr10 = cls.env["survey.survey"].create(
            {
                "title": "NR10",
                "certification": True,
                "scoring_type": "scoring_with_answers",
            }
        )
        cls.certification_type = cls.env.ref(
            "hr_skills_survey.resume_type_certification"
        )

    def _line_vals(self, **vals):
        return dict(
            {
                "employee_id": self.employee.id,
                "name": "NR-35",
                "display_type": "certification",
                "date_start": date(2026, 1, 1),
            },
            **vals,
        )

    def test_certification_requires_survey(self):
        with self.assertRaises(ValidationError):
            self.env["hr.resume.line"].create(self._line_vals())

    def test_classic_line_without_survey(self):
        line = self.env["hr.resume.line"].create(
            self._line_vals(display_type="classic")
        )
        self.assertEqual(line.name, "NR-35")

    def test_name_comes_from_survey(self):
        line = self.env["hr.resume.line"].create(
            self._line_vals(survey_id=self.nr35.id)
        )
        self.assertEqual(line.name, "NR35")
        line.survey_id = self.nr10
        self.assertEqual(line.name, "NR10")

    def _upload(self, user, name="nr35.pdf"):
        return (
            self.env["ir.attachment"]
            .with_user(user)
            .create(
                {
                    "name": name,
                    "raw": b"%PDF-1.4 proof",
                    "res_model": "hr.resume.line",
                    "res_id": 0,
                }
            )
        )

    def test_proof_is_linked_and_readable_by_hr(self):
        worker = new_test_user(self.env, login="haix_worker", groups="base.group_user")
        self.employee.user_id = worker
        hr_user = new_test_user(
            self.env, login="haix_hr", groups="base.group_user,hr.group_hr_user"
        )
        proof = self._upload(worker)
        line = (
            self.env["hr.resume.line"]
            .with_user(worker)
            .create(
                self._line_vals(
                    survey_id=self.nr35.id,
                    proof_attachment_ids=[Command.set(proof.ids)],
                )
            )
        )
        self.assertEqual((proof.res_model, proof.res_id), ("hr.resume.line", line.id))
        self.assertEqual(proof.with_user(hr_user).raw, b"%PDF-1.4 proof")

    def test_proof_of_someone_else_is_not_linked(self):
        other = new_test_user(self.env, login="haix_other", groups="base.group_user")
        foreign = self._upload(other, "other.pdf")
        line = self.env["hr.resume.line"].create(
            self._line_vals(survey_id=self.nr35.id)
        )
        line.proof_attachment_ids = [Command.link(foreign.id)]
        self.assertFalse(foreign.res_id)

    def test_form_fills_certification(self):
        form = self._form()
        form.line_type_id = self.certification_type
        self.assertEqual(form.display_type, "certification")
        form.date_start = date(2026, 1, 15)
        form.survey_id = self.nr35
        self.assertEqual(form.name, "NR35")
        self.assertEqual(form.date_end, date(2028, 1, 15))
        line = form.save()
        self.assertEqual(line.name, "NR35")
        self.assertEqual(line.date_end, date(2028, 1, 15))

    def _form(self):
        return Form(
            self.env["hr.resume.line"].with_context(
                default_employee_id=self.employee.id
            ),
            view="hr_skills.resume_line_view_form",
        )

    def test_type_keeps_the_start_already_filled(self):
        form = self._form()
        form.date_start = date(2025, 6, 1)
        form.line_type_id = self.certification_type
        self.assertEqual(form.display_type, "certification")
        self.assertEqual(form.date_start, date(2025, 6, 1))

    def test_certification_that_never_expires(self):
        """Validity 0 (the default) means the certification never expires."""
        form = self._form()
        form.display_type = "certification"
        form.survey_id = self.nr10
        self.assertEqual(form.date_start, fields.Date.context_today(self.nr10))
        self.assertFalse(form.date_end)
        line = form.save()
        self.assertEqual(line.name, "NR10")
        self.assertFalse(line.date_end)

    def test_form_without_start_starts_today(self):
        form = self._form()
        today = fields.Date.context_today(self.env["hr.resume.line"])
        form.line_type_id = self.certification_type
        self.assertEqual(form.date_start, today)
        form.survey_id = self.nr35
        self.assertEqual(form.date_start, today)
        self.assertEqual(form.date_end, today + relativedelta(months=24))
        form.date_start = date(2026, 3, 10)
        self.assertEqual(form.date_end, date(2028, 3, 10))
        # Both dates stay editable
        form.date_end = date(2027, 12, 31)
        line = form.save()
        self.assertEqual(line.date_start, date(2026, 3, 10))
        self.assertEqual(line.date_end, date(2027, 12, 31))
