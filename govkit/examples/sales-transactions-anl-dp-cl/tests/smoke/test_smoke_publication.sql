-- Smoke post-deploy: hay datos del último día de negocio y la clave es única.
select count(*) as rows_last_day
from dlk_gld_cl_sal_transactions.fact_sales_line
where business_date = current_date - interval '1' day
having count(*) > 0;
