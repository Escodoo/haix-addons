# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from psycopg2.extensions import AsIs

from odoo import models, tools


class MisCashFlow(models.Model):
    _inherit = "mis.cash_flow"

    def init(self):
        """Forecast by the expected payment date instead of the due date."""
        query = """
            SELECT
                -aml.id as id,
                'move_line' as line_type,
                aml.id as move_line_id,
                aml.account_id as account_id,
                CASE
                    WHEN aml.amount_residual > 0
                    THEN aml.amount_residual
                    ELSE 0.0
                END AS debit,
                CASE
                    WHEN aml.amount_residual < 0
                    THEN -aml.amount_residual
                    ELSE 0.0
                END AS credit,
                aml.reconciled as reconciled,
                aml.full_reconcile_id as full_reconcile_id,
                aml.partner_id as partner_id,
                aml.company_id as company_id,
                aml.name as name,
                aml.parent_state as parent_state,
                COALESCE(
                    aml.expected_payment_date, aml.date_maturity, aml.date
                ) as date
            FROM account_move_line as aml
            WHERE aml.parent_state != 'cancel'
            UNION ALL
            SELECT
                fl.id as id,
                'forecast_line' as line_type,
                NULL as move_line_id,
                fl.account_id as account_id,
                CASE
                    WHEN fl.balance > 0
                    THEN fl.balance
                    ELSE 0.0
                END AS debit,
                CASE
                    WHEN fl.balance < 0
                    THEN -fl.balance
                    ELSE 0.0
                END AS credit,
                NULL as reconciled,
                NULL as full_reconcile_id,
                fl.partner_id as partner_id,
                fl.company_id as company_id,
                fl.name as name,
                'posted' as parent_state,
                fl.date as date
            FROM mis_cash_flow_forecast_line as fl
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        self._cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s)", (AsIs(self._table), AsIs(query))
        )
