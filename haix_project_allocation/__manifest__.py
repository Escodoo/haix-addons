# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Haix Project Allocation",
    "summary": "Allocate field employees to tasks by day and shift, "
    "with availability and a timeline per person",
    "version": "18.0.1.0.0",
    "category": "Services/Project",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/haix-addons",
    "license": "AGPL-3",
    "development_status": "Beta",
    "depends": [
        "project",
        "hr",
        "resource",
        "hr_holidays",
        "web_timeline",
    ],
    "data": [
        "security/allocation_security.xml",
        "security/ir.model.access.csv",
        "data/allocation_shift_data.xml",
        "views/project_allocation_shift_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
