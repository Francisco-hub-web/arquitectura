"""Estándar platform-core (ODCS v3.1.0 + perfil xCencosud) como reglas GOV-PCX-* (ADR-009).

El estándar se LEE COMO DATO (no se duplica): primero la copia del propio Data Product (contracts/_schema/), luego el
clon local de global-data-platform-core, luego el índice de `govkit arch` y, en último caso, el fallback destilado
rules/registry/platform_core.yaml. La semántica replica la del validador corporativo (cenco_dc Tier 1) sin copiar su
código; `govkit lint --cenco-dc` puede además ejecutar el validador oficial si está disponible.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from govkit.model import Finding
from govkit.paths import load_yaml_file, registry
from govkit.plugins import at, at_file, plugin
from govkit.plugins.security import is_pii_name
from govkit.yamlloc import Doc

EXCLUDE = ["contracts/_schema/**", "contracts/_templates/**", "contracts/_examples/**", "contracts/policies/**"]
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
_PLACE = re.compile(r"^\s*<[^>]*>\s*$|<\s*COMPLETAR", re.I)


# ------------------------------------------------------------------------------------------------ estándar como dato
def _pver(v: str) -> Tuple[int, ...]:
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return (0,)


def _from_files(std_y: Optional[dict], manifest: Optional[dict], schema: Optional[dict], origin: str) -> Dict[str, Any]:
    base = dict(registry("platform_core"))
    out: Dict[str, Any] = {"origin": origin}
    if manifest:
        out["profile_version"] = str(manifest.get("current_profile_version") or base["profile_version"])
        out["approved_api_versions"] = list(manifest.get("approved_odcs_api_versions") or base["approved_api_versions"])
    if std_y:
        out["profile_version"] = out.get("profile_version") or str(std_y.get("profile_version") or base["profile_version"])
        out["forbidden_root_keys"] = list(std_y.get("forbidden_root_keys") or base["forbidden_root_keys"])
        fb = std_y.get("forbidden_extension_blocks_from_profile") or {}
        if fb:
            out["forbidden_extension_blocks"] = {"profile_from": str(fb.get("profile_from")), "blocks": list(fb.get("blocks") or [])}
        if std_y.get("required_extension_property"):
            out["required_extension_property"] = std_y["required_extension_property"]
        if std_y.get("lineage_rules"):
            out["lineage_rules"] = std_y["lineage_rules"]
        if std_y.get("landing_origin_profiles"):
            out["landing_origin_profiles"] = std_y["landing_origin_profiles"]
            out["ingestion_origins"] = list(std_y["landing_origin_profiles"].keys())
        layers = {}
        for tpl in (std_y.get("scaffold_templates") or {}).values():
            ext = (tpl or {}).get("cencosud_extension") or {}
            key = f"{ext.get('layer')}/{ext.get('medallion_zone')}"
            if ext.get("layer") and key not in layers:
                layers[key] = {"layer": ext["layer"], "zone": ext.get("medallion_zone"),
                               **{k: ext[k] for k in ("required_blocks", "physical_required_keys", "catalog_required_keys") if k in ext}}
        if layers:
            out["layers"] = layers
    if schema:
        out["profile_version"] = out.get("profile_version") or str(schema.get("x-cencosudProfileVersion") or "")
        props = schema.get("properties") or {}
        if (props.get("status") or {}).get("enum"):
            out["status_enum"] = list(props["status"]["enum"])
        if schema.get("required"):
            out["root_required"] = list(schema["required"])
        ext = (schema.get("$defs") or {}).get("cencosudExtension") or {}
        if ext.get("required"):
            out["extension_required"] = list(ext["required"])
        eprops = ext.get("properties") or {}
        if (eprops.get("pii_classification") or {}).get("enum"):
            out["pii_enum"] = list(eprops["pii_classification"]["enum"])
        if (eprops.get("asset_type") or {}).get("enum"):
            out["asset_type_enum"] = list(eprops["asset_type"]["enum"])
        if (eprops.get("ingestion_origin") or {}).get("enum"):
            out["ingestion_origins"] = list(eprops["ingestion_origin"]["enum"])
        out["schema_profile_version"] = schema.get("x-cencosudProfileVersion")
    for k, v in base.items():
        out.setdefault(k, v)
    return out


def _read(p: Path) -> Optional[Any]:
    try:
        if not p.is_file():
            return None
        return json.loads(p.read_text(encoding="utf-8")) if p.suffix == ".json" else load_yaml_file(p)
    except Exception:  # noqa: BLE001 - archivo corrupto: se ignora esa fuente
        return None


def platform_standard() -> Dict[str, Any]:
    """Estándar vigente según platform-core (clon local > índice arch > fallback)."""
    try:
        from govkit.arch import registry as areg
        root = areg.get("platform-core").path / "framework/data-contracts/specs/schemas"
        if root.is_dir():
            std = _from_files(_read(root / "data-contracts-architecture-standard.yaml"), _read(root / "profile-manifest.yaml"),
                              _read(root / "cencosud-odcs-minimal.schema.json"), f"clon local {root}")
            if std.get("schema_profile_version"):
                return std
    except Exception:  # noqa: BLE001
        pass
    try:
        from govkit.arch import index as I
        from govkit.arch import parsers as P
        idx = I.load("platform-core")
        if idx:
            base = "framework/data-contracts/specs/schemas/"

            def load(name: str) -> Optional[Any]:
                e = idx["files"].get(base + name)
                return P.load_structured(name, e["text"])[0] if e and e.get("text") else None
            return _from_files(load("data-contracts-architecture-standard.yaml"), load("profile-manifest.yaml"),
                               load("cencosud-odcs-minimal.schema.json"),
                               f"índice govkit arch {idx['meta']['repo']}@{str(idx['meta'].get('commit'))[:7]}")
    except Exception:  # noqa: BLE001
        pass
    return _from_files(None, None, None, "fallback destilado (rules/registry/platform_core.yaml)")


def standard(ctx) -> Dict[str, Any]:
    if "pc_standard" in ctx.cache:
        return ctx.cache["pc_standard"]
    local = ctx.root / "contracts" / "_schema"
    if (local / "data-contracts-architecture-standard.yaml").is_file() or (local / "profile-manifest.yaml").is_file():
        std = _from_files(_read(local / "data-contracts-architecture-standard.yaml"), _read(local / "profile-manifest.yaml"),
                          _read(local / "cencosud-odcs-minimal.schema.json"), "copia del repo (contracts/_schema/)")
    else:
        std = platform_standard()
    ctx.cache["pc_standard"] = std
    return std


# ------------------------------------------------------------------------------------------------ utilidades
def contracts(ctx) -> List[Doc]:
    files = ctx.glob(["contracts/**/*.yaml", "contracts/**/*.yml"], EXCLUDE)
    return [ctx.doc(f) for f in files]


def extension(doc: Doc, prop: str = "xCencosud") -> Tuple[Dict[str, Any], Optional[str]]:
    data = doc.data if isinstance(doc.data, dict) else {}
    for i, item in enumerate(data.get("customProperties") or []):
        if isinstance(item, dict) and item.get("property") == prop and isinstance(item.get("value"), dict):
            return item["value"], f"customProperties[{i}].value"
    return {}, None


def refs(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(v).strip() for v in value if str(v).strip()] if isinstance(value, list) else []


def rel_in_contracts(rel: str) -> str:
    return rel[len("contracts/"):] if rel.startswith("contracts/") else rel


def ficha(ctx) -> Optional[Doc]:
    rel = registry("platform_core")["ficha"]["path"]
    return ctx.doc(rel) if ctx.exists(rel) else None


def _placeholder(v: Any) -> bool:
    return v is None or (isinstance(v, str) and (not v.strip() or bool(_PLACE.search(v))))


# ------------------------------------------------------------------------------------------------ ficha
@plugin("pcx.ficha_exists")
def ficha_exists(ctx, rule) -> Iterable[Finding]:
    rel = registry("platform_core")["ficha"]["path"]
    if not ctx.exists(rel):
        yield at_file(rel, f"Falta la ficha del Data Product `{rel}` (estándar platform-core; la exige el CI del DP)",
                      fix={"type": "create", "path": rel, "template": "platform_core_ficha"})


@plugin("pcx.ficha_fields")
def ficha_fields(ctx, rule) -> Iterable[Finding]:
    doc = ficha(ctx)
    if doc is None or not isinstance(doc.data, dict):
        return
    spec = registry("platform_core")["ficha"]
    for key in spec["required"]:
        val = doc.data.get(key)
        if _placeholder(val):
            yield at(doc, key, f"`{key}` sin completar en la ficha ({'ausente' if val is None else repr(val)})",
                     fix={"type": "set", "path": key})
    for key, allowed in spec["enums"].items():
        val = doc.data.get(key)
        if val is not None and not _placeholder(val) and str(val) not in [str(a) for a in allowed]:
            yield at(doc, key, f"`{key}` = {val!r} fuera de lo permitido {allowed}", fix={"type": "set", "path": key, "allowed": allowed})


@plugin("pcx.ficha_odcs")
def ficha_odcs(ctx, rule) -> Iterable[Finding]:
    doc = ficha(ctx)
    if doc is None or not isinstance(doc.data, dict):
        return
    std = standard(ctx)
    odcs = doc.data.get("odcs")
    if not isinstance(odcs, dict):
        yield at(doc, "odcs", "Falta el bloque `odcs` (api_version_default, profile_version, profile_schema)")
        return
    if str(odcs.get("profile_version")) != std["profile_version"]:
        yield at(doc, "odcs.profile_version", f"odcs.profile_version debe ser {std['profile_version']!r} "
                 f"(actual {odcs.get('profile_version')!r}; estándar: {std['origin']})",
                 fix={"type": "set", "path": "odcs.profile_version", "value": std["profile_version"]})
    api = odcs.get("api_version_default")
    if not api:
        yield at(doc, "odcs.api_version_default", "odcs.api_version_default es obligatorio")
    elif api not in std["approved_api_versions"]:
        yield at(doc, "odcs.api_version_default", f"odcs.api_version_default {api!r} no aprobado ({std['approved_api_versions']})")
    mv = odcs.get("profile_manifest_version")
    if mv and str(mv) != std["profile_version"]:
        yield at(doc, "odcs.profile_manifest_version", f"odcs.profile_manifest_version {mv!r} ≠ perfil vigente "
                 f"{std['profile_version']!r} (la plantilla oficial arrastra este desfase: C-03)", severity="LOW")


@plugin("pcx.ficha_registry")
def ficha_registry(ctx, rule) -> Iterable[Finding]:
    doc = ficha(ctx)
    if doc is None or not isinstance(doc.data, dict):
        return
    entries = doc.data.get("data_contracts") or []
    listed = set()
    docs = {d.path: d for d in contracts(ctx)}
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            yield at(doc, f"data_contracts[{i}]", "cada entrada de data_contracts debe ser un mapa")
            continue
        path = e.get("contract_path")
        if not path:
            yield at(doc, f"data_contracts[{i}]", "entrada sin contract_path")
            continue
        listed.add(path)
        if not ctx.exists(path):
            yield at(doc, f"data_contracts[{i}].contract_path", f"contract_path no existe: {path}")
            continue
        cd = docs.get(path) or ctx.doc(path)
        cid = e.get("contract_id")
        if cid and isinstance(cd.data, dict) and cd.data.get("id") != cid:
            yield at(doc, f"data_contracts[{i}].contract_id", f"contract_id no coincide con el id de {path}")
    for rel in docs:
        if rel not in listed:
            yield at(doc, "data_contracts", f"El contrato `{rel}` no está registrado en data_contracts[] de la ficha",
                     severity="LOW")
    if docs and not entries:
        yield at(doc, "data_contracts", "data_contracts[] vacío pero hay contratos en contracts/ (no debe quedar vacío)")


@plugin("pcx.dp_repo_match")
def dp_repo_match(ctx, rule) -> Iterable[Finding]:
    doc = ficha(ctx)
    dp_id = doc.data.get("data_product_id") if doc is not None and isinstance(doc.data, dict) else None
    if not dp_id or _placeholder(dp_id):
        return
    for c in contracts(ctx):
        xc, base = extension(c)
        if xc and xc.get("data_product_repo") != dp_id:
            yield at(c, f"{base}.data_product_repo", f"xCencosud.data_product_repo = {xc.get('data_product_repo')!r} "
                     f"debe ser el data_product_id de la ficha ({dp_id!r})")


# ------------------------------------------------------------------------------------------------ rutas y forma
@plugin("pcx.medallion_paths")
def medallion_paths(ctx, rule) -> Iterable[Finding]:
    for rel in ctx.glob(["contracts/**/*.yaml", "contracts/**/*.yml"], EXCLUDE):
        parts = rel_in_contracts(rel).split("/")
        msg = None
        if parts[0] in ("input", "output"):
            msg = (f"`contracts/{parts[0]}/` no es válido en el estándar platform-core: usa "
                   + ("bronze/landing/ o bronze/raw/" if parts[0] == "input" else "la capa medallion del objeto (silver/odm, gold/dim|fact, semantic)"))
        elif parts[0] == "bronze" and (len(parts) < 3 or parts[1] not in ("landing", "raw")):
            msg = "los contratos bronze van en bronze/landing/ o bronze/raw/"
        elif parts[0] == "silver" and (len(parts) < 3 or parts[1] != "odm"):
            msg = ("silver/stg y silver/wap no llevan contrato ODCS: gobernar vía silver/odm/"
                   if len(parts) > 1 and parts[1] in ("stg", "wap") else "los contratos silver van solo en silver/odm/")
        elif parts[0] == "gold" and (len(parts) < 3 or parts[1] not in ("dim", "fact")):
            msg = "los contratos gold van en gold/dim/ o gold/fact/"
        elif len(parts) == 1:
            msg = "contrato en la raíz de contracts/: ubícalo en su capa medallion"
        if msg:
            yield at_file(rel, msg, fix={"type": "rename", "path": rel})


@plugin("pcx.odcs_shape")
def odcs_shape(ctx, rule) -> Iterable[Finding]:
    std = standard(ctx)
    ids: Dict[str, str] = {}
    for c in contracts(ctx):
        if c.error or not isinstance(c.data, dict):
            yield at_file(c.path, f"YAML inválido: {c.error}")
            continue
        d = c.data
        for k in std["root_required"]:
            if k not in d or d.get(k) in (None, ""):
                yield at(c, k, f"falta `{k}` (obligatorio en ODCS/perfil)")
        if d.get("apiVersion") and d["apiVersion"] not in std["approved_api_versions"]:
            yield at(c, "apiVersion", f"apiVersion {d['apiVersion']!r} no aprobado ({std['approved_api_versions']})")
        if d.get("kind") and d["kind"] != "DataContract":
            yield at(c, "kind", "kind debe ser DataContract")
        if d.get("id"):
            try:
                uuid.UUID(str(d["id"]))
            except ValueError:
                yield at(c, "id", "id debe ser un UUID")
            if str(d["id"]) in ids:
                yield at(c, "id", f"id duplicado (también en {ids[str(d['id'])]})")
            ids[str(d["id"])] = c.path
        if d.get("version") and not _SEMVER.match(str(d["version"])):
            yield at(c, "version", f"version {d['version']!r} no es semver MAJOR.MINOR.PATCH")
        if d.get("status") and d["status"] not in std["status_enum"]:
            yield at(c, "status", f"status {d['status']!r} fuera de {std['status_enum']}")
        for k in std["forbidden_root_keys"]:
            if k in d:
                hint = {"x-cencosud": "customProperties con property: xCencosud", "dataQuality": "schema[].quality[]",
                        "sla": "slaProperties[]"}.get(k, "la estructura ODCS")
                yield at(c, k, f"clave raíz `{k}` no es ODCS: usar {hint}")
        if d.get("status") == "active" and not d.get("schema"):
            xc, _ = extension(c)
            if xc.get("asset_type") != "policy":
                yield at(c, "schema", "contrato active (no policy) sin schema")


@plugin("pcx.gold_names")
def gold_names(ctx, rule) -> Iterable[Finding]:
    pref = registry("platform_core")["gold_prefix"]
    for zone in ("dim", "fact"):
        for rel in ctx.glob([f"contracts/gold/{zone}/*.yaml", f"contracts/gold/{zone}/*.yml"]):
            name = rel.rsplit("/", 1)[-1]
            if not name.startswith(pref[zone]):
                yield at_file(rel, f"`{name}`: en platform-core los contratos gold/{zone} se nombran "
                              f"`{pref[zone]}<{'entidad' if zone == 'dim' else 'proceso'}>.yaml`",
                              fix={"type": "rename", "path": rel})


@plugin("pcx.extension")
def extension_required(ctx, rule) -> Iterable[Finding]:
    std = standard(ctx)
    prop = std.get("required_extension_property", "xCencosud")
    layers = std["layers"]
    for c in contracts(ctx):
        if not isinstance(c.data, dict):
            continue
        xc, base = extension(c, prop)
        if not xc:
            yield at(c, "customProperties", f"Falta la extensión corporativa: customProperties con property: {prop}")
            continue
        for k in std["extension_required"]:
            if _placeholder(xc.get(k)):
                yield at(c, f"{base}.{k}", f"extensión {prop}: `{k}` es obligatorio")
        if xc.get("asset_type") and xc["asset_type"] not in std["asset_type_enum"]:
            yield at(c, f"{base}.asset_type", f"asset_type {xc['asset_type']!r} fuera de {std['asset_type_enum']}")
        parts = rel_in_contracts(c.path).split("/")
        key = "/".join(parts[:2])
        exp = layers.get(key)
        if exp:
            if xc.get("layer") and xc["layer"] != exp["layer"]:
                yield at(c, f"{base}.layer", f"ruta {key}/ pero layer = {xc['layer']!r} (esperado {exp['layer']!r})")
            if not xc.get("medallion_zone"):
                yield at(c, f"{base}.medallion_zone", f"medallion_zone obligatorio ({exp['zone']})")
            elif xc["medallion_zone"] != exp["zone"]:
                yield at(c, f"{base}.medallion_zone", f"ruta {key}/ pero medallion_zone = {xc['medallion_zone']!r}")
        pv = xc.get("odcs_profile_version")
        if pv and str(pv) != std["profile_version"]:
            yield at(c, f"{base}.odcs_profile_version", f"odcs_profile_version debe ser {std['profile_version']!r} u omitirse")


@plugin("pcx.processing_forbidden")
def processing_forbidden(ctx, rule) -> Iterable[Finding]:
    std = standard(ctx)
    fb = std.get("forbidden_extension_blocks") or {}
    if _pver(std["profile_version"]) < _pver(fb.get("profile_from", "99")):
        return
    for c in contracts(ctx):
        xc, base = extension(c)
        for block in fb.get("blocks") or []:
            if xc.get(block) is not None:
                yield at(c, f"{base}.{block}", f"bloque `{block}` deprecado desde el perfil {fb['profile_from']}: usar "
                         "upstream_contract_ref / downstream_contract_ref (jobs en el repo DataOps)")


@plugin("pcx.physical_catalog")
def physical_catalog(ctx, rule) -> Iterable[Finding]:
    layers = standard(ctx)["layers"]
    for c in contracts(ctx):
        xc, base = extension(c)
        if not xc:
            continue
        key = "/".join(rel_in_contracts(c.path).split("/")[:2])
        exp = layers.get(key)
        if not exp:
            continue
        phys = xc.get("physical") if isinstance(xc.get("physical"), dict) else {}
        cat = xc.get("catalog") if isinstance(xc.get("catalog"), dict) else {}
        iceberg = (cat.get("iceberg_table") or xc.get("iceberg_table"))
        if key == "bronze/raw":
            if not phys and not cat:
                yield at(c, base, "bronze/raw requiere extension.physical y/o catalog")
        elif "physical" in (exp.get("required_blocks") or []) and not phys:
            yield at(c, base, f"{key} requiere extension.physical")
        for k in exp.get("physical_required_keys") or []:
            if phys and not phys.get(k):
                yield at(c, f"{base}.physical.{k}", f"physical.{k} obligatorio en {key}")
        if key == "bronze/landing" and iceberg and str(iceberg).lower() != "null":
            yield at(c, f"{base}.catalog.iceberg_table", "bronze/landing no debe definir catalog.iceberg_table")
        if "catalog" in (exp.get("required_blocks") or []):
            if not iceberg or str(iceberg).lower() == "null":
                yield at(c, f"{base}.catalog", f"{key} requiere catalog.iceberg_table")
            for k in exp.get("catalog_required_keys") or []:
                if cat and not cat.get(k):
                    yield at(c, f"{base}.catalog.{k}", f"catalog.{k} obligatorio en {key}", severity="MEDIUM")
        fmt = phys.get("format") if phys else None
        if isinstance(fmt, dict) and fmt.get("family") == "csv" and not fmt.get("csv"):
            yield at(c, f"{base}.physical.format", "physical.format.csv obligatorio cuando family es csv")


@plugin("pcx.landing_origin")
def landing_origin(ctx, rule) -> Iterable[Finding]:
    std = standard(ctx)
    profiles = std["landing_origin_profiles"]
    for c in contracts(ctx):
        xc, base = extension(c)
        if not xc or xc.get("layer") != "bronze" or xc.get("medallion_zone") != "landing":
            continue
        origin = xc.get("ingestion_origin")
        if not origin:
            yield at(c, f"{base}.ingestion_origin", f"bronze/landing requiere ingestion_origin ({', '.join(profiles)})")
            continue
        if origin not in profiles:
            yield at(c, f"{base}.ingestion_origin", f"ingestion_origin {origin!r} inválido ({', '.join(profiles)})")
            continue
        prof = profiles[origin]
        phys = xc.get("physical") if isinstance(xc.get("physical"), dict) else {}
        servers = {str(s.get("type")) for s in (c.data.get("servers") or []) if isinstance(s, dict) and s.get("type")}
        strict = c.data.get("status") == "active"
        kinds_ok = {"saas_export": {"saas_export", "object_store", "api"}}.get(origin, {prof.get("physical_kind")})
        if phys.get("kind") not in kinds_ok:
            yield at(c, f"{base}.physical.kind", f"ingestion_origin {origin} requiere physical.kind {' | '.join(sorted(kinds_ok))}")
        st = prof.get("server_type")
        if st and st != "saas" and st not in servers and (origin != "object_store_s3" or strict):
            yield at(c, "servers", f"ingestion_origin {origin} requiere un servers[].type {st}")
        if origin == "api_rest" and strict:
            api = phys.get("api") if isinstance(phys.get("api"), dict) else {}
            for k in ("base_url", "path_template", "http_method"):
                if not api.get(k):
                    yield at(c, f"{base}.physical.api.{k}", f"physical.api.{k} obligatorio para api_rest active")
            auth = api.get("auth") if isinstance(api.get("auth"), dict) else {}
            if not auth.get("type"):
                yield at(c, f"{base}.physical.api.auth.type", "physical.api.auth.type obligatorio para api_rest active")
            if not auth.get("secret_ref"):
                yield at(c, f"{base}.physical.api.auth.secret_ref",
                         "physical.api.auth.secret_ref obligatorio (referencia a Secrets Manager, nunca el secreto)")
            if not (phys.get("schema_binding") or {}).get("root_path"):
                yield at(c, f"{base}.physical.schema_binding.root_path", "schema_binding.root_path obligatorio para api_rest active")
        if origin == "sftp":
            uri = str(phys.get("uri_pattern") or "")
            if uri and not uri.startswith("sftp://"):
                yield at(c, f"{base}.physical.uri_pattern", "uri_pattern debe empezar con sftp://")


# ------------------------------------------------------------------------------------------------ linaje
def _lineage_rule(std: Dict[str, Any], layer: str, zone: str) -> Dict[str, Any]:
    return (std.get("lineage_rules") or {}).get(f"{layer}_{zone}") or {}


@plugin("pcx.lineage")
def lineage(ctx, rule) -> Iterable[Finding]:
    std = standard(ctx)
    lr = std.get("lineage_rules") or {}
    if _pver(std["profile_version"]) < (1, 1, 0):
        return
    for c in contracts(ctx):
        xc, base = extension(c)
        if not xc:
            continue
        r = _lineage_rule(std, str(xc.get("layer")), str(xc.get("medallion_zone")))
        if not r:
            continue
        up, down = refs(xc.get("upstream_contract_ref")), refs(xc.get("downstream_contract_ref"))
        if r.get("upstream_contract_ref") == "forbidden" and up:
            yield at(c, f"{base}.upstream_contract_ref", f"{xc['layer']}/{xc['medallion_zone']} no debe declarar upstream_contract_ref")
        if r.get("upstream_contract_ref") == "required" and not up:
            yield at(c, base, f"upstream_contract_ref obligatorio en {xc['layer']}/{xc['medallion_zone']}")
        prefixes = r.get("upstream_path_prefixes") or ([r["upstream_path_prefix"]] if r.get("upstream_path_prefix") else [])
        for ref in up:
            if prefixes and not any(ref.startswith(p) for p in prefixes):
                yield at(c, f"{base}.upstream_contract_ref", f"upstream {ref!r} debe empezar con {' | '.join(prefixes)}")
        dp = r.get("downstream_path_prefix")
        for ref in down:
            if dp and not ref.startswith(dp):
                yield at(c, f"{base}.downstream_contract_ref", f"downstream {ref!r} debe empezar con {dp}")
        for field, lst in (("upstream_contract_ref", up), ("downstream_contract_ref", down)):
            for ref in lst:
                if not ref.startswith("contracts/"):
                    yield at(c, f"{base}.{field}", f"{field}: las referencias empiezan con contracts/ ({ref!r})")
                elif not ctx.exists(ref):
                    yield at(c, f"{base}.{field}", f"{field}: no existe {ref}")
    _ = lr


@plugin("pcx.lineage_bidirectional")
def lineage_bidirectional(ctx, rule) -> Iterable[Finding]:
    std = standard(ctx)
    lr = std.get("lineage_rules") or {}
    if not lr.get("bidirectional_consistency", True) or _pver(std["profile_version"]) < _pver(lr.get("profile_from", "1.2.0")):
        return
    by_path = {}
    for c in contracts(ctx):
        xc, base = extension(c)
        if xc:
            by_path[c.path] = (c, xc, base)
    for path, (c, xc, base) in by_path.items():
        for down in refs(xc.get("downstream_contract_ref")):
            tgt = by_path.get(down)
            if tgt and path not in refs(tgt[1].get("upstream_contract_ref")):
                yield at(tgt[0], f"{tgt[2]}.upstream_contract_ref", f"debe incluir {path!r} (declarado como downstream en {path})")
        for up in refs(xc.get("upstream_contract_ref")):
            src = by_path.get(up)
            if src and path not in refs(src[1].get("downstream_contract_ref")):
                yield at(src[0], f"{src[2]}.downstream_contract_ref", f"debe incluir {path!r} (declarado como upstream en {path})")


# ------------------------------------------------------------------------------------------------ PII y nombres
@plugin("pcx.pii")
def pii(ctx, rule) -> Iterable[Finding]:
    std = standard(ctx)
    for c in contracts(ctx):
        if not isinstance(c.data, dict):
            continue
        xc, base = extension(c)
        names = [(i, j, p.get("name")) for i, obj in enumerate(c.data.get("schema") or []) if isinstance(obj, dict)
                 for j, p in enumerate(obj.get("properties") or []) if isinstance(p, dict)]
        piis = [(i, j, n) for i, j, n in names if n and is_pii_name(str(n))]
        cls = xc.get("pii_classification") if xc else None
        if cls and cls not in std["pii_enum"]:
            yield at(c, f"{base}.pii_classification", f"pii_classification {cls!r} fuera de {std['pii_enum']}")
        if piis and (not cls or cls == "none"):
            i, j, n = piis[0]
            yield at(c, f"schema[{i}].properties[{j}].name",
                     f"`{n}` parece dato personal pero pii_classification es {cls or 'ausente'} "
                     f"(declarar personal|sensitive; equivalencias con GOV 10 / L0–L4 pendientes: C-07)")


@plugin("pcx.property_names")
def property_names(ctx, rule) -> Iterable[Finding]:
    for c in contracts(ctx):
        if not isinstance(c.data, dict):
            continue
        for i, obj in enumerate(c.data.get("schema") or []):
            for j, p in enumerate((obj or {}).get("properties") or [] if isinstance(obj, dict) else []):
                n = p.get("name") if isinstance(p, dict) else None
                if n and not _SNAKE.match(str(n)):
                    yield at(c, f"schema[{i}].properties[{j}].name", f"`{n}` no está en snake_case (convención de columnas "
                             "aún ambigua frente a ARTS ODM: C-08)")


# ------------------------------------------------------------------------------------------------ copia del estándar, CI
@plugin("pcx.schema_copy_version")
def schema_copy_version(ctx, rule) -> Iterable[Finding]:
    local_dir = ctx.root / "contracts" / "_schema"
    if not local_dir.is_dir():
        if contracts(ctx):
            yield at_file("contracts/_schema", "Falta contracts/_schema/ (copia del estándar que instala bootstrap.sh)",
                          severity="MEDIUM")
        return
    local = standard(ctx)
    plat = platform_standard()
    if plat["origin"].startswith("fallback") and not local.get("schema_profile_version"):
        return
    lv = local.get("schema_profile_version") or local.get("profile_version")
    pv = plat.get("schema_profile_version") or plat.get("profile_version")
    if lv and pv and str(lv) != str(pv):
        yield at_file("contracts/_schema/cencosud-odcs-minimal.schema.json",
                      f"copia local del perfil {lv} desactualizada vs platform-core {pv} ({plat['origin']}): re-sincronizar "
                      "desde data-products-baseline/contracts/_schema/")


@plugin("pcx.dp_workflow")
def dp_workflow(ctx, rule) -> Iterable[Finding]:
    for wf in registry("platform_core")["dp_workflows"]:
        if not ctx.exists(wf):
            yield at_file(wf, f"Falta `{wf}` (CI oficial del Data Product: valida contratos, ficha, catalog-export y "
                          "estándar; copiar desde data-products-baseline/.github/workflows/)")


@plugin("pcx.catalog_export")
def catalog_export(ctx, rule) -> Iterable[Finding]:
    doc = ficha(ctx)
    if doc is None or not isinstance(doc.data, dict) or not contracts(ctx):
        return
    dp_id = doc.data.get("data_product_id")
    if dp_id and not _placeholder(dp_id) and not ctx.exists(f"metadata/catalog-export/{dp_id}.yaml"):
        yield at_file(f"metadata/catalog-export/{dp_id}.yaml", "Falta el catalog-export del Data Product (lo regenera "
                      "`sync_metadata_catalog_export.py` / cenco_dc sync-catalog-export; no editar a mano)")
    tgt = (doc.data.get("catalog_export") or {}).get("target_path") if isinstance(doc.data.get("catalog_export"), dict) else None
    udn = doc.data.get("udn")
    if tgt and dp_id and udn and not _placeholder(tgt):
        want = registry("platform_core")["ficha"]["catalog_export_target"].format(udn=udn, data_product_id=dp_id)
        if tgt != want:
            yield at(doc, "catalog_export.target_path", f"target_path esperado {want!r} (actual {tgt!r})", severity="LOW")


@plugin("pcx.baseline_dirs")
def baseline_dirs(ctx, rule) -> Iterable[Finding]:
    dirs = _baseline_dirs()
    missing = [d for d in dirs if not ctx.is_dir(d)]
    for d in missing:
        yield at_file(d, f"Falta la carpeta del baseline `{d}/`", fix={"type": "create", "path": d + "/"})


def _baseline_dirs() -> List[str]:
    """Carpetas del baseline oficial: del índice de platform-core si está ingerido; si no, el fallback."""
    try:
        from govkit.arch import index as I
        idx = I.load("platform-core")
        if idx:
            pre = "data-products-baseline/"
            dirs = sorted({f[len(pre):].rsplit("/", 1)[0] for f in idx["files"] if f.startswith(pre) and f.endswith(".gitkeep")
                           and "/" in f[len(pre):]})
            dirs = [d for d in dirs if not d.startswith((".github", "contracts/_", "src/", "shared", "publishing",
                                                         "observability", "quality", "modeling/dbt/macros"))
                    and d.count("/") >= 1]
            if dirs:
                return dirs
    except Exception:  # noqa: BLE001
        pass
    return list(registry("platform_core")["baseline_dirs"])


def ficha_template(repo: str, domain: str = "<COMPLETAR dominio>", country: str = "cl") -> str:
    std = platform_standard()
    return registry("platform_core")["ficha_template"].format(repo=repo, domain=domain, country=country,
                                                              profile_version=std["profile_version"])


# ------------------------------------------------------------------------------------------------ cenco_dc (opt-in)
@plugin("pcx.cenco_dc")
def cenco_dc(ctx, rule) -> Iterable[Finding]:
    """Ejecuta el validador oficial desde el clon local de platform-core (solo si el usuario lo activa)."""
    import os
    import subprocess
    import sys
    try:
        from govkit.arch import registry as areg
        src = areg.get("platform-core").path / "framework/data-contracts/tools/cenco_dc/src"
    except Exception:  # noqa: BLE001
        src = Path("/nonexistent")
    if not (src / "cenco_dc").is_dir():
        yield at_file("contracts", f"cenco_dc no disponible (se busca en {src}; clona global-data-platform-core o "
                      "`govkit arch config platform-core <ruta>`)", severity="INFO")
        return
    env = dict(os.environ, PYTHONPATH=str(src) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    for cmd in ("validate-contracts", "validate-metadata"):
        try:
            out = subprocess.run([sys.executable, "-m", "cenco_dc.cli.main", cmd, "--repo-root", str(ctx.root)],
                                 capture_output=True, text=True, timeout=180, env=env, cwd=str(ctx.root))
        except (OSError, subprocess.TimeoutExpired) as exc:
            yield at_file("contracts", f"cenco_dc {cmd}: no se pudo ejecutar ({exc})", severity="INFO")
            continue
        if out.returncode == 0:
            continue
        lines = [ln.strip()[2:] for ln in (out.stderr + out.stdout).splitlines() if ln.strip().startswith("- ")]
        if not lines:
            tail = (out.stderr or out.stdout).strip().splitlines()[-1:] or ["error desconocido"]
            yield at_file("contracts", f"cenco_dc {cmd} no pudo validar: {tail[0][:200]} (requiere Python ≥3.11 + jsonschema)",
                          severity="INFO")
            continue
        for msg in lines[:50]:
            m = re.search(r"(contracts/[\w./-]+\.ya?ml)", msg)
            yield at_file(m.group(1) if m else "contracts", f"[cenco_dc {cmd}] {msg}")


# ------------------------------------------------------------------------------------------------ equivalentes GOV sobre ODCS
def _objects(c: Doc) -> List[Tuple[int, Dict[str, Any]]]:
    data = c.data if isinstance(c.data, dict) else {}
    return [(i, o) for i, o in enumerate(data.get("schema") or []) if isinstance(o, dict)]


def _props(c: Doc) -> Dict[str, Dict[str, Any]]:
    out = {}
    for i, o in _objects(c):
        for j, p in enumerate(o.get("properties") or []):
            if isinstance(p, dict) and p.get("name"):
                out[f"{o.get('name')}.{p['name']}"] = dict(p, _path=f"schema[{i}].properties[{j}]")
    return out


@plugin("pcx.descriptions")
def descriptions(ctx, rule) -> Iterable[Finding]:
    """GOV 06 §11 sobre ODCS: propósito del contrato y descripción de cada propiedad."""
    for c in contracts(ctx):
        if not isinstance(c.data, dict):
            continue
        purpose = (c.data.get("description") or {}).get("purpose") if isinstance(c.data.get("description"), dict) else None
        if _placeholder(purpose) or len(str(purpose or "").strip()) < 15:
            yield at(c, "description.purpose", "description.purpose vacío o demasiado breve (qué representa y para qué sirve)")
        key = "/".join(rel_in_contracts(c.path).split("/")[:2])
        if key.startswith("bronze"):
            continue  # en landing/raw el schema puede ser el del origen; se exige desde silver/odm
        for name, p in _props(c).items():
            d = p.get("description")
            if _placeholder(d) or len(str(d or "").strip()) < 10:
                yield at(c, f"{p['_path']}.description", f"propiedad `{name}` sin descripción útil (≥10 caracteres)",
                         severity="LOW")


@plugin("pcx.compatibility")
def compatibility(ctx, rule) -> Iterable[Finding]:
    """GOV 06 §11 (compatibilidad y política de cambios) en contratos Silver/Gold/semantic."""
    for c in contracts(ctx):
        key = rel_in_contracts(c.path).split("/")[0]
        if key not in ("silver", "gold", "semantic"):
            continue
        for i, o in _objects(c):
            cps = [p for p in (o.get("customProperties") or []) if isinstance(p, dict)]
            comp = next((p.get("value") for p in cps if p.get("property") == "compatibility"), None)
            if not comp:
                yield at(c, f"schema[{i}]", f"`{o.get('name')}` sin compatibilidad declarada (customProperties "
                         "property: compatibility → backward | forward | full | none)")
            elif str(comp) not in ("backward", "forward", "full", "none", "backward_transitive", "forward_transitive"):
                yield at(c, f"schema[{i}].customProperties", f"compatibilidad {comp!r} no reconocida")


@plugin("pcx.breaking_change")
def breaking_change(ctx, rule) -> Iterable[Finding]:
    """GOV 15 §20 sobre ODCS: cambio rompiente (propiedad eliminada, tipo cambiado, deja de ser requerida) sin MAJOR."""
    if not ctx.base_ref:
        return
    from govkit.yamlloc import parse_text
    for c in contracts(ctx):
        old_text = ctx.base_text(c.path)
        if not old_text or not isinstance(c.data, dict):
            continue
        old = parse_text(c.path, old_text)
        if old.error or not isinstance(old.data, dict):
            continue
        op, np_ = _props(old), _props(c)
        reasons = []
        for name, p in op.items():
            q = np_.get(name)
            if q is None:
                reasons.append(f"propiedad eliminada/renombrada `{name}`")
            elif str(p.get("logicalType")) != str(q.get("logicalType")):
                reasons.append(f"cambio de tipo en `{name}` ({p.get('logicalType')} → {q.get('logicalType')})")
            elif p.get("required") and not q.get("required"):
                reasons.append(f"`{name}` deja de ser requerida")
        if not reasons:
            continue
        ov, nv = str(old.data.get("version") or "0.0.0"), str(c.data.get("version") or "0.0.0")
        if ov.split(".")[0] == nv.split(".")[0]:
            yield at(c, "version", f"cambio rompiente sin versión MAJOR ({ov} → {nv}): {'; '.join(reasons[:4])}",
                     fix={"type": "bump", "part": "major"})


@plugin("pcx.quality_rules")
def quality_rules(ctx, rule) -> Iterable[Finding]:
    """GOV 08 §12 sobre ODCS: reglas de calidad críticas declaradas en los contratos Silver/Gold."""
    for c in contracts(ctx):
        key = rel_in_contracts(c.path).split("/")[0]
        if key not in ("silver", "gold"):
            continue
        has = any(o.get("quality") for _, o in _objects(c)) or any(p.get("quality") for p in _props(c).values())
        if not has:
            yield at(c, "schema", "contrato sin reglas de calidad (schema[].quality o properties[].quality): "
                     "un Data Product sin reglas críticas no está listo para producción (08 §12)")


@plugin("pcx.repo_name")
def repo_name(ctx, rule) -> Iterable[Finding]:
    """Nombre de repo DP: {dominio}-{subdominio}[-{tipo}]-dp-{país}; tipos observados en el diseño aprobado (C-04)."""
    name = ctx.repo_name
    m = re.match(r"^([a-z0-9]+(?:-[a-z0-9]+)*)-dp-([a-z]{2,3})$", name)
    if not m:
        yield at_file(".", f"`{name}` no sigue el patrón <dominio>-<subdominio>[-<tipo>]-dp-<país>")
        return
    parts = m.group(1).split("-")
    known = {"txd", "anl", "mdh", "sm"}
    if len(parts) >= 3 and parts[-1] not in known and len(parts[-1]) <= 3:
        yield at_file(".", f"código de tipo `{parts[-1]}` no observado (txd, anl según lineamiento; mdh, sm en ArchiMate "
                      "aprobado; significado de mdh/sm NO DETERMINADO: C-04)", severity="INFO")
