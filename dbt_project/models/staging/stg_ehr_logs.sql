{{
    config(
        materialized='view'
    )
}}

with source_data as (
    select
        trim(cast(Case_ID as string)) as case_id,
        trim(cast(Activity_Name as string)) as activity,
        safe_cast(Timestamp as timestamp) as timestamp
    from {{ source('careflow_raw', 'raw_event_log') }}
),

cleaned_data as (
    select
        case_id,
        activity,
        timestamp,
        farm_fingerprint(concat(case_id, '_', activity, '_', cast(timestamp as string))) as event_id
    from source_data
    where case_id is not null
      and timestamp is not null
)

select
    event_id,
    case_id,
    activity,
    timestamp
from cleaned_data
