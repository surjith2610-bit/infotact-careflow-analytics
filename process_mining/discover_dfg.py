"""
CareFlow - Clinical Pathway Process Mining System
Module: process_mining/discover_dfg.py

Description:
    Connects to Google BigQuery (project: careflow-analytics-189), queries the normalized
    clinical event log table from dbt marts, converts it to PM4Py standard format,
    discovers the Directly-Follows Graph (DFG / Spaghetti Diagram), saves the visualization
    as a PNG at process_mining/output/spaghetti_diagram.png, and prints process mining metrics.
"""

import os
import sys
import pandas as pd
import pm4py
from google.cloud import bigquery
from google.oauth2 import service_account

# Ensure Graphviz executable path is included on Windows if installed in standard location
GRAPHVIZ_WIN_PATH = r"C:\Program Files\Graphviz\bin"
if os.name == "nt" and os.path.exists(GRAPHVIZ_WIN_PATH) and GRAPHVIZ_WIN_PATH not in os.environ.get("PATH", ""):
    os.environ["PATH"] += os.pathsep + GRAPHVIZ_WIN_PATH

# -----------------------------------------------------------------------------
# Configuration Constants
# -----------------------------------------------------------------------------
PROJECT_ID = "careflow-analytics-189"

# Table candidate identifiers in BigQuery dbt marts/staging datasets
CANDIDATE_TABLES = [
    "careflow_marts.event_log",
    "careflow_raw.event_log",
    "stg_marts.event_log",
    "careflow_marts.fct_clinical_events",
]

CREDENTIALS_ENV_VAR = "GOOGLE_APPLICATION_CREDENTIALS"

# Directory & Output Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
OUTPUT_PNG = os.path.join(OUTPUT_DIR, "spaghetti_diagram.png")
LOCAL_CSV_FALLBACK = os.path.join(PROJECT_ROOT, "data", "raw_event_logs.csv")


def get_bigquery_client(project_id: str = PROJECT_ID) -> bigquery.Client:
    """
    Initializes a BigQuery client using service account credentials from an env variable,
    a local key file, or Application Default Credentials (ADC).
    """
    sa_path = os.environ.get(CREDENTIALS_ENV_VAR) or os.environ.get("BIGQUERY_SERVICE_ACCOUNT_PATH")

    if not sa_path and os.path.exists("careflow-key.json"):
        sa_path = "careflow-key.json"

    if sa_path:
        if not os.path.exists(sa_path):
            raise FileNotFoundError(f"Credentials JSON file not found at path: {sa_path}")
        print(f"[AUTH] Authenticating using service account JSON key: {sa_path}")
        credentials = service_account.Credentials.from_service_account_file(sa_path)
        return bigquery.Client(project=project_id, credentials=credentials)
    else:
        print(f"[AUTH] Attempting authentication via Application Default Credentials (ADC)...")
        return bigquery.Client(project=project_id)


def load_event_log_data(project_id: str = PROJECT_ID) -> pd.DataFrame:
    """
    Attempts to fetch the normalized event log from BigQuery dbt marts dataset tables.
    Falls back to local event log CSV if BigQuery credentials/connection are unavailable.
    """
    try:
        client = get_bigquery_client(project_id)
        
        for table_ref in CANDIDATE_TABLES:
            full_ref = f"{project_id}.{table_ref}" if table_ref.count(".") == 1 else table_ref
            query = f"""
                SELECT
                    case_id,
                    activity,
                    timestamp
                FROM `{full_ref}`
                ORDER BY case_id, timestamp ASC
            """
            print(f"[QUERY] Trying BigQuery table `{full_ref}`...")
            try:
                query_job = client.query(query)
                df = query_job.to_dataframe()
                if not df.empty:
                    print(f"        --> Successfully loaded {len(df)} rows from BigQuery table `{full_ref}`.")
                    return df
            except Exception as table_err:
                print(f"        --> Table `{full_ref}` query skipped/failed: {table_err}")

        raise RuntimeError("No candidate BigQuery table returned valid event log data.")

    except Exception as bq_err:
        print(f"[WARNING] Could not retrieve event log from BigQuery ({bq_err}).")
        if os.path.exists(LOCAL_CSV_FALLBACK):
            print(f"[FALLBACK] Loading event log from local dataset: {LOCAL_CSV_FALLBACK}")
            df = pd.read_csv(LOCAL_CSV_FALLBACK)
            column_mapping = {
                "Case_ID": "case_id",
                "Activity_Name": "activity",
                "Timestamp": "timestamp"
            }
            df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
            print(f"           --> Loaded {len(df)} rows from local backup CSV.")
            return df
        else:
            raise FileNotFoundError(f"Local backup file not found at: {LOCAL_CSV_FALLBACK}") from bq_err


def prepare_pm4py_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalizes columns and timestamps, then applies pm4py.format_dataframe().
    """
    print("\n[STEP 1/3] Formatting DataFrame for PM4Py...")
    
    # Standardize column names
    required_cols = {"case_id", "activity", "timestamp"}
    if not required_cols.issubset(set(df.columns)):
        raise KeyError(f"Input DataFrame must contain columns {required_cols}. Found: {list(df.columns)}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    df_formatted = pm4py.format_dataframe(
        df,
        case_id="case_id",
        activity_key="activity",
        timestamp_key="timestamp"
    )
    print("           --> PM4Py DataFrame formatting complete.")
    return df_formatted


def discover_and_visualize_dfg(df_formatted: pd.DataFrame) -> tuple:
    """
    Discovers the Directly-Follows Graph (DFG) and exports the visualization PNG.
    """
    print("\n[STEP 2/3] Discovering Directly-Follows Graph (DFG)...")
    dfg, start_activities, end_activities = pm4py.discover_dfg(df_formatted)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"\n[STEP 3/3] Rendering and saving Spaghetti Diagram to: {OUTPUT_PNG}")
    pm4py.save_vis_dfg(dfg, start_activities, end_activities, OUTPUT_PNG)
    print("           --> Visualization image exported successfully.")
    
    return dfg, start_activities, end_activities


def print_summary(df_formatted: pd.DataFrame, dfg: dict) -> None:
    """
    Prints a concise summary of process mining metrics and top directly-follows relationships.
    """
    # Unique cases and activities
    case_col = "case_id" if "case_id" in df_formatted.columns else "case:concept:name"
    act_col = "activity" if "activity" in df_formatted.columns else "concept:name"

    num_cases = df_formatted[case_col].nunique()
    num_activities = df_formatted[act_col].nunique()

    # Sort DFG relationships by frequency descending
    sorted_dfg = sorted(dfg.items(), key=lambda x: x[1], reverse=True)

    print("\n" + "=" * 65)
    print("   CAREFLOW - PROCESS MINING DISCOVERY SUMMARY (DAY 8)")
    print("=" * 65)
    print(f"   • Number of Unique Cases      : {num_cases}")
    print(f"   • Number of Unique Activities : {num_activities}")
    print(f"   • Total DFG Transitions (Edges): {len(dfg)}")
    print("\n   Top 5 Most Frequent Directly-Follows Relationships:")
    print("   " + "-" * 55)
    for idx, (rel, count) in enumerate(sorted_dfg[:5], 1):
        source_act, target_act = rel
        print(f"   {idx}. {source_act} -> {target_act}: {count}")
    print("=" * 65 + "\n")


def main():
    print("=" * 65)
    print("CareFlow - Day 8: Directly-Follows Graph (DFG) Discovery")
    print("=" * 65)

    try:
        raw_df = load_event_log_data(PROJECT_ID)
        formatted_df = prepare_pm4py_dataframe(raw_df)
        dfg, start_acts, end_acts = discover_and_visualize_dfg(formatted_df)
        print_summary(formatted_df, dfg)
    except Exception as e:
        print(f"\n[FATAL ERROR] DFG discovery failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
