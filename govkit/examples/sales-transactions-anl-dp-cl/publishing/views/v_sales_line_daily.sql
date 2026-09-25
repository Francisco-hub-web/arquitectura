-- Vista publicada para la Semantic Layer Comercial (solo Gold, columnas del contrato sales_line_daily 1.0.0).
create or replace view dlk_smt_cl_sal_transactions.v_sales_line_daily as
select
    ticket_id,
    line_number,
    business_date,
    store_id,
    sku_id,
    sales_channel_id,
    units,
    net_amount_clp
from dlk_gld_cl_sal_transactions.fact_sales_line;
