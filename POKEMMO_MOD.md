# Emerald HGSS Visual 386 para PokeMMO

Este pacote reaproveita os sprites de batalha indexados e as paletas da v1.4 da
ROM, mas os entrega no formato de recurso aceito pelo PokeMMO. A ROM não é
incluída nem modificada.

## Escopo da v0.1.0

- National Dex 001–386;
- frente e costas;
- normal e shiny;
- animação frontal ociosa da v1.4;
- escala explícita para os sprites 64×64;
- `info.xml`, ícone 48×48, créditos e manifesto de procedência.

São 1.544 GIFs no total. Castform normal conserva um quadro frontal porque a
folha da ROM usa os índices seguintes para as formas climáticas. As formas
alternativas serão tratadas em uma versão posterior, depois de validar os IDs
fornecidos pelo dump de recursos do cliente.

## O que não pode ser transferido pelo `.mod`

Os mapas, tilesets, água, cachoeiras, overworlds da história, diálogos PT-BR,
menus e início rápido pertencem ao executável e aos dados da ROM. O PokeMMO
aceita substituições de sprites de batalha, ícones, áudio e temas, mas não usa a
geometria nem o motor da ROM modificada.

## Instalação

1. Abra o PokeMMO e entre em **Mod Management**.
2. Escolha **Import Mod**.
3. Selecione `Emerald-HGSS-Visual-386-v0.1.0.mod`.
4. Ative o pacote e reinicie o cliente.

Use uma ROM Emerald limpa e compatível no gerenciador de ROMs do PokeMMO. O
arquivo `.mod` é instalado separadamente.

## Build reproduzível

```bash
python3 scripts/build_pokemmo_mod.py \
  --project /caminho/para/esmeralda-ptbr \
  --sprites-root /caminho/para/PokeAPI/sprites/pokemon/versions/generation-iv/heartgold-soulsilver \
  --output dist/Emerald-HGSS-Visual-386-v0.1.0.mod \
  --report dist/Emerald-HGSS-Visual-386-v0.1.0.validation.json
```

O workflow fixa as revisões da base e do repositório PokeAPI, recria os assets
indexados da v1.4, gera o `.mod`, testa a integridade ZIP e valida os 1.544 nomes
de arquivo.
