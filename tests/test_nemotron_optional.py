import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "bench"))

from rin.nemotron_optional import gate  # noqa: E402
from assess_nemotron_proposal import assess  # noqa: E402
from rin.nvidia_client import verify_attempt_receipt  # noqa: E402


class OptionalNemotronGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = json.loads((ROOT / "artifacts/starlette_httpx_028_bundle.json").read_text(encoding="utf-8"))
        cls.decision = json.loads((ROOT / "artifacts/zetaris_live_e2e_receipt.json").read_text(encoding="utf-8"))["decision"]
        cls.model_id = "nvidia/nemotron-3.5-lightning-30b-a3b"
        cls.synthetic_proposal = {
            "hypothesis_id": "model_candidate_001", "changed_symbol": "httpx.Client",
            "proposed_impact": "Starlette TestClient construction may fail after the update.",
            "source_receipt_ids": ["rcpt_7d73f32d894c8906"],
            "exact_source_spans": ["The deprecated `app` argument has now been removed."],
            "uncertainty": "Requires project and runtime checks",
            "required_verification": "Check TestClient against both HTTPX versions",
            "model_id": cls.model_id,
        }

    def test_synthetic_valid_proposal_stays_hypothesis(self):
        result = gate(self.bundle, json.dumps(self.synthetic_proposal), self.model_id, self.decision)
        self.assertEqual(result["state"], "HYPOTHESIS")
        self.assertEqual(result["deterministic_verdict"], "REVIEW")
        self.assertNotIn("verification_status", result)

    def test_bad_citation_and_malformed_response_fail_closed(self):
        bad = copy.deepcopy(self.synthetic_proposal)
        bad["exact_source_spans"] = ["Invented release claim"]
        self.assertEqual(gate(self.bundle, json.dumps(bad), self.model_id, self.decision)["reason"], "INVALID_CITATION")
        self.assertEqual(gate(self.bundle, "{broken", self.model_id, self.decision)["state"], "UNKNOWN")

    def test_unavailable_and_contradictory_source_fail_closed(self):
        self.assertEqual(gate(self.bundle, None, self.model_id, self.decision)["state"], "UNKNOWN")
        conflicting = {**self.decision, "verdict": "UNKNOWN"}
        self.assertEqual(gate(self.bundle, json.dumps(self.synthetic_proposal), self.model_id, conflicting)["state"], "UNKNOWN")
        self.assertNotEqual(gate(self.bundle, json.dumps(self.synthetic_proposal), self.model_id, conflicting)["state"], "NO_ACTION")

    def test_wrong_model_and_symbol_fail_closed(self):
        bad = copy.deepcopy(self.synthetic_proposal)
        bad["model_id"] = "another/model"
        self.assertEqual(gate(self.bundle, json.dumps(bad), self.model_id, self.decision)["state"], "UNKNOWN")
        bad["model_id"] = self.model_id
        bad["changed_symbol"] = "unknown.symbol"
        self.assertEqual(gate(self.bundle, json.dumps(bad), self.model_id, self.decision)["state"], "UNKNOWN")

    def test_saved_sponsor_chain_is_revalidated_before_model_proposal(self):
        text = json.dumps(self.synthetic_proposal)
        accepted = assess(text, self.model_id)
        self.assertEqual(accepted["state"], "HYPOTHESIS")
        self.assertEqual(accepted["source_query_id"], self.decision["source_validation"]["join_query_id"])
        with patch("assess_nemotron_proposal.evaluate", return_value={"verdict": "UNKNOWN"}):
            self.assertEqual(assess(text, self.model_id)["state"], "UNKNOWN")

    def test_actual_nvidia_response_replays_as_hypothesis_only(self):
        path = ROOT / "artifacts/nemotron_owner_key_inference_receipt.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(verify_attempt_receipt(receipt), {"ok": True, "status": "INFERENCE_CAPTURED"})
        result = assess(receipt["response_text"], receipt["response_model_id"])
        self.assertEqual(result, receipt["citation_validation"])
        self.assertEqual(result["state"], "HYPOTHESIS")
        self.assertEqual(result["deterministic_verdict"], "REVIEW")
        self.assertIn("INSUFFICIENT_TEST_COVERAGE", result["skeptic_challenges"])
        forged = copy.deepcopy(receipt)
        forged["response_text"] = "{}"
        self.assertEqual(verify_attempt_receipt(forged)["reason"], "RECEIPT_HASH_MISMATCH")


if __name__ == "__main__":
    unittest.main()
