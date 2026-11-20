# Guia de desenvolvimento — Radar pessoal (notícias, vagas e editais)

Este arquivo orienta qualquer agente de IA que trabalhe neste repositório. Leia inteiro antes de escrever código.

## 1. O que estamos construindo

Uma aplicação pessoal que **busca informação sozinha e entrega ao usuário**: notícias do mundo tech, vagas de estágio e editais de concurso. O usuário não navega atrás de nada — o sistema coleta, filtra por relevância, resume e avisa.

Fluxo: `fontes → coletores agendados → triagem por IA → banco → e-mail / portal web`.

### Princípio central (não viole)

- **Coleta é determinística.** Coletores são código comum (RSS, API, HTML, PDF). Nada de "pedir para a IA procurar notícias".
- **IA só filtra, resume e extrai campos** de itens que já foram coletados.
- Toda informação entregue ao usuário precisa ter **link para a fonte original**. A IA nunca inventa dados; se um campo não está no texto, fica `null`.

## 2. Stack (decidida — não troque sem perguntar)

| Camada | Tecnologia |
|---|---|
| Linguagem dos coletores e da IA | Python 3.12, gerenciado com `uv` |
| Bibliotecas de coleta | `feedparser`, `httpx`, `beautifulsoup4`, `pdfplumber` (`playwright` só se uma fonte exigir JS) |
| Validação | `pydantic` v2 |
| Agendamento | GitHub Actions (`schedule: cron`) |
| Banco | Supabase (Postgres; `pgvector` só a partir do bloco 7) |
| IA de triagem | Gemini Flash / Flash-Lite via SDK `google-genai`, plano gratuito |
| IA "editor-chefe" e busca aberta | Rotinas do Claude no plano Pro do usuário (bloco 8, fora do código Python) |
| Notificações | E-mail via SMTP do Gmail (`smtplib`, biblioteca padrão), enviado de uma conta Gmail dedicada ao projeto (trocado do Telegram pelo usuário em 2026-11-19) |
| Portal (bloco 6) | Next.js + TypeScript na Vercel |
| Qualidade | `ruff` (lint + format), `pytest` |

## 3. Estrutura do repositório

```
.
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── .env.example                # nunca commitar .env
├── config/
│   ├── fontes.yaml             # fontes por módulo
│   └── perfil.md               # perfil de interesses do usuário (lido pela triagem)
├── db/
│   └── migrations/
│       └── 001_inicial.sql
├── docs/
│   └── progresso.md            # estado atual — atualize ao fim de cada bloco
├── src/radar/
│   ├── __init__.py
│   ├── cli.py                  # ponto de entrada: `radar coletar|triar|resumo`
│   ├── config.py               # carrega env vars e YAML
│   ├── modelos.py              # dataclass/pydantic Item e afins
│   ├── banco.py                # única camada que fala com o Supabase
│   ├── monitor.py              # registro de execuções e alertas de falha
│   ├── coletores/
│   │   ├── base.py             # classe Coletor
│   │   ├── rss.py
│   │   ├── html.py
│   │   ├── pdf.py
│   │   └── registro.py         # monta coletores a partir do fontes.yaml
│   ├── ia/
│   │   ├── cliente.py          # classificar_lote() — único ponto que chama o LLM
│   │   ├── triagem.py
│   │   └── prompts/            # um arquivo .md por módulo
│   └── entrega/
│       ├── correio.py          # monta e envia o e-mail (SMTP)
│       └── resumo.py           # seleciona itens, envia o resumo diário, marca enviados
├── tests/
│   ├── fixtures/               # XML/HTML/PDF salvos — testes não acessam a rede
│   └── ...
├── web/                        # portal Next.js (bloco 6)
└── .github/workflows/
    ├── testes.yml
    ├── coletar.yml
    └── resumo-diario.yml
```

## 4. Modelo de dados

### Item normalizado (todo coletor devolve isso)

```python
class Item(BaseModel):
    modulo: Literal["noticias", "estagios", "concursos"]
    fonte: str                  # nome da fonte no fontes.yaml
    titulo: str
    url: str
    publicado_em: datetime | None
    texto: str                  # conteúdo bruto, sem HTML
    id_unico: str               # sha256 da URL normalizada (sem utm_*, sem fragmento)
```

### Migração inicial (`db/migrations/001_inicial.sql`)

```sql
create table itens (
  id              bigint generated always as identity primary key,
  id_unico        text unique not null,
  modulo          text not null check (modulo in ('noticias','estagios','concursos')),
  fonte           text not null,
  titulo          text not null,
  url             text not null,
  publicado_em    timestamptz,
  coletado_em     timestamptz not null default now(),
  texto           text,
  status          text not null default 'pendente'
                  check (status in ('pendente','processado','descartado','erro')),
  tentativas_ia   smallint not null default 0,
  nota            smallint check (nota between 0 and 10),
  resumo          text,
  tags            text[] default '{}',
  campos          jsonb not null default '{}',   -- campos específicos do módulo
  prazo           date,                          -- prazo de inscrição (vagas/editais), para alertas
  enviado_em      timestamptz,
  lido            boolean not null default false,
  salvo           boolean not null default false
);
create index on itens (status);
create index on itens (modulo, nota desc);
create index on itens (prazo) where prazo is not null;

create table execucoes (
  id            bigint generated always as identity primary key,
  coletor       text not null,
  iniciado_em   timestamptz not null default now(),
  finalizado_em timestamptz,
  ok            boolean,
  itens_novos   int default 0,
  erro          text
);

create table feedback (
  id         bigint generated always as identity primary key,
  item_id    bigint not null references itens(id) on delete cascade,
  voto       smallint not null check (voto in (-1, 1)),
  criado_em  timestamptz not null default now()
);

alter table itens     enable row level security;
alter table execucoes enable row level security;
alter table feedback  enable row level security;
-- Scripts Python usam a service role key (ignora RLS). Políticas para o portal entram no bloco 6.
```

Campos de `campos` por módulo:
- **estagios:** `empresa`, `area`, `cidade`, `remoto` (bool), `bolsa`, `requisitos` (lista), `link_inscricao`
- **concursos:** `orgao`, `cargos` (lista), `escolaridade`, `salario_max`, `vagas`, `data_prova`, `link_edital`
- **noticias:** vazio

## 5. Variáveis de ambiente

```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=      # só no backend/GitHub Secrets, NUNCA no portal
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash-lite   # escolhido pelo usuário em 2026-11-18; o 3.8 Flash ficava indisponível (503/504)
EMAIL_REMETENTE=                # Gmail dedicado do projeto (precisa de verificação em 2 etapas)
EMAIL_SENHA_APP=                # senha de app do Google, NUNCA a senha da conta
EMAIL_DESTINO=                  # quem recebe o resumo
NOTA_MINIMA_RESUMO=6
RESUMO_MAXIMO=30
```

Mantenha `.env.example` atualizado sempre que criar uma variável nova.

## 6. Regras de implementação

### Coletores
- Cada coletor implementa só `buscar() -> list[Item]`. Deduplicação, gravação e log ficam na função comum `executar()`.
- Um coletor que falha **não pode derrubar os outros**: capture a exceção, registre em `execucoes`, siga em frente.
- Seja educado com os sites: `User-Agent: RadarPessoal/0.1 (+email do usuário)`, timeout de 20s, pausa de 1–2s entre requisições ao mesmo domínio, respeite `robots.txt` (`urllib.robotparser`).
- **Não colete** sites que exigem login ou proíbem coleta automatizada nos termos (ex.: LinkedIn). Prefira RSS > API pública > HTML aberto. Na dúvida, pergunte ao usuário.
- Colete só itens recentes (padrão: últimas 72h, configurável por fonte) e limite a 50 itens por fonte por execução.
- Remova HTML do `texto` e trunque em 4.000 caracteres antes de gravar.

### IA
- Todo acesso a LLM passa por `ia/cliente.py::classificar_lote(itens, modulo) -> list[Resultado]`. Nenhum outro arquivo importa o SDK do Gemini. Isso permite trocar de fornecedor depois.
- **Sempre em lote:** 20–30 itens por requisição. Nunca um item por chamada — o plano gratuito tem limite diário baixo.
- Envie à IA só `id`, `titulo` e os primeiros 1.500 caracteres do `texto`, mais o conteúdo de `config/perfil.md`.
- Use saída estruturada (`response_mime_type="application/json"` + schema) e valide com pydantic. Item ausente ou inválido na resposta → continua `pendente`, incrementa `tentativas_ia`; após 3 tentativas → `erro`.
- Em erro 429 (cota), faça backoff exponencial até 3 vezes e então pare a execução sem falhar o workflow; os pendentes ficam para a próxima rodada.
- Saída esperada por item:

```json
{
  "id": 123,
  "nota": 0,
  "resumo": "até 2 frases em português",
  "tags": ["ia", "dev"],
  "descartar": false,
  "campos": {},
  "prazo": "AAAA-MM-DD ou null"
}
```

- Regras do prompt: notas de 0–10 calibradas pelo `perfil.md`; resumo em português mesmo se a fonte for em inglês; extrair só o que está explícito no texto; datas no formato ISO; nunca inventar link, salário ou prazo.

### Banco
- Só `banco.py` fala com o Supabase. Funções pequenas e nomeadas: `existe(id_unico)`, `salvar_itens(itens)`, `pendentes(modulo, limite)`, `gravar_triagem(resultados)`, `para_resumo(desde)`, `marcar_enviados(ids)`, `registrar_execucao(...)`.
- Use `upsert` por `id_unico` com `ignore_duplicates` para nunca duplicar.

### E-mail
- Mensagem com HTML e versão em texto puro; escape de `<`, `>` e `&` (`html.escape`) em todo texto vindo de fora.
- SMTP com SSL (`smtp.gmail.com:465`), timeout de 30s, autenticação com senha de app.
- Formato do resumo: agrupado por módulo, ordenado por nota, cada item com título em link, fonte, data, resumo de 1–2 linhas e, se houver, o prazo. No máximo `RESUMO_MAXIMO` itens; o rodapé informa quantos ficaram de fora.
- Só marque `enviado_em` depois que o envio der certo. Dia sem itens não gera e-mail.

### Código
- Tipagem em tudo, funções curtas, nomes em português coerentes com o domínio (`coletar`, `triar`, `itens`), mensagens de log claras.
- `logging` padrão, nível INFO; nunca imprima chaves ou tokens.
- Sem dependências novas sem justificar no resumo do bloco.

### Testes
- `pytest` sem acesso à rede: use os arquivos de `tests/fixtures/` e faça mock de `httpx`, do Supabase e de `classificar_lote`.
- Mínimo por bloco: parsing de cada tipo de coletor, normalização de URL/deduplicação, validação da resposta da IA (incluindo resposta quebrada) e montagem do resumo por e-mail.
- `uv run ruff check . && uv run pytest` precisa passar antes de considerar um bloco pronto.

### GitHub Actions
- Cron é em **UTC** (Brasília = UTC−3). Use minutos "quebrados" para evitar atraso no início da hora.
  - `coletar.yml`: `13 9 * * *` (06:13 BRT) → roda `radar coletar --todos` e depois `radar triar`.
  - `resumo-diario.yml`: `2 11 * * *` (08:02 BRT) → roda `radar resumo`; reserva `4 18 * * *` (15:04 BRT) → `radar resumo --reserva`, que só envia se o das 08h falhou ou não rodou (horários escolhidos pelo usuário em 2026-11-20).
- Inclua `workflow_dispatch` em todos para rodar manualmente.
- Segredos só via GitHub Secrets.
- Se o repositório for público, o GitHub desativa crons após 60 dias sem atividade — o bloco 9 deve tratar isso (ex.: commit automático mensal de `docs/progresso.md`).

## 7. Ordem de trabalho (blocos)

Trabalhe **um bloco por vez**. Ao terminar cada bloco: rode lint e testes, atualize `docs/progresso.md` e **pare para o usuário validar** antes de seguir.

### Bloco 0 — Fundação
- `pyproject.toml` com `uv`, `ruff`, `pytest`; estrutura de pastas; `.env.example`; `.gitignore`.
- `001_inicial.sql`; `config.py`; `banco.py` com as funções básicas.
- **Pronto quando:** `radar teste-banco` grava e lê um item de teste no Supabase.

### Bloco 1 — Coletor de notícias (RSS)
- `Item`, `Coletor`, `ColetorRSS`, `registro.py`, `executar()` com deduplicação e log em `execucoes`.
- `fontes.yaml` com 5–10 feeds tech (confirme com o usuário a lista; sugira, não decida sozinho).
- `coletar.yml` + `testes.yml`.
- **Pronto quando:** o workflow roda agendado, grava itens novos e não duplica na segunda execução.

### Bloco 2 — Triagem por IA
- `perfil.md` (peça o texto ao usuário; deixe um modelo comentado).
- `ia/cliente.py`, `ia/triagem.py`, `prompts/noticias.md`.
- **Pronto quando:** itens pendentes ganham nota, resumo e tags; o usuário revisa uma amostra de 20 e concorda com as notas.

### Bloco 3 — Resumo diário por e-mail (fim do MVP)
- `entrega/correio.py`, `entrega/resumo.py`, comando `radar resumo`, `resumo-diario.yml`.
- **Pronto quando:** o resumo chega por e-mail todo dia e os itens enviados não se repetem no dia seguinte.

### Bloco 4 — Vagas de estágio
- Coletores HTML/API, `prompts/estagios.md`, extração dos campos da seção 4.
- **Pronto quando:** vagas relevantes aparecem no resumo com empresa, local e bolsa.

### Bloco 5 — Editais de concurso
- Coletores HTML e PDF, `prompts/concursos.md`, preenchimento de `prazo`.
- Comando `radar alertas-prazo`: avisa por e-mail itens salvos ou de nota alta com prazo em até 3 dias.
- **Pronto quando:** um edital de teste com prazo próximo gera alerta.

### Bloco 6 — Portal web
- Next.js em `web/`: feed por módulo, filtros, marcar lido/salvo, busca.
- Autenticação do Supabase (só o usuário) + políticas RLS; portal usa a anon key.
- **Pronto quando:** publicado na Vercel, acessível só pelo usuário.

### Bloco 7 — Feedback e personalização
- Botões 👍/👎 no portal (e links para eles no e-mail) → tabela `feedback`.
- Exemplos recentes de itens aprovados/rejeitados entram no prompt de triagem.

### Bloco 8 — Rotinas do Claude (configuração, não código Python)
- "Editor-chefe" diário e busca aberta semanal, configurados pelo usuário nas rotinas do Claude. Aqui, o agente só documenta o prompt e, se necessário, expõe um endpoint/consulta para a rotina ler os itens do dia.

### Bloco 9 — Monitoramento (transversal, começa no bloco 1)
- Alerta por e-mail se um coletor falhar 2 vezes seguidas ou passar 3 dias sem itens novos.
- Limpeza mensal: apaga `texto` de itens com mais de 90 dias não salvos (o Supabase gratuito tem 500 MB).

## 8. Quando parar e perguntar

- Trocar qualquer tecnologia da seção 2 ou adicionar serviço pago.
- Adicionar uma fonte cuja coleta pode violar termos de uso.
- Apagar dados ou alterar migrações já aplicadas (crie uma nova migração em vez disso).
- Qualquer decisão sobre o conteúdo do `perfil.md` ou sobre o que é "relevante" para o usuário.

## 9. Fora de escopo por enquanto

App mobile, múltiplos usuários, login social, imagens nas notícias, coleta de redes sociais, Telegram (substituído por e-mail em 2026-11-19).

## 10. Definição de pronto (vale para todo bloco)

1. `uv run ruff check .` e `uv run pytest` passam.
2. Funciona de ponta a ponta com dados reais, executado ao menos uma vez via `workflow_dispatch`.
3. `docs/progresso.md` atualizado: o que foi feito, como testar, pendências e próximas decisões para o usuário.
4. Nenhum segredo no código ou no histórico do git.
