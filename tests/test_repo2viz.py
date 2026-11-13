"""Unit-Tests fuer die reine Logik von repo2viz (nur Standardbibliothek).

Laufen mit `python -m unittest discover -s tests` oder `python -m pytest tests`.
Kein Netzwerk: die Integrations-Tests bauen ein Wegwerf-Repo im Temp-Verzeichnis.
"""
import datetime as dt
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import repo2viz as r  # noqa: E402

FLD, REC = r.FLD, r.REC


def rec(iso, name, email, subject, *numstat, sha="abc"):
    """Baut einen git-log-Datensatz im Format von git_log()."""
    head = f"{REC}{sha}{FLD}{iso}{FLD}{name}{FLD}{email}{FLD}{subject}"
    return "\n".join([head, *numstat]) + "\n"


def day(iso_date):
    return dt.date.fromisoformat(iso_date).toordinal() - r.EPOCH


class ProviderTests(unittest.TestCase):
    def test_detect_provider(self):
        self.assertEqual(r.detect_provider("https://github.com/a/b"), "github")
        self.assertEqual(r.detect_provider("https://GitHub.com/a/b"), "github")
        self.assertEqual(r.detect_provider("https://dev.azure.com/o/p/_git/r"), "azure")
        self.assertEqual(r.detect_provider("https://o.visualstudio.com/p/_git/r"), "azure")
        # Self-hosted Azure DevOps Server nur am /_git/-Segment erkennbar
        self.assertEqual(r.detect_provider("https://tfs.firma.local/tfs/c/p/_git/r"), "azure")
        self.assertEqual(r.detect_provider("https://gitlab.com/a/b"), "generic")

    def test_resolve_token_prefers_explicit_then_env_order(self):
        env = {"GH_TOKEN": "gh", "GITHUB_TOKEN": "github", "GIT_TOKEN": "generic"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(r.resolve_token("github", "explizit"), "explizit")
            self.assertEqual(r.resolve_token("github", None), "github")
            # Fuer Azure sind die GitHub-Variablen tabu, nur GIT_TOKEN greift
            self.assertEqual(r.resolve_token("azure", None), "generic")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(r.resolve_token("generic", None))

    def test_build_clone_url(self):
        self.assertEqual(r.build_clone_url("https://github.com/a/b", "github", None),
                         "https://github.com/a/b")
        # Sonderzeichen im Token werden kodiert, damit die URL nicht zerfaellt
        self.assertEqual(r.build_clone_url("https://github.com/a/b.git", "github", "t:k@/x"),
                         "https://t%3Ak%40%2Fx@github.com/a/b.git")
        self.assertEqual(r.build_clone_url("https://dev.azure.com:8443/o/p/_git/r", "azure", "pat"),
                         "https://pat:pat@dev.azure.com:8443/o/p/_git/r")
        # Bestehende Zugangsdaten werden ersetzt, nicht gestapelt
        self.assertEqual(r.build_clone_url("https://alt@github.com/a/b", "github", "neu"),
                         "https://neu@github.com/a/b")
        # SSH: Token wird nie eingebettet
        self.assertEqual(r.build_clone_url("ssh://git@github.com/a/b", "github", "t"),
                         "ssh://git@github.com/a/b")

    def test_repo_display_name(self):
        self.assertEqual(r.repo_display_name("https://github.com/pepperonas/repo2viz.git"),
                         "pepperonas/repo2viz")
        self.assertEqual(r.repo_display_name("https://dev.azure.com/o/proj/_git/repo"), "proj/repo")
        self.assertEqual(r.repo_display_name("https://dev.azure.com/o/same/_git/same"), "same")
        self.assertEqual(r.repo_display_name("https://host/"), "repository")

    def test_ado_api_base(self):
        self.assertEqual(r.ado_api_base("https://dev.azure.com/o/p/_git/r"),
                         "https://dev.azure.com/o/p")
        self.assertEqual(r.ado_api_base("https://srv:8080/tfs/coll/p/_git/r"),
                         "https://srv:8080/tfs/coll/p")
        self.assertIsNone(r.ado_api_base("https://github.com/a/b"))
        self.assertIsNone(r.ado_api_base("https://host/_git/r"))


class ClassificationTests(unittest.TestCase):
    def test_extract_wi_ids(self):
        self.assertEqual(r.extract_wi_ids("fix #12 und AB#7, nochmal #12"), [12, 7])
        self.assertEqual(r.extract_wi_ids("ab#5"), [5])
        # zu lang, Hexfarbe, Ziffern mitten im Wort: keine IDs
        self.assertEqual(r.extract_wi_ids("#12345678 color #12ab"), [])
        self.assertEqual(r.extract_wi_ids(None), [])

    def test_classify_commit(self):
        cats = r.COMMIT_CATS
        self.assertEqual(cats[r.classify_commit("feat: x")], "feat")
        self.assertEqual(cats[r.classify_commit("Fix(ui)!: x")], "fix")
        self.assertEqual(cats[r.classify_commit("bugfix: x")], "fix")      # Alias
        self.assertEqual(cats[r.classify_commit("docs:kein Leerzeichen")], "sonstige")
        self.assertEqual(cats[r.classify_commit("wip: x")], "sonstige")    # unbekannter Typ
        self.assertEqual(cats[r.classify_commit("")], "sonstige")

    def test_paths(self):
        self.assertEqual(r._top_dir("README.md"), "(root)")
        self.assertEqual(r._top_dir("src/a/b.py"), "src")
        self.assertIsNone(r._module_of("setup.py"))
        self.assertEqual(r._module_of("src/a.py"), "src")
        self.assertEqual(r._module_of("src/auth/x/y.py"), "src/auth")

    def test_is_test_path(self):
        for p in ("tests/a.py", "src/__tests__/x.js", "a.test.ts", "a_spec.rb",
                  "FooTest.java", "pkg/foo_test.go", "spec/x.rb"):
            self.assertTrue(r.is_test_path(p), p)
        for p in ("src/latest.py", "contest/x.py", "attestation.md", "src/app.py"):
            self.assertFalse(r.is_test_path(p), p)

    def test_month_key(self):
        self.assertEqual(r._month_key(day("2026-02-28")), day("2026-02-01"))
        self.assertEqual(r._month_key(day("2026-03-01")), day("2026-03-01"))

    def test_default_output_name(self):
        self.assertEqual(r.default_output_name("pepperonas/repo2viz"),
                         "pepperonas-repo2viz-activity.html")
        self.assertEqual(r.default_output_name("a b/../c"), "a-b-..-c-activity.html")


class ParseLogTests(unittest.TestCase):
    def test_basic_aggregation(self):
        raw = (
            rec("2026-03-02T10:00:00+01:00", "Ann", "ANN@x.de", "feat: neu #4",
                "10\t2\tsrc/a.py", "3\t0\ttests/test_a.py")
            + rec("2026-03-01T23:30:00-05:00", "Ann B", "ann@x.de", "chore: x",
                  "-\t-\tlogo.png")
        )
        d = r.parse_log(raw)
        # E-Mail ist Identitaet, Gross-/Kleinschreibung egal
        self.assertEqual(d["authors"], ["Ann"])
        c0, c1 = d["commits"]
        self.assertEqual(c0[:7], [day("2026-03-02"), 0, 10, 0, 13, 2, r.COMMIT_CATS.index("feat")])
        self.assertEqual(c0[7], [4])
        # Autor-lokale Zeit: 23:30 am 1.3. bleibt der 1.3., nicht UTC-Folgetag
        self.assertEqual(c1[0], day("2026-03-01"))
        self.assertEqual(c1[2], 23)
        # Binaerdatei zaehlt als 0/0
        self.assertEqual(c1[4:6], [0, 0])
        self.assertEqual(d["_withWI"], 1)
        self.assertEqual(d["_conventional"], 2)
        self.assertEqual(d["_totalCommits"], 2)
        tests_churn = sum(t[1] for t in d["quality"]["testSeries"])
        self.assertEqual(tests_churn, 3)

    def test_skips_broken_records(self):
        raw = (REC + "nur-ein-feld\n" + REC + f"sha{FLD}kein-datum{FLD}n{FLD}e{FLD}s\n"
               + rec("2026-01-01T00:00:00+00:00", "x", "x@x", "s", "1\t1\ta"))
        self.assertEqual(len(r.parse_log(raw)["commits"]), 1)
        self.assertEqual(r.parse_log("")["commits"], [])

    def test_rename_notation_resolves_to_target(self):
        raw = rec("2026-01-01T00:00:00+00:00", "x", "x@x", "s",
                  "1\t0\tsrc/{alt => neu}/f.py",
                  "1\t0\tsrc/{sub => }/g.py",
                  "1\t0\t{ => lib}/h.py",
                  "1\t0\talt.txt => neu.txt")
        files = {f[0] for f in r.parse_log(raw)["topFiles"]}
        self.assertEqual(files, {"src/neu/f.py", "src/g.py", "lib/h.py", "neu.txt"})

    def test_hotspots_and_coupling(self):
        raw = "".join(
            rec(f"2026-01-0{i}T12:00:00+00:00", "x", "x@x", "s",
                "1\t1\tsrc/a/x.py", "1\t1\tlib/b/y.py")
            for i in range(1, 4)
        )
        d = r.parse_log(raw)
        self.assertEqual(d["coupling"], [["lib/b/y.py", "src/a/x.py", 3]])
        self.assertEqual({h[0] for h in d["hotspots"]}, {"src/a/x.py", "lib/b/y.py"})
        self.assertEqual(d["architecture"]["crossRate"], 100.0)
        self.assertEqual(d["architecture"]["modPairs"], [["lib/b", "src/a", 3]])

    def test_rework_window(self):
        # git log ist neueste zuerst; feat am 1.1., fix 10 Tage spaeter -> Rework.
        # Ein zweites feat, dessen Fix erst nach dem Fenster kommt, zaehlt nicht.
        raw = (
            rec("2026-03-01T12:00:00+00:00", "x", "x@x", "fix: b", "1\t1\tb.py")
            + rec("2026-01-11T12:00:00+00:00", "x", "x@x", "fix: a", "1\t1\ta.py")
            + rec("2026-01-01T12:00:00+00:00", "x", "x@x", "feat: a", "1\t1\ta.py")
            + rec("2026-01-02T12:00:00+00:00", "x", "x@x", "feat: b", "1\t1\tb.py")
        )
        q = r.parse_log(raw)["quality"]
        self.assertEqual(q["reworkRate"], 50.0)

    def test_orphans(self):
        raw = (rec("2026-12-31T12:00:00+00:00", "aktiv", "a@x", "s", "1\t0\tneu.py")
               + rec("2026-01-01T12:00:00+00:00", "weg", "w@x", "s", "5\t0\talt.py"))
        q = r.parse_log(raw)["quality"]
        self.assertEqual(q["orphanCount"], 1)
        self.assertEqual(q["orphans"][0][0], "alt.py")
        self.assertEqual(q["orphans"][0][2], "weg")


class BuildPoTests(unittest.TestCase):
    def test_classes_and_epic_resolution(self):
        raw = (rec("2026-01-02T12:00:00+00:00", "x", "x@x", "chore: #1", "1\t0\ta")
               + rec("2026-01-01T12:00:00+00:00", "x", "x@x", "docs: ohne Ref", "1\t0\tb"))
        data = r.parse_log(raw)
        meta = {
            1: {"type": "Bug", "state": "Done", "area": "Web", "parent": 2},
            2: {"type": "Feature", "parent": 3},
            3: {"type": "Epic", "title": "Grosses Ding"},
        }
        po = r.build_po(data, meta, "azure")
        # Work-Item-Typ schlaegt Commit-Kategorie, sonst Fallback ueber die Kategorie
        self.assertEqual(data["commits"][0][8], r.PO_CLASSES.index("Bug"))
        self.assertEqual(data["commits"][1][8], r.PO_CLASSES.index("Doku"))
        self.assertEqual(po["epics"], ["Grosses Ding"])
        self.assertEqual(po["items"][0][11], 1)          # Done = abgeschlossen
        self.assertEqual(po["areaAgg"][0][4], 1)         # Bug-Commits je Area
        self.assertEqual(po["refLabel"], "Work Item")

    def test_epic_cycle_terminates(self):
        raw = rec("2026-01-01T12:00:00+00:00", "x", "x@x", "s #1", "1\t0\ta")
        meta = {1: {"type": "Task", "parent": 2}, 2: {"type": "Feature", "parent": 1}}
        po = r.build_po(r.parse_log(raw), meta, "github")
        self.assertEqual(po["epics"], [])
        self.assertEqual(po["refLabel"], "Issue")


@unittest.skipUnless(shutil.which("git"), "git nicht installiert")
class GitIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="repo2viz-test-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.git("init", "-q")

    def git(self, *args, date="2026-01-01T12:00:00+00:00"):
        env = dict(os.environ, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date,
                   GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@t", *args],
                       cwd=self.tmp, env=env, check=True, capture_output=True)

    def write(self, path, text):
        full = os.path.join(self.tmp, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write(text)

    def test_log_and_tree(self):
        self.write("src/sub/f.py", "a\nb\n")
        self.write("README.md", "x\n")
        self.git("add", ".")
        self.git("commit", "-qm", "feat: start")
        self.git("tag", "v1")
        self.git("mv", "src/sub/f.py", "src/f.py", date="2026-01-05T12:00:00+00:00")
        self.git("commit", "-qm", "refactor: flacher", date="2026-01-05T12:00:00+00:00")

        data = r.parse_log(r.git_log(self.tmp))
        self.assertEqual(len(data["commits"]), 2)
        files = {f[0] for f in data["topFiles"]}
        self.assertIn("src/f.py", files)
        self.assertNotIn("src//f.py", files)

        tree = r.git_tree_sizes(self.tmp)
        self.assertEqual(tree["totalFiles"], 2)
        self.assertEqual(tree["totalBytes"], 6)
        self.assertEqual(tree["largest"][0], ["src/f.py", 4])
        self.assertEqual([t[0] for t in r.git_tags(self.tmp)], ["v1"])

    def test_empty_repo(self):
        self.assertIsNone(r.git_tree_sizes(self.tmp))
        self.assertEqual(r.git_tags(self.tmp), [])


if __name__ == "__main__":
    unittest.main()
