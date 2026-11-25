# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models


class ProjectAllocationAvailabilityWizard(models.TransientModel):
    _inherit = "project.allocation.availability.wizard"

    def action_allocate(self):
        action = super().action_allocate()
        action["name"] = _("Allocate People")
        action["context"] = dict(action.get("context") or {}, dialog_size="extra-large")
        return action
