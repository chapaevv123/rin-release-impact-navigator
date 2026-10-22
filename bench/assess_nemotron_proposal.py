"""Optional offline path: model JSON -> verified RIN sponsor chain -> hypothesis gate.

No API request is made here. Keep the input local until account-level free access
and the actual NVIDIA inference have separate receipts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rin.nemotron_optional import gate  # noqa: E402
from capture_zetaris_live_e2e import BUNDLE, JOIN, OUTPUT, evaluate  # noqa: E402


def assess(response: str | None, model_id: str) -> dict:
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
    join = json.loads(JOIN.read_text(encoding="utf-8"))
    saved = json.loads(OUTPUT.read_text(encoding="utf-8"))
    decision = evaluate(bundle, join, saved.get("meterless_graph"))
    return gate(bundle, response, model_id, decision)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--response-file", type=Path, help="Sanitized actual model JSON; omit when access is blocked")
    parser.add_argument("--model-id", default="nvidia/nemotron-3.5-lightning-30b-a3b")
    args = parser.parse_args()
    response = args.response_file.read_text(encoding="utf-8") if args.response_file else None
    print(json.dumps(assess(response, args.model_id), indent=2))
