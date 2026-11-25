# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    def action_open_allocation_wizard(self):
        action = super().action_open_allocation_wizard()
        action["name"] = _("Allocate People")
        action["context"] = dict(action.get("context") or {}, dialog_size="extra-large")
        return action
