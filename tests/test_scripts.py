"""Tests for the skill's Python scripts and SKILL.md. Standard library only.

Run from the repository root:
    python3 -m unittest discover -s tests -v
"""
import copy
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "project-status-board"
SCRIPTS = SKILL / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import init_dashboard  # noqa: E402
import set_progress  # noqa: E402
import validate_status as vs  # noqa: E402


def make_data(shape, progress=0):
    """Build a project from a shape like [[3, 1], [2]] -> goals of stages of N milestones."""
    goals = []
    for gi, stages in enumerate(shape, 1):
        goal = {"id": f"g{gi}", "name": f"Goal {gi}", "stages": []}
        for si, count in enumerate(stages, 1):
            goal["stages"].append({
                "id": f"g{gi}-s{si}", "name": f"Stage {si}",
                "milestones": [{"id": f"g{gi}-s{si}-m{mi}", "name": f"M{mi}", "progress": progress}
                               for mi in range(1, count + 1)],
            })
        goals.append(goal)
    return {"schemaVersion": 1,
            "project": {"name": "Test", "updatedAt": "2026-09-26T10:00:00+00:00"},
            "goals": goals}


def run(fn, argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = fn(argv)
    return code, out.getvalue(), err.getvalue()


class ProgressCalculation(unittest.TestCase):
    def test_single_goal_single_milestone(self):
        data = make_data([[1]], progress=0)
        self.assertEqual(vs.progress(data), 0)
        self.assertEqual(vs.status(vs.progress(data)), "Not Started")
        data["goals"][0]["stages"][0]["milestones"][0]["progress"] = 100
        self.assertEqual(vs.status(vs.progress(data)), "Completed")

    def test_partial_progress_and_goal_weighting(self):
        # Goal = average of ALL its milestones, not of its stages.
        data = make_data([[1, 3]])
        ms1 = data["goals"][0]["stages"][0]["milestones"]
        ms2 = data["goals"][0]["stages"][1]["milestones"]
        ms1[0]["progress"] = 100
        for m in ms2:
            m["progress"] = 0
        goal = data["goals"][0]
        self.assertEqual(vs.progress(goal["stages"][0]), 100)
        self.assertEqual(vs.progress(goal["stages"][1]), 0)
        self.assertEqual(vs.progress(goal), 25)          # 100 / 4, not (100 + 0) / 2
        self.assertEqual(vs.status(vs.progress(goal)), "In Progress")

    def test_project_averages_all_milestones(self):
        data = make_data([[2], [1, 1, 4], [5, 5, 5, 5]])
        values = [10, 20, 30, 40, 50, 60, 70] + [0] * 21
        it = iter(values)
        for g in data["goals"]:
            for s in g["stages"]:
                for m in s["milestones"]:
                    m["progress"] = next(it)
        self.assertAlmostEqual(vs.progress(data), sum(values) / len(values))

    def test_never_rounds_to_false_completion(self):
        data = make_data([[3]], progress=100)
        data["goals"][0]["stages"][0]["milestones"][2]["progress"] = 99
        p = vs.progress(data)                              # 99.67
        self.assertEqual(vs.display_percent(p), 99)
        self.assertEqual(vs.status(p), "In Progress")
        self.assertEqual(vs.display_percent(0.4), 1)

    def test_original_sample_numbers(self):
        data = json.loads((FIXTURES / "original-sample.json").read_text())
        self.assertEqual(vs.display_percent(vs.progress(data)), 38)
        self.assertEqual([vs.display_percent(vs.progress(g)) for g in data["goals"]], [37, 80, 0])  # goal 1 is exactly 36.5 -> half-up


class Validation(unittest.TestCase):
    def assertValid(self, data):
        errors, _ = vs.check(data)
        self.assertEqual(errors, [])

    def assertError(self, data, fragment):
        errors, _ = vs.check(data)
        self.assertTrue(any(fragment in e for e in errors), f"{fragment!r} not in {errors}")

    def test_varied_shapes_are_valid(self):
        for shape in ([[1]], [[5, 5, 5, 5], [5], [5]], [[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]],
                      [[2]] * 9, [[40]]):
            self.assertValid(make_data(shape, progress=50))

    def test_fixtures_and_template(self):
        self.assertValid(json.loads((FIXTURES / "original-sample.json").read_text()))
        self.assertValid(json.loads((REPO / "examples/demo/project-status.json").read_text()))
        template = json.loads((SKILL / "assets/project-status.template.json").read_text())
        errors, warnings = vs.check(template)
        self.assertEqual(errors, [])
        self.assertTrue(any("placeholder" in w for w in warnings))

    def test_missing_required_fields(self):
        data = make_data([[1]])
        del data["project"]["name"]
        self.assertError(data, "missing required field 'name'")
        data = make_data([[1]])
        del data["project"]["updatedAt"]
        self.assertError(data, "'updatedAt'")
        data = make_data([[1]])
        del data["goals"][0]["stages"][0]["milestones"][0]["progress"]
        self.assertError(data, "'progress'")
        self.assertError({"goals": []}, "missing required object 'project'")
        self.assertError({"project": {"name": "x", "updatedAt": "2026-01-01"}}, "missing required list 'goals'")

    def test_duplicate_ids_across_levels(self):
        data = make_data([[2], [1]])
        data["goals"][1]["stages"][0]["milestones"][0]["id"] = "g1-s1-m1"
        self.assertError(data, "duplicate id 'g1-s1-m1'")
        data = make_data([[1]])
        data["goals"][0]["stages"][0]["id"] = "g1"
        self.assertError(data, "duplicate id 'g1'")

    def test_invalid_progress_values(self):
        for bad in (-1, 101, "50", True, None, [50]):
            data = make_data([[1]])
            data["goals"][0]["stages"][0]["milestones"][0]["progress"] = bad
            errors, _ = vs.check(data)
            self.assertTrue(errors, f"progress={bad!r} should be rejected")
        data = make_data([[1]])
        data["goals"][0]["stages"][0]["milestones"][0]["progress"] = 33.5
        errors, warnings = vs.check(data)
        self.assertEqual(errors, [])
        self.assertTrue(any("fractional" in w for w in warnings))

    def test_empty_levels(self):
        data = make_data([[1]])
        data["goals"][0]["stages"] = []
        self.assertError(data, "has no stages")
        data = make_data([[1]])
        data["goals"][0]["stages"][0]["milestones"] = []
        self.assertError(data, "has no milestones")
        data = make_data([[1]])
        data["goals"] = []
        self.assertError(data, "'goals' is empty")

    def test_bad_types_and_timestamp(self):
        data = make_data([[1]])
        data["project"]["updatedAt"] = "yesterday"
        self.assertError(data, "ISO 8601")
        data = make_data([[1]])
        data["goals"][0]["expanded"] = "yes"
        self.assertError(data, "'expanded' must be true or false")
        data = make_data([[1]])
        data["project"]["autoRefreshSeconds"] = -5
        self.assertError(data, "autoRefreshSeconds")
        data = make_data([[1]])
        data["goals"] = {"id": "x"}
        self.assertError(data, "'goals' must be a list")
        self.assertError([], "top level must be a JSON object")
        data = make_data([[1]])
        data["project"]["updatedAt"] = "2026-09-26T10:00:00Z"
        self.assertValid(data)

    def test_unknown_field_is_warning(self):
        data = make_data([[1]])
        data["goals"][0]["stages"][0]["milestones"][0]["progres"] = 5
        errors, warnings = vs.check(data)
        self.assertEqual(errors, [])
        self.assertTrue(any("unknown field 'progres'" in w for w in warnings))

    def test_cli_malformed_json_and_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "project-status.json"
            bad.write_text('{\n  "project": {"name": "x",}\n}')
            code, out, _ = run(vs.main, [str(bad)])
            self.assertEqual(code, 1)
            self.assertIn("malformed JSON at line 2", out)
            code, _, err = run(vs.main, [str(Path(tmp) / "nope.json")])
            self.assertEqual(code, 2)
            self.assertIn("not found", err)

    def test_cli_accepts_folder_and_prints_summary(self):
        code, out, _ = run(vs.main, [str(REPO / "examples/demo")])
        self.assertEqual(code, 0)
        self.assertIn("Inventory Platform: 37% In Progress (6/19 milestones completed)", out)


class InitDashboard(unittest.TestCase):
    def test_init_creates_files_and_is_non_destructive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "my-app"
            root.mkdir()
            (root / "README.md").write_text("unrelated")
            code, out, _ = run(init_dashboard.main, ["--root", str(root), "--subtitle", "Hello"])
            self.assertEqual(code, 0, out)
            status = root / "project-status" / "project-status.json"
            html = root / "project-status" / "index.html"
            self.assertTrue(html.is_file())
            data = json.loads(status.read_text())
            self.assertEqual(data["project"]["name"], "my-app")
            self.assertEqual(data["project"]["subtitle"], "Hello")
            self.assertEqual(vs.check(data)[0], [])

            # Existing JSON is never replaced, even with a different --name.
            data["goals"][0]["name"] = "Real goal"
            status.write_text(json.dumps(data))
            before = status.read_bytes()
            code, out, _ = run(init_dashboard.main, ["--root", str(root), "--name", "Other"])
            self.assertEqual(code, 0)
            self.assertEqual(status.read_bytes(), before)
            self.assertIn("kept existing", out)
            self.assertIn("already up to date", out)

            # A customised index.html is kept unless --upgrade-html, which backs it up.
            html.write_text("<!-- custom -->")
            run(init_dashboard.main, ["--root", str(root)])
            self.assertEqual(html.read_text(), "<!-- custom -->")
            code, out, _ = run(init_dashboard.main, ["--root", str(root), "--upgrade-html"])
            self.assertIn("upgraded", out)
            backups = list(html.parent.glob("index.html.bak-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), "<!-- custom -->")
            self.assertEqual(html.read_bytes(), (SKILL / "assets/index.html").read_bytes())

            self.assertEqual((root / "README.md").read_text(), "unrelated")
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["README.md", "project-status"])

    def test_bad_root(self):
        code, _, err = run(init_dashboard.main, ["--root", "/definitely/not/here"])
        self.assertEqual(code, 1)
        self.assertIn("not a directory", err)


class SetProgress(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "project-status.json"
        self.data = make_data([[2, 1]])
        self.path.write_text(json.dumps(self.data, indent=2))

    def tearDown(self):
        self.tmp.cleanup()

    def load(self):
        return json.loads(self.path.read_text())

    def test_sets_progress_evidence_and_timestamp(self):
        code, out, _ = run(set_progress.main, ["g1-s1-m1=100", "g1-s1-m2=40", "--evidence", "tests pass",
                                               "--file", str(self.path)])
        self.assertEqual(code, 0)
        data = self.load()
        ms = data["goals"][0]["stages"][0]["milestones"]
        self.assertEqual([m["progress"] for m in ms], [100, 40])
        self.assertEqual(ms[0]["evidence"], "tests pass")
        self.assertNotEqual(data["project"]["updatedAt"], self.data["project"]["updatedAt"])
        self.assertIsNotNone(vs._parse_time(data["project"]["updatedAt"]))
        self.assertIn("g1-s1-m1: 0% -> 100%", out)

    def test_rejects_bad_input_without_writing(self):
        before = self.path.read_bytes()
        for argv in (["nope=10"], ["g1=50"], ["g1-s1=50"], ["g1-s1-m1=150"], ["g1-s1-m1=abc"],
                     ["g1-s1-m1"], ["g1-s1-m1=10", "missing=20"]):
            code, _, err = run(set_progress.main, argv + ["--file", str(self.path)])
            self.assertEqual(code, 1, argv)
            self.assertIn("Nothing was written", err)
        self.assertEqual(self.path.read_bytes(), before)

    def test_touch_and_invalid_file(self):
        code, _, _ = run(set_progress.main, ["--touch", "--file", str(self.path)])
        self.assertEqual(code, 0)
        self.assertEqual(self.load()["goals"], self.data["goals"])
        broken = copy.deepcopy(self.data)
        broken["goals"][0]["stages"] = []
        self.path.write_text(json.dumps(broken))
        before = self.path.read_bytes()
        code, _, err = run(set_progress.main, ["--touch", "--file", str(self.path)])
        self.assertEqual(code, 1)
        self.assertIn("already invalid", err)
        self.assertEqual(self.path.read_bytes(), before)


class SkillFile(unittest.TestCase):
    """Checks the Agent Skills spec rules (agentskills.io/specification)."""

    def setUp(self):
        text = (SKILL / "SKILL.md").read_text()
        match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        self.assertIsNotNone(match, "SKILL.md must start with YAML frontmatter")
        self.front, self.body = match.group(1), match.group(2)
        self.fields = dict(re.findall(r"^([a-z-]+):\s*(.*)$", self.front, re.M))

    def test_name(self):
        name = self.fields["name"]
        self.assertEqual(name, SKILL.name, "name must match the folder name")
        self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(name), 64)

    def test_description(self):
        desc = self.fields["description"]
        self.assertTrue(0 < len(desc) <= 1024, len(desc))
        self.assertIn("Use when", desc)

    def test_only_portable_fields(self):
        allowed = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
        top_level = set(re.findall(r"^([a-z-]+):", self.front, re.M))
        self.assertLessEqual(top_level, allowed)
        self.assertLessEqual(len(self.fields.get("compatibility", "")), 500)

    def test_body_size_and_links(self):
        self.assertLess(len(self.body.splitlines()), 500)
        for link in re.findall(r"\]\(([^)#]+)", self.body):
            if not link.startswith("http"):
                self.assertTrue((SKILL / link).exists(), f"broken link {link}")

    def test_scripts_run_with_help(self):
        for script in SCRIPTS.glob("*.py"):
            result = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, script.name)


if __name__ == "__main__":
    unittest.main()
