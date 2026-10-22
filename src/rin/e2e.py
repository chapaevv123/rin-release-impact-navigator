"""One bounded RIN investigation with actual local Zetaris and Meterless calls.

Zetaris currently receives two verified snapshot-derived values as inline SQL
inputs. This proves SQL processing, not connector federation. The sponsor path
fails closed if either service cannot provide the expected result.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .core import canonical, investigate, sha256, verify_bundle
from .zetaris_bridge import run as zetaris_run


def _literal(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_./:-]+", value):
        raise ValueError("unsafe SQL literal")
    return "'" + value + "'"


def _add_service_receipt(bundle: dict, *, source_type: str, source_ref: str,
                         raw: dict, tool: str, version: str) -> str:
    snapshot = canonical(raw).decode()
    digest = sha256(snapshot.encode())
    rid = "rcpt_" + sha256(canonical([source_ref, digest, ""]))[:16]
    bundle["receipts"].append({
        "receipt_id": rid, "source_type": source_type,
        "source_url_or_local_reference": source_ref,
        "content_hash_sha256": digest,
        "source_commit_or_version": version,
        "exact_span_or_line": "",
        "capture_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "tool": tool, "result": "verified service operation",
        "verification_status": "VERIFIED_LOCAL_SERVICE",
        "snapshot": snapshot,
    })
    return rid


def run(case_path: Path, repo_root: Path) -> dict:
    bundle = investigate(case_path)
    bundle["mode"] = "CAPTURED_LOCAL_SPONSOR_RUN_WITH_RECORDED_SOURCE"
    bundle["unknown_reasons"] = set(bundle["unknown_reasons"])
    if bundle["verdict"] != "REVIEW" or not bundle["findings"]:
        bundle["unknown_reasons"].add("INSUFFICIENT_TEST_COVERAGE")
        bundle["verdict"] = "UNKNOWN"
        bundle["unknown_reasons"] = sorted(bundle["unknown_reasons"])
        return bundle
    finding = bundle["findings"][0]
    usage = finding["usage"][0]
    symbol = finding["symbol"]
    path_line = f"{usage['file']}:{usage['line']}"
    sql = ("SELECT changed.symbol, usage.path FROM "
           f"(SELECT {_literal(symbol)} AS symbol) changed JOIN "
           f"(SELECT {_literal(symbol)} AS symbol, {_literal(path_line)} AS path) usage "
           "ON changed.symbol = usage.symbol LIMIT 10")
    try:
        sql_result = zetaris_run(sql)
    except (RuntimeError, subprocess.SubprocessError, OSError):
        sql_result = {"result": "SOURCE_UNAVAILABLE"}
    if sql_result.get("http_status") == 200 and sql_result.get("rows") == [[symbol, path_line]]:
        sql_receipt = _add_service_receipt(bundle, source_type="ZETARIS_SQL_RESULT",
            source_ref="zetaris://local/sql/" + sql_result["query_id"], raw=sql_result,
            tool="zetaris.sql-editor", version="local-compose")
        finding["receipt_ids"].append(sql_receipt)
        bundle["sponsors"]["zetaris"] = "PASS_INLINE_SQL_NO_FEDERATION"
        bundle["zetaris_query"] = {"sql": sql, "query_id": sql_result["query_id"],
                                   "row_count": len(sql_result["rows"]),
                                   "result_sha256": sql_result["result_sha256"],
                                   "source_receipt_ids": finding["receipt_ids"][:2]}
    else:
        bundle["unknown_reasons"].add("SPONSOR_SOURCE_UNAVAILABLE")
        bundle["verdict"] = "UNKNOWN"
        bundle["reason"] = "Zetaris SQL result unavailable or inconsistent with verified snapshots."
        bundle["unknown_reasons"] = sorted(bundle["unknown_reasons"])
        bundle["verification"] = verify_bundle(bundle)
        return bundle
    bundle["unknown_reasons"] = sorted(bundle["unknown_reasons"])
    bundle_path = repo_root / "artifacts" / "_graph_input.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    try:
        proc = subprocess.run(["node", "--no-warnings=ExperimentalWarning",
            "--experimental-transform-types", str(repo_root / "meterless_graph.ts"), str(bundle_path)],
            capture_output=True, text=True, timeout=20, cwd=repo_root)
        graph = json.loads(proc.stdout) if proc.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        graph = {}
    finally:
        bundle_path.unlink(missing_ok=True)
    if graph.get("readAfterWrite") and any(x.get("symbol") == symbol for x in graph.get("graphFindings", [])):
        graph_receipt = _add_service_receipt(bundle, source_type="METERLESS_WORLD_MODEL_GRAPH",
            source_ref="meterless://local/graph/" + graph["releaseId"], raw=graph,
            tool="meterless.world-model.reference", version="1742dec56a66e58eef9dda2d2b865823758ca8cd")
        finding["receipt_ids"].append(graph_receipt)
        bundle["sponsors"]["meterless"] = "PASS_WRITE_READ"
        bundle["graph_next_action"] = graph["nextAction"]
    else:
        bundle["unknown_reasons"] = set(bundle["unknown_reasons"])
        bundle["unknown_reasons"].add("SPONSOR_SOURCE_UNAVAILABLE")
        bundle["verdict"] = "UNKNOWN"
        bundle["reason"] = "Meterless graph read/write did not confirm the investigation state."
    bundle["unknown_reasons"] = sorted(bundle["unknown_reasons"])
    bundle["evidence_hash_sha256"] = sha256(canonical([r["content_hash_sha256"] for r in bundle["receipts"]]))
    bundle["verification"] = verify_bundle(bundle)
    return bundle
