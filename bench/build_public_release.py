"""Build and audit a curated public GitHub candidate ZIP from the current Git tree."""
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".gitattributes", ".gitignore", "ARCHITECTURE.md", "DEVLOG.md", "LICENSE",
    "LIMITATIONS.md", "README.md", "SPONSOR_TECH.md", "meterless_graph.ts",
    "pyproject.toml", "rin.py", "vercel.json",
}
UI_FILES = {"ui/index.html", "ui/app.js", "ui/v3_7.css", "ui/v3_8.css", "ui/v3_9.css"}
DOC_FILES = {
    "docs/CURSOR_AGENT_EVIDENCE.md", "docs/DEMO_SCRIPT.md", "docs/GITHUB_PRESENTATION.md",
    "docs/HOSTING.md", "docs/NEMOTRON_STATUS.md", "docs/PROVENANCE.md",
    "docs/RELEASE_NOTES_V4.md", "docs/RIN_JUDGE_SLIDES.pdf", "docs/ZETARIS_SOURCE_PLAN.md",
    "docs/design/RIN_APPROVED_DESIGN.png",
    "docs/media/investigation_canvas.gif", "docs/media/hypothesis_ledger.gif",
    "docs/media/sponsor_replays.gif", "docs/media/showcase_capture_manifest.json",
}
ARTIFACT_FILES = {
    "artifacts/development_eval.json", "artifacts/flask_3_1_e2e_bundle.json",
    "artifacts/meterless_real_case_receipt.json", "artifacts/nemotron_owner_key_inference_receipt.json",
    "artifacts/nemotron_v3_4_inference_receipt.json", "artifacts/starlette_httpx_028_bundle.json",
    "artifacts/zetaris_live_e2e_receipt.json", "artifacts/zetaris_live_join_receipt.json",
    "artifacts/zetaris_v3_1_gate.json",
    "artifacts/screenshots/v3_9_1920_investigation.png",
}
BENCH_FILES = {
    "bench/assess_nemotron_proposal.py",
    "bench/build_public_release.py", "bench/build_static_demo.py",
    "bench/capture_showcase_gifs.py", "bench/capture_zetaris_live_e2e.py",
    "bench/check_package_links.py", "bench/evaluate_development.py",
}
PREFIXES = ("src/", "tests/", "samples/", "vendor/")
SECRET_PATTERNS = {
    "NVIDIA_KEY": re.compile(rb"nvapi-[A-Za-z0-9_-]{12,}"),
    "AWS_KEY": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "OPENAI_KEY": re.compile(rb"sk-[A-Za-z0-9_-]{24,}"),
    "PRIVATE_KEY": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "PERSONAL_WINDOWS_PATH": re.compile(rb"C:\\Users\\", re.I),
}


def selected(name: str) -> bool:
    return (name in ROOT_FILES | UI_FILES | DOC_FILES | ARTIFACT_FILES | BENCH_FILES
            or name.startswith(PREFIXES))


def audit_name(name: str) -> None:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise RuntimeError(f"unsafe archive path: {name}")
    if any(part.lower() in {".env", ".secrets", "secrets", ".aws", ".ssh"}
           or part.lower().startswith(".env.") for part in path.parts):
        raise RuntimeError(f"private configuration path: {name}")


def audit_content(name: str, payload: bytes) -> None:
    for label, pattern in SECRET_PATTERNS.items():
        if pattern.search(payload):
            raise RuntimeError(f"{label} pattern in {name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True, help="new local ZIP path")
    args = parser.parse_args()
    output = args.out.resolve()
    if output.exists():
        raise RuntimeError(f"archive already exists: {output}")
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    selected_names = sorted(name for name in tracked if name and selected(name))
    required = ROOT_FILES | UI_FILES | DOC_FILES | ARTIFACT_FILES | BENCH_FILES
    missing = required - set(selected_names)
    if missing:
        raise RuntimeError(f"required public files not committed: {sorted(missing)}")
    selected_set = set(selected_names)
    broken_links = []
    for name in selected_names:
        if not name.endswith(".md") or name.startswith("samples/"):
            continue  # Upstream snapshots retain their original source links.
        content = (ROOT / name).read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", content):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            linked = posixpath.normpath(posixpath.join(posixpath.dirname(name),
                                                     target.split("#", 1)[0]))
            if linked not in selected_set:
                broken_links.append(f"{name} -> {target}")
    if broken_links:
        raise RuntimeError(f"links absent from public archive: {broken_links}")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    entries = []
    for name in selected_names:
        audit_name(name)
        source = ROOT / name
        if not source.is_file() or source.is_symlink():
            raise RuntimeError(f"missing or linked source: {name}")
        payload = source.read_bytes()
        audit_content(name, payload)
        entries.append({"path": name, "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest()})
    manifest = {"schema": "rin.public_release.v4", "source_git_head": head,
                "mode": "LOCAL_PUBLICATION_CANDIDATE_NOT_PUBLISHED",
                "files": entries, "excluded": "credentials, .env, internal logs, old QA profiles and obsolete screenshots"}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as archive:
        for item in entries:
            archive.write(ROOT / item["path"], arcname=item["path"])
        archive.writestr("PUBLIC_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
    with zipfile.ZipFile(output) as archive:
        archive.testzip()
        names = set(archive.namelist())
        if names != {item["path"] for item in entries} | {"PUBLIC_MANIFEST.json"}:
            raise RuntimeError("archive file set differs from manifest")
        for item in entries:
            data = archive.read(item["path"])
            if hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise RuntimeError(f"archive hash mismatch: {item['path']}")
            audit_content(item["path"], data)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(json.dumps({"archive": str(output), "files": len(entries) + 1,
                      "bytes": output.stat().st_size, "sha256": digest,
                      "source_git_head": head, "security_findings": 0}, indent=2))


if __name__ == "__main__":
    main()
