"""Analizador de IAM por Data Product (lineamiento "IAM - Roles & Policies").

Principio: 1 rol + 2 policies (data + infra) por producto, aislamiento total, wildcard de
escritura solo sobre recursos exclusivos (aislados por nomenclatura), KMS siempre explícito.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

from govkit.paths import registry
from govkit.plugins import at, at_file, plugin
from govkit.plugins.naming import parse_repo_name

READ = ("Get", "List", "Describe", "Search", "BatchGet", "Query", "Scan", "Head", "Lookup", "Select", "Check")
WRITE = ("Put", "Delete", "Create", "Update", "Modify", "BatchCreate", "BatchDelete", "BatchUpdate", "BatchWrite",
         "Attach", "Detach", "Remove", "Add", "Tag", "Untag", "Restore", "Copy", "Upload", "Replicate", "Set")
DATA_SERVICES = {"s3", "glue", "kms", "athena", "lakeformation", "dynamodb"}
INFRA_SERVICES = {"logs", "ec2", "secretsmanager", "ecr", "emr-serverless", "elasticmapreduce", "sts", "iam",
                  "states", "cloudwatch", "events", "sns", "sqs", "lambda", "dynamodb", "xray", "ssm"}
REGIONAL_DATA = {"glue", "athena", "kms"}
REQUIRED_TAGS = ["ceco", "ambiente", "pais", "unidad-negocio", "bandera", "propietario", "creado-por", "aplicacion",
                 "plataforma", "proyecto", "nombre", "Name", "cuenta", "repo", "tf-pipeline", "tf-module", "by", "pep", "apl"]
KMS_ARN = re.compile(r"^arn:aws:kms:[a-z0-9-]+:\d{12}:key/[0-9a-fA-F-]{8,}$")


def _list(v) -> List[Any]:
    return v if isinstance(v, list) else ([] if v is None else [v])


def verb(action: str) -> str:
    return action.split(":", 1)[-1] if ":" in action else action


def kind_of(action: str) -> str:
    if action == "*" or verb(action) == "*":
        return "all"
    v = verb(action)
    if v.startswith(WRITE):
        return "write"
    if v.startswith(READ):
        return "read"
    return "other"  # Start/Run/Invoke/crypto KMS/Assume...


class Policy:
    def __init__(self, doc, kind: str):
        self.doc, self.kind = doc, kind
        data = doc.data if isinstance(doc.data, dict) else {}
        self.wrapped = "PolicyDocument" in data
        self.base = "PolicyDocument." if self.wrapped else ""
        self.document = data.get("PolicyDocument", data) if self.wrapped else data
        self.name = data.get("PolicyName") if self.wrapped else None
        self.tags = data.get("Tags") if self.wrapped else None

    def statements(self) -> Iterator[Tuple[int, Dict[str, Any]]]:
        for i, st in enumerate(_list(self.document.get("Statement"))):
            if isinstance(st, dict):
                yield i, st

    def spath(self, i: int, key: str = "") -> str:
        return f"{self.base}Statement[{i}]" + (f".{key}" if key else "")


def policies(ctx) -> List[Policy]:
    out = []
    for kind in ("data", "infra"):
        for doc in ctx.artifact(f"iam_policy_{kind}"):
            if not doc.error:
                out.append(Policy(doc, kind))
    return out


def product_scope(ctx) -> Tuple[Optional[str], Optional[str]]:
    parsed = parse_repo_name(ctx.repo_name) or {}
    domain = ctx.dp_get("spec.domain") or parsed.get("domain")
    code = registry("domains").get("domains", {}).get(domain, {}).get("code")
    countries = ctx.dp_get("spec.scope.countries") or []
    country = parsed.get("country") or (countries[0] if countries else None)
    return code, country


def s3_bucket(arn: str) -> Optional[Tuple[str, str]]:
    if not arn.startswith("arn:aws:s3:::"):
        return None
    rest = arn[len("arn:aws:s3:::"):]
    bucket, _, path = rest.partition("/")
    return bucket, path


def exclusive_bucket(bucket: str, code: Optional[str], country: Optional[str]) -> bool:
    if not code:
        return False
    cc = re.escape(country) if country else "[a-z]{2,3}"
    return bool(re.match(rf"^cencosud-{cc}-dlk-(brz|slv|gld|smt|\*)-{re.escape(code)}-", bucket))


def _tags_dict(tags) -> Dict[str, str]:
    if isinstance(tags, dict):
        return {str(k): str(v) for k, v in tags.items()}
    out = {}
    for t in _list(tags):
        if isinstance(t, dict) and "Key" in t:
            out[str(t["Key"])] = str(t.get("Value", ""))
    return out


# ---------------------------------------------------------------------- reglas
@plugin("iam.files_present")
def files_present(ctx, rule):
    if not ctx.glob(["src/**/glue/*.py", "src/**/lambda/*.py", "pipelines/orchestration/**/*.json"]):
        return
    for name, label in (("iam_role", "roles.json"), ("iam_policy_data", "policy-data.json"),
                        ("iam_policy_infra", "policy-infra.json")):
        n = len(ctx.artifact(name))
        if n != 1:
            yield at_file(".", f"Se espera exactamente 1 `{label}` para el producto (encontrados: {n})", key=label,
                          fix={"type": "create", "path": f"infra/iam/{label}"})


@plugin("iam.naming_role")
def naming_role(ctx, rule):
    expected = f"cencosud-role-{ctx.repo_name}"
    for doc in ctx.artifact("iam_role"):
        name = doc.get("RoleName") if isinstance(doc.data, dict) else None
        if name != expected:
            yield at(doc, "RoleName", f"RoleName `{name}` ≠ `{expected}`",
                     fix={"type": "set", "path": "RoleName", "value": expected})


@plugin("iam.naming_policies")
def naming_policies(ctx, rule):
    names = set()
    for doc in ctx.artifact("iam_role"):
        if not isinstance(doc.data, dict):
            continue
        for p in _list(doc.get("Policies")):
            if isinstance(p, dict) and p.get("PolicyName"):
                names.add(p["PolicyName"])
        names |= {str(n).split("/")[-1] for n in _list(doc.get("AttachedPolicies")) + _list(doc.get("ManagedPolicyArns"))}
    names |= {p.name for p in policies(ctx) if p.name}
    if not names and not ctx.artifact("iam_role"):
        return
    repo = ctx.repo_name
    expected = {f"cencosud-policy-{repo}-data", f"cencosud-policy-{repo}-infra"}
    target = (ctx.artifact("iam_role") or [None])[0]
    for n in sorted(names - expected):
        yield at(target, "Policies", f"Policy `{n}` no sigue `cencosud-policy-{repo}-{{data|infra}}`") if target \
            else at_file(".", f"Policy `{n}` fuera de convención")
    for n in sorted(expected - names):
        if target:
            yield at(target, "Policies", f"El rol no declara la policy obligatoria `{n}`", key=n)


@plugin("iam.policy_size")
def policy_size(ctx, rule):
    for p in policies(ctx):
        size = len(json.dumps(p.document, separators=(",", ":"), ensure_ascii=False))
        if size > 6144:
            yield at(p.doc, None, f"Policy {p.kind} de {size} caracteres (> 6144, límite de managed policy AWS)", size=size)


@plugin("iam.rw_separation")
def rw_separation(ctx, rule):
    for p in policies(ctx):
        for i, st in p.statements():
            kinds = {kind_of(a) for a in _list(st.get("Action"))}
            if "read" in kinds and "write" in kinds:
                yield at(p.doc, p.spath(i, "Action"), f"Statement `{st.get('Sid', i)}` mezcla acciones de lectura y "
                         "escritura: separarlas en `{Servicio}Read` / `{Servicio}Write`")


@plugin("iam.write_wildcards")
def write_wildcards(ctx, rule):
    code, country = product_scope(ctx)
    for p in policies(ctx):
        for i, st in p.statements():
            if st.get("Effect", "Allow") != "Allow":
                continue
            if not {kind_of(a) for a in _list(st.get("Action"))} & {"write", "all"}:
                continue
            for r in _list(st.get("Resource")):
                r = str(r)
                sid = st.get("Sid", i)
                if r == "*":
                    yield at(p.doc, p.spath(i, "Resource"), f"`{sid}`: escritura sobre Resource `*`", severity="BLOCKER")
                    continue
                b = s3_bucket(r)
                if b:
                    bucket, path = b
                    if "*" in bucket and not exclusive_bucket(bucket, code, country):
                        yield at(p.doc, p.spath(i, "Resource"), f"`{sid}`: wildcard de escritura sobre buckets no "
                                 f"exclusivos del producto (`{bucket}`)", severity="BLOCKER", resource=r)
                    elif "*" not in bucket and "*" in path and not exclusive_bucket(bucket, code, country):
                        yield at(p.doc, p.spath(i, "Resource"), f"`{sid}`: wildcard sobre path de bucket compartido "
                                 f"`{r}` — usar recurso explícito", severity="HIGH", resource=r)
                m = re.match(r"^arn:aws:glue:[^:]*:[^:]*:(database|table)/([^/]+)", r)
                if m and (m.group(2) == "*" or (code and "*" in m.group(2) and f"_{code}_" not in m.group(2))):
                    yield at(p.doc, p.spath(i, "Resource"), f"`{sid}`: escritura Glue sobre databases no exclusivas "
                             f"(`{m.group(2)}`)", severity="BLOCKER", resource=r)


def _kms_statements(p: Policy):
    for i, st in p.statements():
        if any(str(a).startswith("kms:") for a in _list(st.get("Action"))):
            yield i, st


@plugin("iam.kms_explicit")
def kms_explicit(ctx, rule):
    for p in policies(ctx):
        for i, st in _kms_statements(p):
            for r in _list(st.get("Resource")):
                if not KMS_ARN.match(str(r)):
                    yield at(p.doc, p.spath(i, "Resource"), f"KMS debe declarar cuenta y key ID explícitos (actual `{r}`)")


@plugin("iam.kms_via_service")
def kms_via_service(ctx, rule):
    for p in policies(ctx):
        for i, st in _kms_statements(p):
            cond = json.dumps(st.get("Condition") or {})
            if "kms:ViaService" not in cond:
                yield at(p.doc, p.spath(i), f"Statement KMS `{st.get('Sid', i)}` sin condición kms:ViaService")


def _arns(p: Policy):
    for i, st in p.statements():
        for r in _list(st.get("Resource")):
            r = str(r)
            if r.startswith("arn:aws:"):
                parts = r.split(":", 5)
                if len(parts) == 6:
                    yield i, st, r, parts[2], parts[3], parts[4]


@plugin("iam.region_fixed")
def region_fixed(ctx, rule):
    region = ctx.policies.get("iam_region", "us-east-1")
    for p in policies(ctx):
        for i, st, arn, svc, reg, _ in _arns(p):
            if svc in REGIONAL_DATA and reg != region:
                yield at(p.doc, p.spath(i, "Resource"), f"ARN `{arn}` con región `{reg or '(vacía)'}`: la región es fija `{region}`")


@plugin("iam.account_wildcard")
def account_wildcard(ctx, rule):
    for p in policies(ctx):
        for i, st, arn, svc, _, acct in _arns(p):
            if svc not in ("kms", "sts", "iam") and re.fullmatch(r"\d{12}", acct):
                yield at(p.doc, p.spath(i, "Resource"), f"ARN `{arn}` con account ID fijo: usar `*` para portabilidad dev/prod")


@plugin("iam.action_wildcards")
def action_wildcards(ctx, rule):
    for p in policies(ctx):
        for i, st in p.statements():
            for a in _list(st.get("Action")):
                if a == "*":
                    yield at(p.doc, p.spath(i, "Action"), f"`{st.get('Sid', i)}`: Action `*`", severity="BLOCKER")
                elif str(a).endswith(":*"):
                    yield at(p.doc, p.spath(i, "Action"), f"`{st.get('Sid', i)}`: Action `{a}` (todas las acciones del servicio)")


@plugin("iam.trust_principals")
def trust_principals(ctx, rule):
    allowed = set(ctx.policies.get("trust_services", []))
    for doc in ctx.artifact("iam_role"):
        if not isinstance(doc.data, dict):
            continue
        base = "AssumeRolePolicyDocument"
        for i, st in enumerate(_list(doc.get(f"{base}.Statement"))):
            pr = (st or {}).get("Principal", {})
            if pr == "*" or (isinstance(pr, dict) and "*" in _list(pr.get("AWS"))):
                yield at(doc, f"{base}.Statement[{i}].Principal", "Trust policy abierta a cualquier principal (`*`)",
                         severity="BLOCKER")
                continue
            for svc in _list(pr.get("Service") if isinstance(pr, dict) else None):
                if svc not in allowed:
                    yield at(doc, f"{base}.Statement[{i}].Principal", f"Servicio `{svc}` no autorizado a asumir el rol "
                             f"(permitidos: {sorted(allowed)})")
            for aws in _list(pr.get("AWS") if isinstance(pr, dict) else None):
                yield at(doc, f"{base}.Statement[{i}].Principal", f"Principal AWS `{aws}` en trust del rol de producto: "
                         "requiere justificación (cross-account)")


def _tag_findings(doc, path, tags, ctx):
    reg = registry("domains")
    t = _tags_dict(tags)
    missing = [k for k in REQUIRED_TAGS if not t.get(k)]
    if missing:
        yield at(doc, path, f"Tags obligatorios ausentes: {missing}", missing=missing)
    checks = {
        "ambiente": lambda v: v in ("dev", "stg", "staging", "qa", "prod"),
        "pais": lambda v: v in reg.get("countries", []),
        "cuenta": lambda v: bool(re.fullmatch(r"\d{12}", v)),
        "tf-pipeline": lambda v: v in ("yes", "no"),
        "propietario": lambda v: bool(re.match(r"^[^@\s]+@[^@\s]+$", v)),
        "creado-por": lambda v: bool(re.match(r"^[^@\s]+@[^@\s]+$", v)),
        "repo": lambda v: v.startswith("https://"),
    }
    for key, ok in checks.items():
        if t.get(key) and not ok(t[key]):
            yield at(doc, path, f"Tag `{key}` con formato inválido: `{t[key]}`", key=f"{path}:{key}")


@plugin("iam.tags")
def tags(ctx, rule):
    for doc in ctx.artifact("iam_role"):
        if isinstance(doc.data, dict):
            yield from _tag_findings(doc, "Tags", doc.get("Tags"), ctx)
    for p in policies(ctx):
        if p.wrapped:
            yield from _tag_findings(p.doc, "Tags", p.tags, ctx)


@plugin("iam.policy_scope")
def policy_scope(ctx, rule):
    for p in policies(ctx):
        allowed = DATA_SERVICES if p.kind == "data" else INFRA_SERVICES
        for i, st in p.statements():
            svcs = {str(a).split(":")[0] for a in _list(st.get("Action")) if ":" in str(a)}
            wrong = sorted(svcs - allowed)
            if wrong:
                yield at(p.doc, p.spath(i, "Action"), f"Policy {p.kind} con servicios fuera de su alcance: {wrong} "
                         f"(data = acceso a datos; infra = servicios de soporte)")


@plugin("iam.sid")
def sid(ctx, rule):
    for p in policies(ctx):
        seen = set()
        for i, st in p.statements():
            s = st.get("Sid")
            if not s:
                yield at(p.doc, p.spath(i), f"Statement #{i} sin `Sid`")
            elif not re.fullmatch(r"[A-Z][A-Za-z0-9]+", str(s)) or str(s).lower() in ("test", "stmt", "statement"):
                yield at(p.doc, p.spath(i, "Sid"), f"Sid `{s}` no descriptivo (usar `{{Servicio}}{{Propósito}}`, ej. S3DataLakeRead)")
            elif s in seen:
                yield at(p.doc, p.spath(i, "Sid"), f"Sid duplicado `{s}`")
            seen.add(s)


@plugin("iam.scoped_support")
def scoped_support(ctx, rule):
    for p in policies(ctx):
        for i, st in p.statements():
            svcs = {str(a).split(":")[0] for a in _list(st.get("Action"))}
            if not svcs & {"secretsmanager", "logs"}:
                continue
            for r in _list(st.get("Resource")):
                r = str(r)
                if r == "*" or re.search(r":(secret|log-group):\*?$", r) or r.endswith(":secret:*") or r.endswith("log-group:*"):
                    yield at(p.doc, p.spath(i, "Resource"), f"`{st.get('Sid', i)}`: recurso `{r}` no acotado al "
                             "prefijo del producto")


@plugin("iam.bucket_naming")
def bucket_naming(ctx, rule):
    rx = re.compile(r"^cencosud-[a-z*]{2,3}-dlk-(brz|slv|gld|smt|\*)-[a-z0-9*]+-")
    for p in policies(ctx):
        for i, st in p.statements():
            for r in _list(st.get("Resource")):
                b = s3_bucket(str(r))
                if b and "-dlk-" in b[0] and not rx.match(b[0]):
                    yield at(p.doc, p.spath(i, "Resource"), f"Bucket `{b[0]}` no sigue "
                             "`cencosud-{pais}-dlk-{brz|slv|gld|smt}-{dominio}-*`")


@plugin("iam.glue_db_naming")
def glue_db_naming(ctx, rule):
    rx = re.compile(r"^(\*|dlk_(brz|slv|gld|smt|\*)_([a-z]{2,3}|\*)_[a-z0-9*]+_[a-z0-9_*]+|dlk_[a-z0-9_*]+\*)$")
    for p in policies(ctx):
        for i, st in p.statements():
            for r in _list(st.get("Resource")):
                m = re.match(r"^arn:aws:glue:[^:]*:[^:]*:(?:database|table)/([^/]+)", str(r))
                if m and not rx.match(m.group(1)):
                    yield at(p.doc, p.spath(i, "Resource"), f"Database Glue `{m.group(1)}` no sigue "
                             "`dlk_{zona}_{pais}_{dominio}_{nombre}`")


@plugin("iam.cross_domain_read")
def cross_domain_read(ctx, rule):
    code, _ = product_scope(ctx)
    if not code:
        return
    rx = re.compile(r"^cencosud-[a-z*]{2,3}-dlk-(?:brz|slv|gld|smt|\*)-([a-z0-9]+)-")
    for p in policies(ctx):
        for i, st in p.statements():
            for r in _list(st.get("Resource")):
                b = s3_bucket(str(r))
                m = rx.match(b[0]) if b else None
                if m and m.group(1) != code:
                    yield at(p.doc, p.spath(i, "Resource"), f"Acceso a datos del dominio `{m.group(1)}` desde un producto "
                             f"del dominio `{code}`: debe respaldarse con contrato de entrada", resource=str(r))
