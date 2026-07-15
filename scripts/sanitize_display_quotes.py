from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from release import release_tag, release_version

STRING_RE = re.compile(r'(?P<prefix>\.string\s+")(?P<body>(?:\\.|[^"\\])*)(?P<suffix>")')
C_RE = re.compile(r'(?P<prefix>_\(")(?P<body>(?:\\.|[^"\\])*)(?P<suffix>"\))')


def replace_quotes(raw: str) -> tuple[str, int]:
    count = raw.count('\\"')
    if not count:
        return raw, 0
    parts = raw.split('\\"')
    output = parts[0]
    for index, part in enumerate(parts[1:]):
        output += ('“' if index % 2 == 0 else '”') + part
    return output, count


def process(path: Path, pattern: re.Pattern[str]) -> int:
    original = path.read_text(encoding='utf-8')
    replaced = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal replaced
        body, count = replace_quotes(match.group('body'))
        replaced += count
        return match.group('prefix') + body + match.group('suffix')

    updated = pattern.sub(repl, original)
    if updated != original:
        path.write_text(updated, encoding='utf-8')
    return replaced


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    project = args.project.resolve()

    assembly_files = sorted((project / 'data/maps').rglob('scripts.inc'))
    assembly_files += sorted((project / 'data/text').glob('*.inc'))
    assembly_files += sorted((project / 'data/scripts').glob('*.inc'))
    c_files = [
        project / 'src/strings.c', project / 'src/battle_message.c',
        project / 'src/berry.c', project / 'src/berry_blender.c',
        project / 'src/mystery_event_msg.c', project / 'src/data/union_room.h',
        project / 'src/data/text/match_call_messages.h',
    ]
    c_files = [path for path in c_files if path.exists()]

    files_changed: list[str] = []
    quote_count = 0
    for path in assembly_files:
        count = process(path, STRING_RE)
        if count:
            quote_count += count
            files_changed.append(path.relative_to(project).as_posix())
    for path in c_files:
        count = process(path, C_RE)
        if count:
            quote_count += count
            files_changed.append(path.relative_to(project).as_posix())

    remaining = []
    for path in assembly_files + c_files:
        if '\\"' in path.read_text(encoding='utf-8'):
            remaining.append(path.relative_to(project).as_posix())

    report = {
        'version': release_version(),
        'quotes_converted': quote_count,
        'files_changed': files_changed,
        'remaining_escaped_quotes': remaining,
    }
    report_path = args.report or project / f'display_quote_sanitizer_{release_tag()}.json'
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if remaining:
        raise SystemExit('ASCII display quotes remain')


if __name__ == '__main__':
    main()
