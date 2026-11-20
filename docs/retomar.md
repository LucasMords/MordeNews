# Onde paramos e como retomar

> Documento de passagem escrito em 2026-11-19, ao trocar de máquina.
> Detalhes de cada bloco ficam em [`progresso.md`](progresso.md). As regras do projeto estão no [`CLAUDE.md`](../CLAUDE.md).

## 1. Resumo em uma frase

O **MVP está pronto e rodando sozinho** (blocos 0 a 3). Todo dia o GitHub Actions coleta notícias de 10 feeds, a IA dá nota e resumo a cada uma e um e-mail chega com as mais relevantes. O **Bloco 4 (vagas de estágio)** está na fase de **escolha de fontes**, esperando decisões do usuário (seção 5).

## 2. O que já funciona

| Bloco | Situação | Validado em |
|---|---|---|
| 0 — Fundação (uv, banco Supabase, `radar teste-banco`) | ✅ concluído | 2026-11-18 |
| 1 — Coletor RSS (10 feeds de notícias) | ✅ concluído | 2026-11-18 |
| 2 — Triagem por IA (Gemini `gemini-3.5-flash-lite`) | ✅ concluído, amostra de 20 notas aprovada | 2026-11-19 |
| 3 — Resumo diário **por e-mail** (substituiu o Telegram) | ✅ concluído, e-mail recebido na caixa de entrada | 2026-11-19 |
| 4 — Vagas de estágio | 🟡 pesquisa de fontes feita, aguardando decisão | — |
| 5 a 9 | ⏳ não iniciados | — |

### Rotina automática (GitHub Actions, repositório público `LucasMords/MordeNews`)

| Horário (Brasília) | Workflow | O que faz |
|---|---|---|
| 06:13 | `coletar.yml` | `radar coletar --todos`, depois recria o perfil a partir do secret e roda `radar triar` |
| 07:07 | `resumo-diario.yml` | `radar resumo`: envia até 30 assuntos com nota ≥ 6, agrupando notícias repetidas |
| a cada push | `testes.yml` | `ruff check`, `ruff format --check`, `pytest` |

**Secrets já criados no GitHub:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, `PERFIL_MD`, `EMAIL_REMETENTE`, `EMAIL_SENHA_APP`, `EMAIL_DESTINO`.
Opcionais ainda não criados: `RADAR_CONTATO` (secret), `GEMINI_MODEL`, `NOTA_MINIMA_RESUMO` e `RESUMO_MAXIMO` (aba **Variables**).

## 3. Montar o ambiente na outra máquina

### 3.1 Arquivos que NÃO estão no GitHub (leve você mesmo)

O repositório é público, então estes dois arquivos ficam de fora de propósito (`.gitignore`):

| Arquivo | Conteúdo | Como levar |
|---|---|---|
| `.env` | Chaves do Supabase e do Gemini, e-mail e senha de app | Pen drive, gerenciador de senhas ou cópia manual. **Nunca** por commit, chat ou e-mail sem proteção |
| `config/perfil.md` | Perfil de interesses usado pela triagem | Mesma forma. Atenção: o GitHub **não deixa ler** o valor de um secret depois de salvo, então o `PERFIL_MD` não serve de backup |

Se perder o `.env`, dá para recriar a partir do `.env.example`, gerando chaves novas no Supabase, no Google AI Studio e nas senhas de app do Google.

### 3.2 Passo a passo (Windows)

```powershell
# 1. Ferramentas
winget install --id astral-sh.uv -e        # abra um terminal novo depois
winget install --id Git.Git -e             # se ainda não tiver o git
uv python install 3.12

# 2. Código
git clone https://github.com/LucasMords/MordeNews.git
cd MordeNews
uv sync

# 3. Identidade do git SÓ neste repositório (e-mail noreply: o repositório é público)
git config user.name "LucasMords"
git config user.email "211219958+LucasMords@users.noreply.github.com"

# 4. Copie o .env e o config/perfil.md para a pasta do projeto (seção 3.1)

# 5. Conferir que está tudo certo
uv run ruff check . ; uv run pytest          # deve passar tudo, sem rede
uv run radar teste-banco                       # testa a conexão com o Supabase
$env:PYTHONIOENCODING="utf-8"; uv run radar resumo --simular   # mostra o resumo sem enviar
```

No macOS/Linux: instale o uv com `curl -LsSf https://astral.sh/uv/install.sh | sh`. O resto é igual (troque `;` por `&&`).

### 3.3 Retomar com o Claude Code

Abra o Claude Code na pasta do projeto e peça algo como:

> Leia o `CLAUDE.md`, o `docs/retomar.md` e o `docs/progresso.md` e continue o Bloco 4 a partir das decisões pendentes.

## 4. Comandos do dia a dia

| Comando | Para quê |
|---|---|
| `uv run radar coletar --todos` (ou `--fonte NOME`) | Coleta agora |
| `uv run radar triar` (ou `--max 25`) | Tria os pendentes com a IA |
| `uv run radar revisar --quantidade 20` | Lista os últimos triados por nota |
| `uv run radar resumo --simular --salvar previa.html` | Prévia do e-mail sem enviar |
| `uv run radar resumo` | Envia o e-mail de verdade |
| `uv run radar teste-banco` | Testa o Supabase |

## 5. Bloco 4 — onde paramos exatamente

### Já decidido pelo usuário

- **Áreas:** tecnologia em geral, sem filtro (desenvolvimento, suporte, infraestrutura, dados etc.).
- **Região prioritária:** Palmas e Tocantins, **Goiânia e Goiás** (adicionado agora) e vagas remotas nacionais.
- Fontes citadas pelo usuário: LinkedIn, Indeed, Instagram e "outros sites de vagas".

### Resultado da pesquisa de fontes (2026-11-19)

**Não podem ser usadas:**

| Fonte | Motivo |
|---|---|
| LinkedIn | `robots.txt` bloqueia, os termos proíbem e o `CLAUDE.md` veta |
| Instagram | `robots.txt` bloqueia, exige login e rede social está fora do escopo |
| Indeed | Responde 403 para robôs |
| Catho, Vagas.com.br | 403 / desafio anti-robô (Cloudflare) |
| Portal do Estágio (Substack) | Parado (último post em abril de 2026) |
| Trampos.co | Só 13 estágios, e apenas 1 de TI: pouco útil |

**Recomendadas para começar (canal oficial, permitido):**

| Fonte | Canal | Observação |
|---|---|---|
| Programathor | RSS oficial `https://programathor.com.br/jobs.rss` | Só tecnologia, 30 vagas no feed. Muito pleno e sênior, mas tem júnior e estágio |
| Repositórios de vagas no GitHub | API oficial (`/repos/{repo}/issues`) | `backend-br/vagas` teve 39 vagas em 30 dias. Também: frontendbr, react-brasil, DevOps-Brasil, phpdevbr, androiddevbr, soujava/vagas-java, dotnetdevbr, qa-brasil, nodejsdevbr |

**Promissoras, mas pendentes de decisão:**

| Fonte | O que traz | Pendência |
|---|---|---|
| Remotar | 114 estágios **remotos** abertos, com `createdAt`, `expiresAt` e categorias | Dados por um endpoint JSON usado pelo próprio site, **sem documentação de API pública** |
| CIEE | Maior agente de estágio, com vagas em **GO e TO** | A página de vagas usa uma API interna. A tentativa de examinar o JavaScript dela foi **bloqueada pelo sistema de permissões do Claude Code** como acesso não autorizado; a análise parou ali |
| IEL Tocantins / IEL Goiás | Mural diário de estágios, inclusive informática | Endereço oficial do mural não encontrado (os domínios testados não existem) |

### Decisões do usuário (2026-11-19, segunda sessão)

1. **Programathor (RSS) + repositórios de vagas no GitHub (API):** aprovados.
2. **Remotar e CIEE:** ler os termos antes. Resultado:
   - **Remotar: fora.** Os termos (`remotar.com.br/termos-de-uso`, seção "Obrigações do Candidato") proíbem "mecanismos, software ou scripts" e cópia por "Robot/Crawler".
   - **CIEE: fora por enquanto.** O link "Termos de uso" do portal leva só à política de privacidade, que não trata de acesso automatizado. O `robots.txt` de `portal.ciee.org.br` está vazio, mas as vagas ficam em apps Angular (`web.ciee.org.br`, `pp.ciee.org.br`) que só carregam por API interna sem documentação. Sem canal aberto, não entra.
3. **IEL:** o usuário informou `https://carreiras.iel.org.br/TO`. **Por enquanto, só Tocantins** (Goiás fica para depois).
   - `robots.txt`: `Allow: /`, `Disallow: /api/`. Não usar a API.
   - O `sitemap.xml` oficial lista as vagas (24 de TO em 2026-11-19). A página de cada vaga (`/TO/vaga/estagio/{id}/{slug}`) vem em HTML pronto, com campos rotulados: Empresa, Atividades, Requisitos, Cursos, Escolaridade, Cidade, Remuneração, Benefícios, Horários e Formato de trabalho. **Não tem data de publicação** (`publicado_em = null`; o id é crescente).
   - Plano do coletor: ler o sitemap, filtrar `/TO/vaga/`, baixar só as vagas que ainda não estão no banco e montar o `texto` com os campos rotulados.

### O que o Bloco 4 ainda vai precisar (depois das fontes)

- Coletor de API (GitHub e, se aprovado, Remotar/CIEE) além do RSS que já existe. `fontes.yaml` ganha `tipo: api`, `modulo: estagios`.
- `ia/prompts/estagios.md`: extrair `empresa`, `area`, `cidade`, `remoto`, `bolsa`, `requisitos`, `link_inscricao` e `prazo`, com prioridade para TO, GO e remoto. Vaga sênior não pode aparecer como adequada sem explicar a incompatibilidade (regra do perfil).
- O e-mail já tem uma seção "Estágios" pronta, e o prazo já aparece em destaque.
- Editais de estágio em órgãos públicos (IFTO, UFT, IFG, tribunais) encaixam melhor no **Bloco 5** (editais e PDF).

## 6. Pendências gerais

- [ ] **Conferir se os crons agendados disparam.** Em 2026-11-19 o das 06:13 não disparou (o GitHub pode atrasar ou pular crons em workflows novos). Se pular de novo, adicionar um horário de reserva no `coletar.yml` e no `resumo-diario.yml`. Rodar duas vezes é seguro: a coleta não duplica, a triagem só pega pendentes e o resumo só pega o que não foi enviado.
- [ ] `RADAR_CONTATO`: pode ser o Gmail do projeto (no `.env` e como secret).
- [ ] Hugging Face Blog sem texto no feed: está funcionando só pelo título; manter ou trocar.
- [ ] A mesma notícia em PT e EN com palavras diferentes às vezes não é agrupada no e-mail. Limitação conhecida, candidata ao "editor-chefe" (Bloco 8).
- [ ] Repositório público: no **Bloco 9**, criar um commit automático mensal para o GitHub não desativar os crons depois de 60 dias sem atividade.

## 7. Decisões importantes já tomadas (para não rediscutir)

| Decisão | Motivo |
|---|---|
| Supabase via API REST com `httpx` (sem o SDK `supabase`) | Menos dependências; tudo fica isolado em `banco.py` |
| Modelo `gemini-3.5-flash-lite` | Os Flash maiores (3.5 a 3.8) davam 503/504 por sobrecarga no plano gratuito. O usuário escolheu "só o Lite" |
| Perfil privado (`config/perfil.md` fora do git, secret `PERFIL_MD`) | Repositório público; o perfil tem dados pessoais |
| **E-mail no lugar do Telegram** (Gmail dedicado + senha de app, `smtplib`) | Pedido do usuário; o `CLAUDE.md` foi atualizado |
| Itens sem texto (Hacker News, Hugging Face) recebem um aviso explícito para a IA | Sem isso o Flash-Lite descartava esses itens com nota 0 |
| Agrupamento de repetidos por regras (mesmo CVE, nome com letras e números, títulos parecidos) | Sem custo de IA; CVEs diferentes nunca se juntam |
| Commits com o e-mail noreply do GitHub, configurado só no repositório | Não expor o e-mail pessoal no repositório público |

## 8. Armadilhas conhecidas (Windows)

- **Acentos quebrados no terminal:** use `$env:PYTHONIOENCODING="utf-8"` antes de `radar revisar` ou `radar resumo --simular`. No GitHub Actions (Linux) isso não acontece.
- **Mensagem de commit pelo PowerShell 5.1:** `Out-File -Encoding utf8` grava BOM, por isso o commit `cb4126d` tem um caractere invisível no início. Grave a mensagem com `[IO.File]::WriteAllText(..., (New-Object Text.UTF8Encoding $false))` ou use `git commit -m`.
- **`ruff format` e Markdown:** o ruff recente formata blocos de código dentro de `.md`; o `pyproject.toml` exclui `*.md` para não mexer no `CLAUDE.md`.
- **`uv` recém-instalado:** abra um terminal novo para ele entrar no PATH.
