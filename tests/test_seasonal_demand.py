"""
tests/test_seasonal_demand.py
Unit tests for Module C: Seasonal Demand Intelligence.
Verifies historical demand calculation, stock-gap accounting for incoming POs and usable stock,
handling of unknown products, and supplementary research inspection.
"""

import unittest
import modules.seasonal_demand as seasonal

class TestSeasonalDemandModule(unittest.TestCase):
    def test_calculate_seasonal_demand_sufficient_data(self):
        """Verify seasonal demand calculation for SKU-AMOX-500."""
        res = seasonal.calculate_seasonal_demand("SKU-AMOX-500")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "calculated")
        self.assertGreater(res["estimate"], 0)
        self.assertIn("surge_multiplier", res)

    def test_calculate_seasonal_demand_insufficient_data(self):
        """Verify handling of unknown product gracefully reports insufficient_data."""
        res = seasonal.calculate_seasonal_demand("SKU-DOES-NOT-EXIST")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "insufficient_data")
        self.assertEqual(res["estimate"], 0)

    def test_calculate_stock_gap_considers_pos_and_excludes_recalled(self):
        """Verify stock-gap calculation accounts for incoming POs and excludes quarantined batch B2231."""
        res = seasonal.calculate_stock_gap("SKU-AMOX-500")
        self.assertTrue(res["success"])
        # B2231 (180 units) is recalled, so quarantined_stock must be 180
        self.assertEqual(res["quarantined_stock"], 180)
        # B2240 (400 units) is usable
        self.assertEqual(res["usable_warehouse_stock"], 400)
        # PO-2026-0911 has 800 units confirmed
        self.assertEqual(res["incoming_po_stock"], 800)
        # Total supply should be 400 + 800 = 1200
        self.assertEqual(res["total_available_supply"], 1200)

    def test_forecast_seasonal_demand_contract(self):
        """Verify forecast_seasonal_demand returns contract keys."""
        res = seasonal.forecast_seasonal_demand("SKU-AMOX-500")
        self.assertTrue(res["available"])
        self.assertIn("estimate", res)
        self.assertIn("stock_gap", res)
        self.assertIn("method", res)
        self.assertIn("assumptions", res)
        self.assertIn("evidence", res)

    def test_inspect_supplementary_research(self):
        """Verify inspection of seasonal_diseases_vaccines.csv research file."""
        res = seasonal.inspect_supplementary_research()
        self.assertTrue(res["available"])
        self.assertIn("Disease", res["columns"])
        self.assertIn("Seasonality", res["columns"])
        self.assertIn("limitations_notice", res)

if __name__ == "__main__":
    unittest.main()

