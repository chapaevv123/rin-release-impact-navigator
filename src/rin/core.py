"""Deterministic, fail-closed release impact investigation.

All input files are local snapshots. A release claim is never promoted to a
verified behavior change by an LLM or by textual similarity alone.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


@dataclass(frozen=True)
class Evidence:
    receipt_id: str
    source_type: str
    source_url_or_local_reference: str
    content_hash_sha256: str
    source_commit_or_version: str
    exact_span_or_line: str
    capture_timestamp_utc: str
    tool: str
    result: str
    verification_status: str
    snapshot: str

    def as_dict(self) -> dict[str, str]:
        return vars(self).copy()


def receipt(path: Path, *, source_type: str, source_ref: str,
            version: str, span: str, result: str) -> Evidence:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    if span and span not in text:
        raise ValueError(f"exact span missing: {path.name}")
    digest = sha256(raw)
    return Evidence(
        receipt_id="rcpt_" + sha256(canonical([source_ref, digest, span]))[:16],
        source_type=source_type,
        source_url_or_local_reference=source_ref,
        content_hash_sha256=digest,
        source_commit_or_version=version,
        exact_span_or_line=span,
        capture_timestamp_utc=datetime.now(timezone.utc).isoformat(),
        tool="rin.snapshot.v1",
        result=result,
        verification_status="VERIFIED_LOCAL_SNAPSHOT",
        snapshot=text,
    )


def _imports(tree: ast.AST, dependency: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                if name.name == dependency or name.name.startswith(dependency + "."):
                    aliases[name.asname or name.name.split(".")[0]] = name.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == dependency or node.module.startswith(dependency + "."):
                for name in node.names:
                    aliases[name.asname or name.name] = node.module + "." + name.name
    return aliases


def _symbol_of(node: ast.AST, aliases: dict[str, str]) -> str | None:
    parts: list[str] = []
    cursor = node
    while isinstance(cursor, ast.Attribute):
        parts.append(cursor.attr)
        cursor = cursor.value
    if isinstance(cursor, ast.Name) and cursor.id in aliases:
        parts.append(aliases[cursor.id])
        return ".".join(reversed(parts))
    return None


def inspect_python(text: str, dependency: str, symbols: list[str]) -> dict[str, Any]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"usages": [], "blind_spots": [f"SYNTAX_ERROR:{exc.lineno}"], "imports": []}
    aliases = _imports(tree, dependency)
    # Typed parameters give a bounded, inspectable object-to-API link. This is
    # deliberately not a general type inference engine.
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.annotation is not None:
            annotated = _symbol_of(node.annotation, aliases)
            if isinstance(node.annotation, ast.Name):
                annotated = aliases.get(node.annotation.id)
            if annotated:
                aliases[node.arg] = annotated
    usages: list[dict[str, Any]] = []
    blind: set[str] = set()
    wanted = set(symbols)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Call, ast.Attribute, ast.Name)):
            target = node.func if isinstance(node, ast.Call) else node
            full = _symbol_of(target, aliases)
            if isinstance(target, ast.Name):
                full = aliases.get(target.id)
            if full and full in wanted:
                kind = "call" if isinstance(node, ast.Call) else "reference"
                item = {"symbol": full, "line": node.lineno, "kind": kind}
                if item not in usages:
                    usages.append(item)
        if isinstance(node, ast.Call):
            name = _symbol_of(node.func, aliases)
            raw = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else "")
            if raw in {"getattr", "__import__", "import_module"}:
                blind.add("DYNAMIC_USAGE_UNRESOLVED")
            if any(isinstance(k, ast.keyword) and k.arg is None for k in node.keywords):
                blind.add("KWARGS_FLOW_UNRESOLVED")
            if name and isinstance(node.func, ast.Attribute) and node.func.attr == "__getattr__":
                blind.add("DYNAMIC_USAGE_UNRESOLVED")
    return {"usages": sorted(usages, key=lambda x: (x["line"], x["symbol"], x["kind"])),
            "blind_spots": sorted(blind), "imports": sorted(set(aliases.values()))}


def _missing_source_bundle(case: dict[str, Any], case_path: Path, missing: str,
                           known: list[Evidence]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "rin.bundle.v1", "project": case["project"],
        "dependency": case["dependency"], "old_version": case["old_version"],
        "new_version": case["new_version"], "mode": "RECORDED_FIXTURE",
        "input_hash_sha256": sha256(case_path.read_bytes()),
        "verdict": "UNKNOWN", "reason": f"Required source unavailable: {missing}",
        "scope": "Available local snapshots only", "unknown_reasons": ["SOURCE_UNAVAILABLE"],
        "findings": [], "hypotheses": [], "timeline": [{"event": "SOURCE_UNAVAILABLE", "id": missing}],
        "skeptic": {"checks": [], "challenges": ["SOURCE_UNAVAILABLE"],
                    "changed_hypotheses": 0, "changed_verdict": False},
        "receipts": [r.as_dict() for r in known],
        "sponsors": {"zetaris": "NOT_USED_IN_THIS_RUN", "meterless": "NOT_USED_IN_THIS_RUN",
                     "nemotron": "NOT_USED_IN_THIS_RUN", "cursor": "NOT_CLAIMED"},
    }
    result["evidence_hash_sha256"] = sha256(canonical([r.content_hash_sha256 for r in known]))
    result["verification"] = verify_bundle(result)
    return result


def investigate(case_path: Path) -> dict[str, Any]:
    case_path = case_path.resolve()
    case = json.loads(case_path.read_text(encoding="utf-8"))
    required = {"project", "dependency", "old_version", "new_version", "manifest_path", "release_notes", "changes", "python_files"}
    if not required <= case.keys():
        raise ValueError("missing case fields: " + ", ".join(sorted(required - case.keys())))
    if not isinstance(case["changes"], list) or not isinstance(case["python_files"], list):
        raise ValueError("changes and python_files must be lists")
    if not case["python_files"]:
        raise ValueError("at least one project Python file is required")
    base = case_path.parent
    rel = case["release_notes"]
    notes_path = (base / rel["path"]).resolve()
    if not notes_path.is_relative_to(base):
        raise ValueError("release path escapes case directory")
    if not notes_path.is_file():
        return _missing_source_bundle(case, case_path, rel["path"], [])
    receipts: list[Evidence] = [receipt(notes_path, source_type="PUBLIC_RELEASE_SNAPSHOT" if rel.get("url") else "LOCAL_FIXTURE",
                                        source_ref=rel.get("url") or str(notes_path),
                                        version=case["new_version"], span="", result="release snapshot")]
    note_text = receipts[0].snapshot
    unresolved: set[str] = set()
    findings: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    timeline: list[dict[str, str]] = []
    skeptic_reopened = 0
    project_snapshots: list[tuple[str, str, Evidence]] = []
    manifest_path = (base / case["manifest_path"]).resolve()
    if not manifest_path.is_relative_to(base):
        raise ValueError("manifest path escapes case directory")
    if not manifest_path.is_file():
        return _missing_source_bundle(case, case_path, case["manifest_path"], receipts)
    manifest = receipt(manifest_path, source_type="PROJECT_MANIFEST",
        source_ref=case["manifest_path"], version=case.get("project_commit", "UNPINNED_LOCAL_SNAPSHOT"),
        span="", result="requirements snapshot")
    receipts.append(manifest)
    upstream_manifest = case.get("upstream_manifest_path")
    if upstream_manifest:
        upstream_path = (base / upstream_manifest).resolve()
        if not upstream_path.is_relative_to(base):
            raise ValueError("upstream manifest path escapes case directory")
        if not upstream_path.is_file():
            return _missing_source_bundle(case, case_path, upstream_manifest, receipts)
        receipts.append(receipt(upstream_path, source_type="UPSTREAM_PROJECT_MANIFEST",
            source_ref=upstream_manifest, version=case.get("project_commit", "UNPINNED_LOCAL_SNAPSHOT"),
            span="", result="upstream manifest snapshot"))
    dependency_name = re.sub(r"[-_.]+", "-", case["dependency"]).lower()
    pinned = []
    for line in manifest.snapshot.splitlines():
        match = re.fullmatch(r"\s*([A-Za-z0-9_.-]+)\s*==\s*([A-Za-z0-9_.+!-]+)\s*(?:#.*)?", line)
        if match and re.sub(r"[-_.]+", "-", match.group(1)).lower() == dependency_name:
            pinned.append(match.group(2))
    manifest_status = "PIN_MATCH" if pinned == [case["old_version"]] else "UNRESOLVED_OR_CONFLICTING"
    if manifest_status != "PIN_MATCH":
        unresolved.add("CONFLICTING_EVIDENCE" if pinned else "TRANSITIVE_PATH_UNVERIFIED")
    for path_str in case["python_files"]:
        path = (base / path_str).resolve()
        if not path.is_relative_to(base):
            raise ValueError("project path escapes case directory")
        if path.suffix != ".py":
            raise ValueError("only Python source files are supported")
        if not path.is_file():
            return _missing_source_bundle(case, case_path, path_str, receipts)
        r = receipt(path, source_type="PROJECT_CODE", source_ref=path_str,
                    version=case.get("project_commit", "UNPINNED_LOCAL_SNAPSHOT"),
                    span="", result="project source snapshot")
        receipts.append(r)
        project_snapshots.append((path_str, r.snapshot, r))
    for idx, change in enumerate(case["changes"], 1):
        symbol = change.get("symbol", "")
        span = change.get("release_span", "")
        if not symbol or not span or span not in note_text:
            unresolved.add("RELEASE_DELTA_INCOMPLETE")
            continue
        h_id = f"hyp_{idx:03d}"
        proposed = {"hypothesis_id": h_id, "release_change": span,
                    "potentially_affected_symbol": symbol,
                    "project_usage": [], "testable_claim": f"Project uses {symbol}",
                    "proposed_check": "AST import and symbol reference scan",
                    "state": "PROPOSED", "supporting_receipt_ids": [receipts[0].receipt_id],
                    "contradicting_receipt_ids": [], "next_action": "scan project snapshot"}
        ledger.append(proposed)
        timeline.append({"event": "HYPOTHESIS_PROPOSED", "id": h_id})
        proposed["state"] = "TESTING"
        matches: list[dict[str, Any]] = []
        change_blind: set[str] = set()
        for path_str, source, r in project_snapshots:
            result = inspect_python(source, case["dependency"], [symbol])
            if result["blind_spots"]:
                unresolved.update(result["blind_spots"])
                change_blind.update(result["blind_spots"])
            for usage in result["usages"]:
                matches.append({**usage, "file": path_str, "receipt_id": r.receipt_id})
        proposed["project_usage"] = matches
        if matches:
            proposed["state"] = "SUPPORTED"
            proposed["supporting_receipt_ids"] += sorted({m["receipt_id"] for m in matches})
            proposed["next_action"] = "review behavior and run differential test if available"
            findings.append({"symbol": symbol, "usage": matches,
                             "evidence_level": "L2_STATIC_USAGE",
                             "receipt_ids": proposed["supporting_receipt_ids"] + [manifest.receipt_id]})
            timeline.append({"event": "USAGE_CONFIRMED_PLAN_REVISED", "id": h_id})
        else:
            proposed["state"] = "REFUTED"
            proposed["contradicting_receipt_ids"] = [r.receipt_id for _, _, r in project_snapshots]
            proposed["next_action"] = "check transitive and dynamic paths before any no-action claim"
            timeline.append({"event": "DIRECT_USAGE_HYPOTHESIS_REFUTED", "id": h_id})
            if change_blind:
                # Keep the bounded direct-use refutation and open a separate
                # dynamic-path hypothesis; do not erase what was actually tested.
                dynamic_id = f"{h_id}_dynamic"
                ledger.append({"hypothesis_id": dynamic_id,
                    "release_change": span, "potentially_affected_symbol": symbol,
                    "project_usage": [],
                    "testable_claim": f"Dynamic or indirect usage may reach {symbol}",
                    "proposed_check": "Inspect dynamic imports, wrappers and keyword forwarding",
                    "state": "UNRESOLVED", "supporting_receipt_ids": [r.receipt_id for _, _, r in project_snapshots],
                    "contradicting_receipt_ids": [],
                    "next_action": "inspect dynamic usage before claiming absence"})
                timeline.append({"event": "SKEPTIC_REOPENED_DYNAMIC_PATH", "id": dynamic_id})
                skeptic_reopened += 1
    if not case["changes"]:
        unresolved.add("RELEASE_DELTA_INCOMPLETE")
    if not case.get("complete_project_snapshot", False):
        unresolved.add("INSUFFICIENT_TEST_COVERAGE")
    if not case.get("transitive_paths_verified", False):
        unresolved.add("TRANSITIVE_PATH_UNVERIFIED")
    differential = None
    reports = case.get("differential_reports")
    if reports:
        if not isinstance(reports, dict) or set(reports) != {"old", "new"}:
            raise ValueError("differential_reports must contain old and new paths")
        observed = {}
        for phase in ("old", "new"):
            report_path = (base / reports[phase]).resolve()
            if not report_path.is_relative_to(base):
                raise ValueError("differential report path escapes case directory")
            if not report_path.is_file():
                return _missing_source_bundle(case, case_path, reports[phase], receipts)
            report_receipt = receipt(report_path, source_type="LOCAL_DIFFERENTIAL_RUN",
                source_ref=reports[phase], version=case["old_version" if phase == "old" else "new_version"],
                span="", result="recorded local runtime output")
            receipts.append(report_receipt)
            observed[phase] = json.loads(report_receipt.snapshot)
            observed[phase]["receipt_id"] = report_receipt.receipt_id
        valid = (observed["old"].get("dependency") == case["dependency"]
                 and observed["new"].get("dependency") == case["dependency"]
                 and observed["old"].get("dependency_version") == case["old_version"]
                 and observed["new"].get("dependency_version") == case["new_version"]
                 and observed["old"].get("outcome") == "PASS"
                 and observed["new"].get("outcome") == "FAIL")
        differential = {"status": "RECORDED_LOCAL_DIFFERENTIAL" if valid else "CONFLICTING_EVIDENCE",
                        "old": observed["old"], "new": observed["new"]}
        if valid:
            timeline.append({"event": "LOCAL_DIFFERENTIAL_FAILURE_RECORDED", "id": observed["new"]["receipt_id"]})
            for hypothesis in ledger:
                if hypothesis["state"] == "SUPPORTED":
                    hypothesis["next_action"] = "review failed differential check in target CI and test a compatible upgrade"
        else:
            unresolved.add("CONFLICTING_EVIDENCE")
    if not findings and not unresolved:
        # This MVP intentionally avoids proving NO_ACTION from static absence alone.
        unresolved.add("INSUFFICIENT_TEST_COVERAGE")
    # A bounded skeptic pass can only challenge or downgrade a no-action claim.
    skeptic = {"checks": ["getattr/import_module", "**kwargs", "transitive paths", "source coverage"],
               "challenges": sorted(unresolved), "changed_hypotheses": skeptic_reopened,
               "changed_verdict": False}
    verdict = "REVIEW" if findings and manifest_status == "PIN_MATCH" and "CONFLICTING_EVIDENCE" not in unresolved else "UNKNOWN"
    if "CONFLICTING_EVIDENCE" in unresolved:
        reason = "Conflicting source or runtime evidence requires a targeted recheck."
    elif findings and manifest_status == "PIN_MATCH":
        reason = ("Recorded local differential run changed PASS to FAIL for the selected versions; review the upgrade path."
                  if differential and differential["status"] == "RECORDED_LOCAL_DIFFERENTIAL"
                  else "Release note claims intersect with static project usage; behavior still needs review.")
    elif manifest_status != "PIN_MATCH":
        reason = "Project dependency pin is missing or conflicts with the requested old version."
    else:
        reason = "Direct usage was not confirmed; available scope cannot establish no impact."
    result: dict[str, Any] = {
        "schema": "rin.bundle.v1", "project": case["project"], "dependency": case["dependency"],
        "old_version": case["old_version"], "new_version": case["new_version"],
        "mode": case.get("mode", "RECORDED_FIXTURE"),
        "input_hash_sha256": sha256(case_path.read_bytes()),
        "verdict": verdict, "reason": reason,
        "scope": "Listed local Python files and the supplied release-note snapshot only",
        "manifest_status": manifest_status,
        "manifest_provenance": case.get("manifest_provenance", "PROJECT_SNAPSHOT_NOT_INDEPENDENTLY_ATTESTED"),
        "differential": differential,
        "unknown_reasons": sorted(unresolved), "findings": findings,
        "hypotheses": ledger, "timeline": timeline, "skeptic": skeptic,
        "receipts": [r.as_dict() for r in receipts],
        "sponsors": {"zetaris": "NOT_USED_IN_THIS_RUN", "meterless": "NOT_USED_IN_THIS_RUN",
                     "nemotron": "NOT_USED_IN_THIS_RUN", "cursor": "NOT_CLAIMED"},
    }
    result["evidence_hash_sha256"] = sha256(canonical([r.content_hash_sha256 for r in receipts]))
    result["verification"] = verify_bundle(result)
    return result


def verify_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    by_id = {}
    for r in bundle.get("receipts", []):
        if not isinstance(r, dict):
            problems.append("non-object receipt")
            continue
        if sha256(r.get("snapshot", "").encode()) != r.get("content_hash_sha256"):
            problems.append("receipt hash mismatch: " + str(r.get("receipt_id")))
        expected_id = "rcpt_" + sha256(canonical([r.get("source_url_or_local_reference"),
                r.get("content_hash_sha256"), r.get("exact_span_or_line")]))[:16]
        if expected_id != r.get("receipt_id"):
            problems.append("receipt identity mismatch: " + str(r.get("receipt_id")))
        if r.get("exact_span_or_line") and r["exact_span_or_line"] not in r.get("snapshot", ""):
            problems.append("receipt span mismatch: " + str(r.get("receipt_id")))
        by_id[r.get("receipt_id")] = r
    if len(by_id) != len(bundle.get("receipts", [])):
        problems.append("duplicate receipt id")
    for h in bundle.get("hypotheses", []):
        for rid in h.get("supporting_receipt_ids", []) + h.get("contradicting_receipt_ids", []):
            if rid not in by_id:
                problems.append("missing hypothesis citation: " + str(rid))
    for finding in bundle.get("findings", []):
        for rid in finding.get("receipt_ids", []):
            if rid not in by_id:
                problems.append("missing finding citation: " + str(rid))
    differential = bundle.get("differential")
    if differential:
        for phase in ("old", "new"):
            report = differential.get(phase, {})
            cited = by_id.get(report.get("receipt_id"))
            if not cited or cited.get("source_type") != "LOCAL_DIFFERENTIAL_RUN":
                problems.append("missing differential citation: " + phase)
            else:
                try:
                    expected_report = json.loads(cited["snapshot"])
                except (KeyError, ValueError, TypeError):
                    problems.append("invalid differential snapshot: " + phase)
                else:
                    if {k: v for k, v in report.items() if k != "receipt_id"} != expected_report:
                        problems.append("differential report mismatch: " + phase)
        if differential.get("status") == "RECORDED_LOCAL_DIFFERENTIAL":
            old, new = differential.get("old", {}), differential.get("new", {})
            if (old.get("outcome"), new.get("outcome")) != ("PASS", "FAIL"):
                problems.append("invalid differential transition")
            if (old.get("dependency_version") != bundle.get("old_version")
                    or new.get("dependency_version") != bundle.get("new_version")):
                problems.append("differential version mismatch")
    expected = sha256(canonical([r.get("content_hash_sha256") for r in bundle.get("receipts", [])]))
    if expected != bundle.get("evidence_hash_sha256") and "evidence_hash_sha256" in bundle:
        problems.append("evidence aggregate hash mismatch")
    if bundle.get("verdict") == "NO_ACTION":
        problems.append("NO_ACTION unsupported by current MVP verification contract")
    return {"ok": not problems, "problems": problems, "receipt_count": len(by_id)}
