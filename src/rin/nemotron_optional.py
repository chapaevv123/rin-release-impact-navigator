"""Fail-closed gate for optional NVIDIA hypothesis proposals.

This module never calls a model. An authenticated model listing is not an
inference receipt, and a proposal cannot change RIN's deterministic verdict.
"""
from __future__ import annotations

import json

from .core import verify_bundle


FIELDS = frozenset({"hypothesis_id", "changed_symbol", "proposed_impact",
                    "source_receipt_ids", "exact_source_spans", "uncertainty",
                    "required_verification", "model_id"})


def gate(bundle: dict, model_response: str | None, model_id: str,
         source_decision: dict | None) -> dict:
    """Return a cited HYPOTHESIS or UNKNOWN; never promote model text to evidence."""
    if model_response is None:
        return {"state": "UNKNOWN", "reason": "NVIDIA_INFERENCE_UNAVAILABLE"}
    if not verify_bundle(bundle)["ok"]:
        return {"state": "UNKNOWN", "reason": "BASE_EVIDENCE_INVALID"}
    challenges = bundle.get("skeptic", {}).get("challenges", [])
    if (bundle.get("verdict") == "NO_ACTION" or not isinstance(challenges, list)
            or "INSUFFICIENT_TEST_COVERAGE" not in challenges):
        return {"state": "UNKNOWN", "reason": "SKEPTIC_COVERAGE_UNVERIFIED"}
    try:
        proposal = json.loads(model_response)
    except (TypeError, ValueError):
        return {"state": "UNKNOWN", "reason": "MALFORMED_MODEL_RESPONSE"}
    if not isinstance(proposal, dict) or set(proposal) != FIELDS:
        return {"state": "UNKNOWN", "reason": "MALFORMED_MODEL_RESPONSE"}
    strings = ("hypothesis_id", "changed_symbol", "proposed_impact",
               "uncertainty", "required_verification", "model_id")
    if any(not isinstance(proposal[k], str) or not proposal[k].strip() for k in strings):
        return {"state": "UNKNOWN", "reason": "MALFORMED_MODEL_RESPONSE"}
    if proposal["model_id"] != model_id:
        return {"state": "UNKNOWN", "reason": "MODEL_ID_MISMATCH"}
    ids, spans = proposal["source_receipt_ids"], proposal["exact_source_spans"]
    if (not isinstance(ids, list) or not ids or len(ids) != len(set(map(str, ids)))
            or not isinstance(spans, list) or len(spans) != len(ids)
            or any(not isinstance(x, str) or not x.strip() for x in ids + spans)):
        return {"state": "UNKNOWN", "reason": "INVALID_CITATION"}
    receipts = {r["receipt_id"]: r for r in bundle["receipts"]}
    if any(rid not in receipts or span not in receipts[rid]["snapshot"]
           for rid, span in zip(ids, spans)):
        return {"state": "UNKNOWN", "reason": "INVALID_CITATION"}
    release_ids = {r["receipt_id"] for r in bundle["receipts"]
                   if r["source_type"] == "PUBLIC_RELEASE_SNAPSHOT"}
    if not release_ids.intersection(ids):
        return {"state": "UNKNOWN", "reason": "RELEASE_CITATION_MISSING"}
    symbols = {f["symbol"] for f in bundle.get("findings", [])}
    if proposal["changed_symbol"] not in symbols:
        return {"state": "UNKNOWN", "reason": "CHANGED_SYMBOL_UNVERIFIED"}
    if not isinstance(source_decision, dict) or source_decision.get("verdict") != "REVIEW":
        return {"state": "UNKNOWN", "reason": "SOURCE_OR_GRAPH_UNVERIFIED"}
    source = source_decision.get("source_validation", {})
    if (source.get("matched_rows", 0) < 1
            or source_decision.get("graph_used") is not True
            or source_decision.get("hypothesis_update", {}).get("state_remains") != "SUPPORTED"):
        return {"state": "UNKNOWN", "reason": "SOURCE_OR_GRAPH_UNVERIFIED"}
    return {"state": "HYPOTHESIS", "reason": "CITED_PROPOSAL_REQUIRES_VERIFICATION",
            "proposal": proposal, "deterministic_verdict": source_decision["verdict"],
            "source_query_id": source["join_query_id"],
            "skeptic_challenges": challenges}
