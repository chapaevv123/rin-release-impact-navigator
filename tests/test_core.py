from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rin.core import inspect_python, investigate, verify_bundle
from rin.e2e import run as run_e2e


ROOT = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    def test_public_release_fixture_review_and_citations(self):
        bundle = investigate(ROOT / "samples/flask_3_1_case.json")
        self.assertEqual(bundle["verdict"], "REVIEW")
        self.assertEqual(bundle["hypotheses"][0]["state"], "SUPPORTED")
        self.assertEqual(bundle["findings"][0]["usage"][0]["line"], 6)
        self.assertTrue(bundle["verification"]["ok"])
        self.assertEqual(bundle["sponsors"]["zetaris"], "NOT_USED_IN_THIS_RUN")

    def test_replay_outcome_is_stable(self):
        case = ROOT / "samples/flask_3_1_case.json"
        a, b = investigate(case), investigate(case)
        for key in ("input_hash_sha256", "evidence_hash_sha256", "verdict", "findings"):
            self.assertEqual(a[key], b[key])

    def test_tamper_detected(self):
        bundle = investigate(ROOT / "samples/flask_3_1_case.json")
        forged = copy.deepcopy(bundle)
        forged["receipts"][0]["snapshot"] += "forged"
        self.assertFalse(verify_bundle(forged)["ok"])

    def test_static_absence_does_not_claim_no_action(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "note.txt").write_text("Changed flask.Request.max_content_length", encoding="utf8")
            (directory / "app.py").write_text("import os\nprint(1)\n", encoding="utf8")
            (directory / "requirements.txt").write_text("flask==3.0.3\n", encoding="utf8")
            case = {"project":"fixture", "dependency":"flask", "old_version":"3.0.3",
                    "new_version":"3.1.0", "manifest_path":"requirements.txt",
                    "release_notes":{"path":"note.txt"},
                    "changes":[{"symbol":"flask.Request.max_content_length",
                                "release_span":"Changed flask.Request.max_content_length"}],
                    "python_files":["app.py"], "complete_project_snapshot":True,
                    "transitive_paths_verified":True}
            path = directory / "case.json"
            path.write_text(json.dumps(case), encoding="utf8")
            result = investigate(path)
            self.assertEqual(result["verdict"], "UNKNOWN")
            self.assertIn("INSUFFICIENT_TEST_COVERAGE", result["unknown_reasons"])
            self.assertEqual(result["skeptic"]["challenges"], result["unknown_reasons"])
            self.assertTrue(result["verification"]["ok"])

    def test_unseen_or_dynamic_usage_is_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "note.txt").write_text("Changed flask.Request.max_content_length", encoding="utf8")
            (directory / "app.py").write_text("import flask\ngetattr(flask, 'Request')\n", encoding="utf8")
            (directory / "requirements.txt").write_text("flask==3.0.3\n", encoding="utf8")
            case = {"project":"fixture", "dependency":"flask", "old_version":"3.0.3",
                    "new_version":"3.1.0", "manifest_path":"requirements.txt",
                    "release_notes":{"path":"note.txt"},
                    "changes":[{"symbol":"flask.Request.max_content_length",
                                "release_span":"Changed flask.Request.max_content_length"}],
                    "python_files":["app.py"], "complete_project_snapshot":True,
                    "transitive_paths_verified":True}
            path = directory / "case.json"
            path.write_text(json.dumps(case), encoding="utf8")
            result = investigate(path)
            self.assertEqual(result["verdict"], "UNKNOWN")
            self.assertIn("DYNAMIC_USAGE_UNRESOLVED", result["unknown_reasons"])
            self.assertEqual(result["skeptic"]["changed_hypotheses"], 1)
            self.assertIn("SKEPTIC_REOPENED_DYNAMIC_PATH", [x["event"] for x in result["timeline"]])

    def test_missing_release_span_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "note.txt").write_text("no relevant note", encoding="utf8")
            (directory / "app.py").write_text("import flask\n", encoding="utf8")
            (directory / "requirements.txt").write_text("flask==3.0.3\n", encoding="utf8")
            case = {"project":"fixture", "dependency":"flask", "old_version":"3.0.3",
                    "new_version":"3.1.0", "manifest_path":"requirements.txt",
                    "release_notes":{"path":"note.txt"},
                    "changes":[{"symbol":"flask.Request.max_content_length", "release_span":"missing"}],
                    "python_files":["app.py"]}
            path = directory / "case.json"
            path.write_text(json.dumps(case), encoding="utf8")
            result = investigate(path)
            self.assertEqual(result["verdict"], "UNKNOWN")
            self.assertIn("RELEASE_DELTA_INCOMPLETE", result["unknown_reasons"])

    def test_missing_source_is_unknown_with_resolving_action(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "app.py").write_text("import flask\n", encoding="utf8")
            case = {"project":"fixture", "dependency":"flask", "old_version":"3.0.3",
                    "new_version":"3.1.0", "manifest_path":"requirements.txt",
                    "release_notes":{"path":"absent.txt"},
                    "changes":[], "python_files":["app.py"]}
            path = directory / "case.json"
            path.write_text(json.dumps(case), encoding="utf8")
            result = investigate(path)
            self.assertEqual(result["verdict"], "UNKNOWN")
            self.assertEqual(result["unknown_reasons"], ["SOURCE_UNAVAILABLE"])
            self.assertIn("absent.txt", result["reason"])
            self.assertTrue(result["verification"]["ok"])

    def test_alias_and_typed_parameter(self):
        source = "from flask import Request as R\ndef f(req: R):\n    return req.max_content_length\n"
        result = inspect_python(source, "flask", ["flask.Request.max_content_length"])
        self.assertTrue(any(x["line"] == 3 for x in result["usages"]))

    def test_conflicting_manifest_blocks_review(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            source = ROOT / "samples"
            for filename in ("flask_3_1_case.json", "flask_changes_snapshot.txt", "upload_service.py"):
                (directory / filename).write_bytes((source / filename).read_bytes())
            (directory / "requirements.txt").write_text("flask==2.3.0\n", encoding="utf8")
            result = investigate(directory / "flask_3_1_case.json")
            self.assertEqual(result["verdict"], "UNKNOWN")
            self.assertIn("CONFLICTING_EVIDENCE", result["unknown_reasons"])
            self.assertEqual(result["manifest_status"], "UNRESOLVED_OR_CONFLICTING")

    def test_no_action_forgery_rejected(self):
        bundle = investigate(ROOT / "samples/flask_3_1_case.json")
        bundle["verdict"] = "NO_ACTION"
        self.assertFalse(verify_bundle(bundle)["ok"])

    def test_sponsor_failure_downgrades_to_unknown(self):
        with patch("rin.e2e.zetaris_run", return_value={"result": "SOURCE_UNAVAILABLE"}):
            bundle = run_e2e(ROOT / "samples/flask_3_1_case.json", ROOT)
        self.assertEqual(bundle["verdict"], "UNKNOWN")
        self.assertIn("SPONSOR_SOURCE_UNAVAILABLE", bundle["unknown_reasons"])
        self.assertTrue(bundle["verification"]["ok"])

    def test_real_public_case_records_differential_without_upstream_pin_claim(self):
        bundle = investigate(ROOT / "samples/real_starlette/case.json")
        self.assertEqual(bundle["verdict"], "REVIEW")
        self.assertEqual(bundle["differential"]["status"], "RECORDED_LOCAL_DIFFERENTIAL")
        self.assertEqual(bundle["differential"]["old"]["outcome"], "PASS")
        self.assertEqual(bundle["differential"]["new"]["outcome"], "FAIL")
        self.assertEqual(bundle["manifest_provenance"], "LOCAL_REPRODUCTION_PIN_NOT_UPSTREAM_MANIFEST")
        self.assertEqual(bundle["sponsors"]["zetaris"], "NOT_USED_IN_THIS_RUN")
        self.assertTrue(bundle["verification"]["ok"])

    def test_forged_differential_rejected(self):
        bundle = investigate(ROOT / "samples/real_starlette/case.json")
        forged = copy.deepcopy(bundle)
        forged["differential"]["new"]["outcome"] = "PASS"
        self.assertFalse(verify_bundle(forged)["ok"])

    def test_conflicting_runtime_report_downgrades_to_unknown(self):
        source = ROOT / "samples/real_starlette"
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for name in ("case.json", "requirements.txt", "starlette_pyproject.toml",
                         "httpx_changelog.md", "testclient.py", "runtime_old.json", "runtime_new.json"):
                (directory / name).write_bytes((source / name).read_bytes())
            report = json.loads((directory / "runtime_new.json").read_text(encoding="utf-8"))
            report["outcome"] = "PASS"
            (directory / "runtime_new.json").write_text(json.dumps(report), encoding="utf-8")
            bundle = investigate(directory / "case.json")
        self.assertEqual(bundle["verdict"], "UNKNOWN")
        self.assertIn("CONFLICTING_EVIDENCE", bundle["unknown_reasons"])
        self.assertTrue(bundle["verification"]["ok"])

    def test_missing_graph_downgrades_to_unknown(self):
        expected = {"http_status": 200, "rows": [["flask.Request.max_content_length", "upload_service.py:6"]],
                    "query_id": "test", "result_sha256": "test"}
        process = type("Process", (), {"returncode": 0, "stdout": '{"readAfterWrite":true,"graphFindings":[],"nextAction":"IGNORE"}'})()
        with patch("rin.e2e.zetaris_run", return_value=expected), patch("rin.e2e.subprocess.run", return_value=process):
            bundle = run_e2e(ROOT / "samples/flask_3_1_case.json", ROOT)
        self.assertEqual(bundle["verdict"], "UNKNOWN")
        self.assertIn("SPONSOR_SOURCE_UNAVAILABLE", bundle["unknown_reasons"])
        self.assertTrue(bundle["verification"]["ok"])


if __name__ == "__main__":
    unittest.main()
