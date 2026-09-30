"""Extracción determinista: secciones Markdown, marcas normativas, referencias, YAML/JSON, ArchiMate (coArchi),
enmascarado de secretos e identificadores de cuenta."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, List, Optional, Tuple

from govkit.paths import SafeLoader, yaml

# ------------------------------------------------------------------------------------------------ enmascarado
SECRET_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("connection_string_password", re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s:/@'\"]+:([^\s@/'\"]{4,})@")),
]
SECRET_ASSIGN = re.compile(
    r"(?i)(?<![:/.-])\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?key|client[_-]?secret|token)\b(\s*[:=]\s*[\"']?)"
    r"([^\s\"'#,}{]{8,})")
SAFE_VALUE = re.compile(r"(?i)(\$\{|\{\{|<|example|changeme|xxx|placeholder|secret_ref|secrets\.|env\.|environ|"
                        r"getenv|vault|^arn:|^true$|^false$|^none$|^null$|required|^str$|string|\*\*\*|_ref$)")
ACCOUNT_ID = re.compile(r"(?<![\w.-])\d{12}(?![\w.-])")


def mask(text: str) -> Tuple[str, List[str], int]:
    """→ (texto enmascarado, tipos de secreto detectados, n.º de IDs de cuenta enmascarados). Nunca devuelve valores."""
    found: List[str] = []
    for kind, rx in SECRET_PATTERNS:
        if rx.search(text):
            found.append(kind)
            text = rx.sub(f"[{kind.upper()} ENMASCARADO]", text)

    def _assign(m: "re.Match[str]") -> str:
        if SAFE_VALUE.search(m.group(3)):
            return m.group(0)
        found.append(f"assignment:{m.group(1).lower()}")
        return f"{m.group(1)}{m.group(2)}[ENMASCARADO]"
    text = SECRET_ASSIGN.sub(_assign, text)
    text, n = ACCOUNT_ID.subn("<account-id>", text)
    return text, found, n


# ------------------------------------------------------------------------------------------------ normativa
_MARKERS = {
    "REQUIRED": re.compile(r"(?i)\b(deben?|obligatori[oa]s?|no se permiten?|prohibid[oa]s?|se exige|exigid[oa]|"
                           r"requerid[oa]s?|must|shall|required|forbidden|mandatory|es requisito)\b"),
    "RECOMMENDED": re.compile(r"(?i)\b(se recomienda|recomendad[oa]s?|deber[ií]an?|buenas? pr[aá]cticas?|sugerid[oa]|"
                              r"should|recommended|preferentemente|idealmente)\b"),
    "DEPRECATED": re.compile(r"(?i)\b(deprecad[oa]s?|obsolet[oa]s?|eliminad[oa] en|retirad[oa]s?|reemplazad[oa] por|"
                             r"supersede[sd]?|deprecated|legacy|ya no (?:se )?(?:usa|aplica|es v[aá]lid))"),
}
DRAFT_STATUS = re.compile(r"(?i)^\W*(?:estado|status|state|versi[oó]n)\W*[:：]\W*[^\n]{0,20}?"
                          r"\b(draft|borrador|propuest[oa]|en revisi[oó]n|wip|pendiente)")
DRAFT_ANY = re.compile(r"(?i)pendiente de (?:validaci[oó]n|aprobaci[oó]n|revisi[oó]n)|\bdocumento en borrador\b")
DRAFT_TITLE = re.compile(r"(?i)\b(draft|borrador|wip)\b")


def normative(text: str) -> Dict[str, int]:
    return {k: len(rx.findall(text)) for k, rx in _MARKERS.items()}


def is_draft(text: str, head_lines: int = 40) -> bool:
    """Estado del DOCUMENTO (no menciones a `status: draft` de contratos): línea "Estado: Draft", título con
    "Borrador", "pendiente de validación" o front matter `status: draft`."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for ln in lines[1:30]:
            if ln.strip() == "---":
                break
            if re.match(r"(?i)^\s*status\s*:\s*['\"]?(draft|borrador|proposed|propuesto)", ln):
                return True
    fence = False
    for ln in lines[:head_lines]:
        if _FENCE.match(ln):
            fence = not fence
            continue
        s = ln.strip()
        if fence or s.startswith("|"):
            continue
        s = re.sub(r"`[^`]*`", "", s)
        if DRAFT_STATUS.search(s) or DRAFT_ANY.search(s) or (s.startswith("#") and DRAFT_TITLE.search(s)):
            return True
    return False


# ------------------------------------------------------------------------------------------------ Markdown
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_CODE_SPAN = re.compile(r"`([^`\n]{3,200})`")
_PATHLIKE = re.compile(r"^(?:\.{1,2}/)*(?:[\w@.-]+/)+[\w@.\-{}<>*]*$|^[\w.-]+\.(?:md|ya?ml|json|py|sql|sh|xml|xlsx|csv|toml|js)$")
_REPO_REF = re.compile(r"\b(global-[a-z0-9-]+)(/[\w./{}<>*-]*)?")


def md_sections(text: str) -> List[Dict[str, Any]]:
    """Secciones por encabezado ATX (ignora bloques de código). Cada una con línea inicial/final."""
    lines = text.splitlines()
    heads: List[Tuple[int, int, str]] = []
    fence = False
    for i, ln in enumerate(lines, 1):
        if _FENCE.match(ln):
            fence = not fence
            continue
        if fence:
            continue
        m = _HEADING.match(ln)
        if m:
            heads.append((i, len(m.group(1)), m.group(2).strip()))
    if not heads or heads[0][0] > 1:
        heads.insert(0, (1, 0, "(inicio)"))
    out = []
    for j, (line, level, title) in enumerate(heads):
        end = heads[j + 1][0] - 1 if j + 1 < len(heads) else len(lines)
        body = "\n".join(lines[line - 1:end])
        if title == "(inicio)" and not body.strip():
            continue
        out.append({"t": _clean_title(title), "l": level, "line": line, "end": max(line, end),
                    "norm": normative(body)})
    return out


def _clean_title(t: str) -> str:
    t = re.sub(r"[*`]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()[:160]


def title_of(text: str, rel: str) -> str:
    for ln in text.splitlines()[:60]:
        m = _HEADING.match(ln)
        if m:
            return _clean_title(m.group(2))
    for ln in text.splitlines()[:10]:
        s = ln.strip().lstrip("#").strip()
        if s and not s.startswith(("---", "{", "[")):
            return s[:160]
    return rel.rsplit("/", 1)[-1]


def first_paragraph(text: str, limit: int = 320) -> str:
    """Primer párrafo de prosa (salta encabezados, tablas, código, citas de metadatos y listas de estructura)."""
    fence = False
    buf: List[str] = []
    for ln in text.splitlines():
        if _FENCE.match(ln):
            fence = not fence
            continue
        s = ln.strip()
        if fence or s.startswith(("#", "|", "<", "---", "===", "![", "- 🌿")) or re.match(r"^[-*]\s*\*\*\w+\*\*:", s):
            if buf:
                break
            continue
        if not s:
            if buf:
                break
            continue
        s = s.lstrip("> ").strip()
        if not buf and re.match(r"^\**[\wÁÉÍÓÚáéíóúñ ]{2,25}\**\s*[:：]\s*\S", s) and len(s) < 200:
            continue  # cabecera de metadatos (Versión: …, Estado: …, Alcance: …)
        if s:
            buf.append(s)
    para = re.sub(r"\s+", " ", " ".join(buf))
    para = re.sub(r"\*\*|__|`", "", para)
    return (para[:limit - 1] + "…") if len(para) > limit else para


def refs(text: str, is_markdown: bool) -> List[Dict[str, Any]]:
    """Referencias salientes: enlaces Markdown, rutas en `código`, menciones a otros repos globales."""
    out: List[Dict[str, Any]] = []
    seen = set()
    for no, ln in enumerate(text.splitlines(), 1):
        cands: List[Tuple[str, str]] = []
        if is_markdown:
            cands += [("link", m.group(1)) for m in _MD_LINK.finditer(ln)]
            cands += [("path", m.group(1)) for m in _CODE_SPAN.finditer(ln)]
        cands += [("repo", m.group(1) + (m.group(2) or "")) for m in _REPO_REF.finditer(ln)]
        for kind, target in cands:
            target = target.strip().strip("'\"").split("#")[0]
            if not target or target.startswith(("http://", "https://", "mailto:", "#")) and kind != "repo":
                continue
            if kind == "path" and not _PATHLIKE.match(target):
                continue
            key = (kind, target)
            if key in seen:
                continue
            seen.add(key)
            out.append({"target": target, "line": no, "kind": kind})
    return out


# ------------------------------------------------------------------------------------------------ YAML / JSON
def load_structured(rel: str, text: str) -> Tuple[Any, Optional[str]]:
    try:
        if rel.endswith(".json"):
            return json.loads(text), None
        docs = [d for d in yaml.load_all(text, Loader=SafeLoader)]
        return (docs[0] if len(docs) == 1 else docs), None
    except Exception as exc:  # noqa: BLE001 - archivo inválido: se reporta, no rompe el índice
        return None, f"{type(exc).__name__}: {str(exc)[:160]}"


def flatten(data: Any, prefix: str = "", out: Optional[Dict[str, Any]] = None, limit: int = 4000) -> Dict[str, Any]:
    """{ruta.clave: valor escalar | [lista de escalares]} (para diffs semánticos y hechos)."""
    out = {} if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(data, dict):
        for k, v in data.items():
            flatten(v, f"{prefix}.{k}" if prefix else str(k), out, limit)
    elif isinstance(data, list):
        if all(not isinstance(x, (dict, list)) for x in data):
            out[prefix] = [_scalar(x) for x in data]
        else:
            for i, v in enumerate(data):
                flatten(v, f"{prefix}[{i}]", out, limit)
    else:
        out[prefix] = _scalar(data)
    return out


def _scalar(v: Any) -> Any:
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def dig(data: Any, path: str) -> Tuple[bool, Any]:
    cur = data
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        if part.startswith("["):
            idx = int(part[1:-1])
            if not isinstance(cur, list) or idx >= len(cur):
                return False, None
            cur = cur[idx]
        else:
            if not isinstance(cur, dict) or part not in cur:
                return False, None
            cur = cur[part]
    return True, cur


def structured_refs(flat: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for key, val in flat.items():
        for v in (val if isinstance(val, list) else [val]):
            if isinstance(v, str) and ("/" in v or v.endswith((".md", ".yaml", ".yml", ".json", ".py"))) and \
                    _PATHLIKE.match(v.strip()) and not v.startswith(("http", "s3://", "arn:")):
                out.append({"target": v.strip(), "line": 0, "kind": "value", "key": key})
    return out


# ------------------------------------------------------------------------------------------------ ArchiMate (coArchi)
_XSI_NS = "{http://www.w3.org/2001/XMLSchema-instance}"


def _tag(el: ET.Element) -> str:
    return el.tag.split("}")[-1]


def archimate(files: Iterable[Tuple[str, bytes]]) -> Dict[str, Any]:
    """Parsea un modelo coArchi (un XML por elemento/relación/vista/carpeta)."""
    elements: Dict[str, Dict[str, Any]] = {}
    relations: List[Dict[str, Any]] = []
    diagrams: List[Dict[str, Any]] = []
    folders: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []
    for rel, data in files:
        if not rel.endswith(".xml"):
            continue
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            errors.append(f"{rel}: {exc}")
            continue
        tag = _tag(root)
        folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
        doc = (root.findtext("documentation") or "").strip()
        props = {p.get("key"): p.get("value") for p in root.findall("properties") if p.get("key")}
        if tag == "Folder":
            folders[folder] = {"id": root.get("id"), "name": root.get("name") or folder.rsplit("/", 1)[-1],
                               "type": root.get("type"), "path": folder}
        elif tag == "ArchimateDiagramModel":
            refs_ = []
            for c in root.iter():
                if _tag(c) == "archimateElement" and c.get("href"):
                    refs_.append(c.get("href").split("#")[-1])
            diagrams.append({"id": root.get("id"), "name": root.get("name") or "", "folder": folder,
                             "elements": list(dict.fromkeys(refs_)), "file": rel, "doc": doc})
        elif tag.endswith("Relationship"):
            s, t = root.find("source"), root.find("target")
            relations.append({"id": root.get("id"), "type": tag, "name": root.get("name") or "",
                              "source": (s.get("href") or "").split("#")[-1] if s is not None else None,
                              "target": (t.get("href") or "").split("#")[-1] if t is not None else None,
                              "file": rel})
        elif tag != "ArchimateModel":
            elements[root.get("id") or rel] = {"id": root.get("id"), "type": tag, "name": (root.get("name") or "").strip(),
                                               "folder": folder, "doc": doc, "props": props, "file": rel}
    return {"elements": elements, "relations": relations, "diagrams": diagrams, "folders": folders, "errors": errors}


def folder_names(model: Dict[str, Any], folder_path: str) -> List[str]:
    """Ruta de carpetas por NOMBRE (Views/Data Platform/…) a partir de la ruta física de coArchi."""
    parts = folder_path.split("/")
    names = []
    for i in range(2, len(parts) + 1):
        f = model["folders"].get("/".join(parts[:i]))
        if f:
            names.append(f["name"])
    return names


# ------------------------------------------------------------------------------------------------ diccionarios
TECHNOLOGIES = {
    "dbt": r"\bdbt\b", "AWS Glue": r"\bglue\b", "Apache Iceberg": r"\biceberg\b", "Amazon S3": r"\bs3\b",
    "Lake Formation": r"lake ?formation", "Athena": r"\bathena\b", "Redshift": r"\bredshift\b",
    "Step Functions": r"step ?functions", "Lambda": r"\blambda\b", "DynamoDB": r"dynamo", "Kafka": r"\bkafka\b",
    "Terraform": r"\bterraform\b", "GitHub Actions": r"github actions|\.github/workflows|runs-on:",
    "Python": r"\bpython\b|\.py\b", "JSON Schema": r"json ?schema|\$schema", "ODCS": r"\bodcs\b|open data contract",
    "OpenLineage": r"open ?linage|open ?lineage", "OpenMetadata": r"open ?metadata|\bomd\b",
    "Databricks": r"databricks", "Confluence": r"confluence", "ArchiMate": r"archimate", "Power BI": r"power ?bi",
    "OSI (semantic model)": r"\.osi\.ya?ml|\bosi\b", "SFTP": r"\bsftp\b", "API REST": r"api[_ ]rest|\brest api\b",
    "CloudWatch": r"cloudwatch", "KMS": r"\bkms\b",
}
PATTERNS = {
    "Medallion (bronze/silver/gold)": r"medall?ion|\bbronze\b.*\bsilver\b|\bsilver\b.*\bgold\b",
    "Write-Audit-Publish (WAP)": r"\bwap\b|write[- ]audit[- ]publish",
    "Contract-first (ODCS)": r"contract[- ]first|\bp6\b|data contract",
    "ARTS / ODM": r"\barts\b|\bodm\b",
    "Dimensional (dim/fact)": r"\bdim_|\bfact_|\bfct_|dimensional",
    "Scaffold / baseline de Data Product": r"baseline|scaffold|bootstrap",
    "Linaje bidireccional": r"upstream_contract_ref|downstream_contract_ref|linaje|lineage",
    "Quarantine / calidad bloqueante": r"quarantine|cuarentena|quality gate",
    "Semantic layer / métricas": r"semantic layer|capa sem[aá]ntica|\bm[eé]tricas?\b",
    "Data Mesh / Data Product": r"data product|producto de datos",
    "RoAW / AS-IS → TO-BE": r"\broaw\b|as-is|to-be",
}
_TECH_RX = {k: re.compile(v, re.I) for k, v in TECHNOLOGIES.items()}
_PAT_RX = {k: re.compile(v, re.I) for k, v in PATTERNS.items()}


def technologies(text: str) -> List[str]:
    return [k for k, rx in _TECH_RX.items() if rx.search(text)]


def patterns(text: str) -> List[str]:
    return [k for k, rx in _PAT_RX.items() if rx.search(text)]


def normalize_md(text: str) -> str:
    """Normaliza diferencias cosméticas (escapes, alineación de tablas, espacios, elipsis) para diffs."""
    t = text.replace("\\_", "_").replace("\\[", "[").replace("\\]", "]").replace("…", "...").replace(":---", "---")
    t = re.sub(r"\\([*#<>|~-])", r"\1", t)
    t = re.sub(r"[ \t]+", " ", t)
    return "\n".join(ln.strip() for ln in t.splitlines() if ln.strip())
