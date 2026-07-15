from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from release import release_tag, release_version


BLOCK_RE = re.compile(
    r'(?ms)^(?P<label>[A-Za-z_][A-Za-z0-9_]*::?\n)'
    r'(?P<body>(?:[ \t]*\.string[ \t]+"(?:\\.|[^"\\])*"[ \t]*\n)+)'
)
LINE_RE = re.compile(r'\.string\s+"((?:\\.|[^"\\])*)"')
PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")


@dataclass(frozen=True)
class Fix:
    path: str
    label: str
    lines: tuple[str, ...]


FIXES = (
    Fix(
        "data/maps/BattleFrontier_BattleArenaLobby/scripts.inc",
        "BattleFrontier_BattleArenaLobby_Text_ExplainSkillRules",
        (
            r"O segundo fator de julgamento\né a 'Habilidade'.\p",
            r"Ele avalia a eficiência com\nque os golpes foram usados.\p",
            r"Se um golpe funcionar, a nota\nde Habilidade aumenta.\p",
            r"Se o golpe falhar, a nota\nde Habilidade diminui.\p",
            r"Num golpe ofensivo, a nota\naumenta se for super eficaz\le cai se for pouco eficaz.\p",
            r"PROTECT e DETECT não fazem\nHabilidade aumentar.\p",
            r"Se o rival usar PROTECT ou\nDETECT e seu POKéMON errar,\la nota dele não diminuirá.$",
        ),
    ),
    Fix(
        "data/maps/BattleFrontier_BattlePyramidLobby/scripts.inc",
        "BattleFrontier_BattlePyramidLobby_Text_LostLotOfItems",
        (
            r"Aaaaaaargh!\p",
            r"Eu tinha um monte de itens,\ne perdi tudo na derrota!\p",
            r"Aaaaaaargh!$",
        ),
    ),
    Fix(
        "data/maps/EverGrandeCity_ChampionsRoom/scripts.inc",
        "EverGrandeCity_ChampionsRoom_Text_BrendanCongratulations",
        (
            r"BRENDAN: O quêêê?! … … … …\p",
            r"Bem, se essa é a regra,\nnão há o que fazer.\p",
            r"{JOGADOR}, você conseguiu!\nParabéns!$",
        ),
    ),
    Fix(
        "data/maps/FallarborTown_BattleTentLobby/scripts.inc",
        "FallarborTown_BattleTentLobby_Text_MakeThinkImJustKid",
        (
            r"Fufufufufu.\p",
            r"Vou fazer todos pensarem que\nsou só uma criança e me\lsubestimarem.\p",
            r"Então vou surpreendê-los\ne conquistar o título!$",
        ),
    ),
    Fix(
        "data/maps/LilycoveCity/scripts.inc",
        "LilycoveCity_Text_SixtyYearsAgoHusbandProposed",
        (
            r"Foi aqui que meu marido\nme pediu em casamento,\lhá 60 anos.\p",
            r"O mar continua tão bonito\nquanto naquela época.\p",
            r"Mufufufu mufufufufufu…$",
        ),
    ),
    Fix(
        "data/maps/Route110/scripts.inc",
        "Route110_Text_HairStreamsBehindMe",
        (
            r"O que achou do meu cabelo\ncor de corvo esvoaçando\latrás de mim?\p",
            r"Deixei crescer só para isso!$",
        ),
    ),
    Fix(
        "data/maps/Route110/scripts.inc",
        "Route110_Text_YouGotBikeFromRydel",
        (
            r"Ah, essa BIKE veio da RYDEL!\p",
            r"Está bem claro. Veja o que\nestá escrito nela…\p",
            r"RYDEL, RYDEL, RYDEL, RYDEL,\nRYDEL, RYDEL, RYDEL, RYDEL,\p",
            r"RYDEL, RYDEL, RYDEL, RYDEL…\nO nome está por toda parte.\p",
            r"Ande com ela por aí. É uma\nótima propaganda!$",
        ),
    ),
    Fix(
        "data/maps/Route111_WinstrateFamilysHouse/scripts.inc",
        "Route111_WinstrateFamilysHouse_Text_StrongerFamilyMembers",
        (
            r"Mamãe é mais forte que papai.\p",
            r"Sou mais forte que mamãe.\p",
            r"E a vovó é mais forte que eu!\p",
            r"Mas meu irmão mais velho é\nainda mais forte que a vovó.$",
        ),
    ),
    Fix(
        "data/maps/Route124_DivingTreasureHuntersHouse/scripts.inc",
        "Route124_DivingTreasureHuntersHouse_Text_ShardTradeBoard",
        (
            r"{CLEAR_TO 0x0a}Item pedido{CLEAR_TO 0x7c}Item de troca\n",
            r"{CLEAR_TO 0x0f}FRAG. VERM.{CLEAR_TO 0x59}{LEFT_ARROW}{RIGHT_ARROW}{CLEAR_TO 0x7b}PEDRA FOGO{CLEAR_TO 0xc8}\p",
            r"{CLEAR_TO 0x0a}Item pedido{CLEAR_TO 0x7c}Item de troca\n",
            r"{CLEAR_TO 0x06}FRAG. AMAR.{CLEAR_TO 0x59}{LEFT_ARROW}{RIGHT_ARROW}{CLEAR_TO 0x73}PEDRA TROVÃO{CLEAR_TO 0xc8}\p",
            r"{CLEAR_TO 0x0a}Item pedido{CLEAR_TO 0x7c}Item de troca\n",
            r"{CLEAR_TO 0x0c}FRAG. AZUL{CLEAR_TO 0x59}{LEFT_ARROW}{RIGHT_ARROW}{CLEAR_TO 0x79}PEDRA ÁGUA{CLEAR_TO 0xc8}\p",
            r"{CLEAR_TO 0x0a}Item pedido{CLEAR_TO 0x7c}Item de troca\n",
            r"{CLEAR_TO 0x08}FRAG. VERDE{CLEAR_TO 0x59}{LEFT_ARROW}{RIGHT_ARROW}{CLEAR_TO 0x7b}PEDRA FOLHA$",
        ),
    ),
    Fix(
        "data/scripts/gift_altering_cave.inc",
        "sText_MysteryGiftAlteringCave",
        (
            r"Obrigado por usar o sistema\nMYSTERY GIFT.\p",
            r"Há rumores de avistamentos\nde POKéMON raros.\p",
            r"Eles teriam ocorrido na\nALTERING CAVE da ROUTE 103.\p",
            r"Vale a pena investigar.$",
        ),
    ),
    Fix(
        "data/text/match_call.inc",
        "MatchCall_PersonalizedText6",
        (
            r"Mastiga, mastiga…\nOi, aqui é {STR_VAR_1}.\l",
            r"Adoro comer na praia.\p",
            r"Eu e meus POKéMON estamos\nótimos e cheios de energia!\l",
            r"Vou nadar. Até mais!$",
        ),
    ),
    Fix(
        "data/text/move_tutors.inc",
        "MoveTutor_Text_DynamicPunchTeach",
        (
            r"Não aguento mais!\p",
            r"Não tenho a menor chance!\p",
            r"Treino POKéMON LUTADORES,\nmas não consigo vencer no\lGINÁSIO DE MOSSDEEP!\p",
            r"Argh! Soco! Soco! Soco!\nSoco! Soco! Soco!\p",
            r"Ei, não olhe assim para mim!\nSó estou socando o chão!\p",
            r"Ou quer que eu ensine\nDYNAMICPUNCH ao seu POKéMON?$",
        ),
    ),
    Fix(
        "data/text/trainers.inc",
        "Route102_Text_RickDefeated",
        (r"Ai! Fui derrubado!$",),
    ),
    Fix(
        "data/text/trainers.inc",
        "Route114_Text_StevePostRematch",
        (
            r"Ufufufufufu…\p",
            r"Quando vejo uma batalha\nentre POKéMON, fico\larrepiado e trêmulo…$",
        ),
    ),
    Fix(
        "data/text/tv.inc",
        "gTVTrainerFanClubText11",
        (
            r"MC: Como acabamos de ver,\n{STR_VAR_1} está pegando fogo!\p",
            r"Os FÃS de {STR_VAR_1}\ntêm um grito especial!\p",
            r"MC: Quando eu disser {STR_VAR_1},\nvocês respondem…\p",
            r"FÃS: {STR_VAR_2}!\p",
            r"FÃS: {STR_VAR_3}!\p",
            r"FÃS: {STR_VAR_2}!\p",
            r"FÃS: {STR_VAR_3}!\p",
            r"MC: Isso mesmo! Quando alguém\ndisser '{STR_VAR_1}'…\p",
            r"Respondam '{STR_VAR_2}\n{STR_VAR_3}'!\p",
            r"Que grito marcante! Entendo\npor que todos viram FÃS\lde {STR_VAR_1}!\p",
            r"Você aí na frente da TV,\nparticipe! Todos juntos!\p",
            r"MC: Quando eu disser {STR_VAR_1},\nvocês respondem…\p",
            r"FÃS: {STR_VAR_2}!\p",
            r"FÃS: {STR_VAR_3}!\p",
            r"FÃS: {STR_VAR_2}!\p",
            r"FÃS: {STR_VAR_3}!\p",
            r"MC: Obrigado pela companhia,\nFÃS de {STR_VAR_1}! Até a próxima!\p",
            r"MC: Quando eu disser {STR_VAR_1},\nvocês respondem…\p",
            r"FÃS: {STR_VAR_2}!\p",
            r"FÃS: {STR_VAR_3}!$",
        ),
    ),
)


def raw_body(match: re.Match[str]) -> str:
    return "".join(LINE_RE.findall(match.group("body")))


def placeholder_multiset(raw: str) -> Counter[str]:
    return Counter(PLACEHOLDER_RE.findall(raw))


def replacement_body(fix: Fix) -> str:
    for line in fix.lines:
        if '"' in line or "\n" in line.replace(r"\n", "").replace(r"\l", "").replace(r"\p", ""):
            raise ValueError(f"Unsafe encoded string in {fix.label}")
    return "".join(f'\t.string "{line}"\n' for line in fix.lines)


def apply_fix(project: Path, fix: Fix) -> dict[str, object]:
    path = project / fix.path
    text = path.read_text(encoding="utf-8")
    matches = [match for match in BLOCK_RE.finditer(text) if match.group("label").rstrip(":\n") == fix.label]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {fix.label} block in {fix.path}, found {len(matches)}")

    match = matches[0]
    current = raw_body(match)
    replacement = "".join(fix.lines)
    if placeholder_multiset(current) != placeholder_multiset(replacement):
        raise RuntimeError(f"Placeholder mismatch in {fix.label}")
    if current.endswith("$") != replacement.endswith("$"):
        raise RuntimeError(f"Terminator mismatch in {fix.label}")

    updated = text[: match.start("body")] + replacement_body(fix) + text[match.end("body") :]
    path.write_text(updated, encoding="utf-8")
    return {
        "file": fix.path,
        "label": fix.label,
        "placeholders": dict(placeholder_multiset(replacement)),
        "encoded_characters": len(replacement),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()

    applied = [apply_fix(project, fix) for fix in FIXES]
    report = {
        "version": release_version(),
        "fixes_applied": len(applied),
        "fixes": applied,
        "move_names_policy": "English move names preserved",
        "valid": len(applied) == len(FIXES),
    }
    report_path = args.report or project / f"manual_ptbr_fixes_{release_tag()}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
