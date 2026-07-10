from __future__ import annotations

import argparse
import json
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

EN = set("the and you your is are was were have has had do does did can could would should will this that these those it its to of in on at for from with as not no yes me my we our they their he she him her what who where when why how here there please sorry thank thanks hello good great get got make take look know think want like come go give tell see use need must much many more very just about after before again all any away back because been being but by down even every first if into last let little long made man most never new now off old once only or other out over own people right same so some still such than then there thing through time too two up us way well while work year yet trainer trainers battle battles pokemon move moves item items save game continue cancel select press start link wireless trade record berry berries level points attack defense speed party box bag summary switch delete exit next previous professor gym leader champion received learned caught found room house city town route road team friend father mother kid child".split())
PT = set("o a os as um uma uns umas e você voce seu sua seus suas é sao são foi foram era eram tem têm tinha tinham fazer faz fez pode poderia vai este esta isto isso aquilo de do da dos das em no na nos nas para por com como nao não sim eu meu minha meus minhas nós nosso nossa eles elas ele ela que quem onde quando porque aqui ali favor desculpe obrigado obrigada olá bom boa melhor batalha batalhas treinador treinadores movimento movimentos item itens salvar jogo continuar cancelar selecionar aperte início ligação troca registro fruta frutas nível pontos ataque defesa velocidade equipe caixa mochila resumo usar dar verificar trocar apagar sair próximo anterior professor ginásio líder campeão recebeu aprendeu capturou encontrou sala casa cidade vila rota estrada amigo amiga pai mãe filho filha criança".split())
TOKEN_RE = re.compile(r"\{[^{}]+\}|\\[A-Za-z][A-Za-z0-9_ ]*|[A-Z][A-Z0-9_.-]{2,}")
BLOCK_RE = re.compile(r"(?ms)^(?P<label>[A-Za-z_][A-Za-z0-9_]*::?\n)(?P<body>(?:[ \t]*\.string[ \t]+\"(?:\\.|[^\"\\])*\"[ \t]*\n)+)")
LINE_RE = re.compile(r'\.string\s+"((?:\\.|[^"\\])*)"')
C_RE = re.compile(r'_\("((?:\\.|[^"\\])*)"\)')


@dataclass
class Stats:
    assembly_seen: int = 0
    assembly_translated: int = 0
    c_seen: int = 0
    c_translated: int = 0
    files_changed: int = 0


def looks_english(text: str) -> bool:
    text = re.sub(r"\{[^{}]+\}", " ", text)
    words = re.findall(r"[A-Za-zÀ-ÿ']+", text.lower())
    en = sum(word in EN for word in words)
    pt = sum(word in PT for word in words)
    return en >= 2 and en > pt * 1.35


def normalize(text: str) -> str:
    replacements = {
        "ã": "ä", "õ": "ö", "Ã": "Ä", "Õ": "Ö",
        "Pokémon": "POKéMON", "Pokemon": "POKéMON", "POKÉMON": "POKéMON",
        "Pokédex": "POKéDEX", "Pokedex": "POKéDEX", "POKÉDEX": "POKéDEX",
        "Pokébolas": "POKé BOLAS", "Pokébola": "POKé BOLA",
        "pokébolas": "POKé BOLAS", "pokébola": "POKé BOLA",
        "—": "-", "–": "-", "’": "'",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def protect(text: str) -> tuple[str, dict[str, str]]:
    mapping: dict[str, str] = {}
    def repl(match: re.Match[str]) -> str:
        key = f"ZXQ{len(mapping):03d}QXZ"
        mapping[key] = match.group(0)
        return key
    return TOKEN_RE.sub(repl, text), mapping


def restore(text: str, mapping: dict[str, str]) -> str:
    for key, value in mapping.items():
        text = text.replace(key, value).replace(key.lower(), value)
    return text


def split_raw(raw: str) -> tuple[list[str], bool]:
    terminal = raw.endswith("$")
    if terminal:
        raw = raw[:-1]
    raw = raw.replace("\\n", " ").replace("\\l", " ").replace("\\p", "\n\n")
    raw = raw.replace('\\"', '"')
    paragraphs = [re.sub(r"\s+", " ", part).strip() for part in raw.split("\n\n")]
    return [part for part in paragraphs if part], terminal


def pages(paragraphs: list[str], width: int = 29) -> list[list[str]]:
    result: list[list[str]] = []
    for paragraph in paragraphs:
        lines = textwrap.wrap(paragraph, width=width, break_long_words=False, break_on_hyphens=False) or [""]
        result.extend(lines[index:index + 3] for index in range(0, len(lines), 3))
    return result


def encode(paragraphs: list[str], terminal: bool, assembly: bool) -> str:
    output: list[str] = []
    all_pages = pages(paragraphs)
    for page_index, page in enumerate(all_pages):
        last_page = page_index == len(all_pages) - 1
        for line_index, line in enumerate(page):
            last_line = line_index == len(page) - 1
            if not last_line:
                control = "\\n" if line_index == 0 else "\\l"
            elif not last_page:
                control = "\\p"
            else:
                control = "$" if terminal else ""
            value = line.replace('"', '\\"') + control
            output.append(f'\t.string "{value}"\n' if assembly else value)
    return "".join(output)


def translate_in_batches(texts: list[str], translator: Callable[[list[str]], list[str]]) -> list[str]:
    output: list[str] = []
    for index in range(0, len(texts), 24):
        output.extend(translator(texts[index:index + 24]))
        print(f"Translated {min(index + 24, len(texts))}/{len(texts)}")
    return output


def process_assembly(path: Path, translator: Callable[[list[str]], list[str]], stats: Stats) -> bool:
    original = path.read_text(encoding="utf-8")
    candidates = []
    flat: list[str] = []
    for match in BLOCK_RE.finditer(original):
        stats.assembly_seen += 1
        raw = "".join(LINE_RE.findall(match.group("body")))
        paragraphs, terminal = split_raw(raw)
        if not paragraphs or not looks_english(" ".join(paragraphs)):
            continue
        protected, mappings = [], []
        for paragraph in paragraphs:
            value, mapping = protect(paragraph)
            protected.append(value)
            mappings.append(mapping)
        candidates.append((match, terminal, mappings, len(protected)))
        flat.extend(protected)
    if not candidates:
        return False
    translated = translate_in_batches(flat, translator)
    cursor = 0
    replacements = []
    for match, terminal, mappings, count in candidates:
        values = []
        for mapping in mappings:
            values.append(normalize(restore(translated[cursor], mapping)))
            cursor += 1
        replacements.append((match.start("body"), match.end("body"), encode(values, terminal, True)))
        stats.assembly_translated += 1
    updated = original
    for start, end, value in reversed(replacements):
        updated = updated[:start] + value + updated[end:]
    path.write_text(updated, encoding="utf-8")
    return updated != original


def process_c(path: Path, translator: Callable[[list[str]], list[str]], stats: Stats) -> bool:
    original = path.read_text(encoding="utf-8")
    candidates = []
    flat: list[str] = []
    for match in C_RE.finditer(original):
        stats.c_seen += 1
        paragraphs, terminal = split_raw(match.group(1))
        if not paragraphs or not looks_english(" ".join(paragraphs)):
            continue
        mappings = []
        for paragraph in paragraphs:
            value, mapping = protect(paragraph)
            flat.append(value)
            mappings.append(mapping)
        candidates.append((match, terminal, mappings))
    if not candidates:
        return False
    translated = translate_in_batches(flat, translator)
    cursor = 0
    replacements = []
    for match, terminal, mappings in candidates:
        values = []
        for mapping in mappings:
            values.append(normalize(restore(translated[cursor], mapping)))
            cursor += 1
        replacements.append((match.start(1), match.end(1), encode(values, terminal, False)))
        stats.c_translated += 1
    updated = original
    for start, end, value in reversed(replacements):
        updated = updated[:start] + value + updated[end:]
    path.write_text(updated, encoding="utf-8")
    return updated != original


def make_translator(model_name: str) -> Callable[[list[str]], list[str]]:
    from transformers import MarianMTModel, MarianTokenizer
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)
    model.eval()
    def run(texts: list[str]) -> list[str]:
        encoded = tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=384)
        generated = model.generate(**encoded, max_new_tokens=384, num_beams=1)
        return tokenizer.batch_decode(generated, skip_special_tokens=True)
    return run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--model", default="Helsinki-NLP/opus-mt-en-pt")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    translator = make_translator(args.model)
    stats = Stats()
    assembly_files = sorted((project / "data/maps").rglob("scripts.inc"))
    assembly_files += sorted((project / "data/text").glob("*.inc"))
    assembly_files += sorted((project / "data/scripts").glob("*.inc"))
    c_files = [
        project / "src/strings.c",
        project / "src/battle_message.c",
        project / "src/berry.c",
        project / "src/berry_blender.c",
        project / "src/mystery_event_msg.c",
        project / "src/data/union_room.h",
        project / "src/data/text/match_call_messages.h",
    ]
    for path in assembly_files:
        if process_assembly(path, translator, stats):
            stats.files_changed += 1
    for path in c_files:
        if path.exists() and process_c(path, translator, stats):
            stats.files_changed += 1
    report = {
        "assembly_blocks_seen": stats.assembly_seen,
        "assembly_blocks_translated": stats.assembly_translated,
        "c_strings_seen": stats.c_seen,
        "c_strings_translated": stats.c_translated,
        "files_changed": stats.files_changed,
        "model": args.model,
        "note": "Machine translation consistency pass; manual proofreading remains recommended.",
    }
    report_path = args.report or project / "translation_consistency_v1.3.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
