# ADR-0002: ARTS ODM con extensión Cencosud para la línea de transacción

- Estado: aceptado
- Fecha: 2026-07-10

## Contexto
ARTS es referente no restrictivo (06 §14). El POS Xstore entrega descuentos y canal con semántica propia de Cencosud.

## Decisión
Modelar Silver sobre ARTS ODM RetailTransactionLineItem, extendiendo con `sales_channel_id` y monto neto
después de descuentos. Gold dimensional (fact_sales_line + dim_sales_channel).

## Consecuencias
`spec.modeling.arts_alignment: extension`. Las extensiones se documentan en el contrato y el glosario.
