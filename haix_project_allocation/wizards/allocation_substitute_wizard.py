# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date

from .task_allocation_wizard import AVAILABILITY_STATUS, STATUS_ORDER


class ProjectTaskAllocationSubstituteWizard(models.TransientModel):
    _name = "project.task.allocation.substitute.wizard"
    _description = "Substitute Employee"

    allocation_id = fields.Many2one(
        comodel_name="project.task.allocation",
        required=True,
        ondelete="cascade",
    )
    employee_id = fields.Many2one(
        related="allocation_id.employee_id", string="Leaving Employee"
    )
    company_id = fields.Many2one(related="allocation_id.company_id")
    substitute_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Substitute",
        domain="[('allocation_eligible', '=', True), "
        "('id', '!=', employee_id), ('company_id', '=', company_id)]",
    )
    substitute_conflict_ids = fields.Many2many(
        comodel_name="project.task.allocation",
        relation="project_task_allocation_substitute_conflict_rel",
        column1="wizard_id",
        column2="allocation_id",
        string="Substitute's Overlapping Allocations",
        compute="_compute_substitute_conflict_ids",
    )
    release_mode = fields.Selection(
        [
            ("archive", "Release the substitute from the other site"),
            ("keep", "Keep both allocations"),
        ],
        required=True,
        default="archive",
        help="What to do with the substitute's allocations that overlap this "
        "one. Keeping both is only allowed when overlaps are not blocked.",
    )
    reason = fields.Char(help="Logged in the chatter of the allocations involved.")
    line_ids = fields.One2many(
        comodel_name="project.task.allocation.substitute.wizard.line",
        inverse_name="wizard_id",
        string="Candidates",
        compute="_compute_line_ids",
        store=True,
    )

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        context = self.env.context
        if (
            "allocation_id" in fields_list
            and not result.get("allocation_id")
            and context.get("active_model") == "project.task.allocation"
        ):
            active_ids = context.get("active_ids") or [context.get("active_id")]
            if len(active_ids) != 1:
                raise UserError(_("Select a single allocation to substitute."))
            result["allocation_id"] = active_ids[0]
        return result

    @api.depends("substitute_id", "allocation_id.date_start", "allocation_id.date_end")
    def _compute_substitute_conflict_ids(self):
        for wizard in self:
            origin = wizard.allocation_id
            if not (wizard.substitute_id and origin.date_start and origin.date_end):
                wizard.substitute_conflict_ids = False
                continue
            wizard.substitute_conflict_ids = self.env["project.task.allocation"].search(
                [
                    ("id", "!=", origin.id),
                    ("employee_id", "=", wizard.substitute_id.id),
                    ("date_start", "<", origin.date_end),
                    ("date_end", ">", origin.date_start),
                ]
            )

    @api.depends("allocation_id")
    def _compute_line_ids(self):
        for wizard in self:
            commands = [Command.clear()]
            if wizard.allocation_id.date_start:
                commands += [
                    Command.create(vals) for vals in wizard._prepare_line_vals()
                ]
            wizard.line_ids = commands

    def _prepare_line_vals(self):
        origin = self.allocation_id
        candidates = self.env["hr.employee"].search(
            [
                ("allocation_eligible", "=", True),
                ("id", "!=", origin.employee_id.id),
                ("company_id", "=", origin.company_id.id),
            ]
        )
        availability = candidates._get_allocation_availability(
            origin.allocation_date, origin.allocation_date, origin.shift_id
        )
        rows = []
        for employee in candidates:
            info = availability[employee.id]
            rows.append(
                (
                    (STATUS_ORDER[info["status"]], employee.name or ""),
                    {
                        "employee_id": employee.id,
                        "status": info["status"],
                        "detail": info["detail"],
                    },
                )
            )
        rows.sort(key=lambda row: row[0])
        return [dict(vals, sequence=index) for index, (_key, vals) in enumerate(rows)]

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Substitute Employee"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_confirm(self):
        self.ensure_one()
        origin = self.allocation_id
        outgoing = origin.employee_id
        substitute = self.substitute_id
        if not substitute or substitute == outgoing:
            raise ValidationError(
                _(
                    "Choose a substitute different from %(employee)s.",
                    employee=outgoing.name,
                )
            )
        conflicts = self.substitute_conflict_ids
        if (
            conflicts
            and self.release_mode == "keep"
            and origin.company_id.allocation_block_overlap
        ):
            raise ValidationError(
                _(
                    "%(employee)s is already allocated at that time and "
                    "overlapping allocations are blocked: release the "
                    "substitute from the other site instead.",
                    employee=substitute.name,
                )
            )
        released = self.env["project.task.allocation"]
        if conflicts and self.release_mode == "archive":
            # Release first: switching the employee before would trip the
            # overlap constraint.
            released = conflicts
            released.action_archive()
        origin.employee_id = substitute
        self._post_substitution_notes(outgoing, released)
        return {"type": "ir.actions.act_window_close"}

    def _post_substitution_notes(self, outgoing, released):
        """Log the substitution as internal notes: nobody is notified."""
        origin = self.allocation_id
        values = {
            "substitute": self.substitute_id.name,
            "outgoing": outgoing.name,
            "day": format_date(self.env, origin.allocation_date),
            "shift": origin.shift_id.name,
            "task": origin.task_id.display_name,
        }
        reason = (
            " " + _("Reason: %(reason)s", reason=self.reason) if self.reason else ""
        )
        origin.message_post(
            body=_(
                "%(substitute)s replaced %(outgoing)s on %(day)s (%(shift)s).",
                **values,
            )
            + reason,
            subtype_xmlid="mail.mt_note",
        )
        for allocation in released:
            body = (
                _(
                    "%(substitute)s left this site on %(day)s (%(shift)s) to "
                    "replace %(outgoing)s on %(task)s.",
                    **values,
                )
                + reason
            )
            allocation.message_post(body=body, subtype_xmlid="mail.mt_note")
            allocation.task_id.message_post(body=body, subtype_xmlid="mail.mt_note")


class ProjectTaskAllocationSubstituteWizardLine(models.TransientModel):
    _name = "project.task.allocation.substitute.wizard.line"
    _description = "Substitute Employee Candidate"
    _order = "sequence, id"

    wizard_id = fields.Many2one(
        comodel_name="project.task.allocation.substitute.wizard",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer()
    employee_id = fields.Many2one(comodel_name="hr.employee", required=True)
    status = fields.Selection(AVAILABILITY_STATUS)
    detail = fields.Char()

    def action_choose(self):
        self.ensure_one()
        self.wizard_id.substitute_id = self.employee_id
        return self.wizard_id._reopen()
