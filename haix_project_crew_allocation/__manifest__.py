# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Haix Project Crew Allocation",
    "summary": "Haix customizations for the crew allocation",
    "version": "18.0.1.0.0",
    "category": "Services/Project",
    "author": "Escodoo",
    "maintainers": ["DenerWilliam"],
    "website": "https://github.com/Escodoo/haix-addons",
    "license": "AGPL-3",
    "development_status": "Beta",
    "depends": [
        "hr_skills_survey",
        "project_crew_allocation",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "views/hr_resume_line_views.xml",
        "views/menus.xml",
        "views/project_task_views.xml",
        "wizards/task_allocation_wizard_views.xml",
    ],
    "installable": True,
}
