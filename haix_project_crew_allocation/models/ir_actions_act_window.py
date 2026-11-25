# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models

PLANNING_ACTION = "project_crew_allocation.action_project_task_allocation"
PLANNING_MENU = "project_crew_allocation.menu_allocation_planning"
PLANNING_NAME_PT_BR = "Planejamento"
# One entry per paragraph of the help, in the same order
PLANNING_HELP_PT_BR = (
    "Aloque pessoas nas tarefas",
    'Clique em "Alocar pessoas" numa tarefa para escolher quem trabalha nela '
    "ou crie as alocações aqui. A linha do tempo mostra uma linha por pessoa.",
)


class IrActionsActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    @api.model
    def _haix_translate_planning(self):
        """Write the Portuguese texts of the crew planning action and menu.

        These records belong to project_crew_allocation, so the .po file of
        this module cannot translate them: Odoo only reads the .po entries
        that are in the module .pot, and the export never puts records of
        other modules there. Called from data on every install and update,
        because each update of project_crew_allocation rewrites the texts.
        """
        if "pt_BR" not in dict(self.env["res.lang"].get_installed()):
            return
        action = self.env.ref(PLANNING_ACTION)
        menu = self.env.ref(PLANNING_MENU)
        action.update_field_translations("name", {"pt_BR": PLANNING_NAME_PT_BR})
        menu.update_field_translations("name", {"pt_BR": PLANNING_NAME_PT_BR})
        help_field = action._fields["help"]
        terms = help_field.get_trans_terms(action.with_context(lang="en_US").help)
        action.update_field_translations(
            "help", {"pt_BR": dict(zip(terms, PLANNING_HELP_PT_BR, strict=True))}
        )
