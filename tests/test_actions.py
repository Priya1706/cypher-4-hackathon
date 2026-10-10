"""
tests/test_actions.py
Unit tests for Module D: Action Management & Governance.
Verifies simulated action creation, approval, rejection, state transitions,
persistence, and dispatch validation against live inventory and recall data.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        self.assertTrue(app_res["is_simulated"])
        self.assertFalse(app_res["pharmacist_identity_authenticated"])
        self.assertEqual(
            app_res["review_status_note"],
            "Simulated review; pharmacist identity is not authenticated.",
        )

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

    def test_stage_excursion_review_saves_evidence_without_inventing_batches(self):
        excursion = {
            "warehouse": "Bengaluru",
            "cold_room": "CR-1",
            "start_time": "2026-11-09 02:00",
            "end_time": "2026-11-09 04:00",
            "peak_temp_c": 12.6,
            "limit_max": 8.0,
            "readings_above_limit": 3,
            "affected_batches": [],
        }
        staged = actions.stage_excursion_review(excursion, file_path=self.test_store_path)

        self.assertEqual(staged["status"], "created")
        action = staged["action"]
        self.assertEqual(action["status"], "pending")
        self.assertTrue(action["is_simulated"])
        self.assertFalse(action["pharmacist_identity_authenticated"])
        self.assertEqual(action["review_status_note"], actions.SIMULATED_REVIEW_NOTICE)
        self.assertEqual(action["details"]["facility"], "Bengaluru")
        self.assertEqual(action["details"]["cold_storage_unit"], "CR-1")
        self.assertEqual(
            action["details"]["event_time_window"],
            {"start": "2026-11-09 02:00", "end": "2026-11-09 04:00"},
        )
        self.assertEqual(action["details"]["peak_temperature_c"], 12.6)
        self.assertEqual(action["details"]["configured_upper_limit_c"], 8.0)
        self.assertEqual(action["details"]["readings_above_limit"], 3)
        self.assertEqual(action["details"]["affected_batches"], [])
        self.assertEqual(action["details"]["batch_identification_status"], "pending")
        self.assertIn("no affected batch IDs or quantities", action["details"]["batch_identification_note"])
        self.assertIn("Qualified human/QA/pharmacist review", action["details"]["review_requirement"])
        self.assertEqual(actions.list_pending_actions(self.test_store_path), [action])

        duplicate = actions.stage_excursion_review(excursion, file_path=self.test_store_path)
        self.assertEqual(duplicate["status"], "duplicate")
        self.assertEqual(duplicate["action"]["action_id"], action["action_id"])
        self.assertEqual(len(actions.list_all_actions(self.test_store_path)), 1)

    def test_stage_excursion_review_reports_persistence_failure(self):
        excursion = {
            "warehouse": "Bengaluru", "cold_room": "CR-1",
            "start_time": "2026-11-09 02:00", "end_time": "2026-11-09 04:00",
            "peak_temp_c": 12.6, "limit_max": 8.0, "readings_above_limit": 3,
            "affected_batches": [],
        }
        with patch.object(actions, "_save_store", return_value=False):
            result = actions.stage_excursion_review(excursion, file_path=self.test_store_path)
        self.assertEqual(result["status"], "error")
        self.assertIn("Failed to persist", result["message"])

    def test_environment_button_click_stages_reviewable_excursion_evidence(self):
        from streamlit.testing.v1 import AppTest
        import modules.environment as environment

        excursion = {
            "warehouse": "WH-Test", "cold_room": "CR-TEST",
            "start_time": "2026-11-09 02:00", "end_time": "2026-11-09 03:00",
            "peak_temp_c": 12.6, "limit_max": 8.0, "readings_above_limit": 2,
            "affected_batches": [], "at_risk_units": 0,
        }
        report = {
            "success": True, "status": "excursion_detected", "excursions_count": 1,
            "excursions": [excursion],
        }
        with patch.object(actions, "DEFAULT_STORAGE_FILE", self.test_store_path), patch.object(
            environment, "check_temperature_breach", return_value=report
        ):
            app_path = Path(__file__).resolve().parent.parent / "app.py"
            app = AppTest.from_file(str(app_path)).run(timeout=30)
            app.sidebar.radio[0].set_value("Environmental Risks").run(timeout=30)
            button = next(
                item for item in app.button
                if item.label == "Stage QA Quarantine Action for Excursion Stock"
            )
            button.click().run(timeout=30)

            self.assertEqual([error.message for error in app.exception], [])
            self.assertTrue(any("saved and staged" in item.value for item in app.success))
            staged = actions.list_pending_actions(self.test_store_path)

        self.assertEqual(len(staged), 1)
        action = staged[0]
        self.assertTrue(action["is_simulated"])
        self.assertFalse(action["pharmacist_identity_authenticated"])
        self.assertEqual(action["status"], "pending")
        self.assertEqual(action["details"]["affected_batches"], [])
        self.assertEqual(action["details"]["batch_identification_status"], "pending")
        self.assertNotIn("at_risk_units", action["details"])

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

