"""
tests/test_inventory.py
Unit tests for Module A: Inventory and Traceability.
Verifies batch search, challenge figures for B2231 and B2240, recall detection,
affected customer traceability (23 chemists, 2 hospitals, 640 units), and expiry audits.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
import modules.inventory as inv

class TestInventoryModule(unittest.TestCase):
    def test_trace_batch_recalled_scenario_b2231(self):
        """Verify B2231 challenge figures: 180 remaining in warehouse, 640 dispatched, recalled."""
        res = inv.trace_batch("B2231")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["data"]["is_recalled"])
        self.assertEqual(res["data"]["total_warehouse_stock"], 180)
        self.assertEqual(res["data"]["total_dispatched_qty"], 640)
        self.assertEqual(res["data"]["sku"], "SKU-AMOX-500")

    def test_trace_batch_clean_scenario_b2240(self):
        """Verify B2240 clean stock: 400 remaining, not recalled."""
        res = inv.trace_batch("B2240")
        self.assertTrue(res["success"])
        self.assertFalse(res["data"]["is_recalled"])
        self.assertEqual(res["data"]["total_warehouse_stock"], 400)

    def test_check_recall(self):
        """Verify recall check on recalled and non-recalled batches."""
        res_recalled = inv.check_recall("B2231")
        self.assertTrue(res_recalled["is_recalled"])
        self.assertEqual(res_recalled["status"], "recalled")
        self.assertEqual(res_recalled["recall_details"]["recall_class"], "Class I")

        res_clean = inv.check_recall("B2240")
        self.assertFalse(res_clean["is_recalled"])
        self.assertEqual(res_clean["status"], "not_recalled")

    def test_get_affected_customers_b2231(self):
        """Verify B2231 customer trace: exactly 23 chemists, 2 hospitals, and 640 units."""
        res = inv.get_affected_customers("B2231")
        self.assertTrue(res["success"])
        self.assertEqual(res["total_dispatched_units"], 640)
        self.assertEqual(res["chemists_count"], 23)
        self.assertEqual(res["hospitals_count"], 2)
        self.assertEqual(res["total_customers_count"], 25)

    def test_check_expiry(self):
        """Verify detection of expired and near-expiry batches."""
        # Reference date 2026-10-09
        res = inv.check_expiry(reference_date="2026-10-09", near_expiry_days=30)
        self.assertTrue(res["success"])
        # B8801 expired on 2026-09-30
        expired_batches = [b["batch"] for b in res["expired"]]
        self.assertIn("B8801", expired_batches)
        # B3011 expires on 2026-10-25 (within 16 days)
        near_expiry_batches = [b["batch"] for b in res["near_expiry"]]
        self.assertIn("B3011", near_expiry_batches)

    def test_load_inventory_accepts_official_batch_inventory_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pd.DataFrame([
                {"sku": "PH-X", "batch": "LOT-X", "warehouse": "Bengaluru", "storage_location": "AMB", "qty": 5, "mfg_date": "2025-01-01", "expiry_date": "2026-12-01"},
                {"sku": "PH-X", "batch": "LOT-X", "warehouse": "Mysuru", "storage_location": "AMB", "qty": 7, "mfg_date": "2025-01-01", "expiry_date": "2027-01-01"},
            ]).to_csv(os.path.join(temp_dir, "batch_inventory.csv"), index=False)
            result = inv.load_inventory(temp_dir)
            traced = inv.trace_batch("LOT-X", data_dir=temp_dir)

        records = result["inventory"]
        self.assertEqual(len(records), 2)
        self.assertEqual(records["batch"].tolist(), ["LOT-X", "LOT-X"])
        self.assertEqual(records["expiry_date"].tolist(), ["2026-12-01", "2027-01-01"])
        self.assertEqual(records["warehouse"].tolist(), ["Bengaluru", "Mysuru"])
        self.assertEqual(records["storage_location"].tolist(), ["AMB", "AMB"])
        self.assertEqual(
            [record["storage_location"] for record in traced["data"]["warehouses"]],
            ["AMB", "AMB"],
        )

    def test_trace_batch_preserves_multiple_expiry_dates(self):
        inventory_data = {
            "inventory": pd.DataFrame([
                {"sku": "SKU-TEST", "batch": "B-TEST", "warehouse": "WH-A", "qty": 10, "mfg_date": "2025-01-01", "expiry_date": "2026-12-01"},
                {"sku": "SKU-TEST", "batch": "B-TEST", "warehouse": "WH-B", "qty": 15, "mfg_date": "2025-01-01", "expiry_date": "2027-01-01"},
            ]),
            "products": pd.DataFrame(),
            "dispatches": pd.DataFrame(),
            "customers": pd.DataFrame(),
            "warnings": [],
        }
        with patch.object(inv, "load_inventory", return_value=inventory_data), patch.object(
            inv, "check_recall", return_value={"is_recalled": False, "evidence": {}}
        ):
            result = inv.trace_batch("B-TEST")

        self.assertEqual(result["data"]["expiry_date"], "Multiple dates; see warehouse records")
        self.assertEqual(result["data"]["expiry_dates"], ["2026-12-01", "2027-01-01"])
        self.assertEqual(
            result["data"]["warehouses"],
            [
                {"warehouse": "WH-A", "qty": 10, "mfg_date": "2025-01-01", "expiry_date": "2026-12-01"},
                {"warehouse": "WH-B", "qty": 15, "mfg_date": "2025-01-01", "expiry_date": "2027-01-01"},
            ],
        )

    def test_trace_batch_keeps_batches_sharing_a_sku_separate(self):
        inventory_data = {
            "inventory": pd.DataFrame([
                {"sku": "SKU-SHARED", "batch": "LOT-ALPHA", "warehouse": "WH-A", "qty": 12, "mfg_date": "2025-01-01", "expiry_date": "2026-12-01"},
                {"sku": "SKU-SHARED", "batch": "LOT-BETA", "warehouse": "WH-B", "qty": 30, "mfg_date": "2025-02-01", "expiry_date": "2027-02-01"},
            ]),
            "products": pd.DataFrame(),
            "dispatches": pd.DataFrame(),
            "customers": pd.DataFrame(),
            "warnings": [],
        }
        with patch.object(inv, "load_inventory", return_value=inventory_data), patch.object(
            inv, "check_recall", return_value={"is_recalled": False, "evidence": {}}
        ):
            alpha = inv.trace_batch("LOT-ALPHA")
            beta = inv.trace_batch("LOT-BETA")

        self.assertEqual(alpha["data"]["sku"], beta["data"]["sku"])
        self.assertEqual(alpha["data"]["batch_id"], "LOT-ALPHA")
        self.assertEqual(alpha["data"]["total_warehouse_stock"], 12)
        self.assertEqual(alpha["data"]["expiry_dates"], ["2026-12-01"])
        self.assertEqual(
            alpha["data"]["warehouses"],
            [{"warehouse": "WH-A", "qty": 12, "mfg_date": "2025-01-01", "expiry_date": "2026-12-01"}],
        )
        self.assertEqual(beta["data"]["batch_id"], "LOT-BETA")
        self.assertEqual(beta["data"]["total_warehouse_stock"], 30)
        self.assertEqual(beta["data"]["expiry_dates"], ["2027-02-01"])
        self.assertEqual(
            beta["data"]["warehouses"],
            [{"warehouse": "WH-B", "qty": 30, "mfg_date": "2025-02-01", "expiry_date": "2027-02-01"}],
        )

    def test_unknown_batch_returns_not_found(self):
        """Verify searching an unknown batch ID gracefully returns not_found without error."""
        res = inv.trace_batch("B-NONEXISTENT-999")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "not_found")

if __name__ == "__main__":
    unittest.main()

