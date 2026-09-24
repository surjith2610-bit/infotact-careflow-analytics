"""
CareFlow - Clinical Pathway Process Mining System
Module: process_mining/extract_event_log.py

Description:
    Extracts cleaned clinical event logs from BigQuery dbt mart table, formats
    columns for PM4Py process mining compatibility (case:concept:name, concept:name,
    time:timestamp), converts timestamps to UTC datetime, builds a PM4Py EventLog,
    and exports the dataset as both .xes and .csv backup files.
"""

import os
import sys
import pandas as pd
import pm4py
from google.cloud import bigquery
from google.oauth2 import service_account

# -----------------------------------------------------------------------------
# Configuration Variables (Specify your dataset.table name and GCP project here)
# -----------------------------------------------------------------------------
PROJECT_ID = "careflow-analytics-189"
DATASET_TABLE = "careflow_marts.fct_clinical_events"  # Format: "dataset_name.table_name" or "project_id.dataset_name.table_name"
CREDENTIALS_ENV_VAR = "GOOGLE_APPLICATION_CREDENTIALS"

# Output directory setup (relative to script location)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
OUTPUT_XES = os.path.join(OUTPUT_DIR, "event_log.xes")
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "event_log.csv")


def get_bigquery_client(project_id: str, credentials_env_var: str = CREDENTIALS_ENV_VAR) -> bigquery.Client:
    """
    Initializes a BigQuery client using service account credentials specified in an env variable,
    or falls back to Application Default Credentials (ADC).

    Args:
        project_id (str): GCP project ID.
        credentials_env_var (str): Environment variable name containing JSON key path.

    Returns:
        bigquery.Client: Authenticated BigQuery client instance.
    """
    sa_path = os.environ.get(credentials_env_var)
    if not sa_path:
        # Secondary fallback env variable check
        sa_path = os.environ.get("BIGQUERY_SERVICE_ACCOUNT_PATH")

    if sa_path:
        if not os.path.exists(sa_path):
            raise FileNotFoundError(
                f"Service account JSON key file not found at path specified by '{credentials_env_var}': {sa_path}"
            )
        print(f"[AUTH] Authenticating via service account JSON from environment variable '{credentials_env_var}': {sa_path}")
        credentials = service_account.Credentials.from_service_account_file(sa_path)
        return bigquery.Client(project=project_id, credentials=credentials)
    else:
        print(f"[AUTH] Environment variable '{credentials_env_var}' not set. Attempting Application Default Credentials (ADC)...")
        return bigquery.Client(project=project_id)


def fetch_event_log_from_bigquery(client: bigquery.Client, project_id: str, dataset_table: str) -> pd.DataFrame:
    """
    Queries the dbt mart table on BigQuery for case_id, activity, and timestamp.

    Args:
        client (bigquery.Client): Authenticated BigQuery client.
        project_id (str): GCP project ID.
        dataset_table (str): Table identifier (e.g. 'dataset.table' or 'project.dataset.table').

    Returns:
        pd.DataFrame: DataFrame containing raw query results.
    """
    if "." in dataset_table and dataset_table.count(".") == 2:
        full_table_ref = dataset_table
    else:
        full_table_ref = f"{project_id}.{dataset_table}"

    query = f"""
        SELECT
            case_id,
            activity,
            timestamp
        FROM `{full_table_ref}`
        ORDER BY case_id, timestamp ASC
    """

    print(f"\n[STEP 1/6] Querying BigQuery mart table: `{full_table_ref}`...")
    try:
        query_job = client.query(query)
        df = query_job.to_dataframe()

        total_rows = len(df)
        unique_cases = df["case_id"].nunique() if "case_id" in df and total_rows > 0 else 0
        unique_activities = df["activity"].nunique() if "activity" in df and total_rows > 0 else 0

        print(f"           --> Rows Fetched     : {total_rows}")
        print(f"           --> Unique Cases     : {unique_cases}")
        print(f"           --> Unique Activities: {unique_activities}")

        if total_rows == 0:
            print(f"[WARNING] Query returned 0 rows from BigQuery table '{full_table_ref}'.")

        return df
    except Exception as e:
        print(f"[ERROR] BigQuery query execution failed for table '{full_table_ref}': {e}", file=sys.stderr)
        raise


def format_dataframe_for_pm4py(df: pd.DataFrame) -> pd.DataFrame:
    """
    Renames columns to PM4Py standards, converts timestamps to UTC datetime,
    and runs pm4py.format_dataframe().

    Args:
        df (pd.DataFrame): Raw DataFrame from BigQuery.

    Returns:
        pd.DataFrame: Formatted DataFrame ready for PM4Py conversion.
    """
    if df.empty:
        raise ValueError("Cannot format an empty DataFrame for PM4Py.")

    # Step 2: Rename columns
    print("\n[STEP 2/6] Renaming columns to PM4Py standard format...")
    column_mapping = {
        "case_id": "case:concept:name",
        "activity": "concept:name",
        "timestamp": "time:timestamp",
    }
    df = df.rename(columns=column_mapping)

    print(f"           --> Columns Renamed  : {list(df.columns)}")
    print(f"           --> Row Count        : {len(df)}")
    print(f"           --> Unique Cases     : {df['case:concept:name'].nunique()}")

    # Step 3: Convert timestamp to UTC datetime
    print("\n[STEP 3/6] Converting timestamp column to UTC datetime...")
    try:
        df["time:timestamp"] = pd.to_datetime(df["time:timestamp"], utc=True)
        print(f"           --> Timestamp Dtype  : {df['time:timestamp'].dtype}")
        print(f"           --> Row Count        : {len(df)}")
        print(f"           --> Unique Cases     : {df['case:concept:name'].nunique()}")
    except Exception as e:
        print(f"[ERROR] Failed to convert 'time:timestamp' column to UTC datetime: {e}", file=sys.stderr)
        raise

    # Step 4: PM4Py DataFrame Formatting
    print("\n[STEP 4/6] Formatting DataFrame using pm4py.format_dataframe()...")
    try:
        df_formatted = pm4py.format_dataframe(
            df,
            case_id="case:concept:name",
            activity_key="concept:name",
            timestamp_key="time:timestamp",
        )
        print(f"           --> Format Complete")
        print(f"           --> Row Count        : {len(df_formatted)}")
        print(f"           --> Unique Cases     : {df_formatted['case:concept:name'].nunique()}")
        return df_formatted
    except Exception as e:
        print(f"[ERROR] pm4py.format_dataframe() execution failed: {e}", file=sys.stderr)
        raise


def convert_and_export_log(df: pd.DataFrame) -> None:
    """
    Converts formatted DataFrame to PM4Py EventLog object and exports .xes and .csv backup files.

    Args:
        df (pd.DataFrame): PM4Py formatted DataFrame.
    """
    # Step 5: Convert to PM4Py EventLog
    print("\n[STEP 5/6] Converting DataFrame to PM4Py EventLog object...")
    try:
        event_log = pm4py.convert_to_event_log(df)
        total_traces = len(event_log)
        total_events = sum(len(trace) for trace in event_log)
        print(f"           --> EventLog Created : {type(event_log)}")
        print(f"           --> Total Traces     : {total_traces}")
        print(f"           --> Total Events     : {total_events}")
    except Exception as e:
        print(f"[ERROR] pm4py.convert_to_event_log() failed: {e}", file=sys.stderr)
        raise

    # Step 6: Export XES and CSV backup
    print("\n[STEP 6/6] Exporting outputs to disk...")
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # Export CSV backup
        print(f"           --> Writing CSV backup to: {OUTPUT_CSV}")
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"               Saved {len(df)} rows across {df['case:concept:name'].nunique()} cases.")

        # Export XES file
        print(f"           --> Writing XES event log to: {OUTPUT_XES}")
        pm4py.write_xes(event_log, OUTPUT_XES)
        print(f"               XES file created successfully.")

        print("\n" + "=" * 65)
        print("[SUCCESS] Event log extraction and export completed successfully!")
        print(f"          Outputs folder: {OUTPUT_DIR}")
        print(f"          - XES Log     : {OUTPUT_XES}")
        print(f"          - CSV Backup  : {OUTPUT_CSV}")
        print("=" * 65)
    except Exception as e:
        print(f"[ERROR] Failed to export event log files: {e}", file=sys.stderr)
        raise


def main():
    """
    Main pipeline entry point.
    """
    print("=" * 65)
    print("CareFlow - BigQuery to PM4Py Event Log Extractor")
    print("=" * 65)

    try:
        # Initialize client
        client = get_bigquery_client(PROJECT_ID, CREDENTIALS_ENV_VAR)

        # Fetch data
        raw_df = fetch_event_log_from_bigquery(client, PROJECT_ID, DATASET_TABLE)

        # Format DataFrame
        formatted_df = format_dataframe_for_pm4py(raw_df)

        # Convert and Export
        convert_and_export_log(formatted_df)

    except Exception as e:
        print(f"\n[FATAL ERROR] Pipeline aborted due to error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
