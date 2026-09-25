# %%repo%%

> Data Product `%%dp_id%%` · dominio **%%domain%%** / subdominio **%%subdomain%%** · país **%%country%%**

## Propósito
<COMPLETAR: problema de negocio, decisión que habilita y consumidores principales.>

## Owners
| Rol | Responsable |
|---|---|
| Business Owner | %%owner%% |
| Data Owner / Steward / Technical Owner | ver `metadata/catalog/data_product.yaml` |

## Inputs / Outputs
Ver `spec.inputs` / `spec.outputs` en la ficha y los contratos en `contracts/input` y `contracts/output`.

## SLA
Ver `spec.sla` en la ficha. Freshness, disponibilidad y ventana de publicación se monitorean en `observability/`.

## Branches y flujo de trabajo
`<tipo>/<dominio>/<descripcion>` (feat|fix|hotfix|chore) · Conventional Commits · PR con `govkit lint` obligatorio.

## Runbook
`docs/engineering/runbook.md`

## Gobernanza
```bash
govkit lint                          # motor determinista (reglas como código)
govkit gate --to listo_para_produccion
govkit review                        # revisión semántica con LLM local (consultiva)
```
