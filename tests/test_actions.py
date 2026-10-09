"""
tests/test_actions.py
Unit tests for Module D: Action Management & Governance.
Verifies simulated action creation, approval, rejection, state transitions,
persistence, and dispatch validation against live inventory and recall data.
"""

import os
import tempfile
import unittest

import modules.actions as actions

class TestActionsModule(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_store_path = os.path.join(self.temp_dir.name, "test_actions_store.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_action_with_pending_status(self):
        """Verify created action has unique ID, pending status, and persistence."""
        act = actions.create_action(
            action_type="quarantine_batch",
            details={"batch_id": "B2231", "reason": "Class I recall"},
            file_path=self.test_store_path,
        )
        self.assertTrue(act["action_id"].startswith("ACT-"))
        self.assertEqual(act["status"], "pending")
        self.assertTrue(act["is_simulated"])

        fetched = actions.get_action(act["action_id"], file_path=self.test_store_path)
        self.assertEqual(fetched["action_id"], act["action_id"])

    def test_review_action_approval_and_rejection(self):
        """Verify action review transitions to approved and rejected with reviewer metadata."""
        act1 = actions.create_action("po_request", {"qty": 500}, file_path=self.test_store_path)
        app_res = actions.review_action(
            act1["action_id"], "approved", "Dr. R. Sharma (QP)", file_path=self.test_store_path
        )
        self.assertEqual(app_res["status"], "approved")
        self.assertEqual(app_res["reviewer"], "Dr. R. Sharma (QP)")

        act2 = actions.create_action("dispatch_override", {"qty": 10}, file_path=self.test_store_path)
        rej_res = actions.review_action(
            act2["action_id"], "rejected", "QA Compliance Lead", file_path=self.test_store_path
        )
        self.assertEqual(rej_res["status"], "rejected")

    def test_invalid_state_transition_blocked(self):
        """Verify already approved or rejected action cannot be re-reviewed."""
        act = actions.create_action("test_act", {}, file_path=self.test_store_path)
        actions.review_action(act["action_id"], "approved", "Reviewer 1", file_path=self.test_store_path)

        # Attempt to reject approved action
        second_try = actions.review_action(
            act["action_id"], "rejected", "Reviewer 2", file_path=self.test_store_path
        )
        self.assertEqual(second_try["status"], "error")
        self.assertIn("Invalid state transition", second_try["message"])

    def test_validate_dispatch_blocks_recalled_batch_b2231(self):
        """Verify real B2231 recall stops simulated dispatch."""
        res = actions.validate_dispatch("B2231", 50)
        self.assertFalse(res["valid"])
        self.assertEqual(res["status"], "blocked_recall")
        self.assertIn("active recall notice", res["reason"])

    def test_validate_dispatch_clean_batch_b2240_stock_limits(self):
        """Verify clean batch B2240 (400 units in stock) validates or rejects based on stock."""
        # 100 units should pass
        res_ok = actions.validate_dispatch("B2240", 100)
        self.assertTrue(res_ok["valid"])
        self.assertEqual(res_ok["status"], "valid")

        # 500 units should fail (only 400 available)
        res_fail = actions.validate_dispatch("B2240", 500)
        self.assertFalse(res_fail["valid"])
        self.assertEqual(res_fail["status"], "insufficient_stock")
        self.assertEqual(res_fail["available_stock"], 400)

    def test_validate_dispatch_zero_or_negative_quantity(self):
        """Verify dispatch rejects invalid quantities."""
        res = actions.validate_dispatch("B2240", 0)
        self.assertFalse(res["valid"])
        self.assertEqual(res["status"], "invalid_quantity")

if __name__ == "__main__":
    unittest.main()

