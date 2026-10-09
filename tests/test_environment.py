"""
tests/test_environment.py
Unit tests for Module B: Environmental Risk Detection.
Verifies cold-chain excursion detection (2.0°C - 8.0°C threshold),
identification of compromised cold-chain batches, and power outage evaluation.
"""

import unittest
import modules.environment as env

class TestEnvironmentModule(unittest.TestCase):
    def test_check_temperature_breach_detects_excursion(self):
        """Verify temperature breach detection flags the Central Warehouse excursion."""
        res = env.check_temperature_breach(min_limit=2.0, max_limit=8.0)
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "excursion_detected")
        self.assertGreater(res["excursions_count"], 0)

        central_exc = next(
            (e for e in res["excursions"] if "Central" in e["warehouse"]), None
        )
        self.assertIsNotNone(central_exc)
        self.assertGreater(central_exc["peak_temp_c"], 8.0)
        self.assertEqual(central_exc["cold_room"], "CR-01")

    def test_find_affected_batches_identifies_cold_chain_stock(self):
        """Verify affected batches identifies cold-chain insulin in WH-Central-Bengaluru."""
        res = env.find_affected_batches("WH-Central-Bengaluru")
        self.assertTrue(res["success"])
        cold_batches = [b["batch"] for b in res["potentially_affected_cold_chain_batches"]]
        # B1092 is Regular Insulin stored in Central Warehouse
        self.assertIn("B1092", cold_batches)
        # Amoxicillin (room temp) should NOT be in cold-chain affected batches
        self.assertNotIn("B2231", cold_batches)

    def test_compliant_thresholds(self):
        """Verify that with very loose thresholds, no excursion is reported."""
        res = env.check_temperature_breach(min_limit=0.0, max_limit=20.0)
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "normal")
        self.assertEqual(res["excursions_count"], 0)

    def test_analyse_power_outage(self):
        """Verify power outage analysis produces thermal rise metrics."""
        res = env.analyse_power_outage(
            start_time="2026-10-08T02:00:00",
            end_time="2026-10-08T06:00:00",
            location="WH-Central-Bengaluru",
        )
        self.assertTrue(res["success"])
        self.assertTrue(res["exceeded_cold_chain"])
        self.assertGreater(res["peak_temperature"], 8.0)

if __name__ == "__main__":
    unittest.main()

