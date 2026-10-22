"""Verify a captured registered-CSV Zetaris investigation before graph use."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from .core import verify_bundle
from .zetaris_sources import source_join_sql, validate_join


RELEASE = "RIN_RELEASE.release_changes"
USAGE = "RIN_USAGE.project_usage"
TABLES = {
    RELEASE: ("release_changes.csv", ["symbol", "release_receipt_id", "release_version"]),
    USAGE: ("project_usage.csv", ["symbol", "path", "project_receipt_id"]),
}
CAPTURE_FIELDS = ("bundle_evidence_sha256", "database_ids", "namespace_query", "sources", "join", "join_count", "source_validation")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _unknown(reason: str) -> dict:
    return {"verdict": "UNKNOWN", "reason": reason}


def verify_live_capture(bundle: dict, receipt: dict | None, source_dir: Path) -> dict:
    """Check the local capture and source contents; no service-signature claim."""
    if not isinstance(receipt, dict) or not verify_bundle(bundle)["ok"]:
        return _unknown("SOURCE_RECEIPT_MISSING_OR_BUNDLE_INVALID")
    try:
        if receipt["schema"] != "rin.zetaris_registered_csv_join.v1":
            return _unknown("SOURCE_RECEIPT_SCHEMA_INVALID")
        if receipt["bundle_evidence_sha256"] != bundle["evidence_hash_sha256"]:
            return _unknown("SOURCE_BUNDLE_MISMATCH")
        evidence = {key: receipt[key] for key in CAPTURE_FIELDS}
        actual_capture_hash = hashlib.sha256(json.dumps(
            evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if actual_capture_hash != receipt["capture_sha256"]:
            return _unknown("SOURCE_RECEIPT_TAMPERED")
        namespaces = receipt["namespace_query"]
        if namespaces["http_status"] != 200 or not namespaces["query_id"]:
            return _unknown("SOURCE_NAMESPACE_UNVERIFIED")
        observed_ids = {row[0]: row[2] for row in namespaces["rows"]
                        if isinstance(row, list) and len(row) >= 3 and row[0] in ("RIN_RELEASE", "RIN_USAGE")}
        if observed_ids != receipt["database_ids"] or len(set(observed_ids.values())) != 2:
            return _unknown("SOURCE_NAMESPACE_INCONSISTENT")
        if receipt["status"] != "CROSS_SOURCE_JOIN_VERIFIED":
            return _unknown("SOURCE_CAPTURE_NOT_VERIFIED")
        manifest = json.loads((source_dir / "manifest.json").read_text(encoding="utf-8"))
        if manifest["source_bundle_evidence_sha256"] != bundle["evidence_hash_sha256"]:
            return _unknown("SOURCE_EXPORT_BUNDLE_MISMATCH")
        for table, (filename, headers) in TABLES.items():
            source = receipt["sources"][table]
            raw = (source_dir / filename).read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            if (sha != manifest["files_sha256"][filename]
                    or sha != source["prepared_sha256"] or source["source_id"] != table):
                return _unknown("SOURCE_FILE_MISMATCH")
            with (source_dir / filename).open(encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames != headers:
                    return _unknown("SOURCE_SCHEMA_MISMATCH")
                expected_rows = [[row[field] for field in headers] for row in reader]
            listing, schema, select, count = (source[key] for key in ("listing", "schema", "select", "count"))
            for response in (listing, schema, select, count):
                if (response.get("http_status") != 200 or not response.get("query_id")
                        or response.get("result_sha256") != digest(response.get("rows"))):
                    return _unknown("SOURCE_QUERY_UNVERIFIED")
            if (not source["matched"] or source["expected_row_count"] != len(expected_rows)
                    or not any(row[0] == table for row in listing["rows"])
                    or schema["rows"] != [[field, "string", None] for field in headers]
                    or select["headers"] != headers
                    or sorted(select["rows"]) != sorted(expected_rows)
                    or count["rows"] != [[str(len(expected_rows))]]):
                return _unknown("SOURCE_ROWS_INCONSISTENT")
        join, join_count = receipt["join"], receipt["join_count"]
        if (join.get("sql") != source_join_sql(RELEASE, USAGE)
                or join.get("source_ids") != [RELEASE, USAGE]
                or join.get("result_sha256") != digest(join.get("rows"))
                or join_count.get("http_status") != 200
                or join_count.get("result_sha256") != digest(join_count.get("rows"))
                or join_count.get("rows") != [[str(len(join.get("rows") or []))]]):
            return _unknown("SOURCE_JOIN_INCONSISTENT")
        verdict = validate_join(bundle, join)
        if verdict != receipt["source_validation"] or verdict["verdict"] != "REVIEW":
            return _unknown("SOURCE_JOIN_FAILED_VERIFICATION")
        return {"verdict": "REVIEW", "reason": "LIVE_REGISTERED_SOURCE_JOIN_VERIFIED",
                "matched_rows": verdict["matched_rows"], "join_query_id": join["query_id"],
                "join_result_sha256": join["result_sha256"]}
    except (KeyError, TypeError, ValueError, IndexError, OSError, AttributeError):
        return _unknown("SOURCE_RECEIPT_MALFORMED")
