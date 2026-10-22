import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "bench"))

from rin.zetaris_live import verify_live_capture  # noqa: E402
from capture_zetaris_live_e2e import evaluate, SOURCES  # noqa: E402


class LiveJoinReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = json.loads((ROOT / "artifacts/starlette_httpx_028_bundle.json").read_text(encoding="utf-8"))
        cls.join = json.loads((ROOT / "artifacts/zetaris_live_join_receipt.json").read_text(encoding="utf-8"))
        cls.e2e = json.loads((ROOT / "artifacts/zetaris_live_e2e_receipt.json").read_text(encoding="utf-8"))

    def test_saved_live_join_rechecks_against_csv_and_bundle(self):
        result = verify_live_capture(self.bundle, self.join, SOURCES)
        self.assertEqual(result["verdict"], "REVIEW")
        self.assertEqual(result["matched_rows"], 1)
        self.assertEqual(result["join_query_id"], self.join["join"]["query_id"])

    def test_saved_meterless_graph_uses_live_query(self):
        result = evaluate(self.bundle, self.join, self.e2e["meterless_graph"])
        self.assertEqual(result["verdict"], "REVIEW")
        self.assertEqual(result["hypothesis_update"]["event"], "LIVE_JOIN_CORROBORATED")
        self.assertEqual(result["next_action"], "REVIEW_FAILED_DIFFERENTIAL_IN_TARGET_CI")

    def test_missing_tampered_or_inconsistent_source_fails_closed(self):
        self.assertEqual(evaluate(self.bundle, None, None)["verdict"], "UNKNOWN")
        tampered = copy.deepcopy(self.join)
        tampered["join"]["rows"][0][0] = "not-used-symbol"
        self.assertEqual(evaluate(self.bundle, tampered, None)["verdict"], "UNKNOWN")
        bad_graph = copy.deepcopy(self.e2e["meterless_graph"])
        bad_graph["sourceJoinQueryId"] = "other-query"
        self.assertEqual(evaluate(self.bundle, self.join, bad_graph)["verdict"], "UNKNOWN")
        self.assertNotEqual(evaluate(self.bundle, tampered, None)["verdict"], "NO_ACTION")


if __name__ == "__main__":
    unittest.main()
