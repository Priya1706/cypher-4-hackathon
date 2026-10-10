"""
modules/seasonal_demand.py
Module C — Seasonal Demand Intelligence for Arogya Pharma Distributors.

Provides:
- load_historical_demand()
- calculate_seasonal_demand(product_id: str, period: Optional[str]) -> dict
- calculate_stock_gap(product_id: str, period: Optional[str]) -> dict
- forecast_seasonal_demand(product_id: str) -> dict
- inspect_supplementary_research() -> dict

Estimates are calculated transparently using verifiable historical dispatches,
usable inventory (excluding recalled/expired stock), incoming purchase orders,
and supplier lead times/MOQs.
"""

import os
from math import ceil
from datetime import datetime, date
from typing import Any, Dict, List, Optional
import pandas as pd

import modules.common as common

PROJECT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DEFAULT_DATA_DIR = os.path.abspath(os.environ.get("BATCHGUARD_DATA_DIR", PROJECT_DATA_DIR))
# External Kaggle sales remain isolated from whichever distributor dataset is configured.
EXTERNAL_PHARMACY_DATA_DIR = PROJECT_DATA_DIR
EXTERNAL_PHARMACY_CATEGORIES = ("M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06")
OFFICIAL_PS07_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "official_dataset"))


def get_forecast_source() -> str:
    """Return the optional weekly ML data source; Kaggle remains the default."""
    return os.environ.get("BATCHGUARD_FORECAST_SOURCE", "kaggle").strip().lower()


def forecast_weekly_experiment(
    identifier: Optional[str] = None,
    data_dir: Optional[str] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """Route to the isolated Kaggle or official PS-07 weekly forecasting path."""
    selected_source = (source or get_forecast_source()).strip().lower()
    if selected_source == "official":
        if not identifier:
            return {"success": False, "status": "missing_identifier", "message": "Select an official PS-07 product SKU."}
        return forecast_official_weekly_dispatches(identifier, data_dir=data_dir)
    if selected_source == "kaggle":
        category = identifier or EXTERNAL_PHARMACY_CATEGORIES[0]
        return forecast_external_weekly_sales(category, data_dir=data_dir)
    return {
        "success": False,
        "status": "invalid_source",
        "message": "BATCHGUARD_FORECAST_SOURCE must be 'kaggle' or 'official'.",
    }


def load_official_weekly_dispatches(
    data_dir: Optional[str] = None,
    product_sku: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate actual PS-07 dispatch rows into observed SKU-week totals only."""
    base = data_dir or OFFICIAL_PS07_DATA_DIR
    path = os.path.join(base, "dispatches.csv")
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig")
    except (OSError, UnicodeError, ValueError, pd.errors.ParserError) as exc:
        return {"success": False, "status": "data_error", "message": f"Could not read official dispatch data: {exc}"}

    required = ["date", "sku", "qty"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        return {"success": False, "status": "invalid_schema", "message": f"Official dispatch data is missing: {', '.join(missing)}."}

    dates = pd.to_datetime(frame["date"], errors="coerce", format="mixed")
    quantities = pd.to_numeric(frame["qty"], errors="coerce").replace([float("inf"), float("-inf")], float("nan"))
    clean = pd.DataFrame({"date": dates, "sku": frame["sku"].astype(str).str.strip().str.upper(), "qty": quantities})
    valid_mask = clean["date"].notna() & clean["qty"].notna() & clean["sku"].ne("")
    invalid_rows = int((~valid_mask).sum())
    clean = clean.loc[valid_mask].copy()
    if product_sku:
        clean = clean[clean["sku"] == str(product_sku).strip().upper()]
    if clean.empty:
        return {"success": False, "status": "insufficient_data", "message": "No valid official dispatch rows are available for the selected product SKU.", "invalid_rows_dropped": invalid_rows}

    clean["week"] = clean["date"].dt.to_period("W-SUN").dt.end_time.dt.normalize()
    weekly = clean.groupby(["sku", "week"], as_index=False, sort=True)["qty"].sum()
    return {
        "success": True,
        "weekly": weekly,
        "product_skus": sorted(weekly["sku"].unique().tolist()),
        "invalid_rows_dropped": invalid_rows,
        "date_start": clean["date"].min().date().isoformat(),
        "date_end": clean["date"].max().date().isoformat(),
    }


def forecast_official_weekly_dispatches(
    product_sku: str,
    data_dir: Optional[str] = None,
    n_lags: int = 4,
    test_fraction: float = 0.2,
) -> Dict[str, Any]:
    """Forecast weekly dispatched quantities from synthetic PS-07 records when history permits."""
    loaded = load_official_weekly_dispatches(data_dir=data_dir, product_sku=product_sku)
    if not loaded.get("success"):
        return loaded
    if not isinstance(n_lags, int) or n_lags < 1 or not isinstance(test_fraction, (int, float)) or not 0 < test_fraction < 0.5:
        return {"success": False, "status": "invalid_parameters", "message": "Use positive n_lags and test_fraction between 0 and 0.5."}

    weekly = loaded["weekly"].sort_values("week")
    series = weekly.set_index("week")["qty"].astype(float)
    if len(series) > 1 and not (series.index.to_series().diff().dropna() == pd.Timedelta(days=7)).all():
        return {
            "success": False,
            "status": "insufficient_data",
            "message": "Weekly dispatch history has missing weeks; no weeks were filled or interpolated, so a regular weekly forecast was not run.",
            "weekly_observations": len(series),
            "invalid_rows_dropped": loaded["invalid_rows_dropped"],
        }

    lagged = pd.DataFrame({"target": series})
    for lag in range(1, n_lags + 1):
        lagged[f"lag_{lag}"] = series.shift(lag)
    samples = lagged.dropna()
    test_count = max(3, ceil(len(samples) * test_fraction))
    train_count = len(samples) - test_count
    if train_count < 8 or test_count < 3:
        return {
            "success": False,
            "status": "insufficient_data",
            "message": (
                f"Only {len(series)} observed weekly SKU totals are available; this model needs at least "
                f"{n_lags + 11} regular weeks for lag features, eight training samples, and three chronological test weeks."
            ),
            "weekly_observations": len(series),
            "invalid_rows_dropped": loaded["invalid_rows_dropped"],
        }

    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_absolute_error
    except ImportError:
        return {"success": False, "status": "dependency_unavailable", "message": "Install scikit-learn to run the official dispatch forecasting experiment."}

    train, test = samples.iloc[:train_count], samples.iloc[train_count:]
    features = [f"lag_{lag}" for lag in range(1, n_lags + 1)]
    model = RandomForestRegressor(n_estimators=100, min_samples_leaf=2, random_state=42, n_jobs=1)
    model.fit(train[features], train["target"])
    predictions = model.predict(test[features])
    baseline = test["lag_1"].to_numpy()
    final_model = RandomForestRegressor(n_estimators=100, min_samples_leaf=2, random_state=42, n_jobs=1)
    final_model.fit(samples[features], samples["target"])
    latest = pd.DataFrame([{f"lag_{lag}": float(series.iloc[-lag]) for lag in range(1, n_lags + 1)}])
    backtest = [
        {"date": timestamp.date().isoformat(), "actual": float(actual), "model_prediction": float(prediction), "baseline_prediction": float(base)}
        for timestamp, actual, prediction, base in zip(test.index, test["target"], predictions, baseline)
    ]
    return {
        "success": True,
        "status": "calculated",
        "dataset_label": "Synthetic PS-07 historical dispatch activity; not validated customer demand or annual seasonality",
        "product_sku": str(product_sku).strip().upper(),
        "model": "Random Forest Regressor",
        "n_lags": n_lags,
        "forecast_date": (series.index[-1] + pd.Timedelta(days=7)).date().isoformat(),
        "forecast": float(final_model.predict(latest[features])[0]),
        "model_mae": float(mean_absolute_error(test["target"], predictions)),
        "baseline_name": "Previous-week dispatches",
        "baseline_mae": float(mean_absolute_error(test["target"], baseline)),
        "train_end_date": train.index[-1].date().isoformat(),
        "test_start_date": test.index[0].date().isoformat(),
        "final_model_train_through_date": samples.index[-1].date().isoformat(),
        "weekly_observations": len(series),
        "backtest": backtest,
        "limitation": "This experiment forecasts synthetic PS-07 historical dispatch activity only; dispatches are not validated customer demand, and the short history does not establish annual seasonality or real-world forecasting accuracy.",
    }


def load_historical_demand(data_dir: Optional[str] = None) -> pd.DataFrame:
    """
    Loads historical demand / dispatch records from historical_demand.csv.
    """
    base = data_dir or DEFAULT_DATA_DIR
    df, _ = common.load_csv_as_dataframe(
        os.path.join(base, "historical_demand.csv"),
        required_columns=["date", "warehouse", "sku", "qty"],
    )
    if df.empty:
        # PS-07 supplies dispatches rather than a separate historical-demand file.
        df, _ = common.load_csv_as_dataframe(
            os.path.join(base, "dispatches.csv"),
            required_columns=["date", "sku", "qty"],
        )
    if not df.empty:
        df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0)
    return df


def inspect_supplementary_research(data_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Inspects seasonal_diseases_vaccines.csv research file.
    Reports its actual columns and contents, explicitly noting its geographic context.
    """
    base = data_dir or DEFAULT_DATA_DIR
    path = os.path.join(base, "seasonal_diseases_vaccines.csv")
    if not os.path.exists(path):
        # Also check parent directory
        parent_path = os.path.join(os.path.dirname(base), "seasonal_diseases_vaccines.csv")
        if os.path.exists(parent_path):
            path = parent_path
        else:
            return {
                "available": False,
                "message": "Supplementary research file 'seasonal_diseases_vaccines.csv' not found.",
                "records": [],
            }

    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
        records = df.to_dict(orient="records")
        return {
            "available": True,
            "columns": list(df.columns),
            "record_count": len(df),
            "records": records,
            "limitations_notice": (
                "Notice: This dataset lists general temperate climate patterns (e.g. Winter flu/RSV). "
                "It is supplementary background research and not verified Karnataka/Indian epidemiological surveillance."
            ),
        }
    except Exception as e:
        return {"available": False, "message": f"Error reading research file: {str(e)}"}


def forecast_external_weekly_sales(
    category: str,
    data_dir: Optional[str] = None,
    n_lags: int = 4,
    test_fraction: float = 0.2,
) -> Dict[str, Any]:
    """Run an isolated one-week-ahead forecasting experiment on external pharmacy sales.

    Features are previous observed weekly values. The final holdout is chronological,
    and later holdout targets are never used to predict earlier holdout weeks.
    """
    if category not in EXTERNAL_PHARMACY_CATEGORIES:
        return {
            "success": False,
            "status": "invalid_category",
            "message": f"Choose one of the supported external categories: {', '.join(EXTERNAL_PHARMACY_CATEGORIES)}.",
        }
    if not isinstance(n_lags, int) or n_lags < 1:
        return {"success": False, "status": "invalid_parameters", "message": "n_lags must be a positive integer."}
    if not isinstance(test_fraction, (int, float)) or not 0 < test_fraction < 0.5:
        return {"success": False, "status": "invalid_parameters", "message": "test_fraction must be greater than 0 and less than 0.5."}

    path = os.path.join(data_dir or EXTERNAL_PHARMACY_DATA_DIR, "salesweekly.csv")
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except (OSError, UnicodeError, ValueError, pd.errors.ParserError) as exc:
        return {"success": False, "status": "data_error", "message": f"Could not read external sales data: {exc}"}

    missing_columns = [column for column in ("datum", category) if column not in df.columns]
    if missing_columns:
        return {
            "success": False,
            "status": "invalid_schema",
            "message": f"External sales data is missing required column(s): {', '.join(missing_columns)}.",
        }

    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_absolute_error
    except ImportError:
        return {
            "success": False,
            "status": "dependency_unavailable",
            "message": "Install scikit-learn to run the external sales forecasting experiment.",
        }

    dates = pd.to_datetime(df["datum"], errors="coerce", format="mixed")
    sales = pd.to_numeric(df[category], errors="coerce").replace([float("inf"), float("-inf")], float("nan"))
    invalid_dates = int(dates.isna().sum())
    invalid_sales = int((dates.notna() & sales.isna()).sum())
    clean = pd.DataFrame({"date": dates, "sales": sales}).dropna(subset=["date", "sales"])
    if clean.empty:
        return {
            "success": False,
            "status": "insufficient_data",
            "message": "No rows with both a valid date and numeric sales value remain after cleaning.",
            "data_quality": {"invalid_dates_dropped": invalid_dates, "missing_or_invalid_sales_dropped": invalid_sales},
        }

    # A duplicate date is represented once using the mean; then sort before creating lags.
    series = clean.groupby("date")["sales"].mean().sort_index()
    lagged = pd.DataFrame({"target": series})
    for lag in range(1, n_lags + 1):
        lagged[f"lag_{lag}"] = series.shift(lag)
    samples = lagged.dropna()

    test_count = max(3, ceil(len(samples) * test_fraction))
    train_count = len(samples) - test_count
    if train_count < 8 or test_count < 3:
        return {
            "success": False,
            "status": "insufficient_data",
            "message": "Not enough clean weekly history for lag features and a useful chronological train/test split.",
            "data_quality": {"invalid_dates_dropped": invalid_dates, "missing_or_invalid_sales_dropped": invalid_sales},
        }

    train = samples.iloc[:train_count]
    test = samples.iloc[train_count:]
    feature_columns = [f"lag_{lag}" for lag in range(1, n_lags + 1)]
    model = RandomForestRegressor(n_estimators=100, min_samples_leaf=2, random_state=42, n_jobs=1)
    model.fit(train[feature_columns], train["target"])
    model_predictions = model.predict(test[feature_columns])
    baseline_predictions = test["lag_1"].to_numpy()
    model_mae = float(mean_absolute_error(test["target"], model_predictions))
    baseline_mae = float(mean_absolute_error(test["target"], baseline_predictions))

    # Preserve the chronological holdout above for evaluation, then refit a
    # separate final model on every observed lag/target pair for deployment.
    final_model = RandomForestRegressor(n_estimators=100, min_samples_leaf=2, random_state=42, n_jobs=1)
    final_model.fit(samples[feature_columns], samples["target"])
    latest_features = pd.DataFrame(
        [{f"lag_{lag}": float(series.iloc[-lag]) for lag in range(1, n_lags + 1)}]
    )
    next_week_forecast = float(final_model.predict(latest_features[feature_columns])[0])
    backtest = [
        {
            "date": timestamp.date().isoformat(),
            "actual": float(actual),
            "model_prediction": float(prediction),
            "baseline_prediction": float(baseline),
        }
        for timestamp, actual, prediction, baseline in zip(
            test.index, test["target"], model_predictions, baseline_predictions
        )
    ]

    return {
        "success": True,
        "status": "calculated",
        "dataset_label": "External Kaggle pharmacy sales data; not Arogya Pharma demand",
        "category": category,
        "model": "Random Forest Regressor",
        "n_lags": n_lags,
        "forecast_date": (series.index[-1] + pd.Timedelta(weeks=1)).date().isoformat(),
        "forecast": next_week_forecast,
        "model_mae": model_mae,
        "baseline_name": "Previous-week sales",
        "baseline_mae": baseline_mae,
        "train_weeks": int(len(train)),
        "test_weeks": int(len(test)),
        "train_end_date": train.index[-1].date().isoformat(),
        "test_start_date": test.index[0].date().isoformat(),
        "final_model_train_through_date": samples.index[-1].date().isoformat(),
        "backtest": backtest,
        "backtest_note": "Chronological one-week-ahead holdout; prior observed values are used as lags for later holdout predictions.",
        "data_quality": {
            "invalid_dates_dropped": invalid_dates,
            "missing_or_invalid_sales_dropped": invalid_sales,
            "duplicate_dates_averaged": int(len(clean) - clean["date"].nunique()),
        },
        "limitation": "This experiment measures held-out performance on this external dataset only; it does not establish forecasting accuracy for Arogya Pharma or real-world demand.",
    }


def calculate_seasonal_demand(
    product_id: str,
    period: Optional[str] = None,
    data_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculates seasonal demand estimate for a given SKU/product using historical demand records.
    Method: Rolling weighted historical average with a conservative seasonal surge coefficient.
    """
    df = load_historical_demand(data_dir)
    target_sku = str(product_id).strip().upper()

    if df.empty:
        return common.make_result("error", {}, warnings=["Historical demand dataset is empty or missing."])

    sku_records = df[df["sku"].astype(str).str.strip().str.upper() == target_sku]
    if sku_records.empty:
        # Check if matched by partial name
        return {
            "success": False,
            "status": "insufficient_data",
            "sku": target_sku,
            "estimate": 0,
            "method": "No historical records",
            "assumptions": ["Insufficient historical dispatch records for this SKU."],
            "warnings": [f"No historical demand data found for '{target_sku}'. Cannot generate reliable forecast."],
            "evidence": {"records_found": 0},
        }

    # Aggregate by date across warehouses
    monthly_totals = sku_records.groupby("date")["qty"].sum().sort_index()
    record_count = len(monthly_totals)

    if record_count < 3:
        # Insufficient history for trend analysis
        baseline_avg = int(monthly_totals.mean())
        return {
            "success": True,
            "status": "limited_history",
            "sku": target_sku,
            "estimate": baseline_avg,
            "method": "Simple Mean (Limited Data)",
            "assumptions": ["Fewer than 3 historical periods available; using simple mean without surge modeling."],
            "warnings": ["Forecast confidence is low due to limited historical depth."],
            "evidence": {"periods_evaluated": record_count, "history": monthly_totals.to_dict()},
        }

    # Explainable calculation:
    # 1. Base demand = Average of the most recent 3 recorded periods
    recent_periods = monthly_totals.iloc[-3:]
    base_avg = recent_periods.mean()

    # 2. Peak historical demand ratio
    peak_history = monthly_totals.max()
    surge_multiplier = min(1.25, peak_history / base_avg if base_avg > 0 else 1.0)

    # 3. Forecast for next operational period (e.g. 30 days)
    projected_demand = int(base_avg * surge_multiplier)

    assumptions = [
        f"Baseline demand calculated as 3-period average ({int(base_avg)} units).",
        f"Seasonal surge multiplier ({surge_multiplier:.2f}x) derived from peak historical dispatches.",
        "Projections assume normal distributor supply channels without catastrophic disruptions.",
    ]

    return {
        "success": True,
        "status": "calculated",
        "sku": target_sku,
        "estimate": projected_demand,
        "baseline_demand": int(base_avg),
        "surge_multiplier": round(surge_multiplier, 2),
        "method": "Weighted Recent Average with Historical Peak Surge Multiplier",
        "assumptions": assumptions,
        "warnings": [],
        "evidence": {
            "historical_monthly_totals": monthly_totals.to_dict(),
            "periods_evaluated": record_count,
            "synthetic_data_notice": "Estimates derived from distributor historical dispatch dataset.",
        },
    }


def calculate_stock_gap(
    product_id: str,
    period: Optional[str] = None,
    data_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compares projected seasonal demand against usable warehouse inventory and incoming purchase orders.
    Calculates potential stock deficit and supplier replenishment requirements.
    
    Usable inventory strictly excludes:
    - Batches subject to active recall notices
    - Batches that have expired
    """
    base = data_dir or DEFAULT_DATA_DIR
    target_sku = str(product_id).strip().upper()

    # 1. Get projected demand
    demand_res = calculate_seasonal_demand(target_sku, period, data_dir)
    projected_demand = demand_res.get("estimate", 0)

    # 2. Get inventory and exclude recalled/expired
    inv_df, _ = common.load_csv_as_dataframe(common.dataset_file_path("inventory.csv", base))
    recall_df, _ = common.load_csv_as_dataframe(os.path.join(base, "recalls.csv"))
    po_df, _ = common.load_csv_as_dataframe(os.path.join(base, "purchase_orders.csv"))
    supp_df, _ = common.load_csv_as_dataframe(os.path.join(base, "suppliers.csv"))

    # Recalled batches set
    recalled_batches = set()
    if not recall_df.empty:
        for _, r in recall_df.iterrows():
            for b in str(r["batches"]).replace(";", ",").split(","):
                if b.strip():
                    recalled_batches.add(b.strip().upper())

    # Usable warehouse stock
    total_warehouse_qty = 0
    usable_warehouse_qty = 0
    quarantined_qty = 0
    expired_qty = 0
    today_d = date.today()

    if not inv_df.empty:
        sku_inv = inv_df[inv_df["sku"].astype(str).str.strip().str.upper() == target_sku]
        for _, row in sku_inv.iterrows():
            b_id = str(row["batch"]).strip().upper()
            qty = int(row["qty"])
            total_warehouse_qty += qty

            exp_d = common.parse_date_safely(row["expiry_date"])
            if b_id in recalled_batches:
                quarantined_qty += qty
            elif exp_d and exp_d < today_d:
                expired_qty += qty
            else:
                usable_warehouse_qty += qty

    # 3. Incoming Purchase Orders
    incoming_po_qty = 0
    po_records = []
    if not po_df.empty:
        sku_pos = po_df[po_df["sku"].astype(str).str.strip().str.upper() == target_sku]
        for _, r in sku_pos.iterrows():
            status = str(r["status"]).strip().lower()
            if status in ("confirmed", "in-transit", "approved"):
                qty = int(r["qty"])
                incoming_po_qty += qty
                po_records.append({
                    "po": str(r["po"]),
                    "qty": qty,
                    "expected_date": str(r["expected_date"]),
                    "status": str(r["status"]),
                })

    # Total available pipeline supply
    total_supply = usable_warehouse_qty + incoming_po_qty
    stock_gap = max(0, projected_demand - total_supply)
    has_shortage = stock_gap > 0

    # 4. Supplier Context (MOQ, Lead Time)
    supplier_info = {}
    recommended_order_qty = 0
    if not supp_df.empty:
        sku_supp = supp_df[supp_df["sku"].astype(str).str.strip().str.upper() == target_sku]
        if not sku_supp.empty:
            s_row = sku_supp.iloc[0]
            lead_time = int(s_row["lead_time_days"])
            moq = int(s_row["moq"])
            supplier_info = {
                "manufacturer": str(s_row["manufacturer"]),
                "lead_time_days": lead_time,
                "moq": moq,
                "return_window_days": int(s_row["return_window_days"]),
            }
            if has_shortage:
                # Order at least MOQ or the shortage gap rounded up
                recommended_order_qty = max(stock_gap, moq)

    warnings = []
    if has_shortage:
        warnings.append(
            f"PROJECTED SHORTAGE: Deficit of {stock_gap} units identified for {target_sku} during forecasted period."
        )
    if quarantined_qty > 0:
        warnings.append(
            f"Notice: {quarantined_qty} units excluded from usable inventory due to active recall notices."
        )

    return {
        "success": True,
        "status": "shortage_detected" if has_shortage else "sufficient_stock",
        "sku": target_sku,
        "projected_demand": projected_demand,
        "usable_warehouse_stock": usable_warehouse_qty,
        "quarantined_stock": quarantined_qty,
        "expired_stock": expired_qty,
        "incoming_po_stock": incoming_po_qty,
        "total_available_supply": total_supply,
        "stock_gap": stock_gap,
        "has_shortage": has_shortage,
        "recommended_order_qty": recommended_order_qty,
        "supplier_info": supplier_info,
        "incoming_purchase_orders": po_records,
        "warnings": warnings,
        "evidence": {
            "demand_calculation": demand_res.get("method"),
            "demand_assumptions": demand_res.get("assumptions"),
            "active_pos_counted": len(po_records),
        },
    }


def forecast_seasonal_demand(
    product_id: str,
    data_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified entry point conforming to the shared module interface contract:
    Returns dict with keys: 'status', 'available', 'estimate', 'stock_gap', 'method', 'assumptions', 'evidence'.
    """
    target_sku = str(product_id).strip().upper()
    gap_res = calculate_stock_gap(target_sku, data_dir=data_dir)
    demand_res = calculate_seasonal_demand(target_sku, data_dir=data_dir)

    status = "success" if gap_res["success"] else "insufficient_data"
    return {
        "success": gap_res["success"],
        "status": status,
        "available": True,
        "product_id": target_sku,
        "sku": target_sku,
        "estimate": gap_res["projected_demand"],
        "stock_gap": gap_res["stock_gap"],
        "has_shortage": gap_res["has_shortage"],
        "usable_stock": gap_res["usable_warehouse_stock"],
        "incoming_po": gap_res["incoming_po_stock"],
        "recommended_po_qty": gap_res["recommended_order_qty"],
        "supplier_lead_time_days": gap_res["supplier_info"].get("lead_time_days", "N/A"),
        "method": demand_res.get("method", "Historical Weighted Average"),
        "assumptions": demand_res.get("assumptions", []),
        "warnings": gap_res.get("warnings", []),
        "evidence": {
            "demand_evidence": demand_res.get("evidence", {}),
            "stock_gap_evidence": gap_res.get("evidence", {}),
            "supplier_info": gap_res.get("supplier_info", {}),
        },
        "message": f"Forecast for {target_sku}: projected demand {gap_res['projected_demand']}, stock gap {gap_res['stock_gap']}.",
    }
