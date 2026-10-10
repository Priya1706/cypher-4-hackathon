"""
app.py
BatchGuard AI — Pharmaceutical Supply-Chain Risk and Decision-Support Dashboard.
Developed for Arogya Pharma Distributors.

Author: Lead Integration & AI Agent Architecture (Team DevSync)
"""

import os
from datetime import datetime
import streamlit as st
import pandas as pd

# Import core application modules
import modules.common as common
import modules.inventory as inv
import modules.environment as env
import modules.seasonal_demand as seasonal
import modules.actions as actions
import agent

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="BatchGuard AI | Arogya Pharma",
    page_icon="B",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --canvas: #ecf2ed;
        --surface: #ffffff;
        --surface-alt: #f3f7f3;
        --sage-pale: #e3ece4;
        --ink: #090a0a;
        --muted: #535755;
        --sage: #b6c5b9;
        --sage-dark: #526c5a;
        --line: #bec8d4;
        color-scheme: light;
    }
    .stApp { background: var(--canvas); color: var(--ink); }
    [data-testid="stHeader"] { background: var(--canvas); }
    .block-container {
        box-sizing: border-box;
        width: 100%;
        max-width: 100%;
        padding: 1.35rem clamp(1rem, 2vw, 2rem) 2.5rem;
    }
    .brand-header { display: flex; align-items: center; gap: 1rem; padding: 0.8rem 0 0.25rem; }
    .brand-mark {
        display: grid; place-items: center; flex: 0 0 3.25rem; width: 3.25rem; height: 3.25rem;
        border-radius: 12px; background: #dce8dd; border: 1px solid var(--line);
        color: var(--sage-dark); font-size: 1.05rem; font-weight: 800; letter-spacing: -0.05em;
    }
    .brand-copy h1 { margin: 0; font-size: clamp(1.55rem, 2.4vw, 2rem); line-height: 1.15; }
    .brand-copy p { margin: 0.3rem 0 0; color: var(--muted); }
    .safety-note { margin: 0.55rem 0 1.15rem; color: var(--muted); }
    h1, h2, h3, h4 {
        color: var(--ink);
        letter-spacing: -0.02em;
        margin-top: 0.9rem;
        margin-bottom: 0.45rem;
    }
    [data-testid="stCaptionContainer"] { color: var(--muted); }
    [data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 0.85rem 1rem;
        box-shadow: 0 1px 4px rgba(37, 52, 46, 0.035);
    }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] { color: var(--ink); }
    [data-testid="stSidebar"] {
        background: #edf1eb;
        border-right: 1px solid var(--line);
        color: var(--ink) !important;
    }
    [data-testid="stSidebar"] :is(h1, h2, h3, h4, p, label) { color: var(--ink) !important; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: var(--muted) !important; }
    [data-testid="stSidebar"] input[type="radio"] { accent-color: var(--sage-dark); }
    [data-testid="stSidebar"] input[type="text"] {
        background: var(--surface);
        color: var(--ink);
        border-color: var(--line);
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label[data-testid="stRadioOption"] {
        color: var(--ink);
        border-radius: 7px;
        padding: 0.3rem 0.45rem;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label[data-testid="stRadioOption"]:has(input:checked) {
        color: var(--sage-dark);
        background: var(--sage-pale);
        font-weight: 650;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] input[type="radio"] {
        accent-color: var(--sage-dark);
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label[data-testid="stRadioOption"] > div > div:first-child {
        display: none;
    }
    [data-testid="stAlert"] {
        color: #493b19 !important;
        background: #fff3d7 !important;
        border: 1px solid #ead29a !important;
        border-left: 4px solid #bd8b2e !important;
        border-radius: 9px !important;
    }
    [data-testid="stAlert"] [data-testid="stAlertContainer"],
    [data-testid="stAlert"] [data-testid^="stAlertContent"] {
        background: transparent !important;
    }
    [data-testid="stAlert"] :is(p, span, strong, svg) { color: #493b19 !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--line);
        border-radius: 10px;
        background: var(--surface);
        box-shadow: 0 1px 4px rgba(37, 52, 46, 0.035);
    }
    .stButton > button[kind="primary"] {
        background: var(--sage-dark);
        border-color: var(--sage-dark);
    }
    .stButton > button[kind="primary"]:hover {
        background: var(--sage);
        border-color: var(--sage);
    }
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        box-sizing: border-box;
        width: 100%;
        max-width: 100%;
        border: 1px solid var(--line);
        border-radius: 8px;
        overflow-x: auto;
        background: var(--surface);
        color: var(--ink);
        --gdg-bg-cell: #ffffff;
        --gdg-bg-cell-medium: #f3f7f3;
        --gdg-bg-header: #e3ece4;
        --gdg-bg-header-hasFocus: #e3ece4;
        --gdg-text-dark: #090a0a;
        --gdg-text-medium: #535755;
        --gdg-border-color: #bec8d4;
        --gdg-accent-color: #526c5a;
    }
    [data-testid="stDataFrame"] .stDataFrameGlideDataEditor {
        --gdg-accent-color: #526c5a !important;
        --gdg-accent-fg: #ffffff !important;
        --gdg-accent-light: rgba(82, 108, 90, 0.12) !important;
        --gdg-text-dark: #090a0a !important;
        --gdg-text-medium: #535755 !important;
        --gdg-text-light: #535755 !important;
        --gdg-text-bubble: #535755 !important;
        --gdg-bg-icon-header: #535755 !important;
        --gdg-fg-icon-header: #090a0a !important;
        --gdg-text-header: #535755 !important;
        --gdg-text-group-header: #535755 !important;
        --gdg-text-header-selected: #526c5a !important;
        --gdg-bg-group-header: #e3ece4 !important;
        --gdg-bg-group-header-hovered: #dbe6da !important;
        --gdg-bg-cell: #ffffff !important;
        --gdg-bg-cell-medium: #f3f7f3 !important;
        --gdg-bg-header: #e3ece4 !important;
        --gdg-bg-header-has-focus: #dbe6da !important;
        --gdg-bg-header-hovered: #dbe6da !important;
        --gdg-bg-bubble: #f3f7f3 !important;
        --gdg-bg-bubble-selected: #e3ece4 !important;
        --gdg-bg-search-result: rgba(82, 108, 90, 0.12) !important;
        --gdg-border-color: #bec8d4 !important;
        --gdg-horizontal-border-color: #bec8d4 !important;
        --gdg-drilldown-border: #bec8d4 !important;
        --gdg-link-color: #526c5a !important;
        --gdg-resize-indicator-color: #526c5a !important;
    }
    [data-testid="stDataFrame"] [role="grid"],
    [data-testid="stDataFrame"] canvas {
        max-width: 100%;
        color-scheme: light;
    }
    [data-testid="stTable"] table {
        width: max-content;
        min-width: 100%;
        border-collapse: collapse;
        color: var(--ink);
    }
    [data-testid="stTable"] thead th {
        background: var(--sage-pale);
        color: var(--ink);
        border: 1px solid var(--line);
        font-weight: 650;
        white-space: nowrap;
    }
    [data-testid="stTable"] tbody tr:nth-child(even) { background: var(--surface-alt); }
    [data-testid="stTable"] tbody tr:nth-child(odd) { background: var(--surface); }
    [data-testid="stTable"] tbody td {
        color: var(--ink);
        border: 1px solid var(--line);
        white-space: normal;
        overflow-wrap: anywhere;
    }
    [data-testid="stExpander"] { border-color: var(--line); border-radius: 9px; background: rgba(255, 255, 255, 0.55); }
    [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
    [data-testid="stSelectbox"] [data-baseweb="select"] > div { border-color: var(--line); background: var(--surface); }
    @media (max-width: 900px) {
        .block-container { padding-top: 1rem; padding-left: 1rem; padding-right: 1rem; }
        [data-testid="stDataFrame"], [data-testid="stTable"] { overflow-x: auto; }
    }
    @media (max-width: 600px) {
        .brand-header { align-items: flex-start; gap: 0.7rem; }
        .brand-mark { flex-basis: 2.8rem; width: 2.8rem; height: 2.8rem; }
        .brand-copy h1 { font-size: 1.5rem; }
        [data-testid="stMetric"] { padding: 0.7rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Session State Deduplication Helpers ---
if "action_notice" not in st.session_state:
    st.session_state["action_notice"] = None
if "executed_actions" not in st.session_state:
    st.session_state["executed_actions"] = set()

# --- Header & Safety Banner ---
st.markdown(
    """<header class="brand-header">
      <div class="brand-mark" aria-label="BatchGuard logo">BG</div>
      <div class="brand-copy">
        <h1>BatchGuard AI</h1>
        <p>Pharmaceutical supply-chain control tower &middot; Arogya Pharma</p>
      </div>
    </header>
    <p class="safety-note">Decision support only. Actions are simulated and require qualified QA / QP approval; no physical dispatches or financial orders are executed.</p>""",
    unsafe_allow_html=True,
)

# --- Sidebar Controls & System Status ---
st.sidebar.markdown("## BatchGuard")
st.sidebar.caption("Arogya Pharma · risk monitoring")

tools = agent.get_available_tools()
st.sidebar.metric("Analysis tools online", len(tools))
st.sidebar.caption("NAVIGATION")
section = st.sidebar.radio(
    "Workspace",
    [
        "Overview",
        "Batch Traceability",
        "Environmental Risks",
        "Seasonal Demand",
        "AI Investigation",
        "Action Review",
    ],
    label_visibility="collapsed",
)

st.sidebar.divider()
st.sidebar.subheader("Authorized reviewer")
reviewer_name = st.sidebar.text_input(
    "QA / QP identity",
    value="Dr. R. Sharma (Qualified Person)",
    help="Identifies the authorized officer signing off on simulated actions.",
)


# ==============================================================================
# TAB 1: OVERVIEW
# ==============================================================================
if section == "Overview":
    st.subheader("Operations overview")
    st.caption("Live inventory, recall exposure, and replenishment planning")

    inv_data = inv.load_inventory()
    inv_df = inv_data.get("inventory", pd.DataFrame())
    prod_df = inv_data.get("products", pd.DataFrame())
    pending_actions = actions.list_pending_actions()
    pending_count = len(pending_actions)
    expiry_info = inv.check_expiry(reference_date="2026-10-09", near_expiry_days=30)
    env_info = env.check_temperature_breach(min_limit=2.0, max_limit=8.0)
    recall_df, _ = common.load_csv_as_dataframe(
        os.path.join(os.path.dirname(__file__), "data", "recalls.csv")
    )
    recalled_trace = inv.trace_batch("B2231")
    affected_customers = inv.get_affected_customers("B2231")
    clean_trace = inv.trace_batch("B2240")
    stock_gap = seasonal.calculate_stock_gap("SKU-AMOX-500")

    comparison = None
    incoming_pos = stock_gap.get("incoming_purchase_orders", [])
    recall_data_available = (
        recalled_trace.get("success", False)
        and recalled_trace.get("data", {}).get("is_recalled", False)
        and affected_customers.get("status") == "success"
        and clean_trace.get("success", False)
        and stock_gap.get("success", False)
        and bool(incoming_pos)
    )
    if recall_data_available:
        po = incoming_pos[0]
        comparison = agent.compare_options(
            {"type": "recall_replacement", "batch_id": "B2231"},
            {
                "inventory_available": True,
                "sku": recalled_trace["data"].get("sku"),
                "recalled_wh_qty": recalled_trace["data"]["total_warehouse_stock"],
                "recalled_disp_qty": recalled_trace["data"]["total_dispatched_qty"],
                "hospital_disp_qty": affected_customers["hospital_dispatched_units"],
                "chemist_disp_qty": affected_customers["chemist_dispatched_units"],
                "hospitals_count": affected_customers["hospitals_count"],
                "chemists_count": affected_customers["chemists_count"],
                "clean_stock_batch": clean_trace["batch_id"],
                "clean_stock_qty": clean_trace["data"]["total_warehouse_stock"],
                "incoming_po_number": po["po"],
                "incoming_po_qty": po["qty"],
                "incoming_po_expected": po["expected_date"],
            },
        )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        warehouse_count = int(inv_df["warehouse"].nunique()) if not inv_df.empty and "warehouse" in inv_df else "—"
        st.metric("Warehouses", warehouse_count)
    with col2:
        customer_count = affected_customers.get("total_customers_count", "—") if affected_customers.get("status") == "success" else "—"
        st.metric("Affected customers", customer_count)
    with col3:
        recalled_units = recalled_trace.get("data", {}).get("total_warehouse_stock", "—") if recalled_trace.get("success") else "—"
        st.metric("Recalled units · on hand", recalled_units)
    with col4:
        dispatched_units = recalled_trace.get("data", {}).get("total_dispatched_qty", "—") if recalled_trace.get("success") else "—"
        st.metric("Dispatched · trace required", dispatched_units)

    if pending_count > 0:
        st.warning(
            f"{pending_count} simulated action(s) are awaiting authorized review.",
            icon="!",
        )

    st.markdown("#### Recall status")
    if recalled_trace.get("success") and recalled_trace["data"].get("is_recalled"):
        st.warning(
            f"**Active Class I recall · B2231** — {recalled_units} units remain on hand; "
            f"{dispatched_units} dispatched units across "
            f"{affected_customers.get('total_customers_count', '—')} customers require traceability. "
            f"Total exposure: **{recalled_units + dispatched_units} units**.",
            icon="⚠",
        )
        if not affected_customers.get("success", False):
            st.warning("Affected-customer records are unavailable; verify dispatch data.")
    elif recalled_trace.get("success"):
        st.warning("No active recall is recorded for B2231; verify recall records before action.")
    else:
        st.warning("B2231 recall information is unavailable.")

    option_by_id = {
        option.get("option_id"): option
        for option in (comparison or {}).get("options", [])
    }
    if option_by_id:
        po_evidence = option_by_id.get("OPT-2-EXPEDITE-PO", {}).get("cited_evidence", {})
        clean_evidence = option_by_id.get("OPT-1-INTERNAL-REALLOCATION", {}).get("cited_evidence", {})
        supply_cols = st.columns(3)
        supply_cols[0].metric(
            "Clean stock · on hand",
            f"{clean_evidence.get('available_on_hand_units', '—')} units",
        )
        supply_cols[1].metric(
            "Purchase order · incoming",
            f"{po_evidence.get('po_quantity', '—')} units",
            help="Pipeline stock; not available for dispatch until received.",
        )
        supply_cols[2].metric(
            "PO-only shortfall",
            f"{po_evidence.get('shortfall_units', '—')} units",
            help="Recall exposure not covered by the incoming purchase order alone.",
        )

    st.markdown("#### Recommended response")
    if comparison and comparison.get("options"):
        with st.container(border=True):
            st.markdown(comparison.get("recommendation_summary", ""))
            st.caption("Decision support only · proposed actions remain simulated and require human approval.")

        st.markdown("#### Response options")
        option_rows = []
        for option in comparison["options"]:
            cited = option.get("cited_evidence", {})
            option_id = option.get("option_id")
            if option_id == "OPT-1-INTERNAL-REALLOCATION":
                supply = f"{cited.get('available_on_hand_units')} on-hand · {cited.get('clean_batch_id')}"
                timing = "Available now"
                shortfall = f"{cited.get('shortfall_against_total_exposure')} vs. total exposure"
                trade_off = (
                    f"{cited.get('allocated_units')} allocated · "
                    f"{cited.get('remaining_on_hand_buffer')} clean units remain"
                )
            elif option_id == "OPT-2-EXPEDITE-PO":
                supply = f"{cited.get('po_quantity')} incoming · not on hand"
                timing = option.get("feasibility")
                shortfall = f"{cited.get('shortfall_units')} units"
                trade_off = f"PO delivery delay · {cited.get('shortfall_units')} units remain unfilled"
            elif option_id == "OPT-3-HYBRID-PRIORITY":
                supply = (
                    f"{cited.get('stage_1_clean_stock_available')} on-hand + "
                    f"{cited.get('stage_2_po_available')} incoming"
                )
                timing = f"First stage now; PO stage after {po['expected_date']}"
                shortfall = f"{cited.get('total_shortfall')} units"
                trade_off = (
                    f"{cited.get('stage_1_remaining_clean_stock')} clean + "
                    f"{cited.get('stage_2_remaining_po_surplus')} PO units remain"
                )
            else:
                supply = option.get("available_supply")
                timing = option.get("feasibility")
                shortfall = option.get("shortfall")
                trade_off = option.get("trade_offs")
            option_rows.append({
                "Option": option.get("title"),
                "Supply": supply,
                "Timing": timing,
                "Shortfall": shortfall,
                "Trade-off": trade_off,
            })
        st.dataframe(
            pd.DataFrame(option_rows),
            use_container_width=True,
            hide_index=True,
        )
        with st.expander("Exposure calculation and option evidence"):
            if comparison.get("inventory_exposure_breakdown"):
                st.json(comparison["inventory_exposure_breakdown"])
            for option in comparison["options"]:
                with st.expander(option.get("title", "Option detail")):
                    st.write(f"**Allocation:** {option.get('units_allocated')}")
                    st.write(f"**Remaining stock:** {option.get('remaining_stock')}")
                    st.write(f"**Demand assumptions:** {option.get('demand_assumptions')}")
                    st.write(f"**Benefits:** {option.get('benefits')}")
                    st.write(f"**Limitations:** {option.get('limitations')}")
                    st.json(option.get("cited_evidence", {}))
    else:
        st.info("Response options are unavailable until recall, customer, clean-stock, and incoming-PO records are available.")

    with st.expander("Additional operations signals"):
        signal_cols = st.columns(3)
        signal_cols[0].metric("Active recall directives", len(recall_df))
        signal_cols[1].metric("Cold-chain excursions", env_info.get("excursions_count", "—"))
        signal_cols[2].metric(
            "Near-expiry / expired batches",
            f"{expiry_info.get('near_expiry_count', '—')} / {expiry_info.get('expired_count', '—')}",
        )

    with st.expander("Warehouse inventory records"):
        if not inv_df.empty and not prod_df.empty:
            merged_inv = inv_df.merge(prod_df, on="sku", how="left")
            display_cols = ["sku", "brand", "batch", "warehouse", "qty", "storage", "expiry_date", "critical_drug"]
            present_cols = [c for c in display_cols if c in merged_inv.columns]
            st.dataframe(merged_inv[present_cols], use_container_width=True, hide_index=True)
        else:
            st.warning("Inventory records unavailable.")


# ==============================================================================
# TAB 2: BATCH TRACEABILITY
# ==============================================================================
if section == "Batch Traceability":
    st.subheader("Batch traceability")
    st.caption("Review recall status, warehouse stock, and customer dispatch records.")

    # Batch selection presets
    col_sel, col_manual = st.columns([1, 2])
    with col_sel:
        preset_choice = st.selectbox(
            "Select Scenario Batch",
            ["B2231 (Recalled Amoxicillin)", "B2240 (Clean Amoxicillin)", "B1092 (Cold-Chain Insulin)", "B3011 (Near-Expiry Paracetamol)", "B8801 (Expired Rabies Vax)"],
        )
        selected_batch = preset_choice.split()[0]
    with col_manual:
        search_batch_input = st.text_input("Or Enter Custom Batch ID", value=selected_batch)

    target_batch = search_batch_input.strip().upper()

    if target_batch:
        trace_res = inv.trace_batch(target_batch)

        if not trace_res.get("success"):
            st.warning(f"Batch '{target_batch}' was not located in inventory or dispatch records.")
        else:
            b_data = trace_res["data"]
            is_recalled = b_data.get("is_recalled", False)

            col_t1, col_t2 = st.columns(2)

            with col_t1:
                st.markdown("#### Product and stock")
                st.markdown(f"**{b_data.get('product_name')}** · `{b_data.get('sku')}`")
                st.metric("Warehouse stock", f"{b_data.get('total_warehouse_stock')} units")
                with st.expander("Product and warehouse details"):
                    st.write(f"**Category:** {b_data.get('category')}")
                    st.write(f"**Storage:** {b_data.get('storage')}")
                    st.dataframe(
                        pd.DataFrame(b_data.get("warehouses", [])),
                        use_container_width=True,
                        hide_index=True,
                    )

            with col_t2:
                st.markdown("#### Recall status")
                if is_recalled:
                    st.error(f"Active recall · {target_batch}")
                    recall_res = inv.check_recall(target_batch)
                    details = recall_res.get("recall_details", {})
                    st.markdown(
                        f"Class **{details.get('recall_class', 'unavailable')}** · "
                        f"Notice date {details.get('recall_date', 'unavailable')}"
                    )
                    with st.expander("Recall directive"):
                        st.write(details.get("reason", "Recall reason unavailable."))
                else:
                    st.success(f"No active recall notice for {target_batch}.")

            # Customer Dispatches Trace
            st.divider()
            st.markdown(f"#### Customer trace · {target_batch}")
            cust_res = inv.get_affected_customers(target_batch)

            if cust_res.get("total_dispatched_units", 0) > 0:
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Total Units Dispatched", cust_res["total_dispatched_units"])
                with c2:
                    st.metric("Retail Chemists Reached", cust_res["chemists_count"])
                with c3:
                    st.metric("Hospitals Reached", cust_res["hospitals_count"])

                with st.expander("Affected customer roster"):
                    st.dataframe(
                        pd.DataFrame(cust_res.get("customers", [])),
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.info(f"No customer dispatch records found for batch '{target_batch}'.")

            # Simulated Dispatch Validation Tool
            st.divider()
            st.markdown("#### Simulated dispatch validation")
            st.caption("Recalled batches are blocked, and quantities cannot exceed available stock.")
            d_col1, d_col2, d_col3 = st.columns([2, 1, 1])
            with d_col1:
                test_dispatch_qty = st.number_input("Requested Dispatch Quantity", min_value=1, value=50, step=10)
            with d_col2:
                st.write("")
                st.write("")
                test_val_clicked = st.button("Validate Dispatch", key=f"val_btn_{target_batch}")

            if test_val_clicked:
                val_outcome = actions.validate_dispatch(target_batch, test_dispatch_qty)
                if val_outcome["valid"]:
                    st.success(f"Dispatch validated: {val_outcome['reason']}")
                else:
                    st.error(f"Dispatch rejected: {val_outcome['reason']}")


# ==============================================================================
# TAB 3: ENVIRONMENTAL RISKS
# ==============================================================================
if section == "Environmental Risks":
    st.subheader("Environmental risks")
    st.caption("Cold-chain telemetry · 2.0°C–8.0°C range. Excursions require QA stability review.")

    env_result = env.check_temperature_breach(min_limit=2.0, max_limit=8.0)
    excursions = env_result.get("excursions", [])

    if excursions:
        st.error(f"{len(excursions)} cold-chain excursion event(s) identified")
        st.caption("A breach indicates potential compromise, not confirmed degradation. Stability testing is required.")

        for exc in excursions:
            with st.expander(f"{exc.get('warehouse')} · {exc.get('cold_room')} · peak {exc.get('peak_temp_c')}°C"):
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    st.write(f"**Facility Location:** `{exc.get('warehouse')}`")
                    st.write(f"**Cold Storage Unit:** `{exc.get('cold_room')}`")
                    st.write(f"**Event Time Window:** `{exc.get('start_time')}` to `{exc.get('end_time')}`")
                    st.write(f"**Peak Temperature Recorded:** `{exc.get('peak_temp_c')}°C` (Upper Limit: `8.0°C`)")
                    st.write(f"**Sensor Readings Exceeding Limit:** `{exc.get('readings_above_limit')}`")

                with col_e2:
                    st.write("**Potentially Compromised Cold-Chain Batches:**")
                    affected_list = exc.get("affected_batches", [])
                    if affected_list:
                        for b in affected_list:
                            st.write(f"- Batch `{b}` (Regular Insulin / Vaccine stock)")
                        st.write(f"**Total Units at Risk:** `{exc.get('at_risk_units')}` units")
                    else:
                        st.write("*No cold-chain batches located in this storage zone.*")

                # Action button to stage QA quarantine
                st.write("")
                btn_key = f"stage_exc_{exc.get('warehouse')}_{exc.get('cold_room')}"
                if st.button("Stage QA Quarantine Action for Excursion Stock", key=btn_key):
                    new_action = actions.create_action(
                        action_type="quarantine_excursion_stock",
                        details={
                            "warehouse": exc.get("warehouse"),
                            "cold_room": exc.get("cold_room"),
                            "peak_temp": exc.get("peak_temp_c"),
                            "affected_batches": affected_list,
                            "reason": "Cold chain breached (peak temp > 8.0°C). Requires QA stability clearance.",
                        },
                    )
                    st.success(f"Simulated action `{new_action['action_id']}` staged for human review!")
                    st.rerun()

    else:
        st.success("All cold-chain telemetry is within the configured range.")

    # Power Outage Stability Tool
    st.divider()
    st.markdown("#### Power outage stability audit")
    p_col1, p_col2, p_col3, p_col4 = st.columns(4)
    with p_col1:
        outage_loc = st.selectbox("Warehouse", ["WH-Central-Bengaluru", "WH-North-Hubballi", "WH-South-Mysuru"])
    with p_col2:
        outage_start = st.text_input("Start Timestamp", value="2026-10-08T02:00:00")
    with p_col3:
        outage_end = st.text_input("End Timestamp", value="2026-10-08T06:00:00")
    with p_col4:
        st.write("")
        st.write("")
        run_outage_audit = st.button("Audit Outage Window")

    if run_outage_audit:
        outage_res = env.analyse_power_outage(outage_start, outage_end, outage_loc)
        with st.expander("Outage analysis details", expanded=True):
            st.json(outage_res)


# ==============================================================================
# TAB 4: SEASONAL DEMAND
# ==============================================================================
if section == "Seasonal Demand":
    st.subheader("Seasonal demand")
    st.caption("Compare projected demand with usable on-hand stock and the incoming order pipeline.")

    col_prod, col_season_btn = st.columns([3, 1])
    with col_prod:
        selected_sku = st.selectbox(
            "Select Product Identifier",
            ["SKU-AMOX-500", "SKU-PARA-650", "SKU-INS-REG", "SKU-AZI-250", "SKU-RAB-VAX"],
        )
    with col_season_btn:
        st.write("")
        st.write("")
        forecast_clicked = st.button("Forecast Seasonal Demand", use_container_width=True)

    if selected_sku:
        gap_res = seasonal.calculate_stock_gap(selected_sku)

        st.markdown(f"#### Supply outlook · `{selected_sku}`")
        st.caption("Forecast derived from the distributor historical dispatch dataset.")

        c_f1, c_f2, c_f3, c_f4 = st.columns(4)
        with c_f1:
            st.metric("Projected Seasonal Demand", f"{gap_res.get('projected_demand')} units")
        with c_f2:
            st.metric("Usable Warehouse Stock", f"{gap_res.get('usable_warehouse_stock')} units", help="Excludes recalled and expired inventory")
        with c_f3:
            st.metric(
                "Incoming purchase orders",
                f"{gap_res.get('incoming_po_stock')} units",
                help="Pipeline stock; not currently available for dispatch.",
            )
        with c_f4:
            stock_gap = gap_res.get("stock_gap", 0)
            st.metric(
                "Projected Stock Gap / Deficit",
                f"{stock_gap} units",
                delta=f"-{stock_gap} Shortage" if stock_gap > 0 else "Fully Covered",
                delta_color="inverse",
            )

        # Supplier context
        supp_info = gap_res.get("supplier_info", {})
        if supp_info:
            st.markdown("#### Supplier")
            supplier_cols = st.columns(4)
            supplier_cols[0].markdown(f"**Manufacturer**  \n{supp_info.get('manufacturer')}")
            supplier_cols[1].markdown(f"**Lead time**  \n{supp_info.get('lead_time_days')} days")
            supplier_cols[2].markdown(f"**MOQ**  \n{supp_info.get('moq')} units")
            supplier_cols[3].markdown(f"**Return window**  \n{supp_info.get('return_window_days')} days")
            if gap_res.get("has_shortage"):
                st.warning(f"Recommended purchase order: **{gap_res.get('recommended_order_qty')} units** to satisfy MOQ and clear the projected deficit.")

        with st.expander("Incoming purchase orders · pipeline, not on-hand stock"):
            incoming = gap_res.get("incoming_purchase_orders", [])
            if incoming:
                st.dataframe(pd.DataFrame(incoming), use_container_width=True, hide_index=True)
            else:
                st.caption("No qualifying incoming purchase orders were found.")

        # Supplementary Research Inspection
        research_info = seasonal.inspect_supplementary_research()
        with st.expander("Supplementary research data"):
            if research_info.get("available"):
                st.caption(research_info.get("limitations_notice"))
                st.dataframe(
                    pd.DataFrame(research_info.get("records", [])),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption(research_info.get("message", "Supplementary research file is not loaded."))


# ==============================================================================
# TAB 5: AI INVESTIGATION PANEL
# ==============================================================================
if section == "AI Investigation":
    st.subheader("AI investigation")
    st.caption("Coordinate the existing analysis tools, review findings, and stage simulated actions for approval.")

    # Quick prompt presets
    st.markdown("**Suggested investigations**")
    prompt_cols = st.columns(4)
    active_prompt = None
    if prompt_cols[0].button("Investigate batch B2231"):
        active_prompt = "Investigate batch B2231 and recommend the next steps."
    if prompt_cols[1].button("Check cold-chain excursions"):
        active_prompt = "Which batches have possible temperature excursions?"
    if prompt_cols[2].button("Forecast seasonal demand"):
        active_prompt = "What stock might run short during the next seasonal demand period for SKU-AMOX-500?"
    if prompt_cols[3].button("Compare replacement options"):
        active_prompt = "Compare replacement options for recalled batch B2231"

    query_input = st.text_input(
        "Enter your query for the agent:",
        value=active_prompt if active_prompt else "Investigate batch B2231 and recommend the next steps.",
    )

    if st.button("Run Investigation", type="primary"):
        with st.spinner("Executing agent investigation, querying live tools, and comparing options..."):
            investigation = agent.run_investigation(query_input)

        st.divider()
        st.markdown("### Investigation report")
        engine_label = investigation["engine_mode"]
        st.caption(f"{engine_label} · Intent: {investigation['intent'].replace('_', ' ').title()}")

        col_tools, col_findings = st.columns([1, 2])
        with col_tools:
            st.markdown("#### Tools used")
            st.caption(" · ".join(investigation["tools_used"]) or "No tools were required.")

        with col_findings:
            st.markdown("#### Key findings")
            for f in investigation["findings"]:
                st.markdown(f"- {f}")

        if investigation["uncertainties"]:
            with st.expander("Uncertainties and missing data"):
                for uncertainty in investigation["uncertainties"]:
                    st.write(uncertainty)

        # Feasible Options Comparison
        comp = investigation.get("options_comparison", {})
        st.divider()
        st.markdown("#### Response options")
        if comp.get("options"):
            st.caption(comp.get("recommendation_summary", ""))
            for opt in comp["options"]:
                with st.expander(opt.get("title", "Response option")):
                    st.write(f"**Supply:** {opt.get('available_supply')}")
                    st.write(f"**Timing:** {opt.get('feasibility')}")
                    st.write(f"**Allocation:** {opt.get('units_allocated')}")
                    st.write(f"**Shortfall:** {opt.get('shortfall')}")
                    st.write(f"**Benefits:** {opt.get('benefits')}")
                    st.write(f"**Trade-offs:** {opt.get('trade_offs')}")
                    st.write(f"**Limitations:** {opt.get('limitations')}")
                    st.json(opt.get("cited_evidence", {}))
        else:
            st.info(comp.get("message", "No response options are available for this investigation."))

        # Decision-Support Recommendation
        rec = investigation.get("recommendation", {})
        st.markdown("#### Recommendation")
        with st.container(border=True):
            st.markdown(rec.get("summary") or "No recommendation was returned.")
            if investigation.get("requires_human_approval"):
                st.caption("Simulated action only · qualified human approval required.")

        # Proposed Simulated Action
        proposed = investigation.get("proposed_action")
        if proposed:
            st.markdown("#### Proposed simulated action")
            st.write(f"**Action type:** `{proposed.get('action_type')}` · **Approval required**")
            with st.expander("Proposed action details"):
                st.json(proposed.get("details", {}))

            stage_key = f"btn_stage_{proposed.get('action_type')}_{investigation['intent']}"
            if st.button("Stage for human review", key=stage_key):
                new_act = actions.create_action(
                    action_type=proposed.get("action_type"),
                    details=proposed.get("details", {}),
                )
                st.session_state["action_notice"] = f"Simulated action `{new_act['action_id']}` staged for review."
                st.rerun()

        if st.session_state.get("action_notice"):
            st.success(st.session_state["action_notice"])

        with st.expander("Original query and complete investigation output"):
            st.write(investigation["query"])
            st.json(investigation)

# ==============================================================================
# TAB 6: ACTION REVIEW PANEL
# ==============================================================================
if section == "Action Review":
    st.subheader("Action review")
    st.caption("Pending simulated actions require an explicit decision from the authorized QA / QP reviewer.")

    pending_list = actions.list_pending_actions()

    if not pending_list:
        st.success("No actions are pending human review.")
    else:
        st.markdown(f"**{len(pending_list)}** action(s) awaiting review")

        for act in pending_list:
            act_id = act.get("action_id")
            details = act.get("details", {})
            action_batch = (
                details.get("batch_id")
                or details.get("replacement_batch")
                or details.get("batch")
                or details.get("location")
                or "—"
            )
            quantities = [
                f"{key.replace('_', ' ')}: {value:,}"
                for key, value in details.items()
                if isinstance(value, (int, float))
                and not isinstance(value, bool)
                and any(term in key for term in ("qty", "quantity", "units"))
            ]
            with st.container(border=True):
                col_info, col_decide = st.columns([3, 2])

                with col_info:
                    st.markdown(f"#### {act.get('action_type', 'Action')}")
                    st.caption(f"{act_id} · Created {act.get('created_at', 'time unavailable')}")
                    summary_cols = st.columns(3)
                    summary_cols[0].markdown(f"**Affected batch / location**  \n{action_batch}")
                    summary_cols[1].markdown(f"**Status**  \n{act.get('status', 'unknown').title()}")
                    summary_cols[2].markdown(
                        "**Quantities**  \n" + (" · ".join(quantities) if quantities else "See details")
                    )
                    with st.expander("Full action details"):
                        st.json(details)

                with col_decide:
                    st.markdown("#### Human approval required")
                    st.caption(f"Reviewer: **{reviewer_name}**")

                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        if st.button("Approve", key=f"app_{act_id}", use_container_width=True):
                            res = actions.review_action(act_id, "approved", reviewer_name)
                            if res.get("status") == "error":
                                st.error(res.get("message"))
                            else:
                                st.success(f"Action {act_id} APPROVED.")
                                st.rerun()

                    with btn_c2:
                        if st.button("Reject", key=f"rej_{act_id}", use_container_width=True):
                            res = actions.review_action(act_id, "rejected", reviewer_name)
                            if res.get("status") == "error":
                                st.error(res.get("message"))
                            else:
                                st.warning(f"Action {act_id} REJECTED.")
                                st.rerun()

    # Complete Audit Trail
    st.divider()
    st.subheader("Action audit trail")
    all_acts = actions.list_all_actions()
    if all_acts:
        audit_records = []
        for a in all_acts:
            audit_records.append({
                "Action ID": a.get("action_id"),
                "Action Type": a.get("action_type"),
                "Status": a.get("status"),
                "Created At": a.get("created_at"),
                "Reviewer": a.get("reviewer") or "—",
                "Reviewed At": a.get("reviewed_at") or "—",
            })
        st.dataframe(pd.DataFrame(audit_records), use_container_width=True)
    else:
        st.caption("No action records in store.")
