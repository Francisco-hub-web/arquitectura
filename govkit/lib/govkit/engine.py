"""Motor de evaluación: catálogo → checks → severidad por ciclo de vida → waivers → resultado."""
from __future__ import annotations

import datetime as _dt
import fnmatch
import hashlib
import json
import time
import traceback
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from govkit import __version__
from govkit.declarative import dispatch, when_ok
from govkit.model import SEV_RANK, Finding, Location, Rule, Violation
from govkit.paths import RULES_DIR, load_yaml_file
from govkit.plugins import PLUGINS, load_all
from govkit.repo import RepoContext


def load_catalog(path=None) -> Dict[str, Any]:
    path = path or RULES_DIR / "catalog.yaml"
    raw = load_yaml_file(path)
    raw["_digest"] = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    raw["_rules"] = [Rule(r) for r in raw.get("rules", [])]
    return raw


@dataclass
class Outcome:
    status: str  # pass | fail | skipped | not_applicable | error | semantic | organizational
    severity: Optional[str] = None
    detail: Optional[str] = None


@dataclass
class Result:
    ctx: RepoContext
    catalog: Dict[str, Any]
    violations: List[Violation] = field(default_factory=list)
    outcomes: Dict[str, Outcome] = field(default_factory=dict)
    handoff: List[Dict[str, Any]] = field(default_factory=list)
    waivers_applied: List[Dict[str, Any]] = field(default_factory=list)
    duration_ms: int = 0
    fail_on: str = "BLOCKER"
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    mode: str = "full"

    @property
    def counting(self) -> List[Violation]:
        return [v for v in self.violations if v.counts]

    def counts(self) -> Dict[str, int]:
        out = {s: 0 for s in ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO")}
        for v in self.counting:
            out[v.severity] += 1
        return out

    @property
    def verdict(self) -> str:
        if any(SEV_RANK[v.severity] >= SEV_RANK[self.fail_on] for v in self.counting):
            return "FAIL"
        if any(v.severity in ("BLOCKER", "HIGH", "MEDIUM") for v in self.counting):
            return "WARN"
        return "PASS"

    @property
    def exit_code(self) -> int:
        return 1 if self.verdict == "FAIL" else 0


class Engine:
    def __init__(self, ctx: RepoContext, catalog: Dict[str, Any], packs: Iterable[str] = ("dp",),
                 only: Optional[Iterable[str]] = None, profile: Optional[str] = None,
                 baseline: Optional[Set[str]] = None, fail_on: str = "BLOCKER",
                 changed_only: bool = False, skip_posts: bool = False):
        load_all()
        self.skip_posts = skip_posts
        self.ctx = ctx
        self.catalog = catalog
        self.packs = set(packs)
        self.only = [o.upper() for o in only] if only else None
        self.profile = profile
        self.baseline = baseline or set()
        self.fail_on = fail_on
        self.changed_only = changed_only
        self.changed = set(ctx.changed_files() or []) if changed_only else None

    # ------------------------------------------------------------------ selección
    def selected(self) -> List[Rule]:
        disabled = {d.upper() for d in (self.ctx.config.get("rules") or {}).get("disable", [])}
        out = []
        for r in self.catalog["_rules"]:
            if r.pack not in self.packs or r.id in disabled:
                continue
            if self.only and not any(fnmatch.fnmatch(r.id, o) for o in self.only):
                continue
            if self.profile and self.profile not in r.enforcement:
                continue
            out.append(r)
        return out

    def _severity(self, rule: Rule, override: Optional[str]) -> str:
        base = override or rule.severity
        cfg = (self.ctx.config.get("rules") or {}).get("severity", {}).get(rule.id)
        if cfg and cfg in SEV_RANK and SEV_RANK[cfg] > SEV_RANK[base]:
            base = cfg  # un repo puede ser más estricto, nunca más laxo (usar waivers)
        return rule.severity_for(self.ctx.stage_group, base)

    # ------------------------------------------------------------------ waivers
    def _valid_waivers(self) -> List[Dict[str, Any]]:
        out = []
        for w in self.ctx.config.get("waivers") or []:
            exp = w.get("expires")
            try:
                exp_date = exp if isinstance(exp, _dt.date) else _dt.date.fromisoformat(str(exp))
            except ValueError:
                continue
            if all(w.get(k) for k in ("rule", "reason", "owner", "adr")) and exp_date >= self.ctx.today:
                out.append(w)
        return out

    def _waiver_for(self, v: Violation, waivers: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for w in waivers:
            if not fnmatch.fnmatch(v.rule_id, str(w["rule"]).upper()):
                continue
            paths = w.get("paths")
            if paths and not any(fnmatch.fnmatch(v.location.file, p) for p in paths):
                continue
            return {"reason": w["reason"], "owner": w["owner"], "adr": w["adr"], "expires": str(w["expires"])}
        return None

    # ------------------------------------------------------------------ ejecución
    def _findings(self, rule: Rule) -> List[Finding]:
        req = rule.raw.get("requires") or {}
        if (req.get("artifact") and not self.ctx.artifact(req["artifact"])) or \
                (req.get("glob") and not self.ctx.glob(req["glob"])):
            # Sin el artefacto no hay evidencia: evita "aprobados vacíos" que inflarían el pre-score.
            res.outcomes[rule.id] = Outcome("not_applicable", detail="sin artefacto evaluable")
            return
        chk = rule.check or {}
        if chk.get("target") and not self.ctx.artifact(chk["target"]):
            res.outcomes[rule.id] = Outcome("not_applicable", detail=f"sin artefacto `{chk['target']}`")
            return
        if chk.get("kind") in ("plugin", "post"):
            fn = PLUGINS.get(chk["name"])
            if fn is None:
                raise KeyError(f"plugin no registrado: {chk['name']}")
            if chk["kind"] == "post":  # reglas post-evaluación (consumen el resultado parcial, p.ej. scoring)
                return list(fn(self.ctx, rule, self._res) or [])
            return list(fn(self.ctx, rule) or [])
        return dispatch(self.ctx, chk)

    def run(self) -> Result:
        t0 = time.time()
        res = Result(self.ctx, self.catalog, fail_on=self.fail_on, mode="diff" if self.changed_only else "full")
        waivers = self._valid_waivers()
        self._res = res
        composites: List[Rule] = []
        posts: List[Rule] = []
        for rule in self.selected():
            if rule.nature == "S":
                res.outcomes[rule.id] = Outcome("semantic")
                if when_ok(rule.raw.get("when"), self.ctx):
                    res.handoff.append({"rule_id": rule.id, "question": rule.semantic_question, "kb": rule.kb,
                                        "title": rule.title})
                continue
            if rule.nature == "O" or not rule.check:
                res.outcomes[rule.id] = Outcome("organizational" if rule.nature == "O" else "semantic")
                continue
            if rule.check.get("kind") == "composite":
                composites.append(rule)
                continue
            if rule.check.get("kind") == "post":
                if not self.skip_posts:
                    posts.append(rule)
                continue
            self._eval(rule, res, waivers)
        for rule in posts:
            self._eval(rule, res, waivers)
        failed = {v.rule_id for v in res.counting}
        pending = {r.id: r for r in composites}
        while pending:  # orden topológico: un compuesto puede depender de otro compuesto
            ready = [r for r in pending.values()
                     if not {i for ids in r.check["requires"].values() for i in ids} & set(pending)]
            for rule in ready or list(pending.values()):
                self._eval_composite(rule, res, failed, waivers)
                if res.outcomes.get(rule.id, Outcome("")).status == "fail":
                    failed.add(rule.id)
                pending.pop(rule.id)
        # Preguntas semánticas de reglas híbridas cuya parte determinista pasó.
        for rule in self.selected():
            if rule.nature == "H" and rule.semantic_question and res.outcomes.get(rule.id, Outcome("")).status == "pass":
                res.handoff.append({"rule_id": rule.id, "question": rule.semantic_question, "kb": rule.kb,
                                    "title": rule.title})
        order = {"BLOCKER": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        res.violations.sort(key=lambda v: (not v.counts, order[v.severity], v.location.file, v.location.line))
        res.duration_ms = int((time.time() - t0) * 1000)
        return res

    def _eval(self, rule: Rule, res: Result, waivers: List[Dict[str, Any]]) -> None:
        sev_default = self._severity(rule, None)
        if sev_default == "OFF":
            res.outcomes[rule.id] = Outcome("skipped", detail=f"desactivada en etapa {self.ctx.stage}")
            return
        if not when_ok(rule.raw.get("when"), self.ctx):
            res.outcomes[rule.id] = Outcome("not_applicable")
            return
        req = rule.raw.get("requires") or {}
        if (req.get("artifact") and not self.ctx.artifact(req["artifact"])) or \
                (req.get("glob") and not self.ctx.glob(req["glob"])):
            # Sin el artefacto no hay evidencia: evita "aprobados vacíos" que inflarían el pre-score.
            res.outcomes[rule.id] = Outcome("not_applicable", detail="sin artefacto evaluable")
            return
        chk = rule.check or {}
        if chk.get("target") and not self.ctx.artifact(chk["target"]):
            res.outcomes[rule.id] = Outcome("not_applicable", detail=f"sin artefacto `{chk['target']}`")
            return
        if chk.get("kind") in ("plugin", "post") and getattr(PLUGINS.get(chk.get("name")), "needs_dp", False) \
                and (self.ctx.dp is None or not isinstance(self.ctx.dp.data, dict)):
            res.outcomes[rule.id] = Outcome("not_applicable", detail="sin ficha de Data Product")
            return
        try:
            findings = self._findings(rule)
        except Exception as exc:  # resiliencia: un plugin roto no tumba la corrida
            res.outcomes[rule.id] = Outcome("error", detail=f"{type(exc).__name__}: {exc}")
            res.violations.append(self._violation(rule, Finding(
                f"Error interno evaluando la regla ({type(exc).__name__}: {exc})", Location("."),
                evidence={"trace": traceback.format_exc(limit=2)[-400:]}), "INFO", "INFO"))
            return
        if self.changed is not None and rule.raw.get("scope", "file") == "file":
            findings = [f for f in findings if f.location.file in self.changed or f.location.file == "."]
        if not findings:
            res.outcomes[rule.id] = Outcome("pass", sev_default)
            return
        res.outcomes[rule.id] = Outcome("fail", sev_default)
        for f in findings:
            sev = self._severity(rule, f.severity)
            if sev == "OFF":
                continue
            v = self._violation(rule, f, sev, f.severity or rule.severity)
            v.waived = self._waiver_for(v, waivers)
            if v.waived:
                res.waivers_applied.append({"rule_id": v.rule_id, "file": v.location.file, **v.waived})
            v.baselined = v.fingerprint in self.baseline
            res.violations.append(v)

    def _eval_composite(self, rule: Rule, res: Result, failed: Set[str], waivers: List[Dict[str, Any]]) -> None:
        sev = self._severity(rule, None)
        if sev == "OFF":
            res.outcomes[rule.id] = Outcome("skipped", detail=f"desactivada en etapa {self.ctx.stage}")
            return
        if not when_ok(rule.raw.get("when"), self.ctx):
            res.outcomes[rule.id] = Outcome("not_applicable")
            return
        missing = {bucket: sorted(set(ids) & failed) for bucket, ids in rule.check["requires"].items()}
        missing = {b: ids for b, ids in missing.items() if ids}
        if not missing:
            res.outcomes[rule.id] = Outcome("pass", sev)
            return
        res.outcomes[rule.id] = Outcome("fail", sev)
        target = self.ctx.dp.path if self.ctx.dp else "."
        detail = "; ".join(f"{b} ({', '.join(ids)})" for b, ids in missing.items())
        v = self._violation(rule, Finding(f"Criterios incumplidos: {detail}", Location(target),
                                          evidence={"key": rule.id, "buckets": missing}), sev, rule.severity)
        v.waived = self._waiver_for(v, waivers)
        v.baselined = v.fingerprint in self.baseline
        res.violations.append(v)

    def _violation(self, rule: Rule, f: Finding, sev: str, base: str) -> Violation:
        escalated = f"etapa:{self.ctx.stage}" if sev != base and rule.stages.get(self.ctx.stage_group) else None
        return Violation(rule_id=rule.id, title=rule.title, nature=rule.nature, category=rule.category,
                         pillar=rule.pillar, severity=sev, base_severity=base, message=f.message,
                         location=f.location, remediation=rule.remediation, evidence=f.evidence, fix=f.fix,
                         source=rule.source, kb=rule.kb, escalated_by=escalated)


def load_baseline(path) -> Set[str]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {v["fingerprint"] for v in data.get("violations", [])} if isinstance(data, dict) else set(data)
