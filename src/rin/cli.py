"""RIN command-line entry points."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import investigate, verify_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Release Impact Navigator")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("investigate", help="Analyze pinned local evidence snapshots")
    scan.add_argument("case", type=Path)
    scan.add_argument("--out", type=Path)
    check = sub.add_parser("verify", help="Independently verify a saved evidence bundle")
    check.add_argument("bundle", type=Path)
    replay = sub.add_parser("replay", help="Recompute and compare canonical outcome")
    replay.add_argument("case", type=Path)
    replay.add_argument("bundle", type=Path)
    args = parser.parse_args()
    if args.command == "investigate":
        result = investigate(args.case)
        rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
        raise SystemExit(0 if result["verification"]["ok"] else 2)
    if args.command == "verify":
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
        status = verify_bundle(bundle)
        print(json.dumps(status, indent=2))
        raise SystemExit(0 if status["ok"] else 2)
    saved = json.loads(args.bundle.read_text(encoding="utf-8"))
    current = investigate(args.case)
    keys = ("input_hash_sha256", "evidence_hash_sha256", "verdict", "unknown_reasons", "findings")
    matched = all(saved.get(key) == current.get(key) for key in keys)
    status = {"mode": "REPLAY", "matched": matched, "compared": keys,
              "saved_verified": verify_bundle(saved)["ok"],
              "current_verified": current["verification"]["ok"]}
    print(json.dumps(status, indent=2))
    raise SystemExit(0 if matched and status["saved_verified"] and status["current_verified"] else 2)


if __name__ == "__main__":
    main()
