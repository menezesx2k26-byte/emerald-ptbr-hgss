from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from release import release_tag, release_version

STRING_RE = re.compile(r'(?P<prefix>\.string\s+")(?P<body>(?:\\.|[^"\\])*)(?P<suffix>")')
C_RE = re.compile(r'(?P<prefix>_\(")(?P<body>(?:\\.|[^"\\])*)(?P<suffix>"\))')
PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")
ASSEMBLY_BLOCK_RE = re.compile(
    r'(?ms)^(?P<label>[A-Za-z_][A-Za-z0-9_]*::?\n)'
    r'(?P<body>(?:[ \t]*\.string[ \t]+"(?:\\.|[^"\\])*"[ \t]*\n)+)'
)
ASSEMBLY_LINE_RE = re.compile(r'\.string\s+"((?:\\.|[^"\\])*)"')

# Exact display strings exposed by the interactive P1 pass. They are
# normalized here after the reviewed dialogue pass so legacy mojibake and the
# shared YES/NO menu cannot leak into otherwise translated interfaces.
CORE_UI_REPLACEMENTS = {
    "gText_YesNo": r"SIM\nNÃO",
    "gText_Yes": "SIM",
    "gText_No": "NÃO",
    "gText_No4": "NÃO",
}

# The first playable route is exercised frame by frame. Any malformed or
# visibly rough line found there is pinned by label rather than repaired with
# broad substitutions. Move names and descriptions are deliberately excluded.
P1_ASSEMBLY_REPLACEMENTS = (
    (
        "data/maps/LittlerootTown_BrendansHouse_2F/scripts.inc",
        "PlayersHouse_2F_Text_HowDoYouLikeYourRoom",
        (
            r"MÃE: {JOGADOR}, gostou do seu\nquarto novo?\p",
            r"Ótimo! Está tudo bem\narrumado!\p",
            r"Também terminaram de trazer\ntudo para o andar de baixo.\p",
            r"Os POKéMON carregadores são\nmuito práticos!\p",
            r"Ah, confira se está tudo\ncerto na sua mesa.$",
        ),
    ),
    (
        "data/maps/LittlerootTown_BrendansHouse_1F/scripts.inc",
        "PlayersHouse_1F_Text_MaybeDadWillBeOn",
        (
            r"MÃE: Olhe! É o GINÁSIO DE\nPETALBURG!\p",
            r"Talvez seu PAI apareça!$",
        ),
    ),
    (
        "data/maps/LittlerootTown_BrendansHouse_1F/scripts.inc",
        "PlayersHouse_1F_Text_ReportFromPetalburgGym",
        (
            r"REPÓRTER: ...Transmitimos esta\nreportagem em frente ao\lGINÁSIO DE PETALBURG.$",
        ),
    ),
    (
        "data/maps/LittlerootTown_BrendansHouse_1F/scripts.inc",
        "PlayersHouse_1F_Text_ItsOverWeMissedHim",
        (
            r"MÃE: Ah... Acabou.\p",
            r"Achei que seu PAI apareceria,\nmas perdemos a parte dele.\p",
            r"Que pena.$",
        ),
    ),
    (
        "data/maps/LittlerootTown_BrendansHouse_1F/scripts.inc",
        "PlayersHouse_1F_Text_GoIntroduceYourselfNextDoor",
        (
            r"Ah, sim!\p",
            r"Um amigo do seu PAI mora\nnesta cidade.\p",
            r"Ele se chama PROF. BIRCH.\p",
            r"A casa dele fica ao lado.\nVá se apresentar.$",
        ),
    ),
)


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


def c_constant_pattern(label: str) -> re.Pattern[str]:
    return re.compile(
        rf'(?m)^(?P<prefix>(?:ALIGNED\(4\)\s+)?const u8 {re.escape(label)}\[\]\s*=\s*_\(")'
        rf'(?P<body>(?:\\.|[^"\\])*)'
        rf'(?P<suffix>"\);(?:\s*//.*)?)$'
    )


def normalize_core_ui_strings(path: Path) -> list[dict[str, str]]:
    original = path.read_text(encoding='utf-8')
    updated = original
    applied: list[dict[str, str]] = []

    for label, replacement in CORE_UI_REPLACEMENTS.items():
        pattern = c_constant_pattern(label)
        matches = list(pattern.finditer(updated))
        if len(matches) != 1:
            raise RuntimeError(f"Expected one {label} in {path}, found {len(matches)}")
        match = matches[0]
        current = match.group('body')
        if Counter(PLACEHOLDER_RE.findall(current)) != Counter(PLACEHOLDER_RE.findall(replacement)):
            raise RuntimeError(f"Placeholder mismatch in {label}")
        updated = updated[:match.start('body')] + replacement + updated[match.end('body'):]
        applied.append({"label": label, "before": current, "after": replacement})

    if updated != original:
        path.write_text(updated, encoding='utf-8')
    return applied


def normalize_p1_assembly_strings(project: Path) -> list[dict[str, object]]:
    applied: list[dict[str, object]] = []
    for relative, label, lines in P1_ASSEMBLY_REPLACEMENTS:
        path = project / relative
        original = path.read_text(encoding='utf-8')
        matches = [
            match for match in ASSEMBLY_BLOCK_RE.finditer(original)
            if match.group('label').rstrip(':\n') == label
        ]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one {label} block in {relative}, found {len(matches)}")
        match = matches[0]
        current = ''.join(ASSEMBLY_LINE_RE.findall(match.group('body')))
        replacement = ''.join(lines)
        if Counter(PLACEHOLDER_RE.findall(current)) != Counter(PLACEHOLDER_RE.findall(replacement)):
            raise RuntimeError(f"Placeholder mismatch in {label}")
        if current.endswith('$') != replacement.endswith('$'):
            raise RuntimeError(f"Terminator mismatch in {label}")
        body = ''.join(f'\t.string "{line}"\n' for line in lines)
        updated = original[:match.start('body')] + body + original[match.end('body'):]
        path.write_text(updated, encoding='utf-8')
        applied.append({
            'file': relative,
            'label': label,
            'before_characters': len(current),
            'after_characters': len(replacement),
        })
    return applied


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

    strings_path = project / 'src/strings.c'
    core_ui = normalize_core_ui_strings(strings_path)
    if core_ui and 'src/strings.c' not in files_changed:
        files_changed.append('src/strings.c')

    p1_assembly = normalize_p1_assembly_strings(project)
    for item in p1_assembly:
        if item['file'] not in files_changed:
            files_changed.append(str(item['file']))

    remaining = []
    for path in assembly_files + c_files:
        if '\\"' in path.read_text(encoding='utf-8'):
            remaining.append(path.relative_to(project).as_posix())

    report = {
        'version': release_version(),
        'quotes_converted': quote_count,
        'core_ui_strings_normalized': core_ui,
        'p1_assembly_strings_normalized': p1_assembly,
        'files_changed': files_changed,
        'remaining_escaped_quotes': remaining,
        'move_names_policy': 'English move names and descriptions preserved',
    }
    report_path = args.report or project / f'display_quote_sanitizer_{release_tag()}.json'
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if remaining:
        raise SystemExit('ASCII display quotes remain')


if __name__ == '__main__':
    main()
