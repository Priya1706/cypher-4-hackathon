"""
tests/test_batchguard.py
Unit and integration tests for BatchGuard AI.
Verifies action lifecycles, governance rules, dispatch validations, agent fallbacks, and shared utilities.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

import modules.actions as actions
import modules.common as common
import agent


class TestCommonUtilities(unittest.TestCase):
    """Verifies common helper utilities."""

    def test_make_result(self):
        res = common.make_result("success", data={"count": 5}, warnings=["warn1"])
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["data"]["count"], 5)
        self.assertEqual(res["warnings"], ["warn1"])

    def test_parse_date_safely(self):
        d1 = common.parse_date_safely("2026-10-09")
        self.assertIsNotNone(d1)
        self.assertEqual(d1.year, 2026)

        d2 = common.parse_date_safely("09/10/2026")
        self.assertIsNotNone(d2)

        d_invalid = common.parse_date_safely("not-a-date")
        self.assertIsNone(d_invalid)

    def test_validate_columns(self):
        headers = ["Batch_ID", "Product_Name", "Quantity"]
        valid, missing = common.validate_columns(headers, ["batch_id", "quantity"])
        self.assertTrue(valid)
        self.assertEqual(len(missing), 0)

        valid, missing = common.validate_columns(headers, ["batch_id", "expiry_date"])
        self.assertFalse(valid)
        self.assertIn("expiry_date", missing)

    def test_load_csv_safely_missing_file(self):
        rows, warnings = common.load_csv_safely("non_existent_file.csv")
        self.assertEqual(len(rows), 0)
        self.assertTrue(any("File not found" in w for w in warnings))


class TestActionManagement(unittest.TestCase):
    """Verifies simulated action creation, lifecycle, and review governance."""

    def setUp(self):
        # Create a temporary file for isolated test persistence
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_store_path = os.path.join(self.temp_dir.name, "test_actions.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_action_created_with_pending_status(self):
        """Verify an action is created with unique ID and 'pending' status."""
        action = actions.create_action(
            action_type="quarantine_batch",
            details={"batch_id": "B2231", "reason": "Suspected recall"},
            file_path=self.test_store_path,
        )
        self.assertTrue(action["action_id"].startswith("ACT-"))
        self.assertEqual(action["status"], "pending")
        self.assertIsNotNone(action["created_at"])
        self.assertIsNone(action["reviewer"])

        # Check retrieval from storage
        fetched = actions.get_action(action["action_id"], file_path=self.test_store_path)
        self.assertEqual(fetched["action_id"], action["action_id"])
        self.assertEqual(fetched["status"], "pending")

    def test_approve_valid_action(self):
        """Verify a pending action can be approved by an authorized reviewer."""
        action = actions.create_action(
            action_type="urgent_po",
            details={"product_id": "P101", "units": 500},
            file_path=self.test_store_path,
        )
        review_res = actions.review_action(
            action_id=action["action_id"],
            decision="approved",
            reviewer="Dr. R. Sharma (QP)",
            file_path=self.test_store_path,
        )
        self.assertEqual(review_res["status"], "approved")
        self.assertEqual(review_res["reviewer"], "Dr. R. Sharma (QP)")
        self.assertIsNotNone(review_res["reviewed_at"])

        # Ensure it is no longer listed in pending
        pending = actions.list_pending_actions(file_path=self.test_store_path)
        self.assertFalse(any(a["action_id"] == action["action_id"] for a in pending))

    def test_reject_valid_action(self):
        """Verify a pending action can be rejected."""
        action = actions.create_action(
            action_type="dispatch_override",
            details={"batch_id": "B999"},
            file_path=self.test_store_path,
        )
        review_res = actions.review_action(
            action_id=action["action_id"],
            decision="rejected",
            reviewer="QA Lead",
            file_path=self.test_store_path,
        )
        self.assertEqual(review_res["status"], "rejected")
        self.assertEqual(review_res["reviewer"], "QA Lead")

    def test_invalid_status_transitions_refused(self):
        """Verify that already approved/rejected actions cannot be re-reviewed."""
        action = actions.create_action(
            action_type="quarantine_batch",
            details={"batch_id": "B100"},
            file_path=self.test_store_path,
        )
        # First review: approve
        actions.review_action(
            action_id=action["action_id"],
            decision="approved",
            reviewer="Reviewer A",
            file_path=self.test_store_path,
        )
        # Attempt second review: reject approved action
        second_review = actions.review_action(
            action_id=action["action_id"],
            decision="rejected",
            reviewer="Reviewer B",
            file_path=self.test_store_path,
        )
        self.assertEqual(second_review["status"], "error")
        self.assertIn("Invalid state transition", second_review["message"])

    def test_missing_action_id_handling(self):
        """Verify missing, empty, or non-existent action IDs return error responses cleanly."""
        res_get = actions.get_action("DOES_NOT_EXIST", file_path=self.test_store_path)
        self.assertEqual(res_get["status"], "not_found")

        res_review = actions.review_action(
            action_id="DOES_NOT_EXIST",
            decision="approved",
            reviewer="QA Lead",
            file_path=self.test_store_path,
        )
        self.assertEqual(res_review["status"], "error")

        res_empty = actions.get_action("", file_path=self.test_store_path)
        self.assertEqual(res_empty["status"], "error")

    def test_deduplication_prevents_duplicate_actions(self):
        """Ensure identical save calls update the existing record rather than creating duplicates."""
        action = actions.create_action("test_act", {"key": "val"}, file_path=self.test_store_path)
        # Save same action again
        actions.save_action(action, file_path=self.test_store_path)
        all_acts = actions.list_all_actions(file_path=self.test_store_path)
        matching = [a for a in all_acts if a["action_id"] == action["action_id"]]
        self.assertEqual(len(matching), 1)


class TestDispatchValidationSafety(unittest.TestCase):
    """Verifies safety rules for simulated dispatches against inventory & recall states."""

    def test_missing_inventory_fails_safe(self):
        """When inventory module is unavailable or returns not_implemented, validate_dispatch returns unknown."""
        mock_unavailable = {"available": False, "status": "not_implemented", "message": "Pending module"}
        with patch("modules.inventory.check_recall", return_value=mock_unavailable):
            res = actions.validate_dispatch("B-TEST", 100)
            self.assertFalse(res["valid"])
            self.assertEqual(res["status"], "unknown")
            self.assertIn("unavailable", res["reason"].lower())

    def test_recalled_batch_dispatch_blocked(self):
        """When batch is flagged as recalled, dispatch must be blocked."""
        mock_recall = {
            "status": "recalled",
            "is_recalled": True,
            "evidence": {"notice_id": "REC-2026-01"},
        }
        with patch("modules.inventory.check_recall", return_value=mock_recall):
            res = actions.validate_dispatch("B-RECALLED", 50)
            self.assertFalse(res["valid"])
            self.assertEqual(res["status"], "blocked_recall")
            self.assertIn("active recall notice", res["reason"])

    def test_dispatch_exceeding_stock_blocked(self):
        """When requested quantity exceeds known available stock, dispatch is rejected."""
        mock_recall = {"status": "success", "is_recalled": False}
        mock_trace = {
            "status": "success",
            "data": {"batch_id": "B-VALID", "available_stock": 40},
            "dispatches": [],
        }
        with patch("modules.inventory.check_recall", return_value=mock_recall):
            with patch("modules.inventory.trace_batch", return_value=mock_trace):
                # Request 100 units when only 40 are in stock
                res = actions.validate_dispatch("B-VALID", 100)
                self.assertFalse(res["valid"])
                self.assertEqual(res["status"], "insufficient_stock")
                self.assertEqual(res["available_stock"], 40)

    def test_valid_dispatch_allowed(self):
        """When batch is not recalled and stock is sufficient, dispatch is valid."""
        mock_recall = {"status": "success", "is_recalled": False}
        mock_trace = {
            "status": "success",
            "data": {"batch_id": "B-VALID", "available_stock": 200},
            "dispatches": [],
        }
        with patch("modules.inventory.check_recall", return_value=mock_recall):
            with patch("modules.inventory.trace_batch", return_value=mock_trace):
                res = actions.validate_dispatch("B-VALID", 50)
                self.assertTrue(res["valid"])
                self.assertEqual(res["status"], "valid")


class TestAgentInvestigation(unittest.TestCase):
    """Verifies AI agent investigation coordination, fallbacks, and honest reporting."""

    def test_get_available_tools_reports_active_modules(self):
        tools = agent.get_available_tools()
        self.assertTrue(len(tools) >= 5)
        # All tools should now report as active and implemented
        self.assertTrue(all(t["is_implemented"] for t in tools))

    def test_classify_request(self):
        cls1 = agent.classify_request("Investigate batch B2231")
        self.assertEqual(cls1["intent"], "investigate_batch")
        self.assertEqual(cls1["entities"]["batch_id"], "B2231")

        cls2 = agent.classify_request("Check cold-chain temperature excursions")
        self.assertEqual(cls2["intent"], "check_environment")

        cls3 = agent.classify_request("What is seasonal demand shortage for PARA-500?")
        self.assertEqual(cls3["intent"], "forecast_demand")
        self.assertEqual(cls3["entities"]["product_id"], "PARA-500")

    def test_run_investigation_deterministic_fallback(self):
        """Verifies investigation runs completely without API keys and transparently labels engine."""
        with patch.dict(os.environ, {}, clear=False):
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]
            report = agent.run_investigation("Investigate batch B2231 and recommend next steps")
            self.assertIn("Rule-Based", report["engine_mode"])
            self.assertIn("B2231", report["query"])
            self.assertTrue(report["requires_human_approval"])
            self.assertGreater(len(report["findings"]), 0)

    def test_run_investigation_with_openai_key_labeled(self):
        """Verifies engine transparently indicates LLM-Assisted mode when key is configured."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-mock-key-for-testing-purposes-12345"}):
            report = agent.run_investigation("Investigate batch B2231")
            self.assertIn("OpenAI", report["engine_mode"])

    def test_options_comparison_without_data(self):
        """Verifies compare_options honestly refuses comparison when inventory data is missing."""
        comp = agent.compare_options(
            {"type": "recall_replacement", "batch_id": "B100"},
            {"inventory_available": False},
        )
        self.assertEqual(comp["status"], "insufficient_data")
        self.assertEqual(len(comp["options"]), 0)


if __name__ == "__main__":
    unittest.main()
