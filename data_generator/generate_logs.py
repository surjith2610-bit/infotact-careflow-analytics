"""
CareFlow - Clinical Pathway Process Mining System
Module: data_generator/generate_logs.py

Description:
    Synthetic hospital event log generator designed for healthcare process mining.
    Simulates realistic patient journeys through clinical workflows, introducing
    configurable process bottlenecks (e.g., X-Ray -> Triage rework loop).
"""

import os
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
import pandas as pd


# -----------------------------------------------------------------------------
# Configuration & Clinical Workflow Constants
# -----------------------------------------------------------------------------
DEFAULT_CASE_COUNT = 150
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "raw_event_logs.csv")

# Clinical activities catalog
ACTIVITIES = {
    "REGISTRATION": "Registration",
    "TRIAGE": "Triage",
    "XRAY": "X-Ray",
    "LAB_TEST": "Lab Test",
    "DOCTOR_CONSULT": "Doctor Consult",
    "PAPERWORK_CHECK": "Paperwork Check",
    "DISCHARGE": "Discharge",
}

# Typical activity durations in minutes (min_duration, max_duration)
ACTIVITY_DURATIONS = {
    ACTIVITIES["REGISTRATION"]: (5, 15),
    ACTIVITIES["TRIAGE"]: (10, 25),
    ACTIVITIES["XRAY"]: (20, 60),
    ACTIVITIES["LAB_TEST"]: (30, 90),
    ACTIVITIES["DOCTOR_CONSULT"]: (15, 45),
    ACTIVITIES["PAPERWORK_CHECK"]: (10, 30),
    ACTIVITIES["DISCHARGE"]: (5, 20),
}

# Waiting/transit time between steps (min_wait, max_wait in minutes)
DEFAULT_TRANSIT_TIME = (5, 20)


class HospitalEventLogGenerator:
    """
    Simulates clinical pathway event logs with realistic time distributions
    and intentional operational inefficiencies for process mining analysis.
    """

    def __init__(
        self,
        case_count: int = DEFAULT_CASE_COUNT,
        loopback_probability: float = 0.40,
        start_date: datetime = None,
        random_seed: int = 42,
    ):
        """
        Initialize the generator.

        Args:
            case_count (int): Total number of patient cases (default: 150).
            loopback_probability (float): Rate of X-Ray -> Triage rework (default: 0.40).
            start_date (datetime): Base start timestamp for log generation.
            random_seed (int): Seed for reproducibility.
        """
        self.case_count = case_count
        self.loopback_probability = loopback_probability
        self.start_date = start_date or datetime(2026, 9, 1, 8, 0, 0)
        random.seed(random_seed)

    def _get_next_timestamp(self, current_time: datetime, activity: str) -> datetime:
        """Calculates realistic next event timestamp incorporating activity execution & waiting time."""
        dur_min, dur_max = ACTIVITY_DURATIONS.get(activity, (10, 30))
        wait_min, wait_max = DEFAULT_TRANSIT_TIME
        total_delta = random.randint(dur_min, dur_max) + random.randint(wait_min, wait_max)
        return current_time + timedelta(minutes=total_delta)

    def _generate_pathway(self, case_id: str, case_start_time: datetime) -> List[Dict[str, Any]]:
        """
        Generates a sequence of clinical events for a single patient trace.
        """
        events: List[Dict[str, Any]] = []
        current_time = case_start_time

        # Step 1: Registration
        events.append({
            "Case_ID": case_id,
            "Activity_Name": ACTIVITIES["REGISTRATION"],
            "Timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # Step 2: Triage
        current_time = self._get_next_timestamp(current_time, ACTIVITIES["REGISTRATION"])
        events.append({
            "Case_ID": case_id,
            "Activity_Name": ACTIVITIES["TRIAGE"],
            "Timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # Pathway Branching:
        # 1: Imaging pathway (with potential rework loop)
        # 2: Lab diagnostic pathway
        # 3: Fast-track consultation pathway
        path_type = random.choices(["imaging", "lab", "fast_track"], weights=[0.55, 0.30, 0.15])[0]

        if path_type == "imaging":
            current_time = self._get_next_timestamp(current_time, ACTIVITIES["TRIAGE"])
            events.append({
                "Case_ID": case_id,
                "Activity_Name": ACTIVITIES["XRAY"],
                "Timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            })

            # Intentional Process Bottleneck: 40% loop back to Triage
            if random.random() < self.loopback_probability:
                # Loop-back: X-Ray -> Triage (Re-evaluation / Incomplete clinical order rework)
                current_time = self._get_next_timestamp(current_time, ACTIVITIES["XRAY"])
                events.append({
                    "Case_ID": case_id,
                    "Activity_Name": ACTIVITIES["TRIAGE"],
                    "Timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                })

                # Re-consultation / Secondary routing
                current_time = self._get_next_timestamp(current_time, ACTIVITIES["TRIAGE"])
                events.append({
                    "Case_ID": case_id,
                    "Activity_Name": ACTIVITIES["DOCTOR_CONSULT"],
                    "Timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                })
            else:
                current_time = self._get_next_timestamp(current_time, ACTIVITIES["XRAY"])
                events.append({
                    "Case_ID": case_id,
                    "Activity_Name": ACTIVITIES["DOCTOR_CONSULT"],
                    "Timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                })

        elif path_type == "lab":
            current_time = self._get_next_timestamp(current_time, ACTIVITIES["TRIAGE"])
            events.append({
                "Case_ID": case_id,
                "Activity_Name": ACTIVITIES["LAB_TEST"],
                "Timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            })

            current_time = self._get_next_timestamp(current_time, ACTIVITIES["LAB_TEST"])
            events.append({
                "Case_ID": case_id,
                "Activity_Name": ACTIVITIES["DOCTOR_CONSULT"],
                "Timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            })

        else:  # fast_track
            current_time = self._get_next_timestamp(current_time, ACTIVITIES["TRIAGE"])
            events.append({
                "Case_ID": case_id,
                "Activity_Name": ACTIVITIES["DOCTOR_CONSULT"],
                "Timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            })

        # Post-consultation: Paperwork Check
        current_time = self._get_next_timestamp(current_time, ACTIVITIES["DOCTOR_CONSULT"])
        events.append({
            "Case_ID": case_id,
            "Activity_Name": ACTIVITIES["PAPERWORK_CHECK"],
            "Timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # Final step: Discharge
        current_time = self._get_next_timestamp(current_time, ACTIVITIES["PAPERWORK_CHECK"])
        events.append({
            "Case_ID": case_id,
            "Activity_Name": ACTIVITIES["DISCHARGE"],
            "Timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        return events

    def generate(self) -> pd.DataFrame:
        """
        Executes generation of all patient cases and compiles into a pandas DataFrame.
        """
        all_events: List[Dict[str, Any]] = []

        for i in range(1, self.case_count + 1):
            case_id = f"PAT-{i:04d}"
            # Scatter patient arrival over several days/hours
            arrival_offset_hours = (i - 1) * random.uniform(0.5, 2.5)
            case_start = self.start_date + timedelta(hours=arrival_offset_hours)
            case_events = self._generate_pathway(case_id, case_start)
            all_events.extend(case_events)

        df = pd.DataFrame(all_events)
        return df

    def save_to_csv(self, output_path: str = OUTPUT_FILE) -> str:
        """
        Generates and saves the event logs to a CSV file.
        """
        df = self.generate()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False)
        return output_path


def main():
    """CLI execution entrypoint."""
    print("=" * 60)
    print("CareFlow - Synthetic Clinical Event Log Generator")
    print("=" * 60)

    generator = HospitalEventLogGenerator(
        case_count=150,
        loopback_probability=0.40,
        random_seed=42,
    )

    output_file = generator.save_to_csv()
    df = pd.read_csv(output_file)

    print(f"[SUCCESS] Generated synthetic event log dataset.")
    print(f"[OUTPUT]  Location  : {output_file}")
    print(f"[METRICS] Total Rows: {len(df):,}")
    print(f"[METRICS] Total Cases     : {df['Case_ID'].nunique():,}")
    print(f"[METRICS] Unique Activities: {df['Activity_Name'].nunique()} ({', '.join(df['Activity_Name'].unique())})")
    
    # Calculate and display loopback count
    cases_with_xray = set()
    cases_with_loop = []
    for cid, group in df.groupby("Case_ID"):
        activities = group["Activity_Name"].tolist()
        if "X-Ray" in activities:
            cases_with_xray.add(cid)
        for idx in range(len(activities) - 1):
            if activities[idx] == "X-Ray" and activities[idx+1] == "Triage":
                cases_with_loop.append(cid)
                break

    xray_count = len(cases_with_xray)
    loop_count = len(cases_with_loop)
    xray_loop_pct = (loop_count / xray_count * 100) if xray_count else 0
    total_loop_pct = (loop_count / df['Case_ID'].nunique()) * 100
    print(f"[REWORK]  X-Ray Patients with Loopback: {loop_count}/{xray_count} ({xray_loop_pct:.1f}% of X-Ray cohort)")
    print(f"[REWORK]  Overall Cohort Loopback Rate: {loop_count}/{df['Case_ID'].nunique()} ({total_loop_pct:.1f}% of all patients)")
    print("=" * 60)


if __name__ == "__main__":
    main()
