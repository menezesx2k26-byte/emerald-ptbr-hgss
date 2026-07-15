from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from release import release_tag, release_version

BLOCK_RE = re.compile(r'(?ms)^(?P<label>[A-Za-z_][A-Za-z0-9_]*::?\n)(?P<body>(?:[ \t]*\.string[ \t]+"(?:\\.|[^"\\])*"[ \t]*\n)+)')
LINE_RE = re.compile(r'\.string\s+"((?:\\.|[^"\\])*)"')
C_RE = re.compile(r'_\("((?:\\.|[^"\\])*)"\)')
PLACEHOLDER_RE = re.compile(r'\{[^{}]+\}')
JAPANESE_RE = re.compile(r'[\u3040-\u30ff\u31f0-\u31ff]')
REPLACEMENTS = {
    '‡': ':', '—': '-', '–': '-', '°': 'º',
    '！': '!', '？': '?', '\u3000': ' ', 'Ş': 'S', 'ї': 'i',
}


def parse_allowed(project: Path) -> set[str]:
    allowed: set[str] = set()
    for line in (project / 'charmap.txt').read_text(encoding='utf-8').splitlines():
        match = re.match(r"^'((?:\\.|[^'])*)'\s*=", line)
        if not match:
            continue
        token = match.group(1)
        if token == r"\'":
            allowed.add("'")
        elif token.startswith('\\') and len(token) == 2:
            allowed.add(token[1])
        elif len(token) == 1:
            allowed.add(token)
    return allowed


def original_text(project: Path, path: Path) -> str:
    relative = path.relative_to(project).as_posix()
    return subprocess.check_output(
        ['git', '-C', str(project), 'show', f'HEAD:{relative}'],
        text=True,
        encoding='utf-8',
    )


def normalize_known(raw: str) -> tuple[str, int]:
    replacements = 0
    for old, new in REPLACEMENTS.items():
        replacements += raw.count(old)
        raw = raw.replace(old, new)
    return raw, replacements


def unsupported(raw: str, allowed: set[str]) -> list[str]:
    visible = PLACEHOLDER_RE.sub('', raw)
    visible = re.sub(r'\\[nlp]', '', visible)
    visible = visible.replace('\\"', '').replace('$', '')
    return sorted({character for character in visible if character not in allowed})


def sanitize_assembly(project: Path, path: Path, allowed: set[str], report: dict[str, object]) -> None:
    current = path.read_text(encoding='utf-8')
    original = original_text(project, path)
    original_by_label = {match.group('label').strip(): match for match in BLOCK_RE.finditer(original)}
    changes: list[tuple[int, int, str]] = []

    for match in BLOCK_RE.finditer(current):
        original_match = original_by_label.get(match.group('label').strip())
        if original_match is None:
            continue
        raw = ''.join(LINE_RE.findall(match.group('body')))
        original_raw = ''.join(LINE_RE.findall(original_match.group('body')))
        fixed, count = normalize_known(raw)
        bad = unsupported(fixed, allowed)
        unexpected_japanese = bool(JAPANESE_RE.search(fixed) and not JAPANESE_RE.search(original_raw))
        if bad or unexpected_japanese:
            body = original_match.group('body')
            report['reverted_strings'] += 1
            for character in bad:
                report['unsupported_characters'][character] = report['unsupported_characters'].get(character, 0) + 1
        elif fixed != raw:
            body = f'\t.string "{fixed}"\n'
            report['normalized_characters'] += count
        else:
            continue
        changes.append((match.start('body'), match.end('body'), body))

    updated = current
    for start, end, value in reversed(changes):
        updated = updated[:start] + value + updated[end:]
    if updated != current:
        path.write_text(updated, encoding='utf-8')
        report['files_changed'].append(path.relative_to(project).as_posix())


def sanitize_c(project: Path, path: Path, allowed: set[str], report: dict[str, object]) -> None:
    current = path.read_text(encoding='utf-8')
    original = original_text(project, path)
    current_matches = list(C_RE.finditer(current))
    original_matches = list(C_RE.finditer(original))
    if len(current_matches) != len(original_matches):
        raise RuntimeError(f'C string count changed in {path.relative_to(project)}')
    changes: list[tuple[int, int, str]] = []

    for match, original_match in zip(current_matches, original_matches):
        raw = match.group(1)
        original_raw = original_match.group(1)
        fixed, count = normalize_known(raw)
        bad = unsupported(fixed, allowed)
        unexpected_japanese = bool(JAPANESE_RE.search(fixed) and not JAPANESE_RE.search(original_raw))
        if bad or unexpected_japanese:
            fixed = original_raw
            report['reverted_strings'] += 1
            for character in bad:
                report['unsupported_characters'][character] = report['unsupported_characters'].get(character, 0) + 1
        elif fixed != raw:
            report['normalized_characters'] += count
        if fixed != raw:
            changes.append((match.start(1), match.end(1), fixed))

    updated = current
    for start, end, value in reversed(changes):
        updated = updated[:start] + value + updated[end:]
    if updated != current:
        path.write_text(updated, encoding='utf-8')
        report['files_changed'].append(path.relative_to(project).as_posix())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    allowed = parse_allowed(project)

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

    report: dict[str, object] = {
        'version': release_version(),
        'normalized_characters': 0,
        'reverted_strings': 0,
        'unsupported_characters': {},
        'files_changed': [],
    }
    for path in assembly_files:
        sanitize_assembly(project, path, allowed, report)
    for path in c_files:
        sanitize_c(project, path, allowed, report)

    remaining: list[dict[str, object]] = []
    for path in assembly_files + c_files:
        text = path.read_text(encoding='utf-8')
        matches = BLOCK_RE.finditer(text) if path.suffix == '.inc' else C_RE.finditer(text)
        for match in matches:
            raw = ''.join(LINE_RE.findall(match.group('body'))) if path.suffix == '.inc' else match.group(1)
            bad = unsupported(raw, allowed)
            if bad:
                remaining.append({'file': path.relative_to(project).as_posix(), 'characters': bad})
                break
    report['remaining_problems'] = remaining
    report_path = args.report or project / f'charmap_sanitizer_{release_tag()}.json'
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if remaining:
        raise SystemExit('Unsupported charmap characters remain')


if __name__ == '__main__':
    main()
