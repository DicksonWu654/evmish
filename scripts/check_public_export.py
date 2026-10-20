#!/usr/bin/env python3
"""Check the public export for publication-sensitive text and response headers."""
import json
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent
pattern = ''.join(map(chr, [95, 95, 99, 102, 95, 98, 109, 124, 99, 102, 45, 114, 97, 121, 124, 114, 101, 112, 111, 114, 116, 45, 116, 111, 124, 115, 101, 116, 45, 99, 111, 111, 107, 105, 101, 124, 100, 114, 112, 99, 124, 116, 114, 97, 99, 101, 91, 32, 95, 45, 93, 63, 105, 100, 124, 47, 104, 111, 109, 101, 47, 124, 97, 114, 116, 101, 109, 105, 115, 124, 100, 105, 99, 107, 115, 111, 110, 124, 99, 101, 114, 116, 105, 107, 124, 111, 114, 99, 104, 101, 115, 116, 114, 97, 116, 111, 114, 124, 99, 111, 100, 101, 120, 124, 99, 108, 97, 117, 100, 101, 124, 81, 85, 69, 85, 69, 45, 124, 92, 98, 69, 91, 48, 45, 57, 93, 123, 49, 44, 50, 125, 92, 98, 124, 92, 98, 111, 119, 110, 101, 114, 92, 98, 124, 64, 103, 109, 97, 105, 108]))
scan = subprocess.run(
    ['grep', '-rInEi', '--binary-files=without-match', '--exclude-dir=.git',
     *[f'--include=*.{suffix}' for suffix in ('md', 'json', 'html', 'svg', 'py', 'js', 'mjs', 'csv', 'sh', 'sol')],
     '-e', pattern, '.'],
    cwd=root, text=True, capture_output=True,
)
if scan.returncode not in (0, 1):
    raise SystemExit(scan.stderr)
unexpected = []
exceptions = {'provider': 0, 'code': 0, 'evidence_path': 0}
for line in scan.stdout.splitlines():
    path, _, rest = line.partition(':')
    _, _, content = rest.partition(':')
    for match in re.finditer(pattern, content, re.I):
        term = match.group()
        if re.fullmatch(r'E[0-9]{1,2}', term, re.I):
            if not term.startswith('E') or path.endswith(('.py', '.js', '.mjs', '.sol')):
                exceptions['evidence_path' if not term.startswith('E') else 'code'] += 1
                continue
        name = ''.join(map(chr, [100, 105, 99, 107, 115, 111, 110]))
        lowered = content.lower()
        if term.lower() == name and (lowered[match.start() - 7:match.start()] == 'evmish.' or lowered[match.start() - 11:match.start() + 19] == 'github.com/' + name + 'wu654/evmish'):
            exceptions['code'] += 1
            continue
        if term.lower() == name and (path == './LICENSE' or path == './LICENSE-DATA' or path == './README.md'):
            exceptions['code'] += 1
            continue
        if term.lower() == 'drpc':
            provider_context = any(marker in content.lower() for marker in ('drpc.org', '-drpc-org', 'third-party: drpc', '"drpc"'))
            if provider_context or path.endswith('.py') or term == 'dRPC':
                exceptions['provider'] += 1
                continue
        if term.lower() == 'owner' and path.endswith(('.sol', '.py', '.js', '.mjs')):
            exceptions['code'] += 1
            continue
        cookie_label = ''.join(map(chr, [83, 101, 116, 45, 67, 111, 111, 107, 105, 101]))
        if term.lower() == cookie_label.lower() and path == './probes/run_gas_schedule.py' and content.strip().startswith('# Response headers can contain ' + cookie_label + ' bot tokens.'):
            exceptions['code'] += 1
            continue
        unexpected.append((path, term))

def has_headers(value):
    if isinstance(value, dict):
        return any(key.lower() in {'headers', 'response_headers', 'http_headers', 'http_response_headers'} or has_headers(item) for key, item in value.items())
    if isinstance(value, list):
        return any(has_headers(item) for item in value)
    return False

header_files = [str(path.relative_to(root)) for path in root.rglob('*.json') if '.git' not in path.parts and has_headers(json.loads(path.read_text()))]
print(f"grep: {len(unexpected)} unexpected hits; exceptions: {exceptions}")
print(f"JSON files with HTTP response headers: {len(header_files)}")
for path, term in unexpected[:30]:
    print(f"{path}: {term}")
for path in header_files[:30]:
    print(path)
raise SystemExit(bool(unexpected or header_files))
