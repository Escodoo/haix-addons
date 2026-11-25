# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.tests import TransactionCase

from ..models.ir_actions_act_window import PLANNING_ACTION, PLANNING_MENU


class TestPlanningName(TransactionCase):
    def test_english_name(self):
        for xmlid in (PLANNING_ACTION, PLANNING_MENU):
            record = self.env.ref(xmlid).with_context(lang="en_US")
            self.assertEqual(record.name, "Planning")

    def test_portuguese_texts(self):
        self.env["res.lang"]._activate_lang("pt_BR")
        self.env["ir.actions.act_window"]._haix_translate_planning()
        for xmlid in (PLANNING_ACTION, PLANNING_MENU):
            record = self.env.ref(xmlid).with_context(lang="pt_BR")
            self.assertEqual(record.name, "Planejamento")
        action = self.env.ref(PLANNING_ACTION).with_context(lang="pt_BR")
        self.assertIn("Aloque pessoas nas tarefas", action.help)
        self.assertIn('"Alocar pessoas"', action.help)
        self.assertNotIn("Alocar equipe", action.help)

    def test_without_portuguese(self):
        """Nothing is written, and no error, when pt_BR is not active."""
        Lang = type(self.env["res.lang"])
        with (
            patch.object(Lang, "get_installed", return_value=[("en_US", "English")]),
            patch.object(
                type(self.env.ref(PLANNING_MENU)), "update_field_translations"
            ) as update,
        ):
            self.env["ir.actions.act_window"]._haix_translate_planning()
        update.assert_not_called()
