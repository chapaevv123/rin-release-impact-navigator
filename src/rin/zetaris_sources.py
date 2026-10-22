"""Prepare verified RIN evidence for two registered Zetaris file sources.

Preparation is offline. A CSV export and a local validator do not constitute a
Zetaris federation receipt; the tables must be registered and queried live.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path

from .core import verify_bundle


IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*\Z")
RELEASE_FIELDS = ("symbol", "release_receipt_id", "release_version")
USAGE_FIELDS = ("symbol", "path", "project_receipt_id")


def _csv_bytes(fields: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def prepare(bundle: dict, output_dir: Path) -> dict:
    if not verify_bundle(bundle)["ok"]:
        raise ValueError("bundle receipts do not verify")
    receipt_by_id = {r["receipt_id"]: r for r in bundle["receipts"]}
    release = next((r for r in bundle["receipts"]
                    if r["source_type"] == "PUBLIC_RELEASE_SNAPSHOT"), None)
    if release is None:
        raise ValueError("verified release snapshot is required")
    release_rows = []
    for hypothesis in bundle["hypotheses"]:
        if hypothesis["hypothesis_id"].endswith("_dynamic"):
            continue  # a challenge to a release claim, not another release change
        if release["receipt_id"] not in hypothesis["supporting_receipt_ids"]:
            raise ValueError("hypothesis lacks release citation")
        release_rows.append({"symbol": hypothesis["potentially_affected_symbol"],
                             "release_receipt_id": release["receipt_id"],
                             "release_version": bundle["new_version"]})
    usage_rows = []
    for finding in bundle["findings"]:
        for usage in finding["usage"]:
            cited = receipt_by_id.get(usage["receipt_id"])
            if cited is None or cited["source_type"] != "PROJECT_CODE":
                raise ValueError("usage lacks project-code receipt")
            usage_rows.append({"symbol": finding["symbol"],
                               "path": f"{usage['file']}:{usage['line']}",
                               "project_receipt_id": cited["receipt_id"]})
    if not release_rows or not usage_rows:
        raise ValueError("both source exports need at least one cited row")
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {"release_changes.csv": _csv_bytes(RELEASE_FIELDS, release_rows),
             "project_usage.csv": _csv_bytes(USAGE_FIELDS, usage_rows)}
    for filename, content in files.items():
        (output_dir / filename).write_bytes(content)
    return {"mode": "PREPARED_ONLY_NOT_REGISTERED",
            "source_bundle_evidence_sha256": bundle["evidence_hash_sha256"],
            "release_rows": len(release_rows), "usage_rows": len(usage_rows),
            "files_sha256": {name: hashlib.sha256(content).hexdigest()
                             for name, content in files.items()}}


def source_join_sql(release_table: str, usage_table: str) -> str:
    for table in (release_table, usage_table):
        if not IDENTIFIER.fullmatch(table):
            raise ValueError("source table must be a qualified identifier")
    return ("SELECT r.symbol, u.path, r.release_receipt_id, u.project_receipt_id "
            f"FROM {release_table} r JOIN {usage_table} u ON r.symbol = u.symbol LIMIT 10")


def validate_join(bundle: dict, result: dict | None) -> dict:
    """Consume a bounded source query only with a matching service receipt."""
    if not verify_bundle(bundle)["ok"] or not isinstance(result, dict):
        return {"verdict": "UNKNOWN", "reason": "UNVERIFIED_SOURCE_RESULT"}
    rows = result.get("rows")
    try:
        expected_sql = source_join_sql(result["release_table"], result["usage_table"])
    except (KeyError, ValueError, TypeError):
        return {"verdict": "UNKNOWN", "reason": "UNVERIFIED_SOURCE_RESULT"}
    source_ids = result.get("source_ids")
    if (result.get("http_status") != 200 or not result.get("query_id")
            or result.get("sql") != expected_sql or not isinstance(rows, list)
            or source_ids != [result["release_table"], result["usage_table"]]
            or result.get("result_sha256") != hashlib.sha256(
                json.dumps(rows, sort_keys=True).encode()).hexdigest()):
        return {"verdict": "UNKNOWN", "reason": "UNVERIFIED_SOURCE_RESULT"}
    expected = set()
    release_ids = {r["receipt_id"] for r in bundle["receipts"]
                   if r["source_type"] == "PUBLIC_RELEASE_SNAPSHOT"}
    for finding in bundle["findings"]:
        for usage in finding["usage"]:
            for release_id in release_ids.intersection(finding["receipt_ids"]):
                expected.add((finding["symbol"], f"{usage['file']}:{usage['line']}",
                              release_id, usage["receipt_id"]))
    observed = {tuple(map(str, row)) for row in rows if isinstance(row, list) and len(row) == 4}
    if len(observed) != len(rows) or not observed or not observed.issubset(expected):
        return {"verdict": "UNKNOWN", "reason": "SOURCE_JOIN_ABSENT_OR_INCONSISTENT"}
    return {"verdict": "REVIEW", "reason": "REGISTERED_SOURCE_JOIN_MATCHED_VERIFIED_USAGE",
            "matched_rows": len(observed)}
