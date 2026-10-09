"""
modules/actions.py
Simulated Action Management & Review Workflow for BatchGuard AI (Arogya Pharma Distributors).

All actions are simulated decision-support records. No physical dispatches,
financial transactions, or real-world warehouse modifications are performed.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

# Default persistence file path (local JSON store)
DEFAULT_STORAGE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "actions_store.json"
)


def _load_store(file_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Loads all saved actions from the local JSON store."""
    target_path = file_path or DEFAULT_STORAGE_FILE
    if not os.path.exists(target_path):
        return {}
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            elif isinstance(data, list):
                # Backwards-compatibility if stored as a list
                return {item.get("action_id"): item for item in data if isinstance(item, dict) and "action_id" in item}
            return {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_store(store: Dict[str, Dict[str, Any]], file_path: Optional[str] = None) -> bool:
    """Saves action dictionary to the local JSON store."""
    target_path = file_path or DEFAULT_STORAGE_FILE
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, default=str)
        return True
    except OSError:
        return False


def save_action(action: Dict[str, Any], file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Persist or update an action in the local storage file.
    
    Returns the action dict on success, or an error dict on failure.
    """
    if not isinstance(action, dict):
        return {"status": "error", "message": "Action payload must be a dictionary."}

    action_id = action.get("action_id")
    if not action_id:
        return {"status": "error", "message": "Action is missing 'action_id'."}

    store = _load_store(file_path)
    store[action_id] = action
    success = _save_store(store, file_path)

    if not success:
        return {"status": "error", "message": "Failed to persist action record."}

    return action


def create_action(
    action_type: str,
    details: Dict[str, Any],
    file_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new simulated action record with initial 'pending' status.
    
    Generates a unique action ID and saves it to local persistence.
    """
    timestamp = datetime.now()
    unique_suffix = uuid.uuid4().hex[:6].upper()
    action_id = f"ACT-{timestamp.strftime('%Y%m%d')}-{unique_suffix}"

    evidence = details.get("evidence", {}) if isinstance(details, dict) else {}

    action_record: Dict[str, Any] = {
        "action_id": action_id,
        "action_type": action_type,
        "status": "pending",
        "created_at": timestamp.isoformat(),
        "details": details if isinstance(details, dict) else {},
        "evidence": evidence,
        "reviewer": None,
        "reviewed_at": None,
        "review_decision": None,
        "is_simulated": True,
    }

    return save_action(action_record, file_path)


def get_action(action_id: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve an action record by ID.
    
    Returns the action dictionary if found, or an error dictionary if missing.
    """
    if not action_id:
        return {"status": "error", "message": "Action ID is required."}

    store = _load_store(file_path)
    record = store.get(str(action_id).strip())
    if record:
        return record

    return {
        "status": "not_found",
        "message": f"Action with ID '{action_id}' was not found.",
    }


def list_pending_actions(file_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all actions currently awaiting human review (status == 'pending').
    """
    store = _load_store(file_path)
    return [
        record
        for record in store.values()
        if isinstance(record, dict) and record.get("status") == "pending"
    ]


def list_all_actions(file_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all simulated action records regardless of status.
    """
    store = _load_store(file_path)
    return list(store.values())


def review_action(
    action_id: str,
    decision: str,
    reviewer: str,
    file_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Review a pending action, transitioning it to 'approved' or 'rejected'.
    
    Enforces valid state transitions:
    - Only 'pending' actions can be reviewed.
    - Transitions to already approved or rejected actions are blocked.
    """
    normalized_decision = str(decision).strip().lower()
    if normalized_decision not in ("approved", "rejected"):
        return {
            "status": "error",
            "message": f"Invalid decision '{decision}'. Only 'approved' or 'rejected' are allowed.",
        }

    cleaned_reviewer = str(reviewer).strip()
    if not cleaned_reviewer:
        return {
            "status": "error",
            "message": "Reviewer identity must be provided to sign off on an action.",
        }

    action = get_action(action_id, file_path)
    if action.get("status") in ("not_found", "error") or "action_id" not in action:
        return {
            "status": "error",
            "message": action.get("message", f"Action '{action_id}' not found."),
        }

    current_status = action.get("status")
    if current_status != "pending":
        return {
            "status": "error",
            "message": (
                f"Invalid state transition: Action '{action_id}' is already '{current_status}'. "
                "Only 'pending' actions can be approved or rejected."
            ),
        }

    # Transition status
    action["status"] = normalized_decision
    action["review_decision"] = normalized_decision
    action["reviewer"] = cleaned_reviewer
    action["reviewed_at"] = datetime.now().isoformat()

    return save_action(action, file_path)


def validate_dispatch(batch_id: str, quantity: int) -> Dict[str, Any]:
    """
    Validates a simulated dispatch request against inventory and recall rules.
    
    Safety Rules:
    1. Rejects dispatch if quantity <= 0.
    2. Dynamically calls modules.inventory when available.
    3. Rejects dispatch if batch is recalled.
    4. Rejects dispatch if requested quantity exceeds available stock.
    5. Returns an explicit 'unknown' status if inventory module is missing,
       failing safe instead of falsely assuming the dispatch is safe.
    """
    if quantity <= 0:
        return {
            "valid": False,
            "status": "invalid_quantity",
            "batch_id": batch_id,
            "quantity": quantity,
            "reason": "Dispatch quantity must be greater than zero.",
        }

    # Dynamically import modules.inventory
    try:
        import modules.inventory as inv
    except ImportError:
        return {
            "valid": False,
            "status": "unknown",
            "batch_id": batch_id,
            "quantity": quantity,
            "reason": "Inventory module is not installed; cannot verify batch safety.",
        }

    # Verify check_recall availability
    if not hasattr(inv, "check_recall"):
        return {
            "valid": False,
            "status": "unknown",
            "batch_id": batch_id,
            "quantity": quantity,
            "reason": "Recall checking function is unavailable in modules.inventory.",
        }

    recall_res = inv.check_recall(batch_id)
    # Check if teammate module signaled unavailable or not implemented
    if not isinstance(recall_res, dict) or recall_res.get("available") is False or recall_res.get("status") == "not_implemented":
        return {
            "valid": False,
            "status": "unknown",
            "batch_id": batch_id,
            "quantity": quantity,
            "reason": f"Inventory recall data is unavailable: {recall_res.get('message', 'pending implementation')}.",
        }

    # Check for active recall
    is_recalled = (
        recall_res.get("is_recalled") is True
        or recall_res.get("status") == "recalled"
        or recall_res.get("data", {}).get("is_recalled") is True
    )
    if is_recalled:
        return {
            "valid": False,
            "status": "blocked_recall",
            "batch_id": batch_id,
            "quantity": quantity,
            "reason": f"Batch '{batch_id}' is subject to an active recall notice. Dispatch blocked for safety.",
            "evidence": recall_res.get("evidence", {}),
        }

    # Verify trace_batch availability for stock verification
    if not hasattr(inv, "trace_batch"):
        return {
            "valid": False,
            "status": "unknown",
            "batch_id": batch_id,
            "quantity": quantity,
            "reason": "Trace function is unavailable in modules.inventory; stock level unknown.",
        }

    trace_res = inv.trace_batch(batch_id)
    if not isinstance(trace_res, dict) or trace_res.get("available") is False or trace_res.get("status") == "not_implemented":
        return {
            "valid": False,
            "status": "unknown",
            "batch_id": batch_id,
            "quantity": quantity,
            "reason": f"Inventory trace data is unavailable: {trace_res.get('message', 'pending implementation')}.",
        }

    # Determine available stock
    batch_data = trace_res.get("data", {})
    if not batch_data and trace_res.get("status") == "not_found":
        return {
            "valid": False,
            "status": "not_found",
            "batch_id": batch_id,
            "quantity": quantity,
            "reason": f"Batch '{batch_id}' was not found in inventory records.",
        }

    available_stock = (
        batch_data.get("available_stock")
        or batch_data.get("quantity")
        or batch_data.get("stock")
    )
    if available_stock is None:
        # Stock cannot be determined
        return {
            "valid": False,
            "status": "unknown",
            "batch_id": batch_id,
            "quantity": quantity,
            "reason": f"Could not determine available stock level for batch '{batch_id}'.",
        }

    try:
        available_qty = int(available_stock)
    except (ValueError, TypeError):
        return {
            "valid": False,
            "status": "unknown",
            "batch_id": batch_id,
            "quantity": quantity,
            "reason": f"Invalid stock count value for batch '{batch_id}': {available_stock}",
        }

    if quantity > available_qty:
        return {
            "valid": False,
            "status": "insufficient_stock",
            "batch_id": batch_id,
            "quantity": quantity,
            "available_stock": available_qty,
            "reason": f"Requested quantity ({quantity}) exceeds available stock ({available_qty}).",
        }

    return {
        "valid": True,
        "status": "valid",
        "batch_id": batch_id,
        "quantity": quantity,
        "available_stock": available_qty,
        "reason": "Dispatch validated successfully against current inventory.",
    }

