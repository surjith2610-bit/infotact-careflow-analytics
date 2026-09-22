# CareFlow Project - Week 1 Checkpoint & Verification Summary

**Date**: September 22, 2026  
**Status**: Completed & Verified (Checkpoint Day 5)  
**Milestone Tag**: `v0.1-data-pipeline`  

---

## 1. Executive Summary & Architecture Built

This week (Days 1–5), we successfully architected, generated, loaded, transformed, and verified the foundational data pipeline for **CareFlow**, a hospital clinical process-mining analytics platform.

### End-to-End Pipeline Architecture:
$$\text{Synthetic EHR Log Generator } (\text{Python}) \longrightarrow \text{Google BigQuery Raw Dataset } (\text{raw\_ehr\_logs}) \longrightarrow \text{dbt Staging View } (\text{stg\_ehr\_logs})$$

1. **Day 1 (Event Schema & Process Design)**: Designed the minimum tripartite process mining schema (`Case_ID`, `Activity_Name`, `Timestamp`) and cataloged 7 core hospital activities across 3 normative clinical pathways plus 1 deliberate process bottleneck (X-Ray $\rightarrow$ Triage loopback).
2. **Day 2 (Synthetic Data Generation)**: Built `data_generator/generate_logs.py` producing 800 patient journeys (4,544 total events) with controlled timestamps and a ~40% rework rate for imaging cases.
3. **Day 3 (Warehouse Loading)**: Built `data_generator/load_to_bq.py` using `google-cloud-bigquery` SDK to ingest raw event logs into BigQuery dataset `careflow_raw`, table `raw_ehr_logs`.
4. **Day 4 (dbt Project & Staging Model)**: Initialized `careflow_dbt` project connected to BigQuery, configured `src_careflow_raw.yml` source, and wrote `stg_ehr_logs.sql` staging model with clean string trimming, timestamp type casting, and surrogate key (`event_id`) generation.
5. **Day 5 (Pipeline Audit & Verification)**: Audited row counts, verified data types and zero-null integrity, implemented 5 dbt schema tests, and prepared project documentation.

---

## 2. Data Pipeline Verification Results

### A. End-to-End Row Count Audit

| Pipeline Layer | Location / Table | Row Count | Distinct Patients | Verification Status |
| :--- | :--- | :---: | :---: | :---: |
| **Raw Generator CSV** | `data_generator/output/raw_ehr_logs.csv` | **4,544** | 800 | Source of truth verified |
| **BigQuery Raw Table** | `careflow-analytics-189.careflow_raw.raw_ehr_logs` | **4,544** | 800 | 100% Match (0 rows lost) |
| **dbt Staging View** | `careflow-analytics-189.careflow_raw.stg_ehr_logs` | **4,544** | 800 | 100% Match (0 rows dropped) |

### B. Data Quality & Column Verification

| Staged Field | Target BigQuery Data Type | Transformation Applied | Null Count | Data Quality Finding |
| :--- | :--- | :--- | :---: | :--- |
| `event_id` | `INT64 / STRING` | `farm_fingerprint(concat(case_id, '_', activity, '_', timestamp))` | **0** | 100% unique surrogate key across all 4,544 rows |
| `case_id` | `STRING` | `trim(cast(Case_ID as string))` | **0** | Clean, formatted patient identifier (e.g., `P0001` to `P0800`) |
| `activity` | `STRING` | `trim(cast(Activity_Name as string))` | **0** | 7 distinct standardized activity names |
| `timestamp` | `TIMESTAMP` | `safe_cast(Timestamp as timestamp)` | **0** | Valid ISO-8601 timestamps, chronologically ordered per case |

---

## 3. dbt Schema Tests Summary

We added and verified 5 dbt schema tests inside `dbt_project/models/staging/schema.yml`:

```yaml
version: 2

models:
  - name: stg_ehr_logs
    description: "Staged and cleansed EHR patient event logs."
    columns:
      - name: event_id
        tests:
          - unique
          - not_null
      - name: case_id
        tests:
          - not_null
      - name: activity
        tests:
          - not_null
      - name: timestamp
        tests:
          - not_null
```

### dbt Test Execution Results:
- `PASS` `stg_ehr_logs_event_id_unique` (0 duplicate event keys found)
- `PASS` `stg_ehr_logs_event_id_not_null` (0 nulls found)
- `PASS` `stg_ehr_logs_case_id_not_null` (0 nulls found)
- `PASS` `stg_ehr_logs_activity_not_null` (0 nulls found)
- `PASS` `stg_ehr_logs_timestamp_not_null` (0 nulls found)

**Overall Test Result**: **5 / 5 Tests PASSED (100% Success)**

---

## 4. Issues / Blockers Encountered & Resolutions

1. **Issue: Service Account Credential Pathing**:
   - *Problem*: Hardcoded local paths in `profiles.yml` caused environment dependency errors.
   - *Resolution*: Updated `profiles.yml` to utilize environment variable lookup `{{ env_var('BIGQUERY_KEYFILE', 'careflow-key.json') }}` and verified `.gitignore` rules prevent accidental credential commits.

2. **Issue: Timestamp Type Consistency**:
   - *Problem*: CSV ingestion loads timestamps as strings in raw tables.
   - *Resolution*: Applied `safe_cast(Timestamp as timestamp)` in `stg_ehr_logs.sql` to ensure downstream BigQuery and PM4Py engines receive native `TIMESTAMP` types.

---

## 5. Week 2 Roadmap & Next Steps

In **Week 2**, we will advance from data ingestion to process discovery and PM4Py integration:

1. **Event Log Normalization for PM4Py**:
   - Build intermediate dbt model `int_pm4py_event_log.sql` mapping `case_id` $\rightarrow$ `case:concept:name`, `activity` $\rightarrow$ `concept:name`, `timestamp` $\rightarrow$ `time:timestamp`.
2. **Process Discovery with PM4Py**:
   - Discover Directly-Follows Graphs (DFG) and Inductive Mining process maps.
   - Quantify transition frequencies and bottleneck throughput times for the `X-Ray` $\rightarrow$ `Triage` loopback.
3. **Analytics Mart & Metric Modeling**:
   - Construct case-level summary views (LoS, activity counts, rework indicators) for Power BI dashboard consumption.
