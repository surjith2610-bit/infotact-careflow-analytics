{{
    config(
        materialized='table'
    )
}}

with source_data as (
    select
        case_id,
        activity,
        cast(timestamp as timestamp) as timestamp
    from {{ ref('stg_ehr_logs') }}
)

select
    case_id,
    activity,
    timestamp
from source_data
where case_id is not null
  and activity is not null
  and timestamp is not null
order by case_id, timestamp asc
