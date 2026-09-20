"""
CareFlow - Clinical Pathway Process Mining System
Module: data_generator/load_to_bq.py

Description:
    Production-style ingestion script to load synthetic EHR event logs from CSV
    into Google BigQuery for downstream dbt transformations and process mining.

Security Note:
    Service account credentials (e.g., careflow-key.json) MUST NEVER be hardcoded
    or committed to version control / GitHub. Always ensure key files are listed
    in .gitignore and managed via environment variables.
"""

import os
import sys
from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError


# -----------------------------------------------------------------------------
# 1. SECURITY & AUTHENTICATION SETUP
# -----------------------------------------------------------------------------
# Security Best Practice: Use environment variable for authentication.
# Ensure 'careflow-key.json' is added to .gitignore and NEVER pushed to GitHub.
KEY_FILE = "careflow-key.json"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", KEY_FILE)


# -----------------------------------------------------------------------------
# 2. CONFIGURATION & CONSTANTS
# -----------------------------------------------------------------------------
# Replace 'your-project-id' with your actual Google Cloud Project ID or set GCP_PROJECT_ID env var
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "your-project-id")
DATASET_ID = "careflow_raw"
TABLE_ID = "raw_ehr_logs"

# Full table path: your-project-id.careflow_raw.raw_ehr_logs
TABLE_REF = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

# Absolute path resolution for input CSV file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE_PATH = os.path.join(SCRIPT_DIR, "output", "raw_ehr_logs.csv")


# -----------------------------------------------------------------------------
# 3. BIGQUERY INGESTION LOGIC
# -----------------------------------------------------------------------------
def load_csv_to_bigquery():
    """
    Reads the raw EHR logs CSV and loads it into BigQuery raw dataset.
    """
    print("=" * 60)
    print("CareFlow - BigQuery Data Ingestion Pipeline")
    print("=" * 60)
    print(f"Target table name: {TABLE_REF}")
    print(f"Source CSV file  : {CSV_FILE_PATH}")
    print("=" * 60)

    # Step 1: Verify source CSV file exists
    if not os.path.exists(CSV_FILE_PATH):
        print(f"[ERROR] Source CSV file not found at: {CSV_FILE_PATH}")
        print("[ERROR] Please run 'python data_generator/generate_logs.py' first.")
        sys.exit(1)

    try:
        # Step 2: Initialize BigQuery Client
        # Authenticates automatically using GOOGLE_APPLICATION_CREDENTIALS
        client = bigquery.Client(project=PROJECT_ID)

        # Ensure target dataset exists before attempting load
        dataset_ref = bigquery.DatasetReference(PROJECT_ID, DATASET_ID)
        try:
            client.get_dataset(dataset_ref)
        except GoogleCloudError:
            print(f"[INFO] Dataset '{DATASET_ID}' does not exist. Creating dataset...")
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = "US"
            client.create_dataset(dataset, timeout=30)
            print(f"[INFO] Dataset '{DATASET_ID}' created successfully.")

        # Step 3: Configure BigQuery LoadJobConfig
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,      # Skip CSV header row (Case_ID, Activity_Name, Timestamp)
            autodetect=True,          # Automatically detect schema fields and types
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,  # Truncate and replace table on reload
        )

        # Step 4: Execute Load Job
        print("\nLoading started...")
        with open(CSV_FILE_PATH, "rb") as source_file:
            job = client.load_table_from_file(
                source_file,
                TABLE_REF,
                job_config=job_config
            )

        # Step 5: Wait for job completion
        job.result()  # Blocks until load job completes or raises error

        # Step 6: Verify load completion and log details
        destination_table = client.get_table(TABLE_REF)
        print("\n[SUCCESS] Ingestion pipeline completed!")
        print(f"Target table name      : {TABLE_REF}")
        print(f"Rows loaded successfully: {destination_table.num_rows}")
        print("=" * 60)

    except GoogleCloudError as e:
        print(f"\n[ERROR] BigQuery ingestion job failed with GoogleCloudError:")
        print(f"Details: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred during BigQuery ingestion:")
        print(f"Details: {e}")
        sys.exit(1)


if __name__ == "__main__":
    load_csv_to_bigquery()
