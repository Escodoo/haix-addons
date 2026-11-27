Stock and rental logistics customizations for Haix, on top of `sale_rental`.

- **Products**: a unique number for each product, the asset type (rental equipment or
  assembly supply), whether the item must be inspected when it comes back, and three values
  (indemnity, used sale and supplier).
- **Inspection and maintenance**: returned items that require inspection go to the
  inspection location; the product shows the quantities in inspection and in maintenance.
- **Lease sheet**: the analytic account of the rental order (lease sheet) is propagated to the
  rental deliveries, returns and their moves.
- **Return date**: a group allowed to reschedule only the return date of a rental return.
- **Return slip**: report to print the return slip from the transfer.
- **Missing items**: "Charge Missing Items" on the sale order adds an indemnity line for each
  rented item that went to the customer and did not come back, at its indemnity value.
- **Rental dates** are set at noon, so they do not move to the day before because of the
  time zone.
