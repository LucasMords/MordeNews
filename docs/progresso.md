# Progresso

## Estado atual

- **Bloco 0 — Fundação:** concluído e validado no Supabase real (2026-11-18).
- **Bloco 1 — Coletor RSS:** código pronto, 84 testes passando e coleta real validada localmente: 180 itens na 1ª execução, 0 duplicados na 2ª. **Falta** publicar no GitHub e rodar o workflow via `workflow_dispatch` (passos no fim da seção do bloco 1).

---

## Bloco 1 — Coletor de notícias RSS (2026-11-18)

### O que foi feito

- `config/fontes.yaml` com os 10 feeds aprovados: Hacker News (≥150 pts), Ars Technica, The Verge, MIT Technology Review, Simon Willison, Hugging Face Blog, GitHub Blog, The Hacker News, Tecnoblog e TabNews.
- `modelos.py`: modelo `Fonte`, que valida o `fontes.yaml`. O `nome` aceita só minúsculas, números e hífen, `tipo` é `rss`, a URL precisa ser http(s), `janela_horas` padrão é 72 e `limite` padrão é 50, com teto de 50. Chaves desconhecidas são rejeitadas e nomes repetidos também.
- `coletores/http.py` (arquivo novo, fora da árvore da seção 3): `ClienteHttp` aplica as regras de boa conduta num lugar só. Usa User-Agent `RadarPessoal/0.1 (+RADAR_CONTATO)` e timeout de 20s, pausa 1,5s entre requisições ao mesmo domínio e respeita o `robots.txt`, guardado em cache por domínio. O `robots.txt` segue o `urllib.robotparser`: 401/403 bloqueiam e 404 libera. Se der 5xx ou erro de rede, o domínio é pulado nessa rodada.
- `coletores/base.py`: `Coletor` (só `buscar()`), `limpar_html()` (remove tags, `script` e `style`, e normaliza espaços), `recentes()` (janela de tempo, limite e ordem do mais novo para o mais antigo) e `executar()`. O `executar()` grava com deduplicação, registra em `execucoes` e nunca propaga exceção.
- `coletores/rss.py`: `ColetorRSS` para RSS 2.0 e Atom. Prefere `content` a `summary`, converte datas para UTC e descarta entradas sem título ou link. Uma página HTML ou um conteúdo que não é feed gera erro. Um feed válido e vazio, não.
- `coletores/registro.py`: monta os coletores pelo `tipo` e filtra fontes por nome ou módulo.
- CLI: `radar coletar --todos | --fonte NOME [--fonte ...] | --modulo noticias`. Devolve código 1 só se **todas** as fontes falharem. Falhas parciais aparecem no log e em `execucoes`.
- `.github/workflows/testes.yml`: lint, checagem de formatação e testes a cada push/PR.
- `.github/workflows/coletar.yml`: cron `13 9 * * *` (06:13 BRT) e `workflow_dispatch`, com `concurrency` para evitar duas coletas simultâneas.
- Nova variável `RADAR_CONTATO` (opcional) no `.env.example`. O repositório é público, então o contato fica fora do código.

### Dependências novas

| Dependência | Motivo |
|---|---|
| `feedparser` | Já está na stack. Interpreta RSS e Atom. |
| `beautifulsoup4` | Já está na stack. Remove HTML do texto. |

O download do feed é feito pelo `ClienteHttp` (httpx), e não pelo feedparser. Assim User-Agent, timeout, pausa e robots.txt ficam sob nosso controle.

### Resultado da coleta real (local, 2026-11-18)

| Fonte | Itens (72h) | Observação |
|---|---|---|
| tecnoblog | 50 | Bateu o limite de 50; o feed tem só os 50 mais recentes |
| tabnews | 30 | |
| the-hacker-news | 26 | Texto curto (~400 caracteres) |
| hacker-news | 20 | O "texto" é só metadado (link, pontos, comentários); a triagem vai depender do título |
| ars-technica | 20 | |
| the-verge | 10 | |
| mit-technology-review | 10 | |
| simon-willison | 9 | |
| hugging-face-blog | 3 | **O feed não traz texto**, só título e link |
| github-blog | 2 | |

Nenhum item ficou com HTML no texto. Os 2 casos suspeitos do Simon Willison eram menções a tags escritas no próprio artigo. Todos os itens têm data. Segunda execução: 0 novos.

### Como testar

```powershell
uv run ruff check . ; uv run pytest
uv run radar coletar --fonte tabnews     # uma fonte só
uv run radar coletar --todos             # todas; rodar de novo deve dar "0 itens novos"
```

No Supabase: **Table Editor → itens** (status `pendente`) e **execucoes** (uma linha por fonte por execução).

### Para fechar o bloco 1 (GitHub)

1. Configurar a identidade do git com o **e-mail noreply do GitHub**, porque em repositório público o e-mail do autor aparece em cada commit.
2. Criar o repositório público no GitHub e fazer o primeiro commit e o push.
3. Em **Settings → Secrets and variables → Actions**, criar `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` e (opcional) `RADAR_CONTATO`.
4. Em **Actions → coletar → Run workflow**, rodar manualmente e conferir o log.

### Pendências e decisões

- [ ] Publicar no GitHub e rodar o `coletar` via `workflow_dispatch` (acima).
- [ ] Definir o valor de `RADAR_CONTATO` (sugestão: apelido do Gmail com `+radar`), no `.env` e no Secret.
- [ ] Hugging Face sem texto: aceitar assim (triagem só pelo título) ou trocar por outra fonte de IA?
- Monitoramento (bloco 9): as execuções já ficam registradas em `execucoes`. Os alertas no Telegram dependem do bot (bloco 3).
- Bloco 2: vou precisar do texto do seu `perfil.md` (interesses e o que é relevante para você).

---

## Bloco 0 — Fundação (2026-11-18)

### O que foi feito

- Projeto `uv` (Python 3.12) com `pyproject.toml`, `ruff` (lint + format) e `pytest`; comando `radar` instalado como script.
- Estrutura de pastas da seção 3 do `CLAUDE.md` (`coletores/`, `ia/`, `ia/prompts/`, `entrega/` ainda vazios; entram nos próximos blocos).
- `.env.example`, `.gitignore` (bloqueia `.env`), repositório git inicializado (sem commits).
- `db/migrations/001_inicial.sql`: tabelas `itens`, `execucoes` e `feedback` com RLS ligada.
- `config.py`: lê o `.env` (variáveis já definidas no ambiente, como GitHub Secrets, têm prioridade), valida as obrigatórias com mensagem clara e nunca mostra segredos no `repr`. Também lê o `fontes.yaml`.
- `modelos.py`: `Item` (calcula `id_unico` sozinho, trunca `texto` em 4.000 caracteres, assume UTC em datas sem fuso), `ItemPendente`, `normalizar_url()` e `gerar_id_unico()`.
- `banco.py`: `existe`, `salvar_itens` (upsert por `id_unico` ignorando duplicatas; devolve quantos eram novos), `obter_item`, `apagar_item`, `pendentes`, `marcar_enviados`, `registrar_execucao`, `ultimas_execucoes`.
- `cli.py`: `radar teste-banco` grava um item de teste, confirma que gravar de novo não duplica, relê o item, registra uma linha em `execucoes` e apaga o item (`--manter` deixa o item no banco).
- 38 testes (normalização de URL e deduplicação, modelo `Item`, configuração, banco com Supabase falso em memória, CLI de ponta a ponta).

### Dependências e decisões técnicas

| Dependência | Motivo |
|---|---|
| `httpx` | Já está na stack. Também é usado para falar com o Supabase (veja abaixo). |
| `pydantic` | Já está na stack (validação do `Item`). |
| `pyyaml` | Ler o `config/fontes.yaml`. |
| `python-dotenv` | Carregar o `.env` no desenvolvimento local. No GitHub Actions as variáveis vêm dos Secrets. |
| `ruff`, `pytest` (dev) | Já estão na stack. |

- **Acesso ao Supabase pela API REST (PostgREST) com `httpx`, sem o pacote `supabase`.** O SDK oficial traz auth, realtime e storage, que não usamos. Só precisamos de inserir/consultar tabelas, e o `httpx` já faz isso. Os testes simulam o banco com `httpx.MockTransport`, sem dependências extras. Se você preferir o SDK oficial, a troca fica toda dentro do `banco.py`.
- Funciona com os dois formatos de chave do Supabase: a nova chave secreta (`sb_secret_...`) e a antiga `service_role` (JWT).
- `registrar_execucao` grava uma linha ao **fim** da execução (com `iniciado_em` e `finalizado_em`). `executar()`, no bloco 1, vai capturar as exceções e garantir que toda execução gere uma linha.
- `gravar_triagem` e `para_resumo` não foram feitas agora: dependem do formato do `Resultado` da IA (bloco 2) e das regras do resumo (bloco 3).
- O `ruff` não formata arquivos `.md` (`extend-exclude`), para não mexer nos exemplos de código do `CLAUDE.md`.

### Como testar

Local, sem rede:

```powershell
uv sync
uv run ruff check .
uv run pytest
```

Com o Supabase real (critério de pronto do bloco 0):

1. Crie um projeto gratuito em <https://supabase.com>.
2. No painel, abra **SQL Editor**, cole o conteúdo de `db/migrations/001_inicial.sql` e execute.
3. Em **Project Settings → API Keys** (ou **API**), copie a **URL do projeto** e a **chave secreta** (`sb_secret_...`) ou a `service_role`.
4. `copy .env.example .env` e preencha `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY`.
5. `uv run radar teste-banco`. Ele deve terminar com `teste-banco concluído com sucesso`.
6. Opcional: `uv run radar teste-banco --manter` e confira o item em **Table Editor → itens**.

### Pendências e próximas decisões do usuário

- [x] Rodar o `teste-banco` contra o Supabase real (passos acima). Passou em 2026-11-18.
- [x] Repositório no GitHub: **público** (decidido em 2026-11-18). Consequências: o bloco 9 precisa de um commit automático mensal para o GitHub não desativar os crons, e nenhum dado pessoal (como o e-mail de contato) pode ficar no código. Dados pessoais vão em variável de ambiente e GitHub Secret.
- [x] Bloco 1: feeds escolhidos (os 10 recomendados).
- [x] Bloco 1: contato do `User-Agent` vai na variável `RADAR_CONTATO`, fora do código.
- Observação: o `uv` foi instalado nesta máquina via `winget` (`astral-sh.uv`), e o Python 3.12 via `uv python install 3.12`. Abra um terminal novo para o `uv` entrar no PATH.
