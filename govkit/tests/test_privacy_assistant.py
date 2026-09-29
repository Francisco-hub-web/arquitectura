import io
import json
import os
import stat
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tests.helpers import TempDir, copy_example, git, ids, lint
from govkit import assistant, cli, fixer, privacy
from govkit.paths import TEMPLATES_DIR
from govkit.scaffold import scaffold

ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")


def run(repo, *args, stdin=None):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=ENV, input=stdin)


def quiet(fn, *a):
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return fn(*a)


class TestPrivateMode(unittest.TestCase):
    def repo_with_remote(self, tmp):
        remote = Path(tmp) / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        root = copy_example(tmp)
        (root / ".govkit.yaml").unlink()  # repo corporativo real: sin archivos de govkit versionados
        git(root, "init", "-q")
        git(root, "checkout", "-q", "-b", "main")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "feat: inicial")
        git(root, "remote", "add", "origin", str(remote))
        run(root, "push", "-q", "origin", "main")
        return root

    def test_guards_block_every_leak_path_and_chain_team_hook(self):
        with TempDir() as tmp:
            root = self.repo_with_remote(tmp)
            team = root / ".git/hooks/pre-commit"
            team.write_text("#!/bin/sh\necho team-hook > \"$(git rev-parse --git-dir)/team-ran\"\nexit 0\n")
            team.chmod(team.stat().st_mode | stat.S_IXUSR)
            info = quiet(privacy.setup, root)
            self.assertIn(".govkit.yaml", (root / ".git/info/exclude").read_text())
            self.assertTrue((info["private_dir"] / "config.yaml").exists())
            readme = root / "README.md"
            readme.write_text(readme.read_text() + "\nrevisado con govkit\n")
            run(root, "add", "README.md")
            self.assertNotEqual(run(root, "commit", "-m", "docs: readme").returncode, 0)   # contenido
            run(root, "checkout", "HEAD", "--", "README.md")
            readme.write_text(readme.read_text() + "\nforecast diario\n")
            run(root, "add", "README.md")
            self.assertNotEqual(run(root, "commit", "-m", "chore: via GovKit").returncode, 0)  # mensaje
            self.assertEqual(run(root, "commit", "-m", "docs: readme").returncode, 0)          # limpio
            self.assertTrue((root / ".git/team-ran").exists())                                   # encadenado
            (root / ".govkit.yaml").write_text("version: 1\n")
            self.assertEqual(run(root, "status", "--porcelain", ".govkit.yaml").stdout, "")     # ignorado
            run(root, "checkout", "-q", "-b", "chore/govkit-x")
            self.assertNotEqual(run(root, "push", "origin", "chore/govkit-x").returncode, 0)   # rama
            run(root, "checkout", "-q", "main")
            (root / "notas.txt").write_text("usa govkit\n")
            run(root, "add", "notas.txt")
            run(root, "commit", "-q", "--no-verify", "-m", "docs: notas")
            self.assertNotEqual(run(root, "push", "origin", "main").returncode, 0)              # contenido saltado
            self.assertTrue(any("notas.txt" in i for i in privacy.check(root)))
            run(root, "reset", "-q", "--hard", "HEAD~1")
            run(root, "branch", "-D", "chore/govkit-x")
            self.assertEqual(run(root, "push", "origin", "main").returncode, 0)
            self.assertEqual(privacy.check(root), [])

    def test_versioned_hooks_path_is_never_touched(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            git(root, "init", "-q")
            (root / ".husky").mkdir()
            (root / ".husky/pre-commit").write_text("#!/bin/sh\nnpx lint-staged\n")
            git(root, "config", "core.hooksPath", ".husky")
            info = quiet(privacy.setup, root)
            self.assertTrue(info.get("hooks_skipped"))
            self.assertEqual((root / ".husky/pre-commit").read_text(), "#!/bin/sh\nnpx lint-staged\n")
            self.assertEqual(quiet(cli.main, ["hooks", "install", str(root)]), 2)

    def test_private_config_and_baseline_live_in_git_dir(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            git(root, "init", "-q")
            (root / ".govkit.yaml").unlink()
            (root / "CHANGELOG.md").unlink()
            quiet(privacy.setup, root)
            self.assertIn("GOV-STR-006", ids(lint(root)))
            pdir = privacy.private_dir(root)
            (pdir / "config.yaml").write_text("version: 1\nrules: {disable: [GOV-STR-006]}\n")
            self.assertNotIn("GOV-STR-006", ids(lint(root)))
            (pdir / "config.yaml").write_text("version: 1\n")
            self.assertEqual(quiet(cli.main, ["baseline", str(root)]), 0)
            self.assertTrue((pdir / "baseline.json").exists())
            out = Path(tmp) / "r.json"
            quiet(cli.main, ["lint", str(root), "--format", "json", "-o", str(out)])
            report = json.loads(out.read_text())
            self.assertEqual(report["summary"]["counts"]["MEDIUM"], 0)   # baseline personal cargado solo
            self.assertGreater(report["summary"]["suppressed"]["baselined"], 0)

    def test_nothing_written_to_repo_mentions_govkit(self):
        leaks = [str(p) for p in (TEMPLATES_DIR / "data-product").rglob("*")
                 if p.is_file() and ("govkit" in p.name.lower() or "govkit" in p.read_text(errors="ignore").lower())]
        self.assertEqual(leaks, [])
        with TempDir() as tmp:
            root = scaffold("sales", "orders", "anl", "cl", tmp)
            self.assertEqual([p for p in root.rglob("*") if p.is_file() and "govkit" in p.read_text().lower()], [])

    def test_fix_never_creates_ci_or_codeowners(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            (root / "CODEOWNERS").unlink()
            (root / ".github/workflows/pr.yml").unlink()
            actions = {(a.kind, a.file) for a in fixer.plan(lint(root))}
            self.assertIn(("manual", "CODEOWNERS"), actions)
            self.assertIn(("manual", ".github/workflows/pr.yml"), actions)
            self.assertFalse(any(k == "template" and ("CODEOWNERS" in f or "workflows" in f) for k, f in actions))


FAKE_CLAUDE = """#!{py}
import sys, json
if sys.argv[1:3] == ["mcp", "get"]:
    sys.exit(0)
open({log!r}, "a").write(json.dumps(sys.argv[1:]) + "\\n")
if "-p" in sys.argv:  # imita --output-format stream-json de Claude Code
    for ev in [{{"type": "system", "subtype": "init"}},
               {{"type": "assistant", "message": {{"content": [{{"type": "tool_use", "name": "mcp__govkit__lint",
                                                                  "input": {{"path": "."}}}}]}}}},
               {{"type": "assistant", "message": {{"content": [{{"type": "text", "text": "pensando en voz alta"}}]}}}},
               {{"type": "result", "subtype": "success", "is_error": False,
                 "result": "## Falta la ficha\\n- Crea **metadata/catalog/data_product.yaml** con `govkit fix --apply`"}}]:
        print(json.dumps(ev), flush=True)
"""


FAKE_CLAUDE = """#!{py}
import sys, json
if sys.argv[1:3] == ["mcp", "get"]:
    sys.exit(0)
open({log!r}, "a").write(json.dumps(sys.argv[1:]) + "\\n")
if "-p" in sys.argv:  # imita `--output-format stream-json` de Claude Code
    for ev in [{{"type": "system", "subtype": "init"}},
               {{"type": "assistant", "message": {{"content": [{{"type": "tool_use", "name": "mcp__govkit__lint",
                                                                  "input": {{"path": "."}}}}]}}}},
               {{"type": "assistant", "message": {{"content": [{{"type": "text", "text": "pensando en voz alta"}}]}}}},
               {{"type": "result", "subtype": "success", "is_error": False,
                 "result": "## Falta la ficha\\n- **GOV-DPD-001**: crea la ficha (`govkit fix --apply`); Definition of Ready KB04.R5"}}]:
        print(json.dumps(ev), flush=True)
"""


class _TTY(io.StringIO):
    def isatty(self):
        return True


class TestAssistantLauncher(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir().__enter__()
        self.log = Path(self.tmp) / "log.json"
        fake = Path(self.tmp) / "claude"
        fake.write_text(FAKE_CLAUDE.format(py=sys.executable, log=str(self.log)))
        fake.chmod(0o755)
        self.env = {k: os.environ.get(k) for k in ("GOVKIT_CLAUDE", "GOVKIT_NOTES_DIR")}
        os.environ["GOVKIT_CLAUDE"] = str(fake)
        os.environ["GOVKIT_NOTES_DIR"] = str(Path(self.tmp) / "notas")

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()]

    def main(self, argv):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            rc = cli.main(argv)
        return rc, out.getvalue()

    def test_command_layout(self):
        direct = assistant.build_command("claude", "-x error pegado", Path("."), registered=False)
        self.assertEqual(direct[1:3], ["-p", "Consulta: -x error pegado"])  # texto antes de opciones variádicas
        self.assertIn("--mcp-config", direct)
        self.assertEqual(direct[direct.index("--output-format") + 1], "stream-json")
        self.assertEqual(direct[-2], "--allowedTools")                         # nada después que pueda tragarse
        self.assertIn("Read", direct[-1])
        self.assertNotIn("notes_save", direct[-1])                             # en -p la nota la guarda govkit
        guide = direct[direct.index("--append-system-prompt") + 1]
        self.assertIn("PRIVACIDAD", guide)
        self.assertIn("RESPUESTA DIRECTA", guide)
        inter = assistant.build_command("claude", "hola mundo", Path("."), interactive=True, registered=True)
        self.assertEqual(inter[1], "hola mundo")
        self.assertNotIn("--output-format", inter)
        self.assertIn("mcp__govkit__notes_save", inter[-1])
        self.assertIn("Fuentes para verificar", inter[inter.index("--append-system-prompt") + 1])

    def test_interactive_is_default(self):
        from unittest import mock
        with mock.patch("sys.stdin", _TTY()):
            rc, _ = self.main(["revisa", "este", "repo"])
            self.assertEqual(rc, 0)
            self.assertEqual(self.main(["-p"])[0], 2)                         # flag sin consulta
        self.assertEqual(self.calls()[0][0], "revisa este repo")               # sin -p → sesión interactiva
        self.assertEqual(self.main(["hola"])[0], 2)                             # una palabra: probablemente un typo
        for argv in (["--version"], ["-h"]):                                   # opciones globales no lanzan Claude
            with self.assertRaises(SystemExit):
                self.main(argv)
        self.assertEqual(len(self.calls()), 1)

    def test_answer_only_with_verifiable_sources_and_notes(self):
        rc, out = self.main(["-p", "qué le falta a mi data product"])
        self.assertEqual(rc, 0)
        self.assertIn("Falta la ficha", out)
        self.assertIn("Fuentes para verificar", out)
        self.assertIn("06-data-product-definition.md §26", out)                # KB04.R5 → documento y sección
        self.assertIn("01-data-principles.md §3", out)                         # GOV-DPD-001 → fuente del catálogo
        self.assertNotIn("pensando en voz alta", out)                          # sin narración intermedia
        self.assertNotIn('{"type"', out)                                       # sin JSON crudo
        self.assertEqual(self.calls()[0][:2], ["-p", "qué le falta a mi data product"])
        from govkit import notes
        self.assertIn("Fuentes para verificar", str(notes.get(1)["body"]))
        rc, _ = self.main(["-p", "--sumar", "1", "y qué le pido a cada uno"])
        self.assertEqual(rc, 0)
        self.assertIn('<nota id="1"', self.calls()[1][1])                      # la nota viaja como contexto
        self.assertIn("y qué le pido a cada uno", str(notes.get(1)["body"]))    # y se le suma la respuesta
        self.assertEqual(len(notes.all_notes()), 1)
        self.assertIn("#1", self.main(["notas"])[1])
        self.assertIn("Falta la ficha", self.main(["notas", "ver", "1"])[1])
        self.assertEqual(self.main(["-p", "--nota", "9", "algo nuevo aquí"])[0], 2)  # nota inexistente

    def test_mcp_sources_and_notes(self):
        from govkit import mcpserver
        src = mcpserver.t_sources(["KB04.R5", "GOV-IAM-004"])
        self.assertIn("06-data-product-definition.md §26", src["markdown"])
        self.assertIn("Regla 2", src["markdown"])
        saved = mcpserver.t_notes_save("preguntas al owner", "1. ¿Quién es el business owner?")
        mcpserver.t_notes_append(saved["id"], "arquitecto", "2. ¿Batch o streaming?")
        self.assertIn("Batch", mcpserver.t_notes_get(saved["id"])["contenido"])
        self.assertEqual(mcpserver.t_notes_list("owner")[0]["id"], saved["id"])


if __name__ == "__main__":
    unittest.main()
