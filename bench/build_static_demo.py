"""Build an allowlisted, credential-free static RIN replay demo."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rin.core import verify_bundle

OUTPUT = ROOT / "public_demo"
FILES = (
    "ui/index.html",
    "ui/app.js",
    "ui/v3_7.css",
    "ui/v3_8.css",
    "ui/v3_9.css",
    "artifacts/starlette_httpx_028_bundle.json",
    "artifacts/flask_3_1_e2e_bundle.json",
    "artifacts/zetaris_live_join_receipt.json",
    "artifacts/zetaris_live_e2e_receipt.json",
    "artifacts/nemotron_owner_key_inference_receipt.json",
    "docs/CURSOR_AGENT_EVIDENCE.md",
)
ROOT_PAGE = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="0;url=./ui/"><title>RIN — Release Impact Navigator</title><a href="./ui/">Open the recorded RIN investigation</a></html>\n"""


def main() -> None:
    if OUTPUT.is_symlink() or not OUTPUT.resolve().is_relative_to(ROOT.resolve()):
        raise RuntimeError("unsafe output directory")
    real = json.loads((ROOT / "artifacts/starlette_httpx_028_bundle.json").read_text(encoding="utf-8"))
    fixture = json.loads((ROOT / "artifacts/flask_3_1_e2e_bundle.json").read_text(encoding="utf-8"))
    for name, bundle in (("real", real), ("fixture", fixture)):
        result = verify_bundle(bundle)
        if not result["ok"]:
            raise RuntimeError(f"{name} evidence bundle failed verification: {result['problems']}")
    if real["verdict"] != "REVIEW" or len(real["receipts"]) != 6:
        raise RuntimeError("real case differs from approved replay evidence")
    join = json.loads((ROOT / "artifacts/zetaris_live_join_receipt.json").read_text(encoding="utf-8"))
    graph = json.loads((ROOT / "artifacts/zetaris_live_e2e_receipt.json").read_text(encoding="utf-8"))
    model = json.loads((ROOT / "artifacts/nemotron_owner_key_inference_receipt.json").read_text(encoding="utf-8"))
    if (join.get("status") != "CROSS_SOURCE_JOIN_VERIFIED"
            or join["join"]["http_status"] != 200
            or len(join["join"]["rows"]) != 1
            or graph.get("source_query_id") != join["join"]["query_id"]
            or graph["decision"]["verdict"] != "REVIEW"
            or model.get("http_status") != 200
            or model.get("usage", {}).get("total_tokens") != 516
            or model.get("citation_validation", {}).get("state") != "HYPOTHESIS"):
        raise RuntimeError("saved sponsor receipts differ from recorded evidence")
    expected = set(FILES) | {"index.html", "manifest.json"}
    if OUTPUT.exists():
        extras = {p.relative_to(OUTPUT).as_posix() for p in OUTPUT.rglob("*") if p.is_file()} - expected
        if extras:
            raise RuntimeError(f"unexpected files in static output: {sorted(extras)}")
    OUTPUT.mkdir(exist_ok=True)
    inventory = []
    for name in FILES:
        source = ROOT / name
        if not source.is_file() or source.is_symlink():
            raise RuntimeError(f"required public file unavailable: {name}")
        target = OUTPUT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        payload = target.read_bytes()
        inventory.append({"path": name, "bytes": len(payload),
                          "sha256": hashlib.sha256(payload).hexdigest()})
    (OUTPUT / "index.html").write_text(ROOT_PAGE, encoding="utf-8")
    root_bytes = (OUTPUT / "index.html").read_bytes()
    inventory.insert(0, {"path": "index.html", "bytes": len(root_bytes),
                         "sha256": hashlib.sha256(root_bytes).hexdigest()})
    manifest = {"schema": "rin.public_static_demo.v1", "mode": "SAVED_REPLAY_ONLY",
                "case": "Starlette 0.36.3 / HTTPX 0.27.2 -> 0.28.0",
                "live_sponsor_requests": False, "files": inventory}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "files": len(expected),
                      "bundle_receipts": len(real["receipts"]), "mode": manifest["mode"]}, indent=2))


if __name__ == "__main__":
    main()
