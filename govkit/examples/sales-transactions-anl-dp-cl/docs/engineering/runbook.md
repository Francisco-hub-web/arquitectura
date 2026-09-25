# Runbook — sales-transactions-anl-dp-cl

## Contactos y escalamiento
| Nivel | Rol | Contacto |
|---|---|---|
| N1 | Technical Owner | diego.silva@cencosud.com · #dp-sales-transactions-cl |
| N2 | Data Steward | carla.rojas@cencosud.com |
| N3 | Data Owner | jorge.munoz@cencosud.com |

## SLA y ventanas
Publicación Gold diaria antes de las 07:00 (America/Santiago). Disponibilidad 99.5%.

## Fallas típicas y diagnóstico
### freshness
1. Revisar la ejecución de la Step Function `sales_transactions_daily` (estado del paso fallido).
2. Si falló `IngestBronze`: validar llegada de eventos CDC y credenciales del secreto del producto.
3. Si falló un quality gate: revisar el reporte en `quality/reports` y comunicar a consumidores en el canal.

### volumen
Caída > 20% vs media móvil: confirmar con Operaciones Tienda si hubo cierre de tiendas antes de reprocesar.

## Reproceso y rollback
- Reproceso: relanzar la Step Function con `business_date` explícita (MERGE idempotente).
- Rollback: Iceberg time travel (`CALL system.rollback_to_snapshot`) sobre la tabla Gold al snapshot anterior.
