-- ARTS ODM (extensión Cencosud): línea de transacción retail conformada y deduplicada.
{{ config(materialized='incremental', unique_key=['ticket_id', 'line_number'], incremental_strategy='merge') }}

with source as (
    select ticket_id, line_number, store_code, sku_code, quantity, gross_amount, discount_amount, event_ts, channel_code
    from {{ source('bronze_pos', 'pos_transactions') }}
    {% if is_incremental() %}
    where event_ts > (select max(event_ts) from {{ this }})
    {% endif %}
),
ranked as (
    select *, row_number() over (partition by ticket_id, line_number order by event_ts desc) as rn
    from source
)
select
    ticket_id,
    line_number,
    cast(event_ts as date)                         as business_date,
    store_code                                     as store_id,
    sku_code                                       as sku_id,
    channel_code                                   as sales_channel_id,
    cast(quantity as decimal(18, 3))               as units,
    cast(gross_amount - coalesce(discount_amount, 0) as decimal(18, 2)) as net_amount_clp,
    event_ts
from ranked
where rn = 1
