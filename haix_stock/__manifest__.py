# Copyright 2026 - TODAY, Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Haix Stock",
    "summary": "Stock and rental logistics customizations for Haix Rental",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Escodoo",
    "maintainers": ["WesleyOliveira98"],
    "website": "https://github.com/Escodoo/haix-addons",
    "depends": [
        "sale_rental",
        "stock_analytic",
    ],
    "data": [
        "security/haix_stock_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/product_data.xml",
        "views/product_template.xml",
        "views/stock_warehouse.xml",
        "views/stock_picking.xml",
        "views/sale_order.xml",
        "report/return_slip.xml",
    ],
    "post_init_hook": "post_init_hook",
}
