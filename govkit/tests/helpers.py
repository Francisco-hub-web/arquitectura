"""Utilidades de prueba: copia el Data Product de referencia a un directorio temporal y lo muta."""
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "lib"))

from govkit.engine import Engine, load_catalog  # noqa: E402
from govkit.paths import yaml  # noqa: E402
from govkit.repo import RepoContext  # noqa: E402

EXAMPLE = KIT / "examples" / "sales-transactions-anl-dp-cl"
FIXTURES = KIT / "tests" / "fixtures"
CATALOG = load_catalog()
TODAY = _dt.date(2026, 9, 25)


def copy_example(tmp: str) -> Path:
    dest = Path(tmp) / "sales-transactions-anl-dp-cl"
    shutil.copytree(EXAMPLE, dest)
    return dest


def lint(path, packs=("dp",), stage=None, base=None, **kw):
    ctx = RepoContext(path, CATALOG, stage_override=stage, base_ref=base, today=kw.pop("today", TODAY))
    return Engine(ctx, CATALOG, packs=packs, **kw).run()


def ids(res, counting=True):
    return {v.rule_id for v in res.violations if (v.counts or not counting)}


def edit_yaml(path: Path, fn):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def edit_json(path: Path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def git(repo: Path, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


class TempDir:
    def __enter__(self):
        self.tmp = tempfile.mkdtemp(prefix="govkit-test-")
        return self.tmp

    def __exit__(self, *a):
        shutil.rmtree(self.tmp, ignore_errors=True)
