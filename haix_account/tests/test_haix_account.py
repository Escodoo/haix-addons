# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestHaixAccount(AccountTestInvoicingCommon):
    chart_template = "generic_coa"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env.ref("haix_account.group_vendor_bill_without_purchase")
        cls.env.user.groups_id = [Command.unlink(cls.group.id)]

    def _receivable_line(self, invoice):
        return invoice.line_ids.filtered(
            lambda line: line.account_type == "asset_receivable"
        )

    def test_due_date_locked_and_expected_date_rescheduled(self):
        invoice = self.init_invoice("out_invoice", products=self.product_a, post=True)
        line = self._receivable_line(invoice)
        self.assertEqual(line.expected_payment_date, line.date_maturity)
        self.assertFalse(line.is_rescheduled)
        with self.assertRaises(UserError):
            line.date_maturity = line.date_maturity + timedelta(days=5)
        due_date = line.date_maturity
        new_date = due_date + timedelta(days=10)
        wizard = (
            self.env["account.move.line.reschedule"]
            .with_context(active_model="account.move.line", active_ids=line.ids)
            .create({"expected_payment_date": new_date, "reason": "Customer asked"})
        )
        wizard.action_reschedule()
        self.assertEqual(line.date_maturity, due_date)
        self.assertEqual(line.expected_payment_date, new_date)
        self.assertTrue(line.is_rescheduled)
        self.env.flush_all()
        cash_flow = self.env["mis.cash_flow"].search([("move_line_id", "=", line.id)])
        self.assertEqual(cash_flow.date, new_date)

    def test_due_date_editable_in_draft(self):
        invoice = self.init_invoice("out_invoice", products=self.product_a)
        line = self._receivable_line(invoice)
        new_date = line.date_maturity + timedelta(days=45)
        line.date_maturity = new_date
        self.assertEqual(line.date_maturity, new_date)
        self.assertEqual(line.expected_payment_date, new_date)

    def test_vendor_bill_requires_purchase_order(self):
        bill = self.init_invoice("in_invoice", products=self.product_a)
        with self.assertRaises(UserError):
            bill.action_post()
        self.env.user.groups_id = [Command.link(self.group.id)]
        bill.action_post()
        self.assertEqual(bill.state, "posted")

    def test_vendor_bill_from_purchase_order(self):
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    Command.create(
                        {"product_id": self.product_a.id, "product_qty": 1.0}
                    )
                ],
            }
        )
        order.button_confirm()
        order.order_line.qty_received = 1.0
        order.action_create_invoice()
        bill = order.invoice_ids
        bill.invoice_date = fields.Date.today()
        bill.action_post()
        self.assertEqual(bill.state, "posted")
