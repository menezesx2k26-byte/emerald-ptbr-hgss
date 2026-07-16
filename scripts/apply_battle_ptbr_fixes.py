from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from release import release_tag, release_version


PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")
ASSEMBLY_BLOCK_RE = re.compile(
    r'(?ms)^(?P<label>[A-Za-z_][A-Za-z0-9_]*::?\n)'
    r'(?P<body>(?:[ \t]*\.string[ \t]+"(?:\\.|[^"\\])*"[ \t]*\n)+)'
)
ASSEMBLY_LINE_RE = re.compile(r'\.string\s+"((?:\\.|[^"\\])*)"')


@dataclass(frozen=True)
class CFix:
    path: str
    label: str
    text: str


@dataclass(frozen=True)
class AssemblyFix:
    path: str
    label: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class CategoryFix:
    species: str
    category: str


# The visible battle interface is PT-BR. Move names and move descriptions are
# not listed here; they remain English and are injected through placeholders.
BATTLE_C_FIXES = (
    CFix("src/battle_message.c", "sText_PkmnGainedEXP", r"{B_BUFF1} recebeu{B_BUFF2}\n{B_BUFF3} pontos de EXP.!\p"),
    CFix("src/battle_message.c", "sText_ABoosted", " bônus de"),
    CFix("src/battle_message.c", "sText_PkmnGrewToLv", r"{B_BUFF1} subiu para o\nNv. {B_BUFF2}!{WAIT_SE}\p"),
    CFix("src/battle_message.c", "sText_PkmnLearnedMove", r"{B_BUFF1} aprendeu\n{B_BUFF2}!{WAIT_SE}\p"),
    CFix("src/battle_message.c", "sText_AttackMissed", r"O ataque de\n{B_ATK_NAME_WITH_PREFIX} errou!"),
    CFix("src/battle_message.c", "sText_PkmnProtectedItself", r"{B_DEF_NAME_WITH_PREFIX}\nse protegeu!"),
    CFix("src/battle_message.c", "sText_ItDoesntAffect", r"Não afeta\n{B_DEF_NAME_WITH_PREFIX}..."),
    CFix("src/battle_message.c", "sText_AttackerFainted", r"{B_ATK_NAME_WITH_PREFIX}\ndesmaiou!\p"),
    CFix("src/battle_message.c", "sText_TargetFainted", r"{B_DEF_NAME_WITH_PREFIX}\ndesmaiou!\p"),
    CFix("src/battle_message.c", "sText_CantEscape2", r"Não foi possível fugir!\p"),
    CFix("src/battle_message.c", "sText_AttackerCantEscape", r"{B_ATK_NAME_WITH_PREFIX} não\nconsegue fugir!"),
    CFix("src/battle_message.c", "sText_HitXTimes", r"Acertou {B_BUFF1} vez(es)!"),
    CFix("src/battle_message.c", "sText_NoPPLeft", r"Não há PP suficiente\npara este golpe!\p"),
    CFix("src/battle_message.c", "sText_ButNoPPLeft", r"Mas não havia PP suficiente\npara o golpe!"),
    CFix("src/battle_message.c", "sText_PkmnHasNoMovesLeft", r"{B_ACTIVE_NAME_WITH_PREFIX} não tem\nmais golpes!\p"),
    CFix("src/battle_message.c", "sText_PkmnMoveIsDisabled", r"{B_CURRENT_MOVE} de\n{B_ACTIVE_NAME_WITH_PREFIX} está bloqueado!\p"),
    CFix("src/battle_message.c", "sText_WildPkmnAppeared", r"{B_OPPONENT_MON1_NAME} selvagem\napareceu!\p"),
    CFix("src/battle_message.c", "sText_LegendaryPkmnAppeared", r"{B_OPPONENT_MON1_NAME} selvagem\napareceu!\p"),
    CFix("src/battle_message.c", "sText_WildPkmnAppearedPause", r"{B_OPPONENT_MON1_NAME} selvagem apareceu!{PAUSE 127}"),
    CFix("src/battle_message.c", "sText_GoPkmn", r"Vai, {B_PLAYER_MON1_NAME}!"),
    CFix("src/battle_message.c", "sText_GoPkmn2", r"Vai, {B_BUFF1}!"),
    CFix("src/battle_message.c", "sText_DoItPkmn", r"Agora, {B_BUFF1}!"),
    CFix("src/battle_message.c", "sText_GoForItPkmn", r"Vamos, {B_BUFF1}!"),
    CFix("src/battle_message.c", "sText_AttackerUsedX", r"{B_ATK_NAME_WITH_PREFIX} usou\n{B_BUFF2}"),
    CFix("src/battle_message.c", "sText_WildPkmnPrefix", "Selvagem "),
    CFix("src/battle_message.c", "sText_FoePkmnPrefix", "Oponente "),
    CFix("src/battle_message.c", "sText_FoePkmnPrefix2", "Oponente"),
    CFix("src/battle_message.c", "sText_AllyPkmnPrefix", "Aliado"),
    CFix("src/battle_message.c", "sText_FoePkmnPrefix3", "Oponente"),
    CFix("src/battle_message.c", "sText_AllyPkmnPrefix2", "Aliado"),
    CFix("src/battle_message.c", "sText_FoePkmnPrefix4", "Oponente"),
    CFix("src/battle_message.c", "sText_AllyPkmnPrefix3", "Aliado"),
    CFix("src/battle_message.c", "sText_Attack2", "ATAQUE"),
    CFix("src/battle_message.c", "sText_Defense2", "DEFESA"),
    CFix("src/battle_message.c", "sText_Speed", "VELOCIDADE"),
    CFix("src/battle_message.c", "sText_SpAtk2", "ATQ. ESP."),
    CFix("src/battle_message.c", "sText_SpDef2", "DEF. ESP."),
    CFix("src/battle_message.c", "sText_Accuracy", "precisão"),
    CFix("src/battle_message.c", "sText_Evasiveness", "evasão"),
    CFix("src/battle_message.c", "sText_StatSharply", "muito "),
    CFix("src/battle_message.c", "gText_StatRose", "aumentou!"),
    CFix("src/battle_message.c", "sText_StatHarshly", "muito "),
    CFix("src/battle_message.c", "sText_StatFell", "caiu!"),
    CFix("src/battle_message.c", "sText_AttackersStatRose", r"{B_ATK_NAME_WITH_PREFIX}: {B_BUFF1}\n{B_BUFF2}"),
    CFix("src/battle_message.c", "gText_DefendersStatRose", r"{B_DEF_NAME_WITH_PREFIX}: {B_BUFF1}\n{B_BUFF2}"),
    CFix("src/battle_message.c", "sText_AttackersStatFell", r"{B_ATK_NAME_WITH_PREFIX}: {B_BUFF1}\n{B_BUFF2}"),
    CFix("src/battle_message.c", "sText_DefendersStatFell", r"{B_DEF_NAME_WITH_PREFIX}: {B_BUFF1}\n{B_BUFF2}"),
    CFix("src/battle_message.c", "sText_CriticalHit", "Um golpe crítico!"),
    CFix("src/battle_message.c", "sText_NotVeryEffective", "Não foi muito eficaz..."),
    CFix("src/battle_message.c", "sText_SuperEffective", "Foi super eficaz!"),
    CFix("src/battle_message.c", "sText_CantEscape", r"Não foi possível fugir!\p"),
    CFix("src/battle_message.c", "sText_DontLeaveBirch", r"PROF. BIRCH: Não me deixe assim!\p"),
    CFix("src/battle_message.c", "sText_ButNothingHappened", "Mas nada aconteceu!"),
    CFix("src/battle_message.c", "sText_ButItFailed", "Mas falhou!"),
    CFix("src/battle_message.c", "gText_WhatWillPkmnDo", r"O que\n{B_ACTIVE_NAME_WITH_PREFIX} fará?"),
    CFix("src/battle_message.c", "gText_WhatWillPkmnDo2", r"O que\n{B_PLAYER_NAME} fará?"),
    CFix("src/battle_message.c", "gText_WhatWillWallyDo", r"O que\nWALLY fará?"),
    CFix("src/battle_message.c", "gText_BattleMenu", r"LUTAR{CLEAR_TO 56}MOCHILA\nPOKéMON{CLEAR_TO 56}FUGIR"),
    CFix("src/battle_message.c", "gText_MoveInterfaceType", "TIPO/"),
    CFix("src/battle_message.c", "gText_MoveInterfacePpType", r"{PALETTE 5}{COLOR_HIGHLIGHT_SHADOW DYNAMIC_COLOR4 DYNAMIC_COLOR5 DYNAMIC_COLOR6}PP\nTIPO/"),
    CFix("src/battle_message.c", "gText_WhichMoveToForget4", r"{PALETTE 5}{COLOR_HIGHLIGHT_SHADOW DYNAMIC_COLOR4 DYNAMIC_COLOR5 DYNAMIC_COLOR6}Qual golpe deve\nser esquecido?"),
    CFix("src/battle_message.c", "gText_BattleYesNoChoice", r"{PALETTE 5}{COLOR_HIGHLIGHT_SHADOW DYNAMIC_COLOR4 DYNAMIC_COLOR5 DYNAMIC_COLOR6}SIM\nNÃO"),
    CFix("src/battle_message.c", "gText_BattleSwitchWhich", r"{PALETTE 5}{COLOR_HIGHLIGHT_SHADOW DYNAMIC_COLOR4 DYNAMIC_COLOR5 DYNAMIC_COLOR6}Trocar\nqual?"),
    CFix("src/strings.c", "gText_BirchInTrouble", r"PROF. BIRCH está em perigo!\nEscolha um POKéMON e salve-o!"),
    CFix("src/strings.c", "gText_ConfirmStarterChoice", "Escolher este POKéMON?"),
)


ROUTE101_FIXES = (
    AssemblyFix("data/maps/Route101/scripts.inc", "Route101_Text_HelpMe", (r"A-ajude-me!$",)),
    AssemblyFix(
        "data/maps/Route101/scripts.inc",
        "Route101_Text_PleaseHelp",
        (
            r"Ei! Você aí!\nPor favor, ajude!\p",
            r"Na minha MOCHILA!\nHá uma POKé BOLA!$",
        ),
    ),
    AssemblyFix(
        "data/maps/Route101/scripts.inc",
        "Route101_Text_DontLeaveMe",
        (r"A-aonde você vai?!\nNão me deixe assim!$",),
    ),
    AssemblyFix(
        "data/maps/Route101/scripts.inc",
        "Route101_Text_YouSavedMe",
        (
            r"PROF. BIRCH: Ufa...\p",
            r"Eu estudava POKéMON selvagens\nna grama alta quando fui\latacado.\p",
            r"Você me salvou.\nMuito obrigado!\p",
            r"Oh?\p",
            r"Olá, você é {JOGADOR}{KUN}!\p",
            r"Aqui não é lugar para conversar.\nPasse no meu LABORATÓRIO\ldepois, está bem?$",
        ),
    ),
)


STARTER_CATEGORY_FIXES = (
    CategoryFix("NATIONAL_DEX_TREECKO", "LAGARTIXA"),
    CategoryFix("NATIONAL_DEX_TORCHIC", "PINTINHO"),
    CategoryFix("NATIONAL_DEX_MUDKIP", "PEIXE-LAMA"),
)


def placeholder_multiset(text: str) -> Counter[str]:
    return Counter(PLACEHOLDER_RE.findall(text))


def c_pattern(label: str) -> re.Pattern[str]:
    return re.compile(
        rf'(?m)^(?P<prefix>(?:static\s+)?(?:ALIGNED\(4\)\s+)?const u8 {re.escape(label)}\[\]\s*=\s*_\(")'
        rf'(?P<body>(?:\\.|[^"\\])*)'
        rf'(?P<suffix>"\);(?:\s*//.*)?)$'
    )


def apply_c_fix(project: Path, fix: CFix) -> dict[str, object]:
    path = project / fix.path
    text = path.read_text(encoding="utf-8")
    pattern = c_pattern(fix.label)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {fix.label} in {fix.path}, found {len(matches)}")
    match = matches[0]
    current = match.group("body")
    if placeholder_multiset(current) != placeholder_multiset(fix.text):
        raise RuntimeError(f"Placeholder mismatch in {fix.label}")
    updated = text[:match.start("body")] + fix.text + text[match.end("body"):]
    path.write_text(updated, encoding="utf-8")
    return {
        "kind": "c_string",
        "file": fix.path,
        "label": fix.label,
        "placeholders": dict(placeholder_multiset(fix.text)),
    }


def apply_assembly_fix(project: Path, fix: AssemblyFix) -> dict[str, object]:
    path = project / fix.path
    text = path.read_text(encoding="utf-8")
    matches = [
        match for match in ASSEMBLY_BLOCK_RE.finditer(text)
        if match.group("label").rstrip(":\n") == fix.label
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {fix.label} in {fix.path}, found {len(matches)}")
    match = matches[0]
    current = "".join(ASSEMBLY_LINE_RE.findall(match.group("body")))
    replacement = "".join(fix.lines)
    if placeholder_multiset(current) != placeholder_multiset(replacement):
        raise RuntimeError(f"Placeholder mismatch in {fix.label}")
    if current.endswith("$") != replacement.endswith("$"):
        raise RuntimeError(f"Terminator mismatch in {fix.label}")
    body = "".join(f'\t.string "{line}"\n' for line in fix.lines)
    updated = text[:match.start("body")] + body + text[match.end("body"):]
    path.write_text(updated, encoding="utf-8")
    return {
        "kind": "assembly",
        "file": fix.path,
        "label": fix.label,
        "placeholders": dict(placeholder_multiset(replacement)),
    }


def category_pattern(species: str) -> re.Pattern[str]:
    return re.compile(
        rf'(?ms)(?P<prefix>\[{re.escape(species)}\]\s*=\s*\{{.*?\.categoryName\s*=\s*_\(")'
        rf'(?P<body>(?:\\.|[^"\\])*)'
        rf'(?P<suffix>"\),)'
    )


def apply_category_fix(project: Path, fix: CategoryFix) -> dict[str, object]:
    if len(fix.category) > 11:
        raise ValueError(f"Category too long for PokedexEntry.categoryName[12]: {fix.category}")
    path = project / "src/data/pokemon/pokedex_entries.h"
    text = path.read_text(encoding="utf-8")
    pattern = category_pattern(fix.species)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one category for {fix.species}, found {len(matches)}")
    match = matches[0]
    updated = text[:match.start("body")] + fix.category + text[match.end("body"):]
    path.write_text(updated, encoding="utf-8")
    return {
        "kind": "starter_category",
        "file": "src/data/pokemon/pokedex_entries.h",
        "label": fix.species,
        "category": fix.category,
    }


def apply_all(project: Path) -> list[dict[str, object]]:
    results = [apply_c_fix(project, fix) for fix in BATTLE_C_FIXES]
    results.extend(apply_assembly_fix(project, fix) for fix in ROUTE101_FIXES)
    results.extend(apply_category_fix(project, fix) for fix in STARTER_CATEGORY_FIXES)
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()

    results = apply_all(project)
    expected = len(BATTLE_C_FIXES) + len(ROUTE101_FIXES) + len(STARTER_CATEGORY_FIXES)
    report = {
        "version": release_version(),
        "fixes_applied": len(results),
        "battle_c_strings": len(BATTLE_C_FIXES),
        "route101_dialogues": len(ROUTE101_FIXES),
        "starter_categories": len(STARTER_CATEGORY_FIXES),
        "move_names_policy": "English move names and descriptions preserved",
        "move_data_files_touched": [],
        "fixes": results,
        "valid": len(results) == expected,
    }
    report_path = args.report or project / f"battle_ptbr_fixes_{release_tag()}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
