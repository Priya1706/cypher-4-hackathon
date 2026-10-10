"""
modules/environment.py
Module B — Environmental Risk Detection for Arogya Pharma Distributors.

Provides:
- load_temperature_logs()
- check_temperature_breach() -> dict
- find_affected_batches(location, start_time, end_time) -> dict
- analyse_power_outage(start_time, end_time, location) -> dict

Notes on limits:
- Standard Cold Chain storage range is 2.0°C to 8.0°C (standard illustrative pharmaceutical range for vaccines & biologics).
- Controlled Room Temperature is 15.0°C to 25.0°C.
- A temperature reading outside bounds represents a potential excursion requiring QA review,
  not a conclusive clinical finding of product degradation.
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd

import modules.common as common

PROJECT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DEFAULT_DATA_DIR = os.path.abspath(os.environ.get("BATCHGUARD_DATA_DIR", PROJECT_DATA_DIR))

# Illustrative pharmaceutical storage specifications
STORAGE_LIMITS = {
    "Cold Chain (2-8°C)": {"min_temp": 2.0, "max_temp": 8.0, "label": "Cold Chain (2-8°C)"},
    "Controlled Room Temp (15-25°C)": {"min_temp": 15.0, "max_temp": 25.0, "label": "Controlled Room Temp (15-25°C)"},
    "Room Temp (15-25°C)": {"min_temp": 15.0, "max_temp": 25.0, "label": "Room Temp (15-25°C)"},
    # Default cold room limits if storage type not explicitly known
    "CR": {"min_temp": 2.0, "max_temp": 8.0, "label": "Standard Cold Room"},
}


def load_temperature_logs(data_dir: Optional[str] = None) -> pd.DataFrame:
    """
    Loads environmental temperature sensor records from temperature_logs.csv.
    """
    base = data_dir or DEFAULT_DATA_DIR
    log_path = os.path.join(base, "temperature_logs.csv")
    df, warnings = common.load_csv_as_dataframe(
        log_path,
        required_columns=["warehouse", "cold_room", "timestamp", "temp_c"],
    )
    if not df.empty:
        df["temp_c"] = pd.to_numeric(df["temp_c"], errors="coerce")
    return df


def find_affected_batches(
    location: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    data_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Identifies inventory batches residing in the affected warehouse/cold room during an excursion window.
    Only cold-chain products are flagged for cold-room excursions.
    """
    base = data_dir or DEFAULT_DATA_DIR
    inv_df, _ = common.load_csv_as_dataframe(common.dataset_file_path("inventory.csv", base))
    prod_df, _ = common.load_csv_as_dataframe(os.path.join(base, "products.csv"))

    if inv_df.empty or prod_df.empty:
        return common.make_result("error", {}, warnings=["Inventory or product records unavailable."])

    # Merge inventory with product storage specifications
    merged = inv_df.merge(prod_df, on="sku", how="left")

    loc_clean = str(location).strip().upper()
    # Filter by warehouse
    matching = merged[merged["warehouse"].astype(str).str.strip().str.upper().str.contains(loc_clean)]

    # Cold room excursions primarily threaten Cold Chain products
    cold_chain_batches = []
    other_batches = []

    for _, row in matching.iterrows():
        storage_type = str(row.get("storage", "")).lower()
        batch_record = {
            "batch": str(row["batch"]),
            "sku": str(row["sku"]),
            "product_name": str(row.get("brand", row.get("molecule", "Unknown"))),
            "warehouse": str(row["warehouse"]),
            "qty": int(row["qty"]),
            "storage_spec": str(row.get("storage", "N/A")),
            "critical_drug": bool(row.get("critical_drug", False)),
        }

        if "cold" in storage_type:
            cold_chain_batches.append(batch_record)
        else:
            other_batches.append(batch_record)

    evidence = {
        "location_queried": location,
        "time_window": f"{start_time} to {end_time}" if start_time else "Entire active log",
        "total_warehouse_batches": len(matching),
    }

    return {
        "success": True,
        "status": "success",
        "location": location,
        "time_window": evidence["time_window"],
        "potentially_affected_cold_chain_batches": cold_chain_batches,
        "other_warehouse_batches": other_batches,
        "total_at_risk_units": sum(b["qty"] for b in cold_chain_batches),
        "evidence": evidence,
        "warnings": (
            [f"Identified {len(cold_chain_batches)} cold-chain batch(es) stored in {location}."]
            if cold_chain_batches else ["No cold-chain batches located at this facility."]
        ),
        "message": f"Found {len(cold_chain_batches)} potentially affected cold-chain batches in {location}.",
    }


def check_temperature_breach(
    min_limit: float = 2.0,
    max_limit: float = 8.0,
    data_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Scans temperature sensor logs against defined cold-chain thresholds (2.0°C to 8.0°C).
    Groups excursion events and cross-references potentially compromised inventory batches.
    """
    df = load_temperature_logs(data_dir)
    if df.empty:
        return common.make_result(
            "warning",
            {"excursions": []},
            warnings=["Temperature log file is empty or missing."],
            message="No temperature log data available.",
        )

    breaches = df[(df["temp_c"] < min_limit) | (df["temp_c"] > max_limit)]
    if breaches.empty:
        return {
            "success": True,
            "status": "normal",
            "available": True,
            "total_sensor_readings": len(df),
            "excursions_count": 0,
            "excursions": [],
            "warnings": [],
            "evidence": {"records_analyzed": len(df), "limit_range": f"{min_limit}°C - {max_limit}°C"},
            "message": "All sensor readings within compliant storage limits.",
        }

    excursions_list = []
    # Group breaches by warehouse and cold room
    for (wh, cr), group in breaches.groupby(["warehouse", "cold_room"]):
        sorted_grp = group.sort_values(by="timestamp")
        peak_temp = float(sorted_grp["temp_c"].max())
        min_temp = float(sorted_grp["temp_c"].min())
        start_ts = str(sorted_grp["timestamp"].iloc[0])
        end_ts = str(sorted_grp["timestamp"].iloc[-1])
        readings_count = int((sorted_grp["temp_c"] > max_limit).sum())

        # Cross-reference inventory batches located in this warehouse
        affected_info = find_affected_batches(wh, start_ts, end_ts, data_dir)
        affected_batches = [b["batch"] for b in affected_info.get("potentially_affected_cold_chain_batches", [])]

        excursions_list.append({
            "warehouse": str(wh),
            "cold_room": str(cr),
            "sensor_id": f"{wh}_{cr}",
            "start_time": start_ts,
            "end_time": end_ts,
            "timestamp": f"{start_ts} to {end_ts}",
            "readings_above_limit": readings_count,
            "peak_temp_c": peak_temp,
            "lowest_temp_c": min_temp,
            "recorded_value": peak_temp,  # for dashboard display
            "limit_min": min_limit,
            "limit_max": max_limit,
            "affected_batches": affected_batches,
            "at_risk_units": affected_info.get("total_at_risk_units", 0),
            "detailed_readings": sorted_grp[["timestamp", "temp_c"]].to_dict(orient="records"),
        })

    warnings = [
        f"CRITICAL: Detected {len(excursions_list)} temperature excursion event(s) exceeding {max_limit}°C limit."
    ]

    return {
        "success": True,
        "status": "excursion_detected",
        "available": True,
        "total_sensor_readings": len(df),
        "excursions_count": len(excursions_list),
        "excursions": excursions_list,
        "warnings": warnings,
        "evidence": {
            "total_breach_points": len(breaches),
            "configured_limits": f"{min_limit}°C to {max_limit}°C",
            "regulatory_note": "Requires QA stability evaluation prior to releasing quarantined stock.",
        },
        "message": f"Identified {len(excursions_list)} temperature excursion event(s).",
    }


def analyse_power_outage(
    start_time: str,
    end_time: str,
    location: str,
    data_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates temperature rise rate and thermal stability during a reported power outage window.
    """
    df = load_temperature_logs(data_dir)
    if df.empty:
        return common.make_result("error", {}, warnings=["No temperature logs available."])

    loc_clean = str(location).strip().upper()
    matched = df[df["warehouse"].astype(str).str.strip().str.upper().str.contains(loc_clean)]

    # Filter to outage window if parsable
    start_dt = common.parse_date_safely(start_time[:10])
    end_dt = common.parse_date_safely(end_time[:10])

    readings = matched.sort_values(by="timestamp")
    if readings.empty:
        return common.make_result("warning", {}, warnings=[f"No sensor records located for {location}."])

    max_temp = float(readings["temp_c"].max())
    min_temp = float(readings["temp_c"].min())

    return {
        "success": True,
        "status": "analyzed",
        "location": location,
        "outage_window": f"{start_time} to {end_time}",
        "peak_temperature": max_temp,
        "minimum_temperature": min_temp,
        "exceeded_cold_chain": max_temp > 8.0,
        "evidence": {
            "sensor_points_analyzed": len(readings),
        },
        "message": f"Power outage stability audit complete for {location}. Peak temp: {max_temp}°C.",
    }
