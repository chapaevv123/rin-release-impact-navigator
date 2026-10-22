"""Replayable RIN investigation from a captured live Zetaris JOIN to Meterless."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rin.zetaris_live import verify_live_capture  # noqa: E402


BUNDLE = ROOT / "artifacts" / "starlette_httpx_028_bundle.json"
JOIN = ROOT / "artifacts" / "zetaris_live_join_receipt.json"
OUTPUT = ROOT / "artifacts" / "zetaris_live_e2e_receipt.json"
SOURCES = ROOT / "samples" / "zetaris_sources"
GRAPH_FIELDS = ("graphFindings", "nextAction", "verdictConstraint", "sourceJoinQueryId",
                "sourceJoinResultSha256", "sourceMode", "readAfterWrite", "hypothesisBefore")


def graph_run() -> dict:
    completed = subprocess.run(["node", "--no-warnings=ExperimentalWarning",
        "--experimental-transform-types", str(ROOT / "meterless_graph.ts"), str(BUNDLE), str(JOIN)],
        cwd=ROOT, capture_output=True, text=True, timeout=25, check=True)
    return json.loads(completed.stdout)


def evaluate(bundle: dict, join: dict | None, graph: dict | None = None) -> dict:
    source = verify_live_capture(bundle, join, SOURCES)
    if source["verdict"] != "REVIEW":
        return {"verdict": "UNKNOWN", "reason": source["reason"], "source_validation": source,
                "graph_used": False}
    if graph is None:
        return {"verdict": "UNKNOWN", "reason": "METERLESS_GRAPH_UNAVAILABLE",
                "source_validation": source, "graph_used": False}
    expected_marker = f"zetaris:query:{source['join_query_id']}"
    observed = graph.get("graphFindings")
    valid = (graph.get("readAfterWrite") is True
             and graph.get("sourceMode") == "REGISTERED_LOCAL_CSV_JOIN"
             and graph.get("sourceJoinQueryId") == source["join_query_id"]
             and graph.get("sourceJoinResultSha256") == source["join_result_sha256"]
             and graph.get("verdictConstraint") == "REVIEW_OR_UNKNOWN"
             and graph.get("nextAction") == "REVIEW_FAILED_DIFFERENTIAL_IN_TARGET_CI"
             and isinstance(observed, list) and len(observed) == source["matched_rows"]
             and all(expected_marker in finding.get("evidenceIds", []) for finding in observed)
             and graph.get("hypothesisBefore") == [
                 {"id": h["hypothesis_id"], "state": h["state"]} for h in bundle["hypotheses"]]
             and bundle["verdict"] == "REVIEW")
    if not valid:
        return {"verdict": "UNKNOWN", "reason": "METERLESS_GRAPH_INCONSISTENT",
                "source_validation": source, "graph_used": True}
    return {"verdict": "REVIEW", "reason": "LIVE_SOURCE_JOIN_AND_DIFFERENTIAL_REVIEW",
            "source_validation": source, "graph_used": True,
            "hypothesis_update": {"hypothesis_id": "hyp_001", "event": "LIVE_JOIN_CORROBORATED",
                                  "state_remains": "SUPPORTED", "query_id": source["join_query_id"]},
            "next_action": graph["nextAction"]}


def capture() -> dict:
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
    join = json.loads(JOIN.read_text(encoding="utf-8"))
    preflight = verify_live_capture(bundle, join, SOURCES)
    graph = graph_run() if preflight["verdict"] == "REVIEW" else None
    decision = evaluate(bundle, join, graph)
    result = {"schema": "rin.zetaris_meterless_live_e2e.v1",
              "captured_at_utc": datetime.now(timezone.utc).isoformat(),
              "source_capture_sha256": join["capture_sha256"],
              "source_query_id": join["join"]["query_id"],
              "bundle_evidence_sha256": bundle["evidence_hash_sha256"],
              "decision": decision, "meterless_graph": graph,
              "graph_output_sha256": hashlib.sha256(json.dumps(
                  graph, sort_keys=True, separators=(",", ":")).encode()).hexdigest() if graph else None,
              "scope": "two registered local CSV sources; in-memory Meterless reference graph; no heterogeneous remote federation"}
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def replay() -> dict:
    saved = json.loads(OUTPUT.read_text(encoding="utf-8"))
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
    join = json.loads(JOIN.read_text(encoding="utf-8"))
    source = verify_live_capture(bundle, join, SOURCES)
    if source["verdict"] != "REVIEW" or saved["source_capture_sha256"] != join["capture_sha256"]:
        return {"matched": False, "reason": "SOURCE_RECEIPT_INVALID"}
    current_graph = graph_run()
    matched = (all(current_graph.get(key) == saved["meterless_graph"].get(key)
                   for key in GRAPH_FIELDS)
               and evaluate(bundle, join, current_graph) == saved["decision"])
    return {"matched": matched, "source_verified": True,
            "graph_read_after_write": current_graph.get("readAfterWrite"),
            "compared": list(GRAPH_FIELDS) + ["decision"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    result = replay() if args.replay else capture()
    print(json.dumps(result if args.replay else {
        "verdict": result["decision"]["verdict"],
        "source_query_id": result["source_query_id"],
        "graph_findings": result["meterless_graph"]["graphFindings"] if result["meterless_graph"] else [],
        "next_action": result["decision"].get("next_action"),
        "receipt": str(OUTPUT)}, indent=2))
    if (args.replay and not result["matched"]) or (not args.replay and result["decision"]["verdict"] != "REVIEW"):
        raise SystemExit(1)
