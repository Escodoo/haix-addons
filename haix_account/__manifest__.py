# Copyright 2026 - TODAY, Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Haix Account",
    "summary": "Finance customizations for Haix Rental",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Escodoo",
    "maintainers": ["WesleyOliveira98"],
    "website": "https://github.com/Escodoo/haix-addons",
    "depends": [
        "account_due_list",
        "account_credit_control",
        "mis_builder_cash_flow",
        "purchase",
        "sale",
    ],
    "data": [
        "security/haix_account_security.xml",
        "security/ir.model.access.csv",
        "wizards/account_move_line_reschedule.xml",
        "views/account_move_line.xml",
        "views/account_move.xml",
        "views/sale_order.xml",
    ],
}
