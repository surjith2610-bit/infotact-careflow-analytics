"""
CareFlow - Clinical Pathway Process Mining System
Module: data_generator/generate_logs.py

Description:
    Synthetic hospital EHR event log generator designed for healthcare process mining.
    Simulates realistic patient journeys through clinical workflows, introducing
    a controlled process bug (X-Ray -> Triage rework loop in ~40% of X-Ray cases).
"""

import os
import random
from datetime import datetime, timedelta
import pandas as pd


# -----------------------------------------------------------------------------
# Clinical Activities & Configuration Constants
# -----------------------------------------------------------------------------
TOTAL_PATIENTS = 800

ACTIVITIES = [
    "Registration",
    "Triage",
    "X-Ray",
    "Lab Test",
    "Doctor Consult",
    "Paperwork Check",
    "Discharge",
]

# Output path definition
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "raw_ehr_logs.csv")


def generate_patient_flow(patient_id: int, start_time: datetime) -> list:
    """
    Generates a realistic sequence of clinical events for a single patient.

    Args:
        patient_id (int): Numerical patient index (1 to 800).
        start_time (datetime): Arrival / Registration timestamp.

    Returns:
        list: List of dictionaries representing event log rows for this patient.
    """
    case_id = f"P{patient_id:04d}"
    events = []
    current_time = start_time

    # Decide pathway type:
    # 50% Test Flow (X-Ray pathway), 35% Normal Flow, 15% Lab Flow
    pathway_choice = random.random()

    if pathway_choice < 0.50:
        # Test Flow (X-Ray pathway)
        # Normal sequence: Registration -> Triage -> X-Ray -> Doctor Consult -> Discharge (+ optional Paperwork Check)
        sequence = ["Registration", "Triage", "X-Ray"]

        # 🔥 CRITICAL: INJECT PROCESS BUG (~40% of X-Ray cases loop back to Triage immediately after X-Ray)
        if random.random() < 0.40:
            sequence.append("Triage")  # Loop-back bug

        sequence.append("Doctor Consult")

        # Optionally add Paperwork Check to reach 4-7 events range
        if random.random() < 0.70:
            sequence.append("Paperwork Check")

        sequence.append("Discharge")

    elif pathway_choice < 0.85:
        # Normal Flow
        # Registration -> Triage -> Doctor Consult -> Discharge (+ optional Lab Test / Paperwork Check)
        sequence = ["Registration", "Triage"]

        if random.random() < 0.30:
            sequence.append("Lab Test")

        sequence.append("Doctor Consult")

        if random.random() < 0.60:
            sequence.append("Paperwork Check")

        sequence.append("Discharge")

    else:
        # Lab Flow
        sequence = ["Registration", "Triage", "Lab Test", "Doctor Consult", "Paperwork Check", "Discharge"]

    # Build timed event log rows
    for i, activity in enumerate(sequence):
        events.append({
            "Case_ID": case_id,
            "Activity_Name": activity,
            "Timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # Add random delay (5 to 20 minutes) between events to ensure strictly increasing timestamps
        delay_minutes = random.randint(5, 20)
        current_time += timedelta(minutes=delay_minutes)

    return events


def generate_all_logs(total_patients: int = TOTAL_PATIENTS) -> pd.DataFrame:
    """
    Orchestrates log generation for all patients and formats into a DataFrame.

    Args:
        total_patients (int): Total number of patient cases to generate.

    Returns:
        pd.DataFrame: PM4Py compatible DataFrame with columns [Case_ID, Activity_Name, Timestamp].
    """
    all_events = []
    base_start_time = datetime.now().replace(microsecond=0)

    for i in range(1, total_patients + 1):
        # Stagger patient arrivals (0 to 15 mins offset per patient)
        arrival_offset = timedelta(minutes=random.randint(0, 15) * (i - 1) // 3)
        patient_start_time = base_start_time + arrival_offset

        patient_events = generate_patient_flow(i, patient_start_time)
        all_events.extend(patient_events)

    df = pd.DataFrame(all_events)

    # Convert Timestamp to datetime type for accurate sorting
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])

    # Ensure dataset is sorted by Case_ID and Timestamp
    df = df.sort_values(by=["Case_ID", "Timestamp"]).reset_index(drop=True)

    # Format Timestamp back to clean string format
    df["Timestamp"] = df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

    return df


def main():
    """
    Main function to generate logs, save to CSV, and display validation stats.
    """
    random.seed(42)  # For reproducible output

    print("=" * 60)
    print("CareFlow - EHR Event Log Generator")
    print("=" * 60)
    print(f"Generating synthetic logs for {TOTAL_PATIENTS} patients...")

    # Generate logs
    df = generate_all_logs(TOTAL_PATIENTS)

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Save to CSV
    df.to_csv(OUTPUT_FILE, index=False)

    # Calculate validation metrics
    total_patients = df["Case_ID"].nunique()
    total_events = len(df)

    # Check process bug stats (X-Ray -> Triage rework loop)
    bug_cases = 0
    xray_cases = 0
    for case_id, group in df.groupby("Case_ID"):
        acts = group["Activity_Name"].tolist()
        if "X-Ray" in acts:
            xray_cases += 1
            for idx in range(len(acts) - 1):
                if acts[idx] == "X-Ray" and acts[idx + 1] == "Triage":
                    bug_cases += 1
                    break

    bug_pct = (bug_cases / xray_cases * 100) if xray_cases > 0 else 0

    # Print Validation Information
    print("\n[SUCCESS] Synthetic EHR event log dataset generated successfully!")
    print(f"[FILE PATH]      : {OUTPUT_FILE}")
    print(f"Total Patients   : {total_patients}")
    print(f"Total Events     : {total_events}")
    print(f"Avg Events/Case  : {total_events / total_patients:.2f}")
    print(f"X-Ray Cases      : {xray_cases}")
    print(f"Process Bug Cases: {bug_cases} ({bug_pct:.1f}% of X-Ray cases looped back to Triage)")
    print("\n--- SAMPLE ROWS ---")
    print(df.head(10).to_string(index=False))
    print("=" * 60)


if __name__ == "__main__":
    main()
