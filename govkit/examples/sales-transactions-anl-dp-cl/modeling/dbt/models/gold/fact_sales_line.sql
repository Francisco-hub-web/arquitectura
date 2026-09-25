-- Hecho Gold: una fila por línea de ticket (grano declarado en el contrato fact_sales_line).
{{ config(materialized='incremental', unique_key=['ticket_id', 'line_number'], incremental_strategy='merge') }}

select
    l.ticket_id,
    l.line_number,
    l.business_date,
    l.store_id,
    l.sku_id,
    l.sales_channel_id,
    l.units,
    l.net_amount_clp
from {{ ref('odm_retail_transaction_line') }} as l
inner join {{ source('product_master', 'dim_product') }} as p
    on p.sku_id = l.sku_id
