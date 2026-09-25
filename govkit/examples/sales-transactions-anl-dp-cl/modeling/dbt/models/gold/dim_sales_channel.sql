-- Dimensión conformada de canal de venta (propiedad del dominio Sales).
{{ config(materialized='table') }}

select
    sales_channel_id,
    sales_channel_name,
    is_digital
from {{ ref('sales_channel_dictionary') }}
