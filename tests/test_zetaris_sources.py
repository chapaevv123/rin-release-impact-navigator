import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rin.zetaris_sources import prepare, source_join_sql, validate_join

ROOT = Path(__file__).resolve().parents[1]


class SourceJoinTests(unittest.TestCase):
    def test_prepared_sources_and_bounded_join(self):
        bundle = json.loads((ROOT / "artifacts/starlette_httpx_028_bundle.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            manifest = prepare(bundle, Path(temp))
            self.assertEqual(manifest["mode"], "PREPARED_ONLY_NOT_REGISTERED")
            self.assertEqual((manifest["release_rows"], manifest["usage_rows"]), (2, 1))
        self.assertIn("JOIN RIN_USAGE.project_usage", source_join_sql(
            "RIN_RELEASE.release_changes", "RIN_USAGE.project_usage"))
        with self.assertRaises(ValueError):
            source_join_sql("RIN_RELEASE.release_changes;DROP", "RIN_USAGE.project_usage")

    def test_absent_or_forged_source_result_fails_closed(self):
        bundle = json.loads((ROOT / "artifacts/starlette_httpx_028_bundle.json").read_text(encoding="utf-8"))
        finding = bundle["findings"][0]
        row = [finding["symbol"], "testclient.py:392", finding["receipt_ids"][0],
               finding["usage"][0]["receipt_id"]]
        result = {"http_status": 200, "query_id": "mock-query",
                  "release_table": "RIN_RELEASE.release_changes",
                  "usage_table": "RIN_USAGE.project_usage",
                  "source_ids": ["RIN_RELEASE.release_changes", "RIN_USAGE.project_usage"],
                  "sql": source_join_sql("RIN_RELEASE.release_changes", "RIN_USAGE.project_usage"),
                  "rows": [row]}
        result["result_sha256"] = hashlib.sha256(json.dumps(result["rows"], sort_keys=True).encode()).hexdigest()
        self.assertEqual(validate_join(bundle, result)["verdict"], "REVIEW")
        self.assertEqual(validate_join(bundle, None)["verdict"], "UNKNOWN")
        forged = {**result, "rows": [["forged", *row[1:]]],
                  "result_sha256": hashlib.sha256(json.dumps([["forged", *row[1:]]], sort_keys=True).encode()).hexdigest()}
        self.assertEqual(validate_join(bundle, forged)["verdict"], "UNKNOWN")
        self.assertEqual(validate_join(bundle, {**result, "source_ids": []})["verdict"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
