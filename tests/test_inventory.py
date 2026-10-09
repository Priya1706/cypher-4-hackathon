"""
tests/test_inventory.py
Unit tests for Module A: Inventory and Traceability.
Verifies batch search, challenge figures for B2231 and B2240, recall detection,
affected customer traceability (23 chemists, 2 hospitals, 640 units), and expiry audits.
"""

import os
import unittest
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

    def test_unknown_batch_returns_not_found(self):
        """Verify searching an unknown batch ID gracefully returns not_found without error."""
        res = inv.trace_batch("B-NONEXISTENT-999")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "not_found")

if __name__ == "__main__":
    unittest.main()

