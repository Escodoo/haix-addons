# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

CERTIFICATION_TYPE = "hr_skills_survey.resume_type_certification"


class HrResumeLine(models.Model):
    _inherit = "hr.resume.line"

    proof_attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="haix_hr_resume_line_proof_rel",
        column1="line_id",
        column2="attachment_id",
        string="Proof",
        help="Certificate or other document that proves the certification.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._haix_certification_name(vals)
        lines = super().create(vals_list)
        lines._haix_link_proof_attachments()
        return lines

    def write(self, vals):
        self._haix_certification_name(vals)
        res = super().write(vals)
        if "proof_attachment_ids" in vals:
            self._haix_link_proof_attachments()
        return res

    def _haix_link_proof_attachments(self):
        """Attach the uploaded proofs to their line.

        An upload is not linked to any record until then, so only its author
        could read it. Only the author's own uploads are linked.
        """
        for line in self:
            line.proof_attachment_ids.sudo().filtered(
                lambda att: not att.res_id and att.create_uid == self.env.user
            ).write({"res_model": self._name, "res_id": line.id})

    @api.model
    def _haix_certification_name(self, vals):
        """The title of a certification is always the one of its survey."""
        if vals.get("survey_id"):
            vals["name"] = self.env["survey.survey"].browse(vals["survey_id"]).title

    @api.constrains("display_type", "survey_id")
    def _check_certification_survey(self):
        for line in self:
            if line.display_type == "certification" and not line.survey_id:
                raise ValidationError(
                    _("Choose the certification of %(name)s.", name=line.name)
                )

    @api.onchange("line_type_id")
    def _onchange_line_type_certification(self):
        if self.line_type_id == self.env.ref(
            CERTIFICATION_TYPE, raise_if_not_found=False
        ):
            self.display_type = "certification"
            if not self.date_start:
                self.date_start = fields.Date.context_today(self)

    @api.onchange("survey_id", "date_start")
    def _onchange_certification_validity(self):
        if not self.survey_id:
            return
        self.name = self.survey_id.title
        if not self.date_start:
            self.date_start = fields.Date.context_today(self)
        months = self.survey_id.certification_validity_months
        if months:
            self.date_end = self.date_start + relativedelta(months=months)
