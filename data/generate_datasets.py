"""
generate_datasets.py
Generates consistent, verifiable synthetic datasets for Arogya Pharma Distributors.
Ensures scenario targets:
- Recalled batch B2231: 180 units in inventory, 640 units dispatched to 23 chemists and 2 hospitals over past 30 days.
- Clean batch B2240: 400 units in inventory.
- Cross-file foreign keys and schemas match.
"""

import os
import pandas as pd
from datetime import datetime, timedelta

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

def generate_all():
    # 1. products.csv
    products = [
        {
            "sku": "SKU-AMOX-500",
            "molecule": "Amoxicillin 500mg",
            "brand": "Aro-Amox 500",
            "category": "Antibiotic",
            "storage": "Controlled Room Temp (15-25°C)",
            "critical_drug": False,
        },
        {
            "sku": "SKU-INS-REG",
            "molecule": "Regular Insulin 100IU/ml",
            "brand": "Aro-Insulin R",
            "category": "Anti-diabetic",
            "storage": "Cold Chain (2-8°C)",
            "critical_drug": True,
        },
        {
            "sku": "SKU-PARA-650",
            "molecule": "Paracetamol 650mg",
            "brand": "Aro-Para 650",
            "category": "Antipyretic/Analgesic",
            "storage": "Room Temp (15-25°C)",
            "critical_drug": False,
        },
        {
            "sku": "SKU-RAB-VAX",
            "molecule": "Rabies Vaccine (Human)",
            "brand": "Aro-Rabivax",
            "category": "Vaccine",
            "storage": "Cold Chain (2-8°C)",
            "critical_drug": True,
        },
        {
            "sku": "SKU-AZI-250",
            "molecule": "Azithromycin 250mg",
            "brand": "Aro-Azithro",
            "category": "Antibiotic",
            "storage": "Room Temp (15-25°C)",
            "critical_drug": False,
        },
    ]
    pd.DataFrame(products).to_csv(os.path.join(DATA_DIR, "products.csv"), index=False)

    # 2. customers.csv (400 chemists & 20 hospitals total represented; including 23 chemists & 2 hospitals for B2231)
    customers = []
    # 2 Hospitals
    customers.append({"customer": "HOSP-Victoria", "type": "Hospital", "location": "Bengaluru Central", "credit_terms": "Net 45"})
    customers.append({"customer": "HOSP-Manipal-East", "type": "Hospital", "location": "Bengaluru East", "credit_terms": "Net 30"})
    
    # 23 Chemists that received B2231
    for i in range(1, 24):
        customers.append({
            "customer": f"CHEM-Bengaluru-{i:03d}",
            "type": "Chemist",
            "location": f"Bengaluru Zone {((i-1)%5)+1}",
            "credit_terms": "Net 30" if i % 2 == 0 else "Net 15"
        })
    
    # Additional representative chemists and hospitals
    customers.append({"customer": "HOSP-KIMS-Hubballi", "type": "Hospital", "location": "Hubballi", "credit_terms": "Net 45"})
    customers.append({"customer": "HOSP-KR-Mysuru", "type": "Hospital", "location": "Mysuru", "credit_terms": "Net 45"})
    for i in range(24, 35):
        customers.append({
            "customer": f"CHEM-Regional-{i:03d}",
            "type": "Chemist",
            "location": "Hubballi" if i % 2 == 0 else "Mysuru",
            "credit_terms": "Net 30"
        })
    pd.DataFrame(customers).to_csv(os.path.join(DATA_DIR, "customers.csv"), index=False)

    # 3. inventory.csv
    inventory = [
        # Recalled batch B2231: 180 units in warehouse
        {
            "sku": "SKU-AMOX-500",
            "batch": "B2231",
            "warehouse": "WH-Central-Bengaluru",
            "qty": 180,
            "mfg_date": "2025-10-15",
            "expiry_date": "2027-04-15",
        },
        # Clean batch B2240: 400 units in warehouse
        {
            "sku": "SKU-AMOX-500",
            "batch": "B2240",
            "warehouse": "WH-Central-Bengaluru",
            "qty": 400,
            "mfg_date": "2026-02-10",
            "expiry_date": "2027-08-10",
        },
        # Cold chain insulin batch in Central Warehouse cold room
        {
            "sku": "SKU-INS-REG",
            "batch": "B1092",
            "warehouse": "WH-Central-Bengaluru",
            "qty": 120,
            "mfg_date": "2025-11-01",
            "expiry_date": "2026-11-15",  # near expiry (~1 month)
        },
        {
            "sku": "SKU-INS-REG",
            "batch": "B1105",
            "warehouse": "WH-North-Hubballi",
            "qty": 250,
            "mfg_date": "2026-01-15",
            "expiry_date": "2027-01-15",
        },
        # Near-expiry paracetamol batch (expires 2026-10-25, within 16 days of current date 2026-10-09)
        {
            "sku": "SKU-PARA-650",
            "batch": "B3011",
            "warehouse": "WH-Central-Bengaluru",
            "qty": 850,
            "mfg_date": "2025-06-01",
            "expiry_date": "2026-10-25",
        },
        {
            "sku": "SKU-PARA-650",
            "batch": "B3025",
            "warehouse": "WH-South-Mysuru",
            "qty": 3500,
            "mfg_date": "2026-03-01",
            "expiry_date": "2028-03-01",
        },
        # Expired rabies vaccine (expired 2026-09-30)
        {
            "sku": "SKU-RAB-VAX",
            "batch": "B8801",
            "warehouse": "WH-Central-Bengaluru",
            "qty": 45,
            "mfg_date": "2025-08-01",
            "expiry_date": "2026-09-30",
        },
        {
            "sku": "SKU-AZI-250",
            "batch": "B4412",
            "warehouse": "WH-North-Hubballi",
            "qty": 600,
            "mfg_date": "2026-04-01",
            "expiry_date": "2027-10-01",
        },
    ]
    pd.DataFrame(inventory).to_csv(os.path.join(DATA_DIR, "inventory.csv"), index=False)

    # 4. dispatches.csv
    # Challenge requirement: Recalled batch B2231 had 640 units dispatched over the preceding 30 days to 23 chemists and 2 hospitals
    dispatches = []
    # 2 Hospitals: 80 and 60 units (total 140)
    dispatches.append({"date": "2026-09-15", "customer": "HOSP-Victoria", "sku": "SKU-AMOX-500", "batch": "B2231", "qty": 80})
    dispatches.append({"date": "2026-09-18", "customer": "HOSP-Manipal-East", "sku": "SKU-AMOX-500", "batch": "B2231", "qty": 60})
    
    # 23 Chemists: remaining 500 units (20 chemists * 20 units = 400; 2 chemists * 30 = 60; 1 chemist * 40 = 40)
    chem_dispatches = [20]*20 + [30, 30, 40]
    base_date = datetime(2026, 9, 12)
    for idx, qty in enumerate(chem_dispatches, start=1):
        disp_date = (base_date + timedelta(days=idx)).strftime("%Y-%m-%d")
        dispatches.append({
            "date": disp_date,
            "customer": f"CHEM-Bengaluru-{idx:03d}",
            "sku": "SKU-AMOX-500",
            "batch": "B2231",
            "qty": qty,
        })
    
    # Verify B2231 total dispatches == 640
    b2231_total = sum(d["qty"] for d in dispatches if d["batch"] == "B2231")
    assert b2231_total == 640, f"Expected 640 dispatches for B2231, got {b2231_total}"
    
    # Other normal dispatches
    dispatches.append({"date": "2026-09-20", "customer": "HOSP-KIMS-Hubballi", "sku": "SKU-PARA-650", "batch": "B3011", "qty": 300})
    dispatches.append({"date": "2026-09-25", "customer": "CHEM-Regional-024", "sku": "SKU-PARA-650", "batch": "B3011", "qty": 150})
    dispatches.append({"date": "2026-10-02", "customer": "HOSP-Victoria", "sku": "SKU-INS-REG", "batch": "B1092", "qty": 40})
    
    pd.DataFrame(dispatches).to_csv(os.path.join(DATA_DIR, "dispatches.csv"), index=False)

    # 5. recalls.csv
    recalls = [
        {
            "date": "2026-10-08",
            "sku": "SKU-AMOX-500",
            "batches": "B2231",
            "reason": "API dissolution test failure; potential sub-potency detected in stability batch samples.",
            "recall_class": "Class I",
        }
    ]
    pd.DataFrame(recalls).to_csv(os.path.join(DATA_DIR, "recalls.csv"), index=False)

    # 6. temperature_logs.csv
    # Sensor logs for cold room CR-01 in WH-Central-Bengaluru.
    # Excursion: temperature reached 12.4°C on 2026-10-08 between 02:00 and 06:00
    temp_logs = []
    # Normal logs on Oct 7
    for hour in range(0, 24, 2):
        temp_logs.append({
            "warehouse": "WH-Central-Bengaluru",
            "cold_room": "CR-01",
            "timestamp": f"2026-10-07T{hour:02d}:00:00",
            "temp_c": round(4.0 + (hour % 3) * 0.4, 2),
        })
    # Excursion logs on Oct 8
    excursion_temps = {0: 4.5, 2: 7.8, 3: 11.2, 4: 12.6, 5: 11.8, 6: 8.5, 8: 4.8, 10: 4.2}
    for hour, temp in excursion_temps.items():
        temp_logs.append({
            "warehouse": "WH-Central-Bengaluru",
            "cold_room": "CR-01",
            "timestamp": f"2026-10-08T{hour:02d}:00:00",
            "temp_c": temp,
        })
    # WH-North-Hubballi normal logs
    for hour in range(0, 24, 4):
        temp_logs.append({
            "warehouse": "WH-North-Hubballi",
            "cold_room": "CR-02",
            "timestamp": f"2026-10-08T{hour:02d}:00:00",
            "temp_c": round(3.8 + (hour % 4) * 0.3, 2),
        })
    pd.DataFrame(temp_logs).to_csv(os.path.join(DATA_DIR, "temperature_logs.csv"), index=False)

    # 7. suppliers.csv
    suppliers = [
        {"manufacturer": "Arogya Formulation Labs", "sku": "SKU-AMOX-500", "lead_time_days": 5, "moq": 500, "return_window_days": 30},
        {"manufacturer": "Biocon Life India", "sku": "SKU-INS-REG", "lead_time_days": 7, "moq": 200, "return_window_days": 45},
        {"manufacturer": "Apex Healthcare Ltd", "sku": "SKU-PARA-650", "lead_time_days": 3, "moq": 1000, "return_window_days": 60},
        {"manufacturer": "Serum Biologicals", "sku": "SKU-RAB-VAX", "lead_time_days": 10, "moq": 100, "return_window_days": 30},
        {"manufacturer": "Sun Pharma Labs", "sku": "SKU-AZI-250", "lead_time_days": 4, "moq": 500, "return_window_days": 45},
    ]
    pd.DataFrame(suppliers).to_csv(os.path.join(DATA_DIR, "suppliers.csv"), index=False)

    # 8. purchase_orders.csv
    purchase_orders = [
        {
            "po": "PO-2026-0911",
            "manufacturer": "Arogya Formulation Labs",
            "sku": "SKU-AMOX-500",
            "qty": 800,
            "expected_date": "2026-10-18",
            "status": "Confirmed",
        },
        {
            "po": "PO-2026-0885",
            "manufacturer": "Apex Healthcare Ltd",
            "sku": "SKU-PARA-650",
            "qty": 2000,
            "expected_date": "2026-10-22",
            "status": "In-Transit",
        },
    ]
    pd.DataFrame(purchase_orders).to_csv(os.path.join(DATA_DIR, "purchase_orders.csv"), index=False)

    # 9. historical_demand.csv
    # 6 months of historical monthly aggregated demand across warehouses
    demand_records = []
    months = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    base_demands = {
        "SKU-AMOX-500": [450, 480, 520, 650, 710, 680],  # monsoon surge in Jul/Aug
        "SKU-PARA-650": [1800, 1900, 2100, 3200, 3800, 3100],  # viral seasonal surge
        "SKU-INS-REG": [280, 290, 275, 300, 310, 295],  # steady chronic demand
        "SKU-RAB-VAX": [90, 85, 95, 100, 110, 95],
        "SKU-AZI-250": [350, 360, 410, 580, 620, 590],
    }
    for sku, series in base_demands.items():
        for m_idx, m_str in enumerate(months):
            total_m_qty = series[m_idx]
            # split across 3 warehouses
            demand_records.append({"date": f"{m_str}-01", "warehouse": "WH-Central-Bengaluru", "sku": sku, "qty": int(total_m_qty * 0.6)})
            demand_records.append({"date": f"{m_str}-01", "warehouse": "WH-North-Hubballi", "sku": sku, "qty": int(total_m_qty * 0.25)})
            demand_records.append({"date": f"{m_str}-01", "warehouse": "WH-South-Mysuru", "sku": sku, "qty": int(total_m_qty * 0.15)})

    pd.DataFrame(demand_records).to_csv(os.path.join(DATA_DIR, "historical_demand.csv"), index=False)
    print("All 9 CSV datasets generated successfully.")

if __name__ == "__main__":
    generate_all()

