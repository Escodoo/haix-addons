# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from . import models


def post_init_hook(env):
    """Give a unique number to the products created before the module."""
    templates = (
        env["product.template"]
        .with_context(active_test=False)
        .search([("haix_unique_number", "=", False)], order="id")
    )
    for template in templates:
        template.haix_unique_number = env["ir.sequence"].next_by_code(
            "haix.product.unique.number"
        )
