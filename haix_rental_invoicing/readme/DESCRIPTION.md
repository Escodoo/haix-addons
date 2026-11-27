Brazilian fiscal documents for rental deliveries and returns (`sale_rental`) invoiced from
the transfer (`l10n_br_stock_account`).

- The delivery to the "Rental Out" location is invoiced as an outgoing document and the
  return as an incoming one. "Rental Out" is an internal location, so without this module
  `stock_picking_invoicing` would create a vendor refund.
- The return comes from the rental push rule and gets that rule's fiscal operation and
  invoice state, instead of the delivery operation copied from the outgoing move.
- The invoice line takes the done quantity of the moves (and the matching fiscal quantity),
  so a delivery or return with more or fewer pieces than planned is invoiced as it was
  done. Cancelled moves are not invoiced.
