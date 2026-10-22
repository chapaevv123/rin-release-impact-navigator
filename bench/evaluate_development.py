"""Small development evaluation; never represents the frozen 12-case benchmark."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rin.core import investigate, verify_bundle


def main() -> None:
    real = investigate(ROOT / "samples/real_starlette/case.json")
    fixture = investigate(ROOT / "samples/flask_3_1_case.json")
    saved = json.loads((ROOT / "artifacts/starlette_httpx_028_bundle.json").read_text(encoding="utf-8"))
    replay_keys = ("input_hash_sha256", "evidence_hash_sha256", "verdict",
                   "unknown_reasons", "findings")
    replay = all(real[key] == saved[key] for key in replay_keys)
    with tempfile.TemporaryDirectory() as temp:
        case = json.loads((ROOT / "samples/flask_3_1_case.json").read_text(encoding="utf-8"))
        case["release_notes"]["path"] = "unavailable-release.txt"
        path = Path(temp) / "case.json"
        path.write_text(json.dumps(case), encoding="utf-8")
        missing = investigate(path)
    tampered = copy.deepcopy(real)
    tampered["receipts"][0]["snapshot"] += "tampered"
    forged_no_action = copy.deepcopy(real)
    forged_no_action["verdict"] = "NO_ACTION"
    result = {
        "schema": "rin.development_eval.v1",
        "frozen_benchmark_evaluated": 0,
        "frozen_benchmark_total": 12,
        "cases": [
            {"id": "starlette_httpx_real_public", "kind": "REAL_PUBLIC_LOCAL_REPRODUCTION",
             "verdict": real["verdict"], "receipt_valid": verify_bundle(real)["ok"],
             "replay_matched": replay, "hypotheses_refuted": sum(h["state"] == "REFUTED" for h in real["hypotheses"]),
             "hypotheses_unresolved": sum(h["state"] == "UNRESOLVED" for h in real["hypotheses"])},
            {"id": "flask_upload_fixture", "kind": "SYNTHETIC_PROJECT",
             "verdict": fixture["verdict"], "receipt_valid": verify_bundle(fixture)["ok"]},
            {"id": "missing_release", "kind": "FAILURE_INJECTION",
             "verdict": missing["verdict"], "typed_reason": missing["unknown_reasons"],
             "receipt_valid": verify_bundle(missing)["ok"]},
        ],
        "adversarial_checks": {
            "tampered_receipt_rejected": not verify_bundle(tampered)["ok"],
            "forged_no_action_rejected": not verify_bundle(forged_no_action)["ok"],
            "false_no_action_observed": sum(x["verdict"] == "NO_ACTION" for x in (real, fixture, missing)),
        },
    }
    assert [x["verdict"] for x in result["cases"]] == ["REVIEW", "REVIEW", "UNKNOWN"]
    assert all(result["adversarial_checks"][key] for key in
               ("tampered_receipt_rejected", "forged_no_action_rejected"))
    assert replay and all(x["receipt_valid"] for x in result["cases"])
    target = ROOT / "artifacts/development_eval.json"
    target.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
