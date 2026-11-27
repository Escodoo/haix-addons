# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHaixStock(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        Location = cls.env["stock.location"]
        parent = cls.warehouse.view_location_id
        cls.rental_out = Location.create(
            {"name": "Rental Out", "location_id": parent.id}
        )
        cls.inspection = Location.create(
            {"name": "Inspection", "location_id": parent.id}
        )
        cls.warehouse.write(
            {
                "rental_out_location_id": cls.rental_out.id,
                "haix_inspection_location_id": cls.inspection.id,
            }
        )
        cls.stock = cls.warehouse.lot_stock_id
        cls.partner = cls.env["res.partner"].create({"name": "Obra Teste"})
        cls.platform = cls.env["product.product"].create(
            {
                "name": "Plataforma",
                "is_storable": True,
                "haix_asset_type": "rental_equipment",
                "haix_requires_inspection": True,
                "haix_indemnity_value": 1000.0,
            }
        )
        cls.frame = cls.env["product.product"].create(
            {
                "name": "Quadro",
                "is_storable": True,
                "haix_asset_type": "rental_equipment",
                "haix_indemnity_value": 245.0,
            }
        )
        cls.screw = cls.env["product.product"].create(
            {
                "name": "Parafuso",
                "is_storable": True,
                "haix_asset_type": "assembly_supply",
            }
        )

    def _move(
        self, product, qty, source, dest, group=False, picking_type=False, done_qty=None
    ):
        self.env["stock.quant"]._update_available_quantity(product, source, qty)
        move = self.env["stock.move"].create(
            {
                "name": product.name,
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "location_id": source.id,
                "location_dest_id": dest.id,
                "group_id": group and group.id,
                "picking_type_id": picking_type and picking_type.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        move._action_confirm()
        move._action_assign()
        move.quantity = qty if done_qty is None else done_qty
        move.picked = True
        move._action_done(cancel_backorder=True)
        return move

    def test_unique_number(self):
        template = self.platform.product_tmpl_id
        self.assertTrue(template.haix_unique_number)
        self.assertNotEqual(template.haix_unique_number, self.frame.haix_unique_number)
        copy = template.copy()
        self.assertTrue(copy.haix_unique_number)
        self.assertNotEqual(copy.haix_unique_number, template.haix_unique_number)

    def test_returned_item_goes_to_inspection(self):
        platform_move = self._move(
            self.platform,
            1,
            self.rental_out,
            self.stock,
            picking_type=self.warehouse.in_type_id,
        )
        frame_move = self._move(
            self.frame,
            5,
            self.rental_out,
            self.stock,
            picking_type=self.warehouse.in_type_id,
        )
        self.assertEqual(platform_move.location_dest_id, self.inspection)
        self.assertEqual(frame_move.location_dest_id, self.stock)
        self.assertEqual(self.platform.haix_qty_inspection, 1)
        self.assertEqual(
            self.platform.with_context(location=self.stock.id).qty_available, 0
        )

    def test_charge_missing_items(self):
        order = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "warehouse_id": self.warehouse.id}
        )
        group = self.env["procurement.group"].create(
            {"name": order.name, "sale_id": order.id}
        )
        order.procurement_group_id = group
        self._move(self.frame, 40, self.stock, self.rental_out, group)
        self._move(self.screw, 100, self.stock, self.rental_out, group)
        self._move(self.frame, 40, self.rental_out, self.stock, group, done_qty=38)
        self._move(self.screw, 50, self.rental_out, self.stock, group)
        order.action_haix_charge_missing_items()
        line = order.order_line.filtered("haix_indemnity_product_id")
        self.assertEqual(line.haix_indemnity_product_id, self.frame)
        self.assertEqual(line.product_uom_qty, 2)
        self.assertEqual(line.price_unit, 245.0)
        self.assertFalse(order._haix_missing_rental_quantities())

    def test_sales_user_only_reschedules_returns(self):
        user = self.env["res.users"].create(
            {
                "name": "Comercial",
                "login": "comercial_haix_test",
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref("sales_team.group_sale_salesman").id,
                            self.env.ref("haix_stock.group_rental_return_date").id,
                        ]
                    )
                ],
            }
        )
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.in_type_id.id,
                "location_id": self.rental_out.id,
                "location_dest_id": self.stock.id,
                "partner_id": self.partner.id,
                "move_ids": [
                    Command.create(
                        {
                            "name": "Quadro",
                            "product_id": self.frame.id,
                            "product_uom_qty": 2,
                            "product_uom": self.frame.uom_id.id,
                            "location_id": self.rental_out.id,
                            "location_dest_id": self.stock.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        self.assertTrue(picking.haix_is_rental_return)
        as_user = picking.with_user(user)
        as_user.scheduled_date = "2050-12-31 12:00:00"
        self.assertEqual(str(picking.scheduled_date), "2050-12-31 12:00:00")
        with self.assertRaises(AccessError):
            as_user.origin = "Outro"
