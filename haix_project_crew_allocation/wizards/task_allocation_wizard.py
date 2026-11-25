# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class ProjectTaskAllocationWizard(models.TransientModel):
    _inherit = "project.task.allocation.wizard"

    certification_ids = fields.Many2many(
        comodel_name="survey.survey",
        relation="haix_task_allocation_wizard_certification_rel",
        column1="wizard_id",
        column2="survey_id",
        string="Certifications",
        domain=[("certification", "=", True)],
        help="Only employees with all these certifications valid for the whole "
        "period are listed.",
    )

    def write(self, vals):
        res = super().write(vals)
        if "certification_ids" in vals:
            self._rebuild_line_ids()
        return res

    @api.onchange("certification_ids")
    def _onchange_certification_ids(self):
        if self._get_line_key() != self.line_key:
            self._rebuild_line_ids()

    def _get_line_key(self):
        certifications = ",".join(str(cid) for cid in self.certification_ids.ids)
        return f"{super()._get_line_key()}|{certifications}"

    def _get_candidate_employees(self):
        employees = super()._get_candidate_employees()
        certifications = self.certification_ids._origin
        if not certifications or not employees:
            return employees
        lines = self.env["hr.resume.line"].search(
            [
                ("employee_id", "in", employees.ids),
                ("survey_id", "in", certifications.ids),
                ("date_start", "<=", self.date_from),
                "|",
                ("date_end", "=", False),
                ("date_end", ">=", self.date_to),
            ]
        )
        return employees.filtered(
            lambda employee: certifications
            <= lines.filtered(lambda line: line.employee_id == employee).survey_id
        )

    def _reopen(self):
        action = super()._reopen()
        action["name"] = _("Allocate People")
        action["context"] = dict(action.get("context") or {}, dialog_size="extra-large")
        return action


class ProjectTaskAllocationWizardLine(models.TransientModel):
    _inherit = "project.task.allocation.wizard.line"

    job_id = fields.Many2one(related="employee_id.job_id")
