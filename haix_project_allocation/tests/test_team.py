# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import new_test_user, tagged

from .common import AllocationCommon


@tagged("post_install", "-at_install")
class TestTeam(AllocationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Team = cls.env["project.allocation.team"]
        cls.team_a = cls.Team.create(
            {"name": "Team A", "member_ids": [Command.link(cls.emp_a.id)]}
        )
        cls.team_b = cls.Team.create({"name": "Team B"})

    def test_one_team_per_person(self):
        self.assertEqual(self.emp_a.allocation_team_id, self.team_a)
        self.team_b.member_ids = [Command.link(self.emp_a.id)]
        self.assertEqual(self.emp_a.allocation_team_id, self.team_b)
        self.assertNotIn(self.emp_a, self.team_a.member_ids)
        self.assertIn(self.emp_a, self.team_b.member_ids)

    def test_fields_readable_without_hr_rights(self):
        reader = new_test_user(
            self.env,
            login="alloc_reader",
            groups="base.group_user,haix_project_allocation.group_allocation_user",
        )
        employee = self.emp_a.with_user(reader)
        self.assertTrue(employee.allocation_eligible)
        self.assertEqual(employee.allocation_team_id, self.team_a)

    def test_team_multi_company(self):
        company_b = self.env["res.company"].create({"name": "Company B"})
        team_other = self.Team.create(
            {"name": "Team Other", "company_id": company_b.id}
        )
        user_a = new_test_user(
            self.env,
            login="alloc_company_a",
            groups="base.group_user,haix_project_allocation.group_allocation_user",
            company_id=self.env.company.id,
            company_ids=[Command.set(self.env.company.ids)],
        )
        visible = self.Team.with_user(user_a).search([])
        self.assertIn(self.team_a, visible)
        self.assertNotIn(team_other, visible)
