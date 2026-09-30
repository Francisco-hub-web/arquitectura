"""Modelo ArchiMate (coArchi): inventario de Data Products modelados y diseño APROBADO vs IMPLEMENTADO."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from govkit.arch import index as I

LAYER_KEYS = [
    ("bronze/landing", r"\blanding\b"), ("bronze/raw", r"\braw\b"), ("bronze", r"\bbronce\b|\bbronze\b"),
    ("silver/stg", r"\bstg\b|staging"), ("silver/odm", r"\bodm\b"), ("silver", r"\bsilver\b"),
    ("gold/dim", r"\bdim\b|dimension"), ("gold/fact", r"\bfact\b|\bfct\b"), ("gold", r"\bgold\b"),
    ("semantic", r"\bsemantic"),
]
TECH_TYPES = {"TechnologyService", "Node", "SystemSoftware", "Device", "TechnologyInterface", "Artifact"}


def _model(idx: Dict[str, Any]) -> Dict[str, Any]:
    return idx.get("archimate") or {"elements": {}, "relations": [], "diagrams": [], "folders": {}}


def _names(model: Dict[str, Any], folder: str) -> List[str]:
    parts = folder.split("/")
    out = []
    for i in range(2, len(parts) + 1):
        f = model["folders"].get("/".join(parts[:i]))
        if f:
            out.append(f["name"])
    return out


def dp_inventory(idx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Carpetas Views/…/Data Products/<país>/<data-product>: vistas por nivel (HLD/MLD/LLD) y si están vacías."""
    model = _model(idx)
    out = []
    for path in sorted(model["folders"]):
        names = _names(model, path)
        if "Data Products" not in names:
            continue
        k = names.index("Data Products")
        if len(names) != k + 3:
            continue
        views = [d for d in model["diagrams"] if d["folder"] == path or d["folder"].startswith(path + "/")]
        levels = Counter()
        for d in views:
            sub = _names(model, d["folder"])[k + 3:]
            levels[sub[0] if sub else "(raíz)"] += 1
        sublevels = sorted({_names(model, p)[k + 3] for p in model["folders"]
                            if p.startswith(path + "/") and len(_names(model, p)) > k + 3})
        out.append({"name": names[-1], "country": names[k + 1], "folder": path, "path_names": names,
                    "views": len(views), "levels": dict(levels), "declared_levels": sublevels,
                    "view_names": [d["name"] for d in views],
                    "elements": sum(len(d["elements"]) for d in views)})
    return out


def find_dp(idx: Dict[str, Any], repo_name: str) -> Dict[str, Any]:
    inv = dp_inventory(idx)
    exact = [d for d in inv if d["name"] == repo_name]
    if exact:
        return {"match": "exact", "dp": exact[0], "similar": []}
    stem = re.sub(r"-dp-[a-z]{2}$", "", repo_name)
    domain = stem.split("-")[0]
    similar = [d["name"] for d in inv if d["name"].split("-")[0] == domain or stem in d["name"]]
    return {"match": None, "dp": None, "similar": similar}


def design(idx: Dict[str, Any], dp: Dict[str, Any]) -> Dict[str, Any]:
    """Elementos modelados en las vistas del DP: capas, tecnologías, procesos y datos."""
    model = _model(idx)
    views = [d for d in model["diagrams"] if d["folder"] == dp["folder"] or d["folder"].startswith(dp["folder"] + "/")]
    ids = {e for d in views for e in d["elements"]}
    els = [model["elements"][i] for i in ids if i in model["elements"]]
    groupings = sorted({e["name"] for e in els if e["type"] == "Grouping"})
    text = " ".join(e["name"] for e in els).lower()
    layers = [k for k, rx in LAYER_KEYS if re.search(rx, text, re.I)]
    return {
        "views": [{"name": d["name"], "level": " / ".join(_names(model, d["folder"])[len(dp["path_names"]):]) or "(raíz)",
                   "elements": len(d["elements"]), "empty": not d["elements"]} for d in views],
        "layers_modeled": layers,
        "technologies": sorted({e["name"] for e in els if e["type"] in TECH_TYPES}),
        "processes": sorted({e["name"] for e in els if e["type"] in ("ApplicationProcess", "BusinessProcess")}),
        "data_objects": sorted({e["name"] for e in els if e["type"] == "DataObject"}),
        "components": sorted({e["name"] for e in els if e["type"] == "ApplicationComponent"}),
        "groupings": groupings,
        "documented": sum(1 for e in els if e.get("doc")),
        "total_elements": len(els),
    }


def implemented_layers(repo: Path) -> Dict[str, List[str]]:
    """Capas implementadas en un repo de Data Product (contratos + modelos dbt + src)."""
    out: Dict[str, List[str]] = {}
    checks = {
        "bronze/landing": ["contracts/bronze/landing"], "bronze/raw": ["contracts/bronze/raw"],
        "silver/odm": ["contracts/silver/odm", "modeling/dbt/models/silver"],
        "silver/stg": ["modeling/dbt/models/staging", "modeling/dbt/models/silver/stg"],
        "gold/dim": ["contracts/gold/dim"], "gold/fact": ["contracts/gold/fact"],
        "gold": ["modeling/dbt/models/gold", "contracts/gold"], "semantic": ["contracts/semantic", "src/semantic"],
    }
    for layer, dirs in checks.items():
        hits = []
        for d in dirs:
            p = repo / d
            if p.is_dir():
                files = [f for f in p.rglob("*") if f.is_file() and f.name != ".gitkeep"]
                if files:
                    hits.append(f"{d} ({len(files)})")
        if hits:
            out[layer] = hits
    return out


def compare(idx: Dict[str, Any], repo: Path, repo_name: Optional[str] = None) -> Dict[str, Any]:
    """APPROVED (AM main) vs IMPLEMENTED (repo local). Nunca concluye desviación sin evidencia de ambos lados."""
    name = repo_name or repo.name
    found = find_dp(idx, name)
    impl = implemented_layers(repo)
    res: Dict[str, Any] = {"repo": name, "archimate": idx["meta"].get("repo"),
                           "trace": f"{idx['meta']['repo']}@{str(idx['meta'].get('commit') or '?')[:7]}",
                           "found": found, "implemented": impl, "rows": []}
    if not found["dp"]:
        res["verdict"] = ("NO DETERMINADO: el Data Product no tiene carpeta de diseño en el modelo ArchiMate aprobado"
                          + (f" (similares: {', '.join(found['similar'])})" if found["similar"] else ""))
        return res
    des = design(idx, found["dp"])
    res["design"] = des
    if not des["total_elements"]:
        res["verdict"] = ("NO DETERMINADO: la carpeta del Data Product existe en ArchiMate pero sus vistas están vacías "
                          f"({', '.join(found['dp']['declared_levels']) or 'sin niveles'})")
        return res
    for layer, _ in LAYER_KEYS:
        modeled = layer in des["layers_modeled"]
        implemented = layer in impl
        if not modeled and not implemented:
            continue
        state = ("coincide" if modeled and implemented else
                 "modelado, no implementado (APPROVED sin IMPLEMENTED)" if modeled else
                 "implementado, no modelado (IMPLEMENTED sin APPROVED)")
        res["rows"].append({"layer": layer, "modeled": modeled, "implemented": impl.get(layer, []), "state": state})
    gaps = [r for r in res["rows"] if r["state"] != "coincide"]
    res["verdict"] = ("Sin desviaciones de capas entre diseño aprobado e implementación" if not gaps else
                      f"{len(gaps)} diferencia(s) de capas entre el diseño aprobado y la implementación (revisar; "
                      "puede ser avance parcial, no necesariamente desviación)")
    return res


def current() -> Optional[Dict[str, Any]]:
    return I.load("archimate")
