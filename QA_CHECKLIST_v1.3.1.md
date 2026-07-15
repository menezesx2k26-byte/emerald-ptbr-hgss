# Checklist de QA — Emerald PT-BR HGSS v1.3.1

Use uma ROM cujo SHA-256 seja o publicado no artefato do Actions. Faça a
primeira passagem sem save anterior e registre cada falha com screenshot,
local, ação executada e texto exibido.

## Critério de saída

A v1.3.1 pode sair de draft quando todos os itens P0 e P1 estiverem aprovados.
Problemas P0 bloqueiam a ROM; P1 bloqueiam a localização; P2 podem entrar no
backlog artístico da v1.4.

## Automático no Actions

- [ ] P0 — ROM com 16 MiB, cabeçalho `POKEMON EMER`, código `BPEE` e checksum válido.
- [ ] P0 — mGBA headless chega a pelo menos 900 frames sem crash.
- [ ] P0 — VRAM contém dados nos três pontos de amostragem.
- [ ] P0 — três screenshots de 240×160 são produzidos e pelo menos dois são diferentes.
- [ ] P0 — 386 conjuntos de sprites de batalha passam na auditoria de formato/paleta.
- [ ] P0 — 129 overworlds são importados sem arquivos pulados.

## Inicialização e persistência

- [ ] P0 — abrir a ROM no mGBA sem BIOS externo e chegar à tela de título.
- [ ] P0 — iniciar `NEW GAME` com save limpo.
- [ ] P0 — salvar, fechar o emulador, reabrir e carregar o save.
- [ ] P1 — relógio, nome e gênero do personagem persistem corretamente.

## Texto e interface PT-BR

- [ ] P1 — introdução do professor sem caracteres quebrados ou linhas cortadas.
- [ ] P1 — menus, opções, bolsa, PC, Pokédex e mensagens de sistema legíveis.
- [ ] P1 — acentos `ã`, `õ`, `ç`, `á`, `é`, `í`, `ó` e `ú` aparecem corretamente.
- [ ] P1 — placeholders de nome, Pokémon, item e números aparecem no lugar correto.
- [ ] P1 — nomes e descrições dos golpes continuam em inglês.
- [ ] P1 — revisar em jogo os 15 diálogos listados em `manual_ptbr_fixes_v1.3.1.json`.

## Mapas e overworlds

- [ ] P0 — sair da casa inicial e atravessar Littleroot sem travar ou atravessar colisões.
- [ ] P0 — percorrer Route 101, Oldale e as transições entre os mapas.
- [ ] P1 — verificar árvores, bordas, sombras e animação da água nesses mapas.
- [ ] P1 — percorrer Petalburg Woods e testar entradas/saídas.
- [ ] P1 — observar Brendan, May e ao menos dez classes diferentes de NPC andando e virando.
- [ ] P1 — testar Fly na ida e na volta; personagem e ave devem permanecer alinhados.

## Água e efeitos de campo

- [ ] P1 — testar todas as margens acessíveis em caminhada.
- [ ] P1 — iniciar e encerrar Surf nas quatro direções.
- [ ] P1 — testar ripple, splash pequeno, splash grande e surgimento da água.
- [ ] P1 — subir e descer uma cachoeira com Waterfall.
- [ ] P1 — confirmar que personagem, blob de Surf e reflexos não trocam de paleta.

## Batalhas

- [ ] P0 — completar a primeira batalha obrigatória.
- [ ] P1 — conferir sprites frontais e traseiros, HUD, HP, EXP e mensagens.
- [ ] P1 — testar pelo menos um Pokémon shiny.
- [ ] P1 — testar troca, item, captura, fuga, vitória, derrota e evolução.
- [ ] P1 — confirmar `PROTECT`, `DETECT` e `DYNAMICPUNCH` em inglês nos locais revisados.

## Limites conhecidos — não bloquear v1.3.1

- [ ] P2 — segundo quadro frontal dos 386 Pokémon ainda é estático.
- [ ] P2 — formas alternativas de Unown e Castform ainda usam assets da base.
- [ ] P2 — os quatro mapas usam tiles de Emerald com paletas inspiradas em HGSS.

## Registro de defeito

Para cada falha, anote:

- prioridade P0/P1/P2;
- mapa ou tela;
- passos exatos;
- resultado esperado e observado;
- screenshot e, se possível, save state imediatamente anterior;
- SHA-256 da ROM e versão do mGBA.
