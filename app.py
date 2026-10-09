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
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Session State Deduplication Helpers ---
if "action_notice" not in st.session_state:
    st.session_state["action_notice"] = None
if "executed_actions" not in st.session_state:
    st.session_state["executed_actions"] = set()

# --- Header & Safety Banner ---
st.title("🛡️ BatchGuard AI")
st.caption(
    "Agentic Supply-Chain Risk Detection & Decision-Support System | **Arogya Pharma Distributors** | "
    "*Serving 3 Warehouses, 400 Chemists, and 20 Hospitals*"
)

st.info(
    "⚠️ **Operational Safety Notice**: All workflows and actions in this system are **simulated**. "
    "BatchGuard AI does not provide autonomous clinical safety determinations, execute physical dispatches, "
    "or place financial orders. All decisions require verification by a qualified person (QP / QA Compliance Officer).",
    icon="ℹ️",
)

# --- Sidebar Controls & System Status ---
st.sidebar.header("System & Governance Status")

tools = agent.get_available_tools()
st.sidebar.success(f"✅ Active Analysis Tools: {len(tools)} Online")
st.sidebar.markdown(
    """
    - **Inventory & Trace**: Live (`modules.inventory`)
    - **Environmental Cold Chain**: Live (`modules.environment`)
    - **Seasonal Demand**: Live (`modules.seasonal_demand`)
    - **Simulated Action Store**: Live (`modules.actions`)
    """
)

st.sidebar.divider()
st.sidebar.subheader("Authorized Reviewer")
reviewer_name = st.sidebar.text_input(
    "Logged-in QA / QP Identity",
    value="Dr. R. Sharma (Qualified Person)",
    help="Identifies the authorized officer signing off on simulated actions.",
)

st.sidebar.divider()
st.sidebar.markdown(
    """
    **Navigation Tabs:**
    1. **Overview**: Risk telemetry & warehouse stock
    2. **Batch Traceability**: Recalls, stock & customer trace
    3. **Environmental Risks**: Cold-room excursions
    4. **Seasonal Demand**: Surge forecasts & stock gaps
    5. **AI Investigation**: Natural language decision agent
    6. **Action Review**: Human-in-the-loop governance
    """
)

# --- Navigation Tabs ---
tab_overview, tab_batch, tab_env, tab_seasonal, tab_ai, tab_actions = st.tabs([
    "📊 Overview",
    "🔍 Batch Traceability",
    "❄️ Environmental Risks",
    "📈 Seasonal Demand",
    "🤖 AI Investigation",
    "📋 Action Review Panel",
])


# ==============================================================================
# TAB 1: OVERVIEW
# ==============================================================================
with tab_overview:
    st.subheader("Executive Supply-Chain Risk Telemetry")

    # Fetch live data metrics
    pending_actions = actions.list_pending_actions()
    pending_count = len(pending_actions)

    expiry_info = inv.check_expiry(reference_date="2026-10-09", near_expiry_days=30)
    expired_count = expiry_info.get("expired_count", 0)
    near_expiry_count = expiry_info.get("near_expiry_count", 0)

    env_info = env.check_temperature_breach(min_limit=2.0, max_limit=8.0)
    excursion_count = env_info.get("excursions_count", 0)

    recall_df, _ = common.load_csv_as_dataframe(
        os.path.join(os.path.dirname(__file__), "data", "recalls.csv")
    )
    active_recalls_count = len(recall_df)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Pending Actions for Review",
            value=pending_count,
            delta="Awaiting Sign-off" if pending_count > 0 else "All Approved",
            delta_color="inverse",
        )
    with col2:
        st.metric(
            label="Active Recall Directives",
            value=active_recalls_count,
            help="Active manufacturer or regulatory recalls in recalls.csv",
        )
    with col3:
        st.metric(
            label="Cold-Chain Excursions",
            value=excursion_count,
            help="Temperature events exceeding 8.0°C in cold storage rooms",
        )
    with col4:
        st.metric(
            label="Near-Expiry / Expired Batches",
            value=f"{near_expiry_count} / {expired_count}",
            help="Batches expiring within 30 days / Already expired",
        )

    if pending_count > 0:
        st.error(
            f"🚨 **Attention Required**: There are **{pending_count}** simulated action(s) awaiting your decision in the Action Review Panel.",
            icon="🔔",
        )

    st.divider()
    st.markdown("### Warehouse Inventory Summary")
    inv_data = inv.load_inventory()
    inv_df = inv_data.get("inventory", pd.DataFrame())
    prod_df = inv_data.get("products", pd.DataFrame())

    if not inv_df.empty and not prod_df.empty:
        merged_inv = inv_df.merge(prod_df, on="sku", how="left")
        display_cols = ["sku", "brand", "batch", "warehouse", "qty", "storage", "expiry_date", "critical_drug"]
        present_cols = [c for c in display_cols if c in merged_inv.columns]
        st.dataframe(merged_inv[present_cols], use_container_width=True)
    else:
        st.warning("Inventory records unavailable.")


# ==============================================================================
# TAB 2: BATCH TRACEABILITY
# ==============================================================================
with tab_batch:
    st.subheader("Batch Investigation & Customer Traceability")
    st.caption("Search Arogya Pharma inventory for regulatory recall status, physical warehouse stock, and recipient customer dispatches.")

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
                st.markdown("#### Product & Warehouse Inventory")
                st.write(f"**Product Name:** {b_data.get('product_name')}")
                st.write(f"**SKU:** `{b_data.get('sku')}`")
                st.write(f"**Category:** {b_data.get('category')}")
                st.write(f"**Storage Requirement:** {b_data.get('storage')}")
                st.write(f"**Total Remaining Warehouse Stock:** `{b_data.get('total_warehouse_stock')}` units")

                # Warehouse breakdown
                st.markdown("##### Stock by Warehouse")
                st.table(b_data.get("warehouses", []))

            with col_t2:
                st.markdown("#### Regulatory Recall Status")
                if is_recalled:
                    st.error(f"⛔ **CRITICAL ALERT: Batch '{target_batch}' is actively RECALLED!**")
                    recall_res = inv.check_recall(target_batch)
                    details = recall_res.get("recall_details", {})
                    st.write(f"**Recall Class:** `{details.get('recall_class', 'Class I')}`")
                    st.write(f"**Notice Date:** `{details.get('recall_date')}`")
                    st.write(f"**Directive Reason:** {details.get('reason')}")
                else:
                    st.success(f"✅ Batch '{target_batch}' is CLEAN (No active recall notice).")

            # Customer Dispatches Trace
            st.divider()
            st.markdown(f"#### Customer Dispatches Trace for Batch '{target_batch}'")
            cust_res = inv.get_affected_customers(target_batch)

            if cust_res.get("total_dispatched_units", 0) > 0:
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Total Units Dispatched", cust_res["total_dispatched_units"])
                with c2:
                    st.metric("Retail Chemists Reached", cust_res["chemists_count"])
                with c3:
                    st.metric("Hospitals Reached", cust_res["hospitals_count"])

                st.markdown("##### Affected Customer Roster")
                st.dataframe(pd.DataFrame(cust_res.get("customers", [])), use_container_width=True)
            else:
                st.info(f"No customer dispatch records found for batch '{target_batch}'.")

            # Simulated Dispatch Validation Tool
            st.divider()
            st.markdown("#### Test Simulated Dispatch Validation")
            st.caption("Verify the safety engine rules: recalled batches are strictly blocked, and quantities cannot exceed available stock.")
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
                    st.success(f"✅ Dispatch VALIDATED: {val_outcome['reason']}")
                else:
                    st.error(f"⛔ Dispatch REJECTED: {val_outcome['reason']}")


# ==============================================================================
# TAB 3: ENVIRONMENTAL RISKS
# ==============================================================================
with tab_env:
    st.subheader("Environmental Cold-Chain Storage Monitoring")
    st.caption("Review sensor telemetry for temperature excursions (configured limit: 2.0°C to 8.0°C). Escalates potential incidents for human QA stability review.")

    env_result = env.check_temperature_breach(min_limit=2.0, max_limit=8.0)
    excursions = env_result.get("excursions", [])

    if excursions:
        st.error(f"⚠️ **Identified {len(excursions)} Cold-Chain Excursion Event(s)**", icon="❄️")
        st.caption("Note: A temperature breach indicates potential cold-chain compromise, but does not independently determine product degradation. Stability testing is required.")

        for exc in excursions:
            with st.expander(f"Excursion at {exc.get('warehouse')} ({exc.get('cold_room')}) — Peak: {exc.get('peak_temp_c')}°C", expanded=True):
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
                            st.write(f"- 📦 Batch `{b}` (Regular Insulin / Vaccine stock)")
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
        st.success("✅ All cold-chain storage sensor telemetry is within compliant bounds (2.0°C - 8.0°C).")

    # Power Outage Stability Tool
    st.divider()
    st.markdown("#### Power Outage Thermal Stability Audit")
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
        st.json(outage_res)


# ==============================================================================
# TAB 4: SEASONAL DEMAND
# ==============================================================================
with tab_seasonal:
    st.subheader("Seasonal Demand Intelligence & Pipeline Deficit Analysis")
    st.caption("Evaluates historical dispatch velocity, projected seasonal surges, usable warehouse stock, and incoming purchase orders.")

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

        st.markdown(f"#### Seasonal Demand & Supply Pipeline for `{selected_sku}`")
        st.caption("ℹ️ *Estimates calculated from distributor historical dispatch dataset.*")

        c_f1, c_f2, c_f3, c_f4 = st.columns(4)
        with c_f1:
            st.metric("Projected Seasonal Demand", f"{gap_res.get('projected_demand')} units")
        with c_f2:
            st.metric("Usable Warehouse Stock", f"{gap_res.get('usable_warehouse_stock')} units", help="Excludes recalled and expired inventory")
        with c_f3:
            st.metric("Incoming Purchase Orders", f"{gap_res.get('incoming_po_stock')} units", help="Confirmed and In-Transit purchase orders")
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
            st.markdown("##### Supplier Lead Time & MOQ Parameters")
            st.write(
                f"- **Manufacturer:** {supp_info.get('manufacturer')} | "
                f"**Lead Time:** `{supp_info.get('lead_time_days')}` days | "
                f"**MOQ:** `{supp_info.get('moq')}` units | "
                f"**Return Window:** `{supp_info.get('return_window_days')}` days"
            )
            if gap_res.get("has_shortage"):
                st.warning(f"Recommended purchase order: **{gap_res.get('recommended_order_qty')} units** to satisfy MOQ and clear the projected deficit.")

        # Supplementary Research Inspection
        st.divider()
        st.markdown("#### Supplementary Research Data: `seasonal_diseases_vaccines.csv`")
        research_info = seasonal.inspect_supplementary_research()
        if research_info.get("available"):
            st.info(f"ℹ️ **Research Note**: {research_info.get('limitations_notice')}")
            st.dataframe(pd.DataFrame(research_info.get("records", [])), use_container_width=True)
        else:
            st.caption("Supplementary research file is not loaded.")


# ==============================================================================
# TAB 5: AI INVESTIGATION PANEL
# ==============================================================================
with tab_ai:
    st.subheader("AI Supply-Chain Decision-Support Agent")
    st.caption("Ask questions in natural language. The agent coordinates real analytical tools, gathers concrete evidence, compares response options, and stages actions.")

    # Quick prompt presets
    st.markdown("**Quick Example Prompts:**")
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
        st.markdown(f"### Investigation Report: *\"{investigation['query']}\"*")

        # Engine mode badge
        engine_label = investigation["engine_mode"]
        badge_color = "blue" if "LLM" in engine_label else "orange"
        st.markdown(f"**Execution Mode:** :{badge_color}[**{engine_label}**] | **Classified Intent:** `{investigation['intent']}`")

        col_tools, col_findings = st.columns([1, 2])
        with col_tools:
            st.markdown("#### Tools Coordinated")
            for t in investigation["tools_used"]:
                st.write(f"- 🔧 `{t}`")

            if investigation["uncertainties"]:
                st.markdown("#### Uncertainties & Missing Data")
                for u in investigation["uncertainties"]:
                    st.warning(f"⚠️ {u}")

        with col_findings:
            st.markdown("#### Analytical Findings & Evidence")
            for f in investigation["findings"]:
                st.write(f"• {f}")

        # Feasible Options Comparison
        comp = investigation.get("options_comparison", {})
        st.divider()
        st.markdown("#### Response Options Comparison")
        if comp.get("options"):
            st.info(f"💡 **Recommendation Strategy**: {comp.get('recommendation_summary')}")
            for opt in comp["options"]:
                with st.expander(f"Option: {opt.get('title')} — {opt.get('feasibility')}", expanded=True):
                    st.write(f"**Benefits:** {opt.get('benefits')}")
                    st.write(f"**Trade-offs:** {opt.get('trade_offs')}")
                    st.write(f"**Limitations:** {opt.get('limitations')}")
                    st.json(opt.get("cited_evidence", {}))

        # Decision-Support Recommendation
        rec = investigation.get("recommendation", {})
        st.markdown("#### Decision-Support Recommendation")
        st.success(rec.get("summary"))

        # Proposed Simulated Action
        proposed = investigation.get("proposed_action")
        if proposed:
            st.markdown("#### Proposed Action for Human Authorization")
            st.write(f"Action Type: `{proposed.get('action_type')}`")
            st.json(proposed.get("details", {}))

            stage_key = f"btn_stage_{proposed.get('action_type')}_{investigation['intent']}"
            if st.button("Stage This Action for Human Review", key=stage_key):
                new_act = actions.create_action(
                    action_type=proposed.get("action_type"),
                    details=proposed.get("details", {}),
                )
                st.session_state["action_notice"] = f"Simulated action `{new_act['action_id']}` successfully staged! Review it in the Action Review Panel."
                st.rerun()

        if st.session_state.get("action_notice"):
            st.success(st.session_state["action_notice"])


# ==============================================================================
# TAB 6: ACTION REVIEW PANEL
# ==============================================================================
with tab_actions:
    st.subheader("Simulated Action Review & Human Governance Panel")
    st.caption("Qualified human reviewers (QA / QP) must explicitly approve or reject simulated supply-chain actions.")

    pending_list = actions.list_pending_actions()

    if not pending_list:
        st.success("🎉 No actions currently pending human review.")
    else:
        st.write(f"Found **{len(pending_list)}** action(s) awaiting your decision:")

        for act in pending_list:
            act_id = act.get("action_id")
            with st.container():
                st.markdown("---")
                col_info, col_decide = st.columns([3, 2])

                with col_info:
                    st.markdown(f"### Action `{act_id}`")
                    st.write(f"**Type:** `{act.get('action_type')}` | **Status:** ⏳ `{act.get('status')}`")
                    st.write(f"**Created At:** `{act.get('created_at')}`")
                    st.write("**Details:**")
                    st.json(act.get("details", {}))

                with col_decide:
                    st.markdown("#### Governance Sign-off")
                    st.caption(f"Signing Reviewer: **{reviewer_name}**")

                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        if st.button("✅ Approve", key=f"app_{act_id}", use_container_width=True):
                            res = actions.review_action(act_id, "approved", reviewer_name)
                            if res.get("status") == "error":
                                st.error(res.get("message"))
                            else:
                                st.success(f"Action {act_id} APPROVED.")
                                st.rerun()

                    with btn_c2:
                        if st.button("❌ Reject", key=f"rej_{act_id}", use_container_width=True):
                            res = actions.review_action(act_id, "rejected", reviewer_name)
                            if res.get("status") == "error":
                                st.error(res.get("message"))
                            else:
                                st.warning(f"Action {act_id} REJECTED.")
                                st.rerun()

    # Complete Audit Trail
    st.divider()
    st.subheader("Simulated Action Audit Trail")
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
