"""Check local Markdown links before publishing the standalone repository."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
broken = []
checked = 0
for source in ROOT.rglob("*.md"):
    if ".git" in source.parts or source.is_relative_to(ROOT / "samples"):
        # Upstream snapshots retain original relative links as evidence bytes.
        continue
    content = source.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", content):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = (source.parent / target.split("#", 1)[0]).resolve()
        checked += 1
        if not path.is_file():
            broken.append(f"{source.relative_to(ROOT)} -> {target}")
print(f"local_links_checked={checked}, broken={len(broken)}")
for item in broken:
    print(item)
raise SystemExit(1 if broken else 0)
