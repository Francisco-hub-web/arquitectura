"""Seguridad, privacidad y compliance (01 §13-14, 10-data-security-framework)."""
from __future__ import annotations

import ast
import re

from govkit.plugins import at, at_file, line_of, plugin

SECRET_PATTERNS = [
    ("AWS Access Key ID", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("AWS Secret Access Key", re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}")),
    ("Llave privada", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("Token GitHub", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36}\b")),
    ("Token Slack", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("Credencial en URL JDBC", re.compile(r"(?i)jdbc:[^\s'\"]*password=[^&\s'\"$]{4,}")),
    ("Credencial en cadena de conexión", re.compile(r"(?i)\b[a-z+]+://[^\s:/'\"]+:[^\s@/'\"${]{4,}@")),
    ("Secreto asignado en claro", re.compile(
        r"(?i)\b(?:password|passwd|pwd|secret|client_secret|api_key|apikey|access_token|auth_token)\b"
        r"\s*[:=]\s*['\"](?![$<{%])(?!os\.environ)[^'\"\s]{6,}['\"]")),
]
SECRET_KWARGS = {"password", "passwd", "aws_secret_access_key", "aws_session_token", "secret", "api_key",
                 "client_secret", "token"}
PII_TOKENS = {"rut", "dni", "cedula", "cpf", "cuit", "cuil", "ruc", "curp", "pasaporte", "passport", "email",
              "correo", "mail", "telefono", "phone", "celular", "movil", "mobile", "direccion", "address",
              "domicilio", "nombre", "nombres", "apellido", "apellidos", "firstname", "lastname", "birth",
              "nacimiento", "dob", "tarjeta", "card", "pan", "iban", "ip", "geolocalizacion"}
NON_PERSON = {"producto", "product", "tienda", "store", "categoria", "category", "proveedor", "supplier", "campana",
              "campaign", "local", "sku", "articulo", "marca", "brand", "sucursal", "bodega", "archivo", "file",
              "tabla", "table", "metrica", "metric", "canal", "channel", "servidor", "server", "cluster", "host",
              "dominio", "domain", "tipo", "type", "id_tipo", "count", "flag", "hash", "masked", "tokenized"}
MASKING = {"dynamic", "static", "tokenization", "hashing", "pseudonymization", "encryption", "redaction"}
MASK_FN = re.compile(r"(?i)\b(sha1|sha2|sha256|md5|mask|hash|tokeniz\w*|regexp_replace|substr|substring|left|right|"
                     r"pseudonymi\w*|encrypt\w*)\s*\(|'\*{3,}'")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@(?!(?:example|test|cencosud)\.)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
RUT = re.compile(r"\b(\d{1,2})\.(\d{3})\.(\d{3})-([\dkK])\b")
CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
SAMPLE_GLOBS = ["**/*.csv", "**/*.tsv", "**/*.jsonl", "tests/**/*.json", "**/fixtures/**", "**/samples/**",
                "**/sample_data/**", "**/seeds/**"]


def is_pii_name(name: str) -> bool:
    tokens = set(re.split(r"[_\W]+", str(name).lower()))
    return bool(tokens & PII_TOKENS) and not tokens & NON_PERSON


def _rut_ok(m) -> bool:
    body = int(m.group(1) + m.group(2) + m.group(3))
    s, mul = 0, 2
    while body:
        s += (body % 10) * mul
        body //= 10
        mul = 2 if mul == 7 else mul + 1
    dv = 11 - s % 11
    return {11: "0", 10: "k"}.get(dv, str(dv)) == m.group(4).lower()


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for d in reversed(digits):
        n = int(d)
        if alt:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total, alt = total + n, not alt
    return total % 10 == 0


@plugin("security.pii_coherence", needs_dp=True)
def pii_coherence(ctx, rule):
    dp = ctx.dp
    if not dp or dp.get("spec.classification.pii") is not True:
        return
    if dp.get("spec.classification.level") != "sensible_pii":
        yield at(dp, "spec.classification.level", "Contiene PII pero la clasificación no es `sensible_pii`",
                 fix={"type": "set", "path": "spec.classification.level", "value": "sensible_pii"})
    if dp.get("spec.classification.masking_required") is not True:
        yield at(dp, "spec.classification.masking_required", "Contiene PII sin `masking_required: true`",
                 fix={"type": "set", "path": "spec.classification.masking_required", "value": True})


@plugin("security.secrets_scan")
def secrets_scan(ctx, rule):
    for rel in ctx.text_files("**", exclude=["**/*.md", "**/*.lock"]):
        text = ctx.text(rel)
        if not text:
            continue
        seen = set()
        for label, rx in SECRET_PATTERNS:
            for m in rx.finditer(text):
                line = line_of(text, m.start())
                if line not in seen:
                    seen.add(line)
                    yield at_file(rel, f"{label} en el código (línea {line}): usar Secrets Manager / variables seguras",
                                  line=line, secret_type=label)
        if rel.endswith(".py"):
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.keyword) and node.arg and node.arg.lower() in SECRET_KWARGS \
                        and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) \
                        and len(node.value.value) >= 4 and node.value.lineno not in seen:
                    seen.add(node.value.lineno)
                    yield at_file(rel, f"Argumento `{node.arg}=` con literal hardcodeado (AST)",
                                  line=node.value.lineno, col=node.value.col_offset + 1, secret_type="kwarg")


@plugin("security.pii_column_names")
def pii_column_names(ctx, rule):
    for doc in ctx.artifact("contracts_all"):
        if doc.error or not isinstance(doc.data, dict):
            continue
        for i, f in enumerate(doc.get("spec.schema") or []):
            if isinstance(f, dict) and is_pii_name(f.get("name", "")) and f.get("pii") is not True:
                yield at(doc, f"spec.schema[{i}].pii", f"Campo `{f.get('name')}` parece dato personal y no está "
                         "marcado `pii: true` (confirmar con Data Steward)")


@plugin("security.pii_in_samples")
def pii_in_samples(ctx, rule):
    for rel in ctx.text_files(SAMPLE_GLOBS):
        text = ctx.text(rel)
        if not text:
            continue
        hits = []
        for m in EMAIL.finditer(text):
            hits.append(("email", m))
        for m in RUT.finditer(text):
            if _rut_ok(m):
                hits.append(("RUT válido", m))
        for m in CPF.finditer(text):
            hits.append(("CPF", m))
        for m in CARD.finditer(text):
            digits = re.sub(r"\D", "", m.group(0))
            if 13 <= len(digits) <= 19 and _luhn(digits) and len(set(digits)) > 2:
                hits.append(("tarjeta (Luhn válido)", m))
        if hits:
            kind, m = hits[0]
            yield at_file(rel, f"Posible PII real en datos de muestra: {len(hits)} coincidencia(s), p.ej. {kind} "
                          "— usar datos sintéticos o enmascarados (10 §11, §15)", line=line_of(text, m.start()),
                          kinds=sorted({k for k, _ in hits}))


@plugin("security.third_party", needs_dp=True)
def third_party(ctx, rule):
    dp = ctx.dp
    if not dp or dp.get("spec.classification.third_party_exposure") is not True:
        return
    if not ctx.artifact("contracts_output"):
        yield at(dp, "spec.classification.third_party_exposure", "Exposición a terceros sin contrato de salida (10 §17)")
    for key in ("spec.access.third_party.auth", "spec.access.third_party.recipients"):
        if not dp.get(key):
            yield at(dp, key, f"Exposición a terceros sin `{key.split('.')[-1]}` declarado (10 §17)")


@plugin("security.rls_required", needs_dp=True)
def rls_required(ctx, rule):
    dp = ctx.dp
    if not dp or not isinstance(dp.data, dict):
        return
    sensitive = dp.get("spec.classification.level") in ("confidencial", "sensible_pii") or \
        dp.get("spec.classification.pii") is True
    bi = any(re.search(r"(?i)bi|semantic|power|looker|microstrategy|dashboard",
                       f"{o.get('type', '')} {o.get('channel', '')}")
             for o in dp.get("spec.outputs") or [] if isinstance(o, dict)) or \
        str(dp.get("spec.consumption_pattern", "")).startswith(("bi_", "self_service", "analitica_embebida"))
    if sensitive and bi and dp.get("spec.access.rls") is not True:
        yield at(dp, "spec.access.rls", "Consumo BI/semántico de datos confidenciales o PII sin RLS declarada (10 §18)")


@plugin("security.contract_pii_fields")
def contract_pii_fields(ctx, rule):
    for doc in ctx.artifact("contracts_all"):
        if doc.error or not isinstance(doc.data, dict):
            continue
        pii_fields = [(i, f) for i, f in enumerate(doc.get("spec.schema") or []) if isinstance(f, dict) and f.get("pii") is True]
        for i, f in pii_fields:
            if str(f.get("masking", "")).lower() not in MASKING:
                yield at(doc, f"spec.schema[{i}].masking", f"Campo PII `{f.get('name')}` sin técnica de protección "
                         f"declarada ({sorted(MASKING)})")
        if pii_fields and doc.get("spec.classification") not in ("sensible_pii",):
            yield at(doc, "spec.classification", "Contrato con campos PII pero clasificación distinta de `sensible_pii`")


@plugin("security.views_expose_pii")
def views_expose_pii(ctx, rule):
    pii = set()
    for doc in ctx.artifact("contracts_all"):
        if not doc.error and isinstance(doc.data, dict):
            pii |= {str(f.get("name")) for f in doc.get("spec.schema") or [] if isinstance(f, dict) and f.get("pii") is True}
    if not pii:
        return
    rx = re.compile(r"\b(" + "|".join(re.escape(p) for p in sorted(pii)) + r")\b", re.IGNORECASE)
    for rel in ctx.glob(["publishing/**/*.sql", "modeling/dbt/models/semantic/**/*.sql", "src/semantic/**/*.sql"]):
        text = ctx.text(rel) or ""
        for no, line in enumerate(text.splitlines(), 1):
            m = rx.search(line)
            if m and not MASK_FN.search(line) and not line.strip().startswith("--"):
                yield at_file(rel, f"Columna PII `{m.group(1)}` expuesta sin función de enmascaramiento", line=no)
                break
