# Emerald PT-BR HGSS v1.4 — checklist de QA

Este checklist separa o gate reproduzível do CI da inspeção humana. Nenhum item
de gameplay é aprovado apenas porque a ROM compilou.

## P0 — bloqueia a candidata a release

### Build e integridade

- [ ] 33 testes automatizados aprovados;
- [ ] auditoria visual integral aprovada;
- [ ] ROM de produção com 16 MiB, cabeçalho e checksum válidos;
- [ ] smoke test normal de 900 frames aprovado;
- [ ] SHA-256 da ROM conferido antes e depois das ROMs diagnósticas.

### Quatro mapas-piloto

- [ ] Littleroot carregada nativamente no mGBA e screenshot 240×160 válida;
- [ ] Oldale carregada nativamente no mGBA e screenshot 240×160 válida;
- [ ] Route 101 carregada nativamente no mGBA e screenshot 240×160 válida;
- [ ] Petalburg Woods carregada nativamente no mGBA e screenshot 240×160 válida;
- [ ] quatro assinaturas de VRAM e quatro screenshots distintas;
- [ ] nenhuma lacuna, tile preto, índice de paleta inválido ou emenda quebrada;
- [ ] caminhos, grama alta, copas, telhados e solo da floresta legíveis;
- [ ] entradas de prédios, placas, flores, árvores e ledges alinhados;
- [ ] `map.bin`, `border.bin`, metatiles e atributos preservados byte a byte;
- [ ] warps e eventos continuam usando os layouts originais.

### Batalha e assets preservados

- [ ] Castform e Unown continuam aprovados nos nove casos front/back;
- [ ] 386 espécies-base e 30 formas alternativas continuam válidas;
- [ ] 129 overworlds humanos continuam válidos;
- [ ] 16 assets de água e efeitos continuam válidos;
- [ ] diálogos, menus e mensagens permanecem em PT-BR;
- [ ] nomes e descrições de golpes permanecem em inglês.

## P1 — passagem humana na ROM de produção

- [ ] iniciar um jogo novo e chegar a Littleroot sem travamento;
- [ ] testar D-pad, A, B, Start e abertura/fechamento de menus;
- [ ] caminhar ao redor das duas casas e do laboratório de Littleroot;
- [ ] atravessar Littleroot → Route 101 → Oldale nos dois sentidos;
- [ ] testar colisão em árvores, placas, flores, grama e ledges;
- [ ] entrar e sair das casas, laboratório, PokéCenter e PokéMart;
- [ ] entrar e sair de Petalburg Woods pelas duas conexões;
- [ ] conferir encontros selvagens e retorno ao overworld após batalha;
- [ ] conferir Surf, Waterfall, Fly, ripple, splash e water surfacing;
- [ ] revisar caixas de diálogo e menus em telas pequenas e longas.

## Evidências esperadas

- `visual_audit_v1.4.0-dev.1.json`;
- `map_art_v1.4.0-dev.1.json`;
- `map_qa_validation_v1.4.0-dev.1.json`;
- quatro previews completos e quatro screenshots reais do mGBA;
- `mgba_smoke_validation_v1.4.0-dev.1.json`;
- `form_battle_validation_v1.4.0-dev.1.json`;
- ROM jogável, `SHA256SUMS.txt` e link do workflow verde.
