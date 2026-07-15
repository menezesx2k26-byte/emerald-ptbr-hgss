# Emerald PT-BR HGSS

Overhaul de Pokémon Emerald com localização em português brasileiro e uma
direção visual inspirada em HeartGold/SoulSilver.

## Estado da v1.3.1

- 386 Pokémon com sprites de batalha frontais, traseiros, normais e shiny da
  coleção HGSS do PokeAPI.
- 129 folhas de sprites humanos de overworld importadas sem arquivos pulados e
  com a correção de alinhamento da animação de Fly.
- água, cachoeira, margens, Surf, ondulação e splash refeitos para a paleta do
  GBA.
- Littleroot, Oldale, Route 101 e Petalburg Woods com tilesets isolados e
  tratamento de paleta inspirado em HGSS.
- 21.965 segmentos processados pelos quatro shards de tradução; 15 diálogos
  problemáticos receberam revisão manual em PT-BR na v1.3.1.
- nomes e descrições de golpes preservados em inglês de propósito.
- build reproduzível com a base, sprites, overworlds e compilador fixados por
  commit; os patches de tradução concluídos também ficam versionados.
- auditoria automática de 386 conjuntos de sprites, 129 overworlds, 16 assets
  de água/efeitos, quatro layouts, charmap e cabeçalho/checksum da ROM.
- smoke test no `mgba-headless` fixado por commit: 900 frames, amostragem de
  VRAM e três screenshots validados contra tela vazia ou congelada.

## Limites conhecidos

“Inspirado em HGSS” não significa que todo o mapa foi redesenhado com arte
original de HGSS. Os quatro mapas listados acima ainda reutilizam a geometria e
os tiles de Emerald com novas paletas. Da mesma forma, a fonte pública fornece
uma pose frontal por Pokémon; por isso o segundo quadro de `anim_front.png` é
uma cópia estática. Formas alternativas de Unown e Castform também continuam
com os assets da base.

Esses pontos são trabalho de arte e animação para uma v1.4, não defeitos que a
pipeline da v1.3.1 possa corrigir automaticamente.

## Build

O workflow `Rebuild Emerald PT-BR HGSS v1.3.1` aplica, nesta ordem:

1. os quatro patches de tradução versionados;
2. sanitização de segurança, reparo de tokens e as 15 revisões manuais;
3. normalização e validação do charmap PT-BR;
4. overhaul visual e auditoria dos assets;
5. compilação com `agbcc` fixado por commit;
6. validação estrutural da ROM de 16 MiB;
7. boot automatizado no mGBA headless com validação de frames, VRAM e imagens.

O smoke test detecta ROM que não abre, trava ou deixa de renderizar. Ele não
substitui o playtest humano de diálogos, colisões, transições, batalhas e
efeitos. A passagem manual está especificada em
[`QA_CHECKLIST_v1.3.1.md`](QA_CHECKLIST_v1.3.1.md).

## Créditos e fontes

- base PT-BR: `lucmsilva651/esmeralda-ptbr`
- sprites de batalha HGSS: `PokeAPI/sprites`
- overworlds convertidos: `TeamAquasHideout/Team-Aquas-Asset-Repo`, coleção de
  RavePossum/Poffin Case
- compilador: `pret/agbcc`
