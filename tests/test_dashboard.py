"""Browser tests for assets/index.html (rendering, calculations, expand/collapse, refresh).

Optional: needs Playwright and a local Chrome. Skipped automatically otherwise.
    uv venv .venv && uv pip install playwright     # or: pip install playwright
    .venv/bin/python -m unittest tests.test_dashboard -v
"""
import functools
import json
import shutil
import tempfile
import threading
import time
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

REPO = Path(__file__).resolve().parent.parent
HTML = REPO / "skills" / "project-status-board" / "assets" / "index.html"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def project(goals, **extra):
    return {"schemaVersion": 1,
            "project": {"name": "Browser Test", "updatedAt": "2026-09-26T10:00:00Z", **extra},
            "goals": goals}


def goal(gid, *stages, **kw):
    return {"id": gid, "name": gid.title(), "stages": list(stages), **kw}


def stage(sid, *progress, **kw):
    return {"id": sid, "name": sid.title(), "milestones": [
        {"id": f"{sid}-m{i}", "name": f"{sid} milestone {i}", "progress": p} for i, p in enumerate(progress, 1)
    ], **kw}


@unittest.skipIf(sync_playwright is None, "playwright not installed")
class Dashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        shutil.copyfile(HTML, cls.dir / "index.html")
        handler = functools.partial(QuietHandler, directory=str(cls.dir))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}/"
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch(channel="chrome")
        except Exception:
            cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.dir)

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1400, "height": 900})
        self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.errors, [], "JavaScript errors on the page")

    # helpers -------------------------------------------------------------
    def write(self, data, name="project-status.json"):
        path = self.dir / name
        path.write_text(data if isinstance(data, str) else json.dumps(data))
        return path

    def open(self, data=None, query=""):
        if data is not None:
            self.write(data)
        self.page.goto(self.base + query)
        self.page.wait_for_selector("#rows .row, #notice:not(.hidden)")

    def text(self, sel):
        return self.page.locator(sel).inner_text().strip()

    def row(self, item_id):
        return self.page.locator(f'.row[data-id="{item_id}"]')

    def visible_ids(self, kind):
        return self.page.eval_on_selector_all(
            f".{kind}-row:not(.hidden)", "els => els.map(e => e.dataset.id)")

    def row_info(self, item_id):
        r = self.row(item_id)
        return r.locator(".progress-number").inner_text(), r.locator(".state").inner_text()

    # tests ---------------------------------------------------------------
    def test_original_sample_renders_same_numbers(self):
        self.open(json.loads((FIXTURES / "original-sample.json").read_text()))
        self.assertEqual(self.text("#projectName"), "Project Alpha")
        self.assertEqual(self.text("#overallPercent"), "38%")
        self.assertEqual(self.text("#overallCopy"), "11 of 30 milestones completed")
        self.assertEqual(self.row_info("goal-1"), ("37%", "In Progress"))
        self.assertEqual(self.row_info("goal-2"), ("80%", "In Progress"))
        self.assertEqual(self.row_info("goal-3"), ("0%", "Not Started"))
        self.assertEqual(self.row_info("g1-s1"), ("100%", "Completed"))
        self.assertEqual(self.row_info("g1-s2"), ("46%", "In Progress"))
        # explicit "expanded" flags in the JSON are honoured
        self.assertEqual(self.visible_ids("stage"), ["g1-s1", "g1-s2", "g1-s3", "g1-s4"])
        self.assertEqual(len(self.visible_ids("milestone")), 10)
        self.assertEqual(self.page.title(), "Project Alpha · Project Status")

    def test_single_goal_completed(self):
        self.open(project([goal("only", stage("only-s", 100))]))
        self.assertEqual(self.text("#overallPercent"), "100%")
        self.assertEqual(self.text("#overallState"), "Completed")
        self.assertIn("completed", self.page.get_attribute("#projectStateTop", "class"))
        self.assertEqual(self.row_info("only"), ("100%", "Completed"))
        self.assertEqual(self.visible_ids("stage"), [])      # completed goal starts collapsed

    def test_all_zero_starts_collapsed(self):
        self.open(project([goal("a", stage("a1", 0, 0)), goal("b", stage("b1", 0))]))
        self.assertEqual(self.text("#overallPercent"), "0%")
        self.assertEqual(self.text("#overallState"), "Not Started")
        self.assertEqual(self.visible_ids("goal"), ["a", "b"])
        self.assertEqual(self.visible_ids("stage"), [])

    def test_no_false_completion_from_rounding(self):
        self.open(project([goal("g", stage("s", 100, 100, 99))]))
        self.assertEqual(self.row_info("s"), ("99%", "In Progress"))
        self.assertEqual(self.text("#overallPercent"), "99%")
        self.open(project([goal("g", stage("s", 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))]))
        self.assertEqual(self.row_info("s"), ("1%", "In Progress"))

    def test_many_goals_and_uneven_shapes(self):
        goals = [goal(f"goal{g}", *[stage(f"goal{g}-s{s}", *([50] * (s + g))) for s in range(1, g + 1)])
                 for g in range(1, 8)]
        self.open(project(goals))
        self.assertEqual(len(self.visible_ids("goal")), 7)
        total = sum(s + g for g in range(1, 8) for s in range(1, g + 1))
        self.assertEqual(self.text("#overallCopy"), f"0 of {total} milestones completed")
        self.assertEqual(self.page.locator(".stage-row").count(), 28)
        self.assertIn("7 stages", self.text('.row[data-id="goal7"] .item-meta'))

    def test_goal_progress_weights_milestones(self):
        self.open(project([goal("g", stage("s1", 100), stage("s2", 0, 0, 0))]))
        self.assertEqual(self.row_info("g")[0], "25%")

    def test_default_expansion_and_toggling(self):
        data = json.loads((REPO / "examples/demo/project-status.json").read_text())
        self.open(data)
        self.assertEqual(self.visible_ids("stage"),
                         ["api-foundation", "api-endpoints", "api-hardening", "console-design", "console-build"])
        # only the active stage in each open goal shows milestones
        visible_m = self.visible_ids("milestone")
        self.assertTrue(all(m.startswith(("api-endpoints", "console-design")) for m in visible_m), visible_m)
        self.assertEqual(len(visible_m), 6)

        # expand a future goal, then one of its stages
        self.row("rollout").locator(".toggle").click()
        self.assertIn("rollout-infra", self.visible_ids("stage"))
        self.assertEqual(self.row("rollout").locator(".toggle").get_attribute("aria-expanded"), "true")
        self.row("rollout-infra").locator(".item-title").click()      # whole cell is clickable
        self.assertIn("rollout-infra-m1", self.visible_ids("milestone"))
        # collapse the goal hides stages and milestones
        self.row("rollout").locator(".toggle").click()
        self.assertNotIn("rollout-infra", self.visible_ids("stage"))
        self.assertNotIn("rollout-infra-m1", self.visible_ids("milestone"))

        # milestone details toggle
        details = self.page.locator('[data-details-for="api-endpoints-m3"]')
        self.assertTrue(details.is_hidden())
        self.row("api-endpoints-m3").locator(".toggle").click()
        self.assertTrue(details.is_visible())
        self.assertIn("pagination pending", details.inner_text())
        self.row("api-foundation").locator(".toggle").click()
        evidence = self.page.locator('[data-details-for="api-foundation-m1"]')
        self.row("api-foundation-m1").locator(".toggle").click()
        self.assertIn("Evidence:", evidence.inner_text())
        # milestones without details have no toggle
        self.assertEqual(self.row("api-endpoints-m4").locator("button.toggle").count(), 0)

    def test_refresh_reloads_json_and_keeps_expansion(self):
        data = project([goal("a", stage("a1", 50, 0)), goal("b", stage("b1", 0))])
        self.open(data)
        self.row("b").locator(".toggle").click()                      # user opens a future goal
        data["goals"][0]["stages"][0]["milestones"][1]["progress"] = 100
        data["project"]["name"] = "Renamed"
        data["project"]["updatedAt"] = "2026-09-27T09:30:00Z"
        self.write(data)
        self.page.click("#refreshBtn")
        self.page.wait_for_function("document.querySelector('#projectName').textContent === 'Renamed'")
        self.assertEqual(self.text("#overallPercent"), "50%")
        self.assertEqual(self.row_info("a1"), ("75%", "In Progress"))
        self.assertIn("b1", self.visible_ids("stage"))                 # user's choice survived
        self.assertIn("2026", self.text("#updatedAt"))

    def test_malformed_json_keeps_last_good_data(self):
        self.open(project([goal("a", stage("a1", 40))]))
        self.write('{"project": {"name": "broken",}')
        self.page.click("#refreshBtn")
        self.page.wait_for_selector("#notice:not(.hidden)")
        self.assertIn("invalid JSON", self.text("#notice"))
        self.assertIn("last good data", self.text("#notice"))
        self.assertEqual(self.text("#projectName"), "Browser Test")
        self.write(project([goal("a", stage("a1", 60))]))
        self.page.click("#refreshBtn")
        self.page.wait_for_selector("#notice.hidden", state="attached")
        self.assertEqual(self.text("#overallPercent"), "60%")

    def test_bad_initial_load_and_missing_file(self):
        self.write("not json")
        self.open()
        self.assertIn("invalid JSON", self.text("#notice"))
        self.assertEqual(self.text("#projectName"), "Project Status")
        self.open(query="?data=missing.json")
        self.assertIn("HTTP 404", self.text("#notice"))

    def test_data_query_parameter(self):
        self.write(project([goal("alt", stage("alt-s", 10))], name="Alt Data"), name="alt.json")
        self.open(query="?data=alt.json")
        self.assertEqual(self.text("#projectName"), "Alt Data")

    def test_file_url_shows_serve_hint(self):
        self.write(project([goal("a", stage("a1", 0))]))
        self.page.goto((self.dir / "index.html").as_uri())
        self.page.wait_for_selector("#notice:not(.hidden)")
        self.assertIn("python3 -m http.server", self.text("#notice"))

    def test_escapes_html_in_names(self):
        self.open(project([goal("x", stage("x1", 0), name='<img src=x onerror="window.pwned=1">')]))
        self.assertIsNone(self.page.evaluate("window.pwned"))
        self.assertIn("<img", self.text('.row[data-id="x"] .item-title'))

    def test_auto_refresh(self):
        data = project([goal("a", stage("a1", 10))], autoRefreshSeconds=5)
        self.open(data)
        data["goals"][0]["stages"][0]["milestones"][0]["progress"] = 90
        self.write(data)
        self.page.wait_for_function("document.querySelector('#overallPercent').textContent === '90%'",
                                    timeout=9000)

    def test_mobile_has_no_horizontal_scroll(self):
        self.page.set_viewport_size({"width": 375, "height": 800})
        self.open(json.loads((REPO / "examples/demo/project-status.json").read_text()))
        overflow = self.page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        self.assertLessEqual(overflow, 0)


if __name__ == "__main__":
    unittest.main()
