"""Pack `omd`: roles cross-account (repo access-analyzer) y conexiones de ingesta de OpenMetadata.

Fuente: lineamientos "OpenMetadata - Guía Rápida AWS" y "OpenMetadata - Cross-Account Role" (v0.2).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from govkit.paths import registry
from govkit.plugins import at, plugin

ARN_ACCT = re.compile(r"^arn:aws:iam::(\d{12}):role/(.+)$")
REGION = re.compile(r"^[a-z]{2}(-gov)?-[a-z]+-\d$")


def _reg():
    return registry("aws_accounts")


def _list(v):
    return v if isinstance(v, list) else ([] if v is None else [v])


def role_entries(ctx):
    """(doc, ruta, entrada) de roles.json que participan del esquema OpenMetadata."""
    omd = _reg()["omd"]
    for doc in ctx.artifact("omd_access_roles"):
        if doc.error:
            continue
        data = doc.data
        items, base = (data, "") if isinstance(data, list) else ((data or {}).get("roles", []), "roles")
        for i, e in enumerate(items if isinstance(items, list) else []):
            if not isinstance(e, dict):
                continue
            blob = str(e)
            if e.get("name") == omd["role_name"] or omd["pod_role"] in blob or "omdata" in blob:
                yield doc, f"{base}[{i}]", e


def _env_of(account: str) -> Optional[str]:
    return (_reg()["data_accounts"].get(str(account)) or {}).get("env")


def _trust_statements(e):
    return [s for s in _list((e.get("trustRelationshipPolicy") or {}).get("Statement")) if isinstance(s, dict)]


@plugin("omd.role_name")
def role_name(ctx, rule):
    expected = _reg()["omd"]["role_name"]
    for doc, path, e in role_entries(ctx):
        if e.get("name") != expected:
            yield at(doc, f"{path}.name", f"El rol debe llamarse exactamente `{expected}` (el pod role confía en ese nombre)")


@plugin("omd.env_isolation")
def env_isolation(ctx, rule):
    envs = _reg()["omd"]["environments"]
    for doc, path, e in role_entries(ctx):
        env = _env_of(e.get("accountId"))
        if not env:
            continue
        expected = f"arn:aws:iam::{envs[env]['dg_corp_account']}:role/{_reg()['omd']['pod_role']}"
        for j, st in enumerate(_trust_statements(e)):
            for p in _list((st.get("Principal") or {}).get("AWS")):
                if p != expected:
                    yield at(doc, f"{path}.trustRelationshipPolicy.Statement[{j}].Principal",
                             f"Cuenta {e.get('accountId')} ({env.upper()}) confía en `{p}`; debe confiar solo en `{expected}` "
                             "(TEST con TEST, PROD con PROD)")


@plugin("omd.trust_actions")
def trust_actions(ctx, rule):
    required = set(_reg()["omd"]["trust_actions"])
    for doc, path, e in role_entries(ctx):
        actions = set()
        for st in _trust_statements(e):
            actions |= set(_list(st.get("Action")))
        missing = sorted(required - actions)
        if missing:
            yield at(doc, f"{path}.trustRelationshipPolicy", f"Trust policy sin {missing} (EKS Pod Identity propaga "
                     "session tags transitivas: sin sts:TagSession el AssumeRole falla)")


@plugin("omd.env_policy")
def env_policy(ctx, rule):
    envs = _reg()["omd"]["environments"]
    for doc, path, e in role_entries(ctx):
        env = _env_of(e.get("accountId"))
        if env and envs[env]["policy"] not in _list(e.get("policies")):
            yield at(doc, f"{path}.policies", f"Cuenta {env.upper()} debe adjuntar `{envs[env]['policy']}` "
                     f"(actual: {e.get('policies')})")


@plugin("omd.managed_account")
def managed_account(ctx, rule):
    managed = set(_reg()["managed_accounts"])
    for doc, path, e in role_entries(ctx):
        acct = str(e.get("accountId"))
        if acct not in managed:
            yield at(doc, f"{path}.accountId", f"Cuenta {acct} fuera de las gestionadas por access-analyzer: coordinar "
                     "primero con Seguridad Informática")
        elif not _env_of(acct):
            yield at(doc, f"{path}.accountId", f"Cuenta {acct} sin ambiente registrado (rules/registry/aws_accounts.yaml)",
                     severity="MEDIUM")


@plugin("omd.policy_arns")
def policy_arns(ctx, rule):
    by_env: Dict[str, List[str]] = {}
    for _, _, e in role_entries(ctx):
        env = _env_of(e.get("accountId"))
        if env:
            by_env.setdefault(env, []).append(str(e.get("accountId")))
    for doc in ctx.artifact("omd_env_policies"):
        if doc.error or not isinstance(doc.data, dict):
            continue
        env = "test" if "test" in doc.path.lower() else "prod" if "prod" in doc.path.lower() else None
        text = doc.text or ""
        for acct in by_env.get(env or "", []):
            needed = [f"arn:aws:glue:us-east-1:{acct}:catalog", f"arn:aws:glue:us-east-1:{acct}:database/*",
                      f"arn:aws:glue:us-east-1:{acct}:table/*", f"arn:aws:dynamodb:us-east-1:{acct}:table/*"]
            missing = [n for n in needed if n not in text]
            if missing:
                yield at(doc, "Statement", f"Policy {env.upper()} sin ARNs de la cuenta {acct}: {missing} "
                         "(el Test Connection fallará con AccessDenied)", key=acct)


@plugin("omd.sid")
def sid(ctx, rule):
    for doc, path, e in role_entries(ctx):
        for j, st in enumerate(_trust_statements(e)):
            if str(st.get("Sid", "")).lower() in ("", "test", "stmt"):
                yield at(doc, f"{path}.trustRelationshipPolicy.Statement[{j}].Sid",
                         f"Sid `{st.get('Sid')}` no descriptivo (recomendación §5: describir el propósito)")


# ---------------------------------------------------------------- ingesta OpenMetadata
def ingestions(ctx):
    for doc in ctx.artifact("omd_ingestion"):
        if not doc.error and isinstance(doc.data, dict) and doc.get("source.serviceConnection"):
            yield doc


def _aws(doc) -> Tuple[str, Dict[str, Any]]:
    base = "source.serviceConnection.config.awsConfig"
    return base, doc.get(base) or {}


@plugin("omd.no_static_keys")
def no_static_keys(ctx, rule):
    for doc in ingestions(ctx):
        base, aws = _aws(doc)
        for k in ("awsAccessKeyId", "awsSecretAccessKey", "awsSessionToken"):
            if aws.get(k):
                yield at(doc, f"{base}.{k}", f"`{k}` informado: se usarán llaves estáticas en lugar del rol "
                         "(ExpiredTokenException). Dejar vacío y usar assumeRoleArn")


@plugin("omd.region")
def region(ctx, rule):
    for doc in ingestions(ctx):
        base, aws = _aws(doc)
        reg = str(aws.get("awsRegion") or "")
        if not REGION.match(reg):
            yield at(doc, f"{base}.awsRegion", f"awsRegion `{reg}` inválida (¿zona de disponibilidad? usar p.ej. us-east-1)")


@plugin("omd.instance_env")
def instance_env(ctx, rule):
    envs = _reg()["omd"]["environments"]
    for doc in ingestions(ctx):
        base, aws = _aws(doc)
        host = str(doc.get("workflowConfig.openMetadataServerConfig.hostPort") or "")
        inst = next((e for e, v in envs.items() if v["instance_host"] in host and
                     (e == "test" or envs["test"]["instance_host"] not in host)), None)
        m = ARN_ACCT.match(str(aws.get("assumeRoleArn") or ""))
        if not m:
            yield at(doc, f"{base}.assumeRoleArn", "assumeRoleArn ausente o inválido")
            continue
        acct_env = _env_of(m.group(1))
        if m.group(2) != _reg()["omd"]["role_name"]:
            yield at(doc, f"{base}.assumeRoleArn", f"El rol asumido debe ser `{_reg()['omd']['role_name']}`")
        if inst and acct_env and inst != acct_env:
            yield at(doc, f"{base}.assumeRoleArn", f"Instancia {inst.upper()} ({host}) usando cuenta {acct_env.upper()} "
                     f"{m.group(1)}: los ambientes no se cruzan")


def _filters(doc):
    cfg = doc.get("source.sourceConfig.config") or {}
    for key, val in cfg.items():
        if key.endswith("FilterPattern") and isinstance(val, dict):
            for i, pat in enumerate(_list(val.get("includes"))):
                yield f"source.sourceConfig.config.{key}.includes[{i}]", key, str(pat)


@plugin("omd.filters_anchored")
def filters_anchored(ctx, rule):
    for doc in ingestions(ctx):
        for path, key, pat in _filters(doc):
            if not pat.endswith("$") and not pat.endswith("-") and not pat.endswith(".*"):
                yield at(doc, path, f"Filtro `{pat}` sin ancla final: también incluye `{pat}_*` (usar ^{pat.lstrip('^')}$)")


@plugin("omd.dynamo_filter")
def dynamo_filter(ctx, rule):
    for doc in ingestions(ctx):
        if str(doc.get("source.type", "")).lower() == "dynamodb":
            if not (doc.get("source.sourceConfig.config.tableFilterPattern") or {}).get("includes"):
                yield at(doc, "source.sourceConfig.config", "DynamoDB sin filtro de tablas: cada ejecución hace Scan de "
                         "hasta 1000 ítems por tabla (consumo RCU en la cuenta de datos)")


@plugin("omd.s3_filter")
def s3_filter(ctx, rule):
    for doc in ingestions(ctx):
        if str(doc.get("source.type", "")).lower() in ("s3", "s3storage"):
            inc = _list((doc.get("source.sourceConfig.config.containerFilterPattern") or {}).get("includes"))
            if "^cencosud-" not in inc:
                yield at(doc, "source.sourceConfig.config", "S3 Storage sin filtro `^cencosud-` (la policy solo permite leer "
                         "buckets con ese prefijo)")


@plugin("omd.session_name")
def session_name(ctx, rule):
    for doc in ingestions(ctx):
        base, aws = _aws(doc)
        if str(aws.get("assumeRoleSessionName") or "OpenMetadataSession") == "OpenMetadataSession":
            yield at(doc, f"{base}.assumeRoleSessionName", "Session name por defecto: usar `omd-<servicio>` para atribuir "
                     "llamadas en CloudTrail")
