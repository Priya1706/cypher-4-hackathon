"""
modules/inventory.py
Module A — Inventory and Traceability for Arogya Pharma Distributors.

Provides:
- load_inventory()
- trace_batch(batch_id: str) -> dict
- check_recall(batch_id: str) -> dict
- get_affected_customers(batch_id: str) -> dict
- check_expiry() -> dict
- check_dispatch_order() -> dict
"""

import os
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
import pandas as pd

import modules.common as common

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def get_data_path(filename: str, data_dir: Optional[str] = None) -> str:
    base = data_dir or DEFAULT_DATA_DIR
    return os.path.join(base, filename)


def load_inventory(data_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Loads all inventory-related datasets into DataFrames with schema validation.
    """
    base = data_dir or DEFAULT_DATA_DIR
    warnings: List[str] = []

    inv_df, w1 = common.load_csv_as_dataframe(
        os.path.join(base, "inventory.csv"),
        required_columns=["sku", "batch", "warehouse", "qty", "mfg_date", "expiry_date"],
    )
    prod_df, w2 = common.load_csv_as_dataframe(
        os.path.join(base, "products.csv"),
        required_columns=["sku", "molecule", "brand", "category", "storage", "critical_drug"],
    )
    disp_df, w3 = common.load_csv_as_dataframe(
        os.path.join(base, "dispatches.csv"),
        required_columns=["date", "customer", "sku", "batch", "qty"],
    )
    cust_df, w4 = common.load_csv_as_dataframe(
        os.path.join(base, "customers.csv"),
        required_columns=["customer", "type", "location", "credit_terms"],
    )
    recall_df, w5 = common.load_csv_as_dataframe(
        os.path.join(base, "recalls.csv"),
        required_columns=["date", "sku", "batches", "reason", "recall_class"],
    )
    supp_df, w6 = common.load_csv_as_dataframe(
        os.path.join(base, "suppliers.csv"),
        required_columns=["manufacturer", "sku", "lead_time_days", "moq", "return_window_days"],
    )

    warnings.extend(w1 + w2 + w3 + w4 + w5 + w6)

    return {
        "inventory": inv_df,
        "products": prod_df,
        "dispatches": disp_df,
        "customers": cust_df,
        "recalls": recall_df,
        "suppliers": supp_df,
        "warnings": warnings,
    }


def check_recall(batch_id: str, data_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Checks if the specified batch_id has an active regulatory or manufacturer recall notice.
    """
    clean_batch = str(batch_id).strip().upper()
    recall_path = get_data_path("recalls.csv", data_dir)
    recall_df, warnings = common.load_csv_as_dataframe(
        recall_path, required_columns=["date", "sku", "batches", "reason", "recall_class"]
    )

    if recall_df.empty:
        return common.make_result(
            status="error" if warnings else "not_recalled",
            data={"is_recalled": False, "batch_id": clean_batch},
            warnings=warnings,
            evidence={"recall_records_checked": 0},
            message=f"No recall records found or error reading recalls file for {clean_batch}.",
        )

    # Search for matching batch in recalls. Batches can be comma or space separated.
    for _, row in recall_df.iterrows():
        raw_batches = str(row["batches"]).replace(";", ",").split(",")
        batch_list = [b.strip().upper() for b in raw_batches if b.strip()]
        if clean_batch in batch_list:
            evidence = {
                "recall_date": str(row["date"]),
                "sku": str(row["sku"]),
                "reason": str(row["reason"]),
                "recall_class": str(row["recall_class"]),
                "matched_batch": clean_batch,
            }
            return {
                "success": True,
                "status": "recalled",
                "available": True,
                "is_recalled": True,
                "batch_id": clean_batch,
                "recall_details": evidence,
                "data": {"is_recalled": True, "details": evidence},
                "results": {"is_recalled": True, "details": evidence},
                "warnings": [
                    f"CRITICAL: Batch '{clean_batch}' is under active {row['recall_class']} recall for reason: {row['reason']}"
                ],
                "evidence": evidence,
                "message": f"Batch '{clean_batch}' is actively recalled.",
            }

    return {
        "success": True,
        "status": "not_recalled",
        "available": True,
        "is_recalled": False,
        "batch_id": clean_batch,
        "data": {"is_recalled": False},
        "results": {"is_recalled": False},
        "warnings": warnings,
        "evidence": {"records_checked": len(recall_df)},
        "message": f"No active recall notice found for batch '{clean_batch}'.",
    }


def trace_batch(batch_id: str, data_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Traces a batch across warehouse inventory and customer dispatches.
    Reports:
    - Product name, SKU, storage conditions
    - Total remaining warehouse stock
    - Warehouse location breakdown
    - Customer dispatches and quantities
    - Recall status
    """
    clean_batch = str(batch_id).strip().upper()
    data = load_inventory(data_dir)
    warnings = list(data["warnings"])

    inv_df = data["inventory"]
    prod_df = data["products"]
    disp_df = data["dispatches"]
    cust_df = data["customers"]

    if inv_df.empty:
        return common.make_result(
            status="error",
            data={},
            warnings=warnings or ["Inventory records could not be loaded."],
            message="Inventory records missing or empty.",
        )

    # Locate batch in inventory
    batch_rows = inv_df[inv_df["batch"].astype(str).str.strip().str.upper() == clean_batch]

    # Check dispatches even if remaining warehouse inventory is zero
    disp_rows = pd.DataFrame()
    if not disp_df.empty:
        disp_rows = disp_df[disp_df["batch"].astype(str).str.strip().str.upper() == clean_batch]

    if batch_rows.empty and disp_rows.empty:
        return {
            "success": False,
            "status": "not_found",
            "available": True,
            "batch_id": clean_batch,
            "data": {},
            "results": {},
            "warnings": [f"Batch '{clean_batch}' was not found in inventory or dispatch records."],
            "evidence": {},
            "message": f"Batch '{clean_batch}' not found.",
        }

    # Determine SKU
    sku = None
    if not batch_rows.empty:
        sku = str(batch_rows.iloc[0]["sku"]).strip()
    elif not disp_rows.empty:
        sku = str(disp_rows.iloc[0]["sku"]).strip()

    # Product details
    prod_info = {}
    if not prod_df.empty and sku:
        p_match = prod_df[prod_df["sku"].astype(str).str.strip() == sku]
        if not p_match.empty:
            prod_info = p_match.iloc[0].to_dict()

    # Calculate warehouse stock breakdown
    warehouses = []
    total_stock = 0
    if not batch_rows.empty:
        for _, r in batch_rows.iterrows():
            qty = int(r["qty"])
            total_stock += qty
            warehouses.append({
                "warehouse": str(r["warehouse"]),
                "qty": qty,
                "mfg_date": str(r["mfg_date"]),
                "expiry_date": str(r["expiry_date"]),
            })

    # Trace dispatches with customer metadata
    dispatches = []
    total_dispatched = 0
    if not disp_rows.empty:
        merged_disp = disp_rows.copy()
        if not cust_df.empty:
            merged_disp = merged_disp.merge(cust_df, on="customer", how="left")
        for _, r in merged_disp.iterrows():
            d_qty = int(r["qty"])
            total_dispatched += d_qty
            dispatches.append({
                "date": str(r["date"]),
                "customer": str(r["customer"]),
                "customer_type": str(r.get("type", "Unknown")),
                "location": str(r.get("location", "Unknown")),
                "qty": d_qty,
            })

    # Check recall status
    recall_res = check_recall(clean_batch, data_dir)
    is_recalled = recall_res.get("is_recalled", False)

    summary_data = {
        "batch_id": clean_batch,
        "sku": sku,
        "product_name": prod_info.get("brand", prod_info.get("molecule", sku or "N/A")),
        "molecule": prod_info.get("molecule", "N/A"),
        "category": prod_info.get("category", "N/A"),
        "storage": prod_info.get("storage", "N/A"),
        "critical_drug": prod_info.get("critical_drug", False),
        "total_warehouse_stock": total_stock,
        "available_stock": total_stock,  # explicitly provided for actions validation
        "warehouses": warehouses,
        "total_dispatched_qty": total_dispatched,
        "dispatches_count": len(dispatches),
        "is_recalled": is_recalled,
        "location": warehouses[0]["warehouse"] if warehouses else "Dispatched",
        "expiry_date": warehouses[0]["expiry_date"] if warehouses else "N/A",
    }

    if is_recalled:
        warnings.append(f"WARNING: Batch '{clean_batch}' has an active recall notice.")

    return {
        "success": True,
        "status": "success",
        "available": True,
        "batch_id": clean_batch,
        "data": summary_data,
        "results": summary_data,
        "dispatches": dispatches,
        "warnings": warnings,
        "evidence": {
            "warehouse_records": warehouses,
            "dispatches_count": len(dispatches),
            "total_dispatched_qty": total_dispatched,
            "recall_info": recall_res.get("evidence", {}),
        },
        "message": f"Successfully traced batch '{clean_batch}'.",
    }


def get_affected_customers(batch_id: str, data_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Traces customer distribution for a specific batch.
    Returns customer list, breakdown by customer type (Chemist vs Hospital),
    and total quantities dispatched.
    """
    clean_batch = str(batch_id).strip().upper()
    data = load_inventory(data_dir)
    disp_df = data["dispatches"]
    cust_df = data["customers"]

    if disp_df.empty:
        return common.make_result("error", {}, warnings=["No dispatch records found."])

    batch_dispatches = disp_df[disp_df["batch"].astype(str).str.strip().str.upper() == clean_batch]
    if batch_dispatches.empty:
        return {
            "success": True,
            "status": "no_dispatches",
            "batch_id": clean_batch,
            "total_dispatched_units": 0,
            "chemists_count": 0,
            "hospitals_count": 0,
            "customers": [],
            "warnings": [f"No customer dispatch records found for batch '{clean_batch}'."],
            "evidence": {},
        }

    merged = batch_dispatches.merge(cust_df, on="customer", how="left")
    customer_summary = []
    chemist_count = 0
    hospital_count = 0
    total_qty = 0

    # Aggregate by customer
    grouped = merged.groupby(["customer", "type", "location", "credit_terms"], as_index=False)["qty"].sum()
    for _, row in grouped.iterrows():
        c_type = str(row["type"]).strip()
        c_qty = int(row["qty"])
        total_qty += c_qty
        if "hospital" in c_type.lower():
            hospital_count += 1
        else:
            chemist_count += 1

        customer_summary.append({
            "customer": str(row["customer"]),
            "type": c_type,
            "location": str(row["location"]),
            "credit_terms": str(row["credit_terms"]),
            "total_qty_received": c_qty,
        })

    hospital_qty = sum(c["total_qty_received"] for c in customer_summary if "hospital" in c["type"].lower())
    chemist_qty = sum(c["total_qty_received"] for c in customer_summary if "hospital" not in c["type"].lower())

    return {
        "success": True,
        "status": "success",
        "batch_id": clean_batch,
        "total_dispatched_units": total_qty,
        "total_customers_count": len(customer_summary),
        "chemists_count": chemist_count,
        "hospitals_count": hospital_count,
        "hospital_dispatched_units": hospital_qty,
        "chemist_dispatched_units": chemist_qty,
        "customers": customer_summary,
        "warnings": [],
        "evidence": {
            "dispatch_entries": len(batch_dispatches),
            "unique_recipients": len(customer_summary),
            "hospital_dispatched_units": hospital_qty,
            "chemist_dispatched_units": chemist_qty,
        },
        "message": f"Identified {len(customer_summary)} customers ({chemist_count} chemists, {hospital_count} hospitals) for batch '{clean_batch}'.",
    }


def check_expiry(
    reference_date: Optional[str] = None,
    near_expiry_days: int = 30,
    data_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates inventory for expired and near-expiry stock against a reference date.
    Default near_expiry threshold is 30 days.
    """
    data = load_inventory(data_dir)
    inv_df = data["inventory"]
    prod_df = data["products"]

    if inv_df.empty:
        return common.make_result("error", {}, warnings=["Inventory data unavailable."])

    ref_d = common.parse_date_safely(reference_date) or date.today()

    expired_list = []
    near_expiry_list = []
    healthy_count = 0

    for _, row in inv_df.iterrows():
        exp_d = common.parse_date_safely(row["expiry_date"])
        if not exp_d:
            continue

        item = {
            "sku": str(row["sku"]),
            "batch": str(row["batch"]),
            "warehouse": str(row["warehouse"]),
            "qty": int(row["qty"]),
            "expiry_date": str(row["expiry_date"]),
        }

        if exp_d < ref_d:
            item["days_expired"] = (ref_d - exp_d).days
            expired_list.append(item)
        elif exp_d <= ref_d + timedelta(days=near_expiry_days):
            item["days_remaining"] = (exp_d - ref_d).days
            near_expiry_list.append(item)
        else:
            healthy_count += 1

    warnings = []
    if expired_list:
        warnings.append(f"CRITICAL: Found {len(expired_list)} batch(es) that have expired.")
    if near_expiry_list:
        warnings.append(f"WARNING: Found {len(near_expiry_list)} batch(es) expiring within {near_expiry_days} days.")

    return {
        "success": True,
        "status": "success",
        "available": True,
        "reference_date": ref_d.isoformat(),
        "expired_count": len(expired_list),
        "near_expiry_count": len(near_expiry_list),
        "healthy_count": healthy_count,
        "expired": expired_list,
        "near_expiry": near_expiry_list,
        "warnings": warnings,
        "evidence": {
            "total_batches_checked": len(inv_df),
            "near_expiry_threshold_days": near_expiry_days,
        },
        "message": f"Found {len(expired_list)} expired and {len(near_expiry_list)} near-expiry batch records.",
    }


def check_dispatch_order(data_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Audits dispatches for FEFO (First-Expired, First-Out) compliance.
    Flags instances where a batch with later expiration was dispatched while an
    earlier-expiring batch of the same SKU remained available.
    """
    data = load_inventory(data_dir)
    disp_df = data["dispatches"]
    inv_df = data["inventory"]

    if disp_df.empty or inv_df.empty:
        return common.make_result("error", {}, warnings=["Insufficient data for dispatch order audit."])

    violations = []
    # Map batch to expiry date
    batch_expiry = {}
    for _, r in inv_df.iterrows():
        b_key = (str(r["sku"]).strip(), str(r["batch"]).strip().upper())
        exp_d = common.parse_date_safely(r["expiry_date"])
        if exp_d:
            batch_expiry[b_key] = exp_d

    # Group dispatches by SKU and audit dates
    for (sku, _), group in disp_df.groupby(["sku", "date"]):
        # Check against available inventory batches for same SKU
        sku_batches = inv_df[inv_df["sku"].astype(str).str.strip() == sku]
        for _, disp_row in group.iterrows():
            d_batch = str(disp_row["batch"]).strip().upper()
            d_exp = batch_expiry.get((sku, d_batch))
            if not d_exp:
                continue

            for _, inv_row in sku_batches.iterrows():
                i_batch = str(inv_row["batch"]).strip().upper()
                if i_batch != d_batch and int(inv_row["qty"]) > 0:
                    i_exp = common.parse_date_safely(inv_row["expiry_date"])
                    if i_exp and i_exp < d_exp:
                        violations.append({
                            "sku": sku,
                            "dispatched_batch": d_batch,
                            "dispatched_expiry": d_exp.isoformat(),
                            "older_inventory_batch": i_batch,
                            "older_inventory_expiry": i_exp.isoformat(),
                            "dispatch_date": str(disp_row["date"]),
                            "remaining_older_qty": int(inv_row["qty"]),
                        })

    return {
        "success": True,
        "status": "success",
        "potential_fefo_deviations": len(violations),
        "deviations": violations,
        "warnings": [f"Detected {len(violations)} possible dispatch order (FEFO) deviation(s)."] if violations else [],
        "evidence": {"audited_dispatches": len(disp_df)},
        "message": f"Audit complete. Found {len(violations)} FEFO deviations.",
    }
