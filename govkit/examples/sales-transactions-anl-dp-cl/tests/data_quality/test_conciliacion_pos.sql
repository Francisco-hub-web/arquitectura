-- Regla conciliacion_pos (consistencia): diferencia diaria Gold vs control POS ≤ 0.5%.
-- El test pasa cuando la consulta no retorna filas.
select g.business_date, g.net_amount, c.control_amount
from (
    select business_date, sum(net_amount_clp) as net_amount
    from dlk_gld_cl_sal_transactions.fact_sales_line
    group by business_date
) g
join dlk_slv_cl_sal_pos.pos_daily_control c on c.business_date = g.business_date
where abs(g.net_amount - c.control_amount) > 0.005 * c.control_amount;
