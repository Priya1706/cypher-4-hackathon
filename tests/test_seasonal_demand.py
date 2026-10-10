"""
tests/test_seasonal_demand.py
Unit tests for Module C: Seasonal Demand Intelligence.
Verifies historical demand calculation, stock-gap accounting for incoming POs and usable stock,
handling of unknown products, and supplementary research inspection.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
import modules.seasonal_demand as seasonal

class TestSeasonalDemandModule(unittest.TestCase):
    def _write_external_sales(self, directory, values, dates=None):
        if dates is None:
            dates = pd.date_range("2018-01-07", periods=len(values), freq="W-SUN")
        frame = pd.DataFrame({"datum": dates})
        for category in seasonal.EXTERNAL_PHARMACY_CATEGORIES:
            frame[category] = values
        path = os.path.join(directory, "salesweekly.csv")
        frame.to_csv(path, index=False)
        return path

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

    def test_external_weekly_forecast_uses_chronological_holdout_and_baseline(self):
        values = [10 + i * 0.4 + (i % 5) for i in range(80)]
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_external_sales(temp_dir, values)
            result = seasonal.forecast_external_weekly_sales("M01AB", data_dir=temp_dir)

        self.assertTrue(result["success"], result.get("message"))
        self.assertEqual(result["category"], "M01AB")
        self.assertEqual(result["model"], "Random Forest Regressor")
        self.assertGreater(result["forecast"], 0)
        self.assertGreaterEqual(result["model_mae"], 0)
        self.assertGreaterEqual(result["baseline_mae"], 0)
        self.assertLess(result["train_end_date"], result["test_start_date"])
        self.assertEqual(len(result["backtest"]), result["test_weeks"])
        self.assertGreater(result["forecast_date"], result["backtest"][-1]["date"])

    def test_external_forecast_refits_final_model_after_unchanged_holdout_evaluation(self):
        from math import ceil
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_absolute_error

        values = [12 + i * 0.3 + (i % 7) for i in range(80)]
        values[-8:] = [45, 20, 50, 18, 55, 16, 60, 14]
        dates = pd.date_range("2018-01-07", periods=len(values), freq="W-SUN")
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_external_sales(temp_dir, values, dates)
            result = seasonal.forecast_external_weekly_sales("M01AB", data_dir=temp_dir)

        self.assertTrue(result["success"], result.get("message"))
        observed = pd.Series(values, index=dates)
        samples = pd.DataFrame({"target": observed})
        for lag in range(1, result["n_lags"] + 1):
            samples[f"lag_{lag}"] = observed.shift(lag)
        samples = samples.dropna()
        test_count = max(3, ceil(len(samples) * 0.2))
        train = samples.iloc[:-test_count]
        test = samples.iloc[-test_count:]
        features = [f"lag_{lag}" for lag in range(1, result["n_lags"] + 1)]

        evaluation_model = RandomForestRegressor(
            n_estimators=100, min_samples_leaf=2, random_state=42, n_jobs=1
        )
        evaluation_model.fit(train[features], train["target"])
        expected_predictions = evaluation_model.predict(test[features])
        expected_model_mae = mean_absolute_error(test["target"], expected_predictions)
        expected_baseline_mae = mean_absolute_error(test["target"], test["lag_1"])

        final_model = RandomForestRegressor(
            n_estimators=100, min_samples_leaf=2, random_state=42, n_jobs=1
        )
        final_model.fit(samples[features], samples["target"])
        latest_features = pd.DataFrame(
            [{f"lag_{lag}": values[-lag] for lag in range(1, result["n_lags"] + 1)}]
        )
        expected_final_forecast = final_model.predict(latest_features[features])[0]

        self.assertEqual(result["train_end_date"], train.index[-1].date().isoformat())
        self.assertEqual(result["test_start_date"], test.index[0].date().isoformat())
        self.assertEqual(
            result["final_model_train_through_date"], samples.index[-1].date().isoformat()
        )
        self.assertEqual(result["model_mae"], expected_model_mae)
        self.assertEqual(result["baseline_mae"], expected_baseline_mae)
        self.assertEqual(
            [row["model_prediction"] for row in result["backtest"]],
            expected_predictions.tolist(),
        )
        self.assertEqual(result["forecast"], expected_final_forecast)

    def test_external_forecast_excludes_invalid_dates_and_sales(self):
        values = [10 + i * 0.5 for i in range(80)]
        dates = pd.date_range("2018-01-07", periods=len(values), freq="W-SUN").strftime("%m/%d/%Y").tolist()
        dates[0] = "not-a-date"
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_external_sales(temp_dir, values, dates)
            frame = pd.read_csv(os.path.join(temp_dir, "salesweekly.csv"), dtype=str)
            frame.loc[1, "M01AB"] = ""
            frame.loc[2, "M01AB"] = "not-a-number"
            frame.to_csv(os.path.join(temp_dir, "salesweekly.csv"), index=False)
            result = seasonal.forecast_external_weekly_sales("M01AB", data_dir=temp_dir)

        self.assertTrue(result["success"], result.get("message"))
        self.assertEqual(result["data_quality"]["invalid_dates_dropped"], 1)
        self.assertEqual(result["data_quality"]["missing_or_invalid_sales_dropped"], 2)

    def test_external_forecast_does_not_use_future_holdout_targets(self):
        values = [15 + i * 0.25 + (i % 6) for i in range(80)]
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_external_sales(temp_dir, values)
            first_result = seasonal.forecast_external_weekly_sales("M01AB", data_dir=temp_dir)

            values[-1] = 1_000_000
            self._write_external_sales(temp_dir, values)
            changed_future_result = seasonal.forecast_external_weekly_sales("M01AB", data_dir=temp_dir)

        self.assertTrue(first_result["success"])
        self.assertTrue(changed_future_result["success"])
        self.assertEqual(
            first_result["backtest"][0]["model_prediction"],
            changed_future_result["backtest"][0]["model_prediction"],
        )

    def test_external_forecast_handles_invalid_category_and_missing_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_external_sales(temp_dir, [10 + i for i in range(40)])
            invalid_category = seasonal.forecast_external_weekly_sales("SKU-AMOX-500", data_dir=temp_dir)
            pd.DataFrame({"datum": ["2018-01-07"], "M01AB": [10]}).drop(columns="datum").to_csv(
                os.path.join(temp_dir, "salesweekly.csv"), index=False
            )
            missing_date_column = seasonal.forecast_external_weekly_sales("M01AB", data_dir=temp_dir)

        self.assertEqual(invalid_category["status"], "invalid_category")
        self.assertEqual(missing_date_column["status"], "invalid_schema")

    def test_official_dispatches_can_supply_seasonal_demand_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pd.DataFrame([
                {"date": "2026-09-01", "customer": "C-1", "sku": "PH-X", "batch": "LOT-1", "qty": 4},
                {"date": "2026-09-01", "customer": "C-2", "sku": "PH-X", "batch": "LOT-2", "qty": 7},
            ]).to_csv(os.path.join(temp_dir, "dispatches.csv"), index=False)
            result = seasonal.load_historical_demand(temp_dir)

        self.assertEqual(result[["date", "sku", "qty"]].to_dict("records"), [
            {"date": "2026-09-01", "sku": "PH-X", "qty": 4},
            {"date": "2026-09-01", "sku": "PH-X", "qty": 7},
        ])

    def test_forecast_source_defaults_to_kaggle_and_can_select_official(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(seasonal.get_forecast_source(), "kaggle")
        with patch.dict(os.environ, {"BATCHGUARD_FORECAST_SOURCE": "official"}, clear=True):
            self.assertEqual(seasonal.get_forecast_source(), "official")
            routed = seasonal.forecast_weekly_experiment("PH-001")
            self.assertEqual(routed["status"], "insufficient_data")
        self.assertEqual(seasonal.forecast_weekly_experiment(source="other")["status"], "invalid_source")

    def test_official_dispatches_aggregate_by_observed_week_and_sku(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pd.DataFrame([
                {"date": "2026-09-17", "customer": "C1", "sku": "PH-001", "batch": "B1", "qty": 4},
                {"date": "2026-09-19", "customer": "C2", "sku": "PH-001", "batch": "B2", "qty": 6},
                {"date": "2026-09-20", "customer": "C3", "sku": "PH-002", "batch": "B3", "qty": 9},
                {"date": "2026-10-01", "customer": "C4", "sku": "PH-001", "batch": "B4", "qty": 3},
            ]).to_csv(os.path.join(temp_dir, "dispatches.csv"), index=False)
            result = seasonal.load_official_weekly_dispatches(temp_dir, "PH-001")

        self.assertTrue(result["success"])
        self.assertEqual(result["weekly"].to_dict("records"), [
            {"sku": "PH-001", "week": pd.Timestamp("2026-09-20"), "qty": 10},
            {"sku": "PH-001", "week": pd.Timestamp("2026-10-04"), "qty": 3},
        ])
        self.assertEqual(len(result["weekly"]), 2)  # No empty week was fabricated.

    def test_official_dispatch_forecast_reports_insufficient_real_history(self):
        result = seasonal.forecast_official_weekly_dispatches("PH-001")

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["weekly_observations"], 9)
        self.assertIn("needs at least 15 regular weeks", result["message"])

    def test_official_dispatch_forecast_uses_chronological_evaluation(self):
        dates = pd.date_range("2026-01-04", periods=24, freq="W-SUN")
        records = []
        for index, week in enumerate(dates):
            for offset, qty in ((2, 20 + index), (1, 5)):
                records.append({
                    "date": (week - pd.Timedelta(days=offset)).date().isoformat(),
                    "customer": f"C{index}-{offset}", "sku": "PH-TEST",
                    "batch": f"B{index}-{offset}", "qty": qty,
                })
        with tempfile.TemporaryDirectory() as temp_dir:
            pd.DataFrame(records).to_csv(os.path.join(temp_dir, "dispatches.csv"), index=False)
            result = seasonal.forecast_official_weekly_dispatches("PH-TEST", data_dir=temp_dir)

        self.assertTrue(result["success"], result.get("message"))
        self.assertEqual(result["weekly_observations"], 24)
        self.assertLess(result["train_end_date"], result["test_start_date"])
        self.assertEqual(len(result["backtest"]), 4)
        self.assertGreaterEqual(result["model_mae"], 0)
        self.assertGreaterEqual(result["baseline_mae"], 0)
        self.assertIn("Synthetic PS-07", result["dataset_label"])
        self.assertGreater(result["forecast_date"], result["backtest"][-1]["date"])

if __name__ == "__main__":
    unittest.main()

