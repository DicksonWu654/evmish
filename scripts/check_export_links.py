#!/usr/bin/env python3
"""Check local Markdown links and site evidence paths in a public export."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"!?\[[^\]]*\]\((<[^>]+>|[^)]+)\)")
REFERENCE = re.compile(r"^\s*\[[^]]+\]:\s*(<[^>]+>|\S+)", re.M)
HTML_LINK = re.compile(r'''(?:href|src)=["']([^"']+)["']''')
SCHEMES = ("http:", "https:", "mailto:", "data:", "javascript:")
issues: list[str] = []
markdown_count = evidence_count = 0


def check(path: Path, target: str, *, repository_relative: bool = False) -> None:
    target = target.strip().strip("<>")
    if not target or target.startswith(SCHEMES):
        return
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return
    relative = unquote(parsed.path)
    if not relative and not repository_relative:
        return
    base = ROOT if repository_relative else path.parent
    resolved = (base / relative).resolve()
    if not resolved.is_relative_to(ROOT) or not resolved.exists():
        issues.append(f"{path.relative_to(ROOT)}: {target}")


for path in ROOT.rglob("*.md"):
    if ".git" in path.parts:
        continue
    body = path.read_text(encoding="utf-8")
    body = re.sub(r"^```.*?^```\s*$", "", body, flags=re.M | re.S)
    for match in (*LINK.finditer(body), *REFERENCE.finditer(body), *HTML_LINK.finditer(body)):
        markdown_count += 1
        check(path, match.group(1))


def evidence(value: object, key: str = ""):
    global evidence_count
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from evidence(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from evidence(child, key)
    elif isinstance(value, str) and "evidence" in key.lower() and key.lower() != "evidence_dates":
        evidence_count += 1
        yield value


data_path = ROOT / "site/data/data.json"
for target in evidence(json.loads(data_path.read_text(encoding="utf-8"))):
    check(data_path, target, repository_relative=True)

print(f"links: {markdown_count} Markdown targets, {evidence_count} data evidence paths; {len(issues)} unresolved")
for issue in issues[:50]:
    print(issue)
raise SystemExit(bool(issues))
