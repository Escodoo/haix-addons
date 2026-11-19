# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .common import MON, AllocationCommon

ALLOCATION_USER = "haix_project_allocation.group_allocation_user"
ALLOCATION_MANAGER = "haix_project_allocation.group_allocation_manager"


@tagged("post_install", "-at_install")
class TestSecurity(AllocationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reader = new_test_user(
            cls.env,
            login="alloc_sec_reader",
            groups=f"base.group_user,{ALLOCATION_USER}",
        )
        cls.scheduler = new_test_user(
            cls.env,
            login="alloc_sec_scheduler",
            groups=f"base.group_user,{ALLOCATION_MANAGER}",
        )
        cls.leader = new_test_user(
            cls.env,
            login="alloc_sec_leader",
            groups="base.group_user,project.group_project_user",
        )
        Team = cls.env["project.allocation.team"]
        cls.team_a = Team.create(
            {"name": "Team Alpha", "member_ids": [Command.link(cls.emp_a.id)]}
        )
        cls.team_b = Team.create(
            {"name": "Team Beta", "member_ids": [Command.link(cls.emp_b.id)]}
        )

    def test_12_reader_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env["project.task.allocation"].with_user(self.reader).create(
                {
                    "employee_id": self.emp_a.id,
                    "task_id": self.task_1.id,
                    "allocation_date": MON,
                    "shift_id": self.shift_morning.id,
                }
            )

    def test_scheduler_without_hr_rights(self):
        self.assertFalse(self.scheduler.has_group("hr.group_hr_user"))
        env = self.env(user=self.scheduler)
        wizard = (
            env["project.task.allocation.wizard"]
            .with_context(default_task_id=self.task_1.id)
            .create({"date_from": MON, "date_to": MON})
        )
        for line in wizard.line_ids:
            line.selected = line.employee_id == self.emp_a
        wizard.action_confirm()
        allocation = env["project.task.allocation"].search(
            [
                ("employee_id", "=", self.emp_a.id),
                ("shift_id", "=", self.shift_morning.id),
            ]
        )
        self.assertEqual(allocation.team_id, self.team_a)
        availability = env["project.allocation.availability.wizard"].create(
            {"date_from": MON, "date_to": MON}
        )
        self.assertTrue(availability.line_ids)
        substitute = (
            env["project.task.allocation.substitute.wizard"]
            .with_context(default_allocation_id=allocation.id)
            .create({"substitute_id": self.emp_c.id})
        )
        substitute.action_confirm()
        self.assertEqual(allocation.employee_id, self.emp_c)

    def test_13_member_filter(self):
        allocation = self._alloc(
            self.emp_b, MON, self.shift_morning, team_id=self.team_a.id
        )
        Allocation = self.env["project.task.allocation"]
        by_team_a = Allocation.search([("team_id", "ilike", "Team Alpha")])
        by_team_b = Allocation.search([("team_id", "ilike", "Team Beta")])
        members_b = Allocation.search(
            [("employee_id.allocation_team_id", "ilike", "Team Beta")]
        )
        self.assertIn(allocation, by_team_a)
        self.assertNotIn(allocation, by_team_b)
        self.assertIn(allocation, members_b)

    def test_menus(self):
        Menu = self.env["ir.ui.menu"]
        planning = self.env.ref("haix_project_allocation.menu_allocation_planning")
        availability = self.env.ref(
            "haix_project_allocation.menu_allocation_availability"
        )
        leader_menus = Menu.with_user(self.leader)._visible_menu_ids()
        self.assertNotIn(planning.id, leader_menus)
        self.assertNotIn(availability.id, leader_menus)
        reader_menus = Menu.with_user(self.reader)._visible_menu_ids()
        self.assertIn(availability.id, reader_menus)
        self.assertNotIn(planning.id, reader_menus)
        scheduler_menus = Menu.with_user(self.scheduler)._visible_menu_ids()
        self.assertIn(planning.id, scheduler_menus)

    def test_planning_views_load(self):
        action = self.env.ref("haix_project_allocation.action_project_task_allocation")
        view_types = action.view_mode.split(",")
        self.assertEqual(view_types[0], "timeline")
        views = (
            self.env["project.task.allocation"]
            .with_user(self.scheduler)
            .get_views([(False, view_type) for view_type in view_types + ["search"]])
        )
        self.assertEqual(set(views["views"]), set(view_types + ["search"]))

    def test_open_planning_from_availability(self):
        wizard = self.env["project.allocation.availability.wizard"].create(
            {"date_from": MON, "date_to": MON}
        )
        action = wizard.action_open_timeline()
        self.assertTrue(action["view_mode"].startswith("timeline"))
        self.assertIn(("allocation_date", ">=", MON), action["domain"])

    def test_employee_smart_button(self):
        self._alloc(self.emp_a, MON, self.shift_morning)
        action = self.emp_a.action_view_allocations()
        found = self.env["project.task.allocation"].search(action["domain"])
        self.assertEqual(found.employee_id, self.emp_a)

    def test_settings(self):
        settings = self.env["res.config.settings"].create(
            {"allocation_block_overlap": False}
        )
        settings.execute()
        self.assertFalse(self.env.company.allocation_block_overlap)
