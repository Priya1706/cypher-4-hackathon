# BatchGuard AI — Pharmaceutical Supply-Chain Risk & Decision-Support System

**Team DevSync | Arogya Pharma Distributors | Cypher 4 Hackathon**

BatchGuard AI is an agentic AI-powered pharmaceutical supply-chain risk detection and decision-support web application built for a fictional distributor, **Arogya Pharma Distributors** (operating 3 regional warehouses serving 400 chemists and 20 hospitals).

> **Operational & Clinical Safety Notice**: All workflows and actions in this system are **simulated**. BatchGuard AI provides decision-support telemetry and does not autonomously execute physical dispatches, alter live warehouse stock, or claim product safety without qualified human review (Qualified Person / QA Compliance Officer). All dataset records are synthetic.

---

## 1. Project Purpose

The distributor must:
- Track stock at the batch level across regional warehouses.
- Identify expired and near-expiry inventory.
- Identify batches potentially affected by storage-temperature excursions (cold-chain).
- Trace recalled batches to customers and dispatched quantities.
- Quantify potential seasonal demand surges and pipeline stock gaps.
- Evaluate and compare feasible response options citing concrete evidence.
- Stage simulated actions for authorized human sign-off (Approve / Reject).
- Maintain an immutable audit log of all human governance decisions.

---

## 2. Architecture & Folder Structure

```text
cypher-4-hackathon/
├── app.py                             # Streamlit dashboard & UI coordination
├── agent.py                           # AI decision-support agent & deterministic engine
├── requirements.txt                   # Minimal dependencies (streamlit, pandas)
├── README.md                          # Documentation and run instructions
├── .gitignore                         # Excludes cache and local actions store
├── data/                              # Fictional synthetic business datasets
│   ├── products.csv                   # SKU master list, storage specs, critical drug flags
│   ├── inventory.csv                  # Warehouse stock, batch numbers, mfg & expiry dates
│   ├── dispatches.csv                 # Historical dispatch log with customer destinations
│   ├── customers.csv                  # Chemists & hospitals with locations & credit terms
│   ├── temperature_logs.csv           # Sensor log telemetry with timestamps & readings
│   ├── recalls.csv                    # Regulatory & manufacturer recall notices
│   ├── suppliers.csv                  # Lead times, MOQs, return windows
│   ├── purchase_orders.csv            # Pipeline orders, statuses, expected delivery dates
│   ├── historical_demand.csv          # Multi-month dispatch velocity by warehouse
│   ├── seasonal_diseases_vaccines.csv # Supplementary research (temperate climate patterns)
│   └── generate_datasets.py           # Deterministic synthetic data generator script
├── modules/
│   ├── __init__.py                    # Python package initializer
│   ├── common.py                      # Shared CSV loaders, date parsers, result envelopes
│   ├── inventory.py                   # Module A: Batch trace, recall check, customer impact, expiry
│   ├── environment.py                 # Module B: Sensor parsing, cold-chain excursion detection
│   ├── seasonal_demand.py             # Module C: Surge forecasting, stock gap & PO pipeline
│   └── actions.py                     # Module D: Simulated actions, JSON store, dispatch validation
└── tests/
    ├── __init__.py                    # Test package initializer
    ├── test_inventory.py              # Tests for Module A (6 tests)
    ├── test_environment.py            # Tests for Module B (4 tests)
    ├── test_seasonal_demand.py        # Tests for Module C (5 tests)
    ├── test_actions.py                # Tests for Module D (6 tests)
    └── test_batchguard.py             # Integration & agent safety tests (19 tests)
```

---

## 3. Data Schemas & Challenge Targets

The challenge scenario centers around:
- **Recalled Batch `B2231` (Amoxicillin 500mg)**:
  - `180` units remaining in `WH-Central-Bengaluru`.
  - `640` units dispatched over the preceding 30 days.
  - Traceable to **23 chemists** (500 units) and **2 hospitals** (140 units).
  - Subject to an active Class I recall directive. Simulated dispatches are blocked.
- **Clean Batch `B2240` (Amoxicillin 500mg)**:
  - `400` units available in warehouse for clean replacement.
- **Incoming Order `PO-2026-0911`**:
  - `800` units confirmed from Arogya Formulation Labs expected 2026-10-18.
- **Cold-Chain Excursion**:
  - `WH-Central-Bengaluru` cold room `CR-01` breached the 8.0°C limit (peaked at 12.6°C).
  - Identifies at-risk Regular Insulin batch `B1092` (120 units).
- **Supplementary Research File**:
  - `seasonal_diseases_vaccines.csv` provides background research on temperate disease patterns (e.g. Winter RSV/Flu). It is explicitly disclosed as supplementary research rather than verified Indian epidemiology.

---

## 4. Quickstart Guide

### Step 1: Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### Step 2: Run the Automated Test Suite (40 Tests)
Run all 40 unit and integration tests using Python's built-in test runner:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

### Step 3: Launch the Streamlit Web Application
```bash
python -m streamlit run app.py
```
Open **`http://localhost:8501`** in your browser.

---

## 5. Application Feature Walkthrough

1. **📊 Executive Risk Overview**:
   - Live metrics calculating pending review actions, active recalls, excursions, and expired stock.
   - Live inventory summary table across all 3 warehouses.
2. **🔍 Batch Traceability**:
   - Presets for scenario batches (`B2231`, `B2240`, `B1092`, `B3011`, `B8801`).
   - Customer dispatch breakdown showing all 23 chemists and 2 hospitals for `B2231`.
   - Interactive dispatch validator testing real inventory constraints.
3. **❄️ Environmental Risks**:
   - Cold-chain threshold auditor (2.0°C - 8.0°C) with expandable excursion logs.
   - Affected cold-chain batch list and "Stage QA Quarantine Action" button.
   - Power outage thermal stability audit tool.
4. **📈 Seasonal Demand**:
   - Surge projection, usable stock calculator, and incoming purchase order pipeline.
   - Supplementary research review table with geographic notices.
5. **🤖 AI Investigation Panel**:
   - Natural language query interface with deterministic rule fallback and optional LLM labeling.
   - Options comparison comparing internal reallocation, purchase orders, and hybrid priority delivery.
   - Staging proposed actions for human review.
6. **📋 Action Review & Governance Panel**:
   - Human-in-the-loop review with **Approve** and **Reject** buttons.
   - Reviewer identity logging and complete audit trail.

---

## 6. Known Limitations

- **Simulated Actions**: Staged actions write to local JSON persistence (`data/actions_store.json`) and do not connect to external ERP or physical warehouse robots.
- **Synthetic Data**: Datasets are designed to test risk workflows deterministically and should not be used as clinical reference.