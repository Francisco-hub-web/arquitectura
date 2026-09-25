# Arquitectura — sales-transactions-anl-dp-cl

```
POS Xstore (CDC) ─► Bronze (Iceberg, append) ─► Silver ODM (dbt, merge) ─► Gold fact_sales_line / dim_sales_channel
                                                     ▲                                 │
                          Product Master DP (contrato 2.1.0)                            ├─► Semantic Layer Comercial (MetricFlow)
                                                                                        └─► v_sales_line_daily (serving analítica)
Orquestación: Step Functions · Quality gates Silver/Gold · Monitores: freshness, volumen, esquema, calidad, linaje, uso, seguridad
```

Decisiones: ARTS ODM con extensión Cencosud (ADR-0002), Iceberg para Time Travel (01 §5), RLS por país/BU en la serving layer.
