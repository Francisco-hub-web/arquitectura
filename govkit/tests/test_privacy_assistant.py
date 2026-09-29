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


class TestAssistantLauncher(unittest.TestCase):
    def test_command_layout(self):
        cmd = assistant.build_command("claude", "-x error pegado", Path("."), registered=False)
        self.assertEqual(cmd[1], "Consulta: -x error pegado")        # posicional antes de opciones variádicas
        self.assertIn("--mcp-config", cmd)
        self.assertLess(cmd.index("--mcp-config"), cmd.index("--allowedTools"))
        self.assertEqual(cmd[-2], "--allowedTools")                    # nada después que pueda tragarse
        guide = cmd[cmd.index("--append-system-prompt") + 1]
        self.assertIn("PRIVACIDAD", guide)
        self.assertNotIn("--mcp-config", assistant.build_command("claude", "hola mundo", Path("."), registered=True))
        self.assertEqual(assistant.build_command("claude", "a b", Path("."), print_mode=True, registered=True)[1], "-p")

    def test_free_text_dispatch(self):
        with TempDir() as tmp:
            log = Path(tmp) / "log.json"
            fake = Path(tmp) / "claude"
            fake.write_text(f"#!{sys.executable}\nimport sys, json\n"
                            "if sys.argv[1:3] == ['mcp', 'get']: sys.exit(0)\n"
                            f"open({str(log)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n")
            fake.chmod(0o755)
            old = os.environ.get("GOVKIT_CLAUDE")
            os.environ["GOVKIT_CLAUDE"] = str(fake)
            try:
                self.assertEqual(quiet(cli.main, ["revisa", "este", "repo"]), 0)
                self.assertEqual(quiet(cli.main, ["-p", "qué exige el gate"]), 0)
                self.assertEqual(quiet(cli.main, ["hola"]), 2)          # una palabra: probablemente un typo
            finally:
                if old is None:
                    os.environ.pop("GOVKIT_CLAUDE", None)
                else:
                    os.environ["GOVKIT_CLAUDE"] = old
            calls = [json.loads(l) for l in log.read_text().splitlines()]
            self.assertIn("revisa este repo", calls[0][0:2])
            self.assertEqual(calls[1][:2], ["-p", "qué exige el gate"])
            self.assertNotIn("--mcp-config", calls[0])                 # ya registrado → no se duplica


if __name__ == "__main__":
    unittest.main()
