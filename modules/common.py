"""
modules/common.py
Shared utilities for BatchGuard AI (Arogya Pharma Distributors).

Contains beginner-friendly, reusable functions for:
- Standardized structured result envelopes
- Safe CSV loading with DictReader and pandas
- Column and date validation
- Consistent error and warning handling
"""

import csv
import os
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd


def dataset_file_path(filename: str, data_dir: str) -> str:
    """Resolve known official PS-07 filename differences without changing source files."""
    path = os.path.join(data_dir, filename)
    if filename == "inventory.csv" and not os.path.exists(path):
        official_path = os.path.join(data_dir, "batch_inventory.csv")
        if os.path.exists(official_path):
            return official_path
    return path


def make_result(
    status: str,
    data: Any = None,
    warnings: Optional[List[str]] = None,
    evidence: Optional[Dict[str, Any]] = None,
    message: str = "",
) -> Dict[str, Any]:
    """
    Constructs a consistent structured dictionary used across all BatchGuard modules.
    
    Status can be: 'success', 'warning', 'error', or 'not_implemented'.
    Includes both 'data' and 'results' keys for backwards and forward compatibility.
    """
    is_success = status.lower() in ("success", "valid")
    payload = data if data is not None else {}
    return {
        "success": is_success,
        "status": status,
        "data": payload,
        "results": payload,
        "warnings": list(warnings) if warnings else [],
        "evidence": dict(evidence) if evidence else {},
        "message": message,
    }


def parse_date_safely(date_string: Any) -> Optional[date]:
    """
    Safely parse a date string into a datetime.date object.
    Supports YYYY-MM-DD, DD/MM/YYYY, and DD-MM-YYYY formats.
    Returns None if the value cannot be parsed.
    """
    if not date_string:
        return None
    if isinstance(date_string, date):
        return date_string
    if isinstance(date_string, datetime):
        return date_string.date()

    cleaned = str(date_string).strip()
    candidate_formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]
    for fmt in candidate_formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def validate_columns(
    headers: List[str], required_columns: List[str]
) -> Tuple[bool, List[str]]:
    """
    Checks if all required columns are present in the provided headers.
    Returns (is_valid, list_of_missing_columns).
    """
    cleaned_headers = {str(h).strip().lower() for h in headers if h}
    missing = [
        col for col in required_columns if col.strip().lower() not in cleaned_headers
    ]
    return (len(missing) == 0, missing)


def load_csv_safely(
    file_path: str, required_columns: Optional[List[str]] = None
) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Safely load a CSV file into a list of row dictionaries.
    Returns (rows, warnings).
    """
    warnings: List[str] = []
    if not os.path.exists(file_path):
        warnings.append(f"File not found: {file_path}")
        return [], warnings

    rows: List[Dict[str, str]] = []
    try:
        with open(file_path, mode="r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                warnings.append(f"CSV file is empty: {file_path}")
                return [], warnings

            if required_columns:
                is_valid, missing = validate_columns(
                    list(reader.fieldnames), required_columns
                )
                if not is_valid:
                    warnings.append(
                        f"Missing required columns in {file_path}: {', '.join(missing)}"
                    )
                    return [], warnings

            for row in reader:
                cleaned_row = {
                    (k.strip() if k else f"col_{i}"): (v.strip() if v else "")
                    for i, (k, v) in enumerate(row.items())
                }
                rows.append(cleaned_row)

    except Exception as e:
        warnings.append(f"Error reading CSV file {file_path}: {str(e)}")
        return [], warnings

    return rows, warnings


def load_csv_as_dataframe(
    file_path: str, required_columns: Optional[List[str]] = None
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Safely loads a CSV file into a pandas DataFrame with column validation.
    Returns (dataframe, warnings). If missing or invalid, returns empty DataFrame.
    """
    warnings: List[str] = []
    if not os.path.exists(file_path):
        warnings.append(f"File not found: {file_path}")
        return pd.DataFrame(), warnings

    try:
        df = pd.read_csv(file_path, encoding="utf-8-sig")
        df.columns = [str(c).strip() for c in df.columns]

        if required_columns:
            is_valid, missing = validate_columns(list(df.columns), required_columns)
            if not is_valid:
                warnings.append(f"Missing required columns in {file_path}: {', '.join(missing)}")
                return pd.DataFrame(), warnings

        return df, warnings
    except Exception as e:
        warnings.append(f"Failed to read CSV into DataFrame: {str(e)}")
        return pd.DataFrame(), warnings
