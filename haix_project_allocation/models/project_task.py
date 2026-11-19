# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    allocation_ids = fields.One2many(
        comodel_name="project.task.allocation",
        inverse_name="task_id",
        string="Allocations",
    )
    allocation_count = fields.Integer(compute="_compute_allocation_stats")
    allocated_employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        string="Allocated Employees",
        compute="_compute_allocation_stats",
    )

    def _compute_allocation_stats(self):
        groups = self.env["project.task.allocation"]._read_group(
            [("task_id", "in", self.ids)],
            ["task_id"],
            ["__count", "employee_id:array_agg"],
        )
        stats = {task.id: (count, employee_ids) for task, count, employee_ids in groups}
        for task in self:
            count, employee_ids = stats.get(task.id, (0, []))
            task.allocation_count = count
            task.allocated_employee_ids = self.env["hr.employee"].browse(
                list(set(employee_ids))
            )

    def action_open_allocation_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Allocate Team"),
            "res_model": "project.task.allocation.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_task_id": self.id},
        }

    def action_view_allocations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Allocations"),
            "res_model": "project.task.allocation",
            "view_mode": "list,form",
            "domain": [("task_id", "=", self.id)],
            "context": {"default_task_id": self.id},
        }
