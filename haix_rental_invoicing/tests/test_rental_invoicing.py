# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRentalInvoicing(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        if not cls.warehouse.rental_allowed:
            cls.warehouse.rental_allowed = True
        cls.rental_in = cls.warehouse.rental_in_location_id
        cls.rental_out = cls.warehouse.rental_out_location_id
        cls.delivery_operation = cls.env.ref("l10n_br_fiscal.fo_simples_remessa")
        cls.return_operation = cls.env.ref("l10n_br_fiscal.fo_entrada_remessa")
        rules = cls.warehouse.rental_route_id.rule_ids
        cls.pull_rule = rules.filtered(
            lambda r: r.action == "pull" and r.location_dest_id == cls.rental_out
        )
        cls.push_rule = rules.filtered(
            lambda r: r.action == "push" and r.location_src_id == cls.rental_out
        )
        cls.pull_rule.write(
            {
                "fiscal_operation_id": cls.delivery_operation.id,
                "invoice_state": "2binvoiced",
            }
        )
        cls.push_rule.write(
            {
                "fiscal_operation_id": cls.return_operation.id,
                "invoice_state": "2binvoiced",
            }
        )
        cls.partner = cls.env["res.partner"].create({"name": "Obra Teste"})
        cls.equipment = cls.env["product.product"].create(
            {"name": "Motor do Guincho", "is_storable": True}
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.equipment, cls.rental_in, 5
        )
        cls.rental_service = cls.env["product.product"].create(
            {
                "name": "Locação do Motor",
                "type": "service",
                "uom_id": cls.env.ref("uom.product_uom_day").id,
                "uom_po_id": cls.env.ref("uom.product_uom_day").id,
                "must_have_dates": True,
                "rented_product_id": cls.equipment.id,
            }
        )

    def _rental_order(self, delivered=2):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "warehouse_id": self.warehouse.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.rental_service.id,
                            "rental_type": "new_rental",
                            "rental_qty": 2,
                            "start_date": date(2026, 12, 1),
                            "end_date": date(2026, 12, 10),
                            "product_uom_qty": 20,
                        },
                    )
                ],
            }
        )
        order.action_confirm()
        delivery = order.picking_ids.filtered(
            lambda p: p.location_dest_id == self.rental_out
        )
        delivery.action_assign()
        delivery.move_ids.quantity = delivered
        delivery.move_ids.picked = True
        delivery.with_context(
            picking_ids_not_to_backorder=delivery.ids
        ).button_validate()
        back = order.picking_ids.filtered(lambda p: p.location_id == self.rental_out)
        return delivery, back

    def _invoice_type(self, picking):
        return (
            self.env["stock.invoice.onshipping"]
            .with_context(active_model="stock.picking", active_ids=picking.ids)
            .new({})
            ._get_invoice_type()
        )

    def test_fiscal_operations_on_delivery_and_return(self):
        delivery, back = self._rental_order()
        self.assertEqual(delivery.state, "done")
        self.assertEqual(delivery.move_ids.fiscal_operation_id, self.delivery_operation)
        self.assertEqual(delivery.move_ids.invoice_state, "2binvoiced")
        self.assertTrue(back)
        self.assertEqual(back.move_ids.fiscal_operation_id, self.return_operation)
        self.assertEqual(back.move_ids.invoice_state, "2binvoiced")
        self.assertEqual(
            back.move_ids.fiscal_operation_line_id.fiscal_operation_id,
            self.return_operation,
        )

    def test_invoice_type(self):
        delivery, back = self._rental_order()
        self.assertEqual(self._invoice_type(delivery), "out_invoice")
        self.assertEqual(self._invoice_type(back), "out_refund")

    def test_invoice_done_quantity(self):
        company = self.env.company
        journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", company.id)], limit=1
        )
        self.delivery_operation.with_company(company).journal_id = journal
        nfe = self.env.ref("l10n_br_fiscal.document_55")
        company.document_type_id = nfe
        if not self.env["l10n_br_fiscal.document.serie"].search(
            [("document_type_id", "=", nfe.id), ("company_id", "=", company.id)]
        ):
            self.env["l10n_br_fiscal.document.serie"].create(
                {
                    "code": "99",
                    "name": "Teste",
                    "document_type_id": nfe.id,
                    "company_id": company.id,
                }
            )
        self.equipment.standard_price = 100.0
        # 2 planned, 3 shipped (one extra piece added at the site)
        delivery, _back = self._rental_order(delivered=3)
        self.env["stock.invoice.onshipping"].with_context(
            active_model="stock.picking", active_ids=delivery.ids
        ).create({}).action_generate()
        invoice = delivery.invoice_ids
        self.assertEqual(invoice.move_type, "out_invoice")
        self.assertEqual(invoice.invoice_line_ids.quantity, 3)
        self.assertEqual(invoice.invoice_line_ids.fiscal_quantity, 3)
