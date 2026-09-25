-- Diccionario estático de canales (src/silver/dictionary/*.json se carga como seed).
select sales_channel_id, sales_channel_name, is_digital
from {{ ref('seed_sales_channel') }}
