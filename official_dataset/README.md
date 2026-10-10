# Challenge 07 – Batch B2231
**Arogya Pharma Distributors**  ·  Data snapshot: morning of 2026-11-16; dispatch history up to 2026-11-15

## Files

### `batch_inventory.csv`  (338 rows)

`sku`, `batch`, `warehouse`, `storage_location`, `qty`, `mfg_date`, `expiry_date`

### `customers.csv`  (420 rows)

`customer`, `type`, `location`, `credit_terms`

### `dispatches.csv`  (5,174 rows)

`date`, `customer`, `sku`, `batch`, `qty`

### `products.csv`  (75 rows)

`sku`, `molecule`, `brand`, `category`, `storage`, `critical_drug`

### `purchase_orders.csv`  (30 rows)

`po`, `manufacturer`, `sku`, `qty`, `expected_date`, `status`

### `recalls.csv`  (2 rows)

`date`, `sku`, `batches`, `reason`, `recall_class`

### `suppliers.csv`  (75 rows)

`manufacturer`, `sku`, `lead_time_days`, `moq`, `return_window_days`

### `temperature_logs.csv`  (1,008 rows)

`warehouse`, `cold_room`, `timestamp`, `temp_c`

## Notes

- `batch_inventory.csv` includes `storage_location`: CR-1/CR-2 are cold rooms (2–8°C), AMB is ambient.
- `return_window_days`: the manufacturer accepts near-expiry returns only until this many days before the batch expiry date.
- Data is synthetic. Batch numbers and companies are fictional.

At hour 14 an updated version of one of these files will be released. Same columns, same format.