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
from datetime import datetime, date
from typing import Any, Dict, List, Optional
import pandas as pd

import modules.common as common

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_historical_demand(data_dir: Optional[str] = None) -> pd.DataFrame:
    """
    Loads historical demand / dispatch records from historical_demand.csv.
    """
    base = data_dir or DEFAULT_DATA_DIR
    df, _ = common.load_csv_as_dataframe(
        os.path.join(base, "historical_demand.csv"),
        required_columns=["date", "warehouse", "sku", "qty"],
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
    inv_df, _ = common.load_csv_as_dataframe(os.path.join(base, "inventory.csv"))
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
