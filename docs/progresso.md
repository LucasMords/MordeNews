# Progresso

## Estado atual

> **Trocando de máquina?** Veja [`retomar.md`](retomar.md): como montar o ambiente, quais arquivos levar à mão e onde o projeto parou.

- **Bloco 0 — Fundação:** concluído e validado no Supabase real (2026-11-18).
- **Bloco 1 — Coletor RSS:** concluído (2026-11-18). Coleta local: 180 itens, e 0 duplicados na 2ª execução. No GitHub Actions (`workflow_dispatch`): 10/10 fontes ok e 7 itens novos sem duplicar, total de 187 no banco. O cron diário (06:13 BRT) está ativo.
- **Bloco 2 — Triagem por IA:** concluído (2026-11-19). Amostra de 20 notas aprovada pelo usuário. No GitHub Actions (`workflow_dispatch`, 12:48 UTC): coleta de 106 itens novos e triagem dos 106, sem erro. No banco: 265 processados, 28 descartados, 0 pendentes. 
- **Bloco 3 — Resumo diário por e-mail:** concluído (2026-11-19). **Fim do MVP.** 1º envio local: 30 assuntos (45 itens). O usuário confirmou que chegou na caixa de entrada, fora do spam. Depois, via `workflow_dispatch` no GitHub: 31 itens novos, sem repetir nenhum do 1º envio (76 itens distintos marcados). 
- **Bloco 4 — Vagas de estágio:** concluído (2026-11-20). 12 fontes de vagas. Via `workflow_dispatch` no GitHub: coleta de 22/22 fontes, triagem e e-mail "MordeNews 20/11: 41 itens" (30 assuntos de notícias + 11 entradas de vagas). O usuário confirmou que o e-mail chegou com a seção Estágios (empresa, local e bolsa). Coleta, triagem e resumo agora rodam no mesmo job, às 08:02 BRT, com reserva às 15:04.
- **Bloco 5 — Editais de concurso:** pronto localmente (2026-11-20), aguardando validação do usuário. 3 fontes (Concursos no Brasil TO e GO, PCI filtrado por TO e GO), 26 concursos triados com dados reais, seção Concursos no e-mail (sem nota, por prazo) e o comando `radar alertas-prazo`. Rodado via `workflow_dispatch` em 2026-11-20: coleta ok (25 fontes), e-mail enviado com a seção Concursos; a triagem pegou 503 do Gemini e o job ficou vermelho. Ajuste: 5xx persistente agora interrompe a triagem como o 429 (aviso no log, pendentes para a próxima, workflow não falha). Em 2026-11-21 o usuário considerou o alerta de prazo "meio dispensável por enquanto": ver o primeiro alerta real chegar deixou de ser requisito. **Falta:** o usuário validar a seção Concursos do e-mail.
- **Bloco 9 — Monitoramento:** pronto localmente (2026-11-21), aguardando validação do usuário. `radar monitorar` (fonte falhando 2 vezes seguidas ou há 3 dias sem itens novos), `radar limpar` (apaga o texto bruto depois de 90 dias) e o workflow mensal `manutencao`, que mantém os crons ativos.
- Crons: em 2026-11-19 o `coletar` rodou com ~9h de atraso, e o `resumo-diario` nunca disparou pelo cron. Resolvido juntando coleta, triagem e resumo em um job às 08:02, com reserva às 15:04. Em 2026-11-20 a reserva rodou com ~5h40 de atraso e deu certo. Em 2026-11-21, às 10h BRT, o das 08:02 ainda não tinha disparado. O usuário aceita o atraso: se um dia não rodar, o seguinte compensa (a coleta olha as últimas 72h de cada fonte). Sem serviço externo de cron.
- **Manutenção automática:** última em 2026-11-21 (workflow `manutencao`, todo dia 1).

---

## Bloco 9 — Monitoramento (2026-11-21)

Feito antes do bloco 6, a pedido do usuário. O `CLAUDE.md` já o tratava como transversal, desde o bloco 1.

### O que foi feito

- **`radar monitorar`** (`monitor.py`): olha as execuções dos últimos 4 dias de cada fonte do `fontes.yaml` e aponta dois tipos de problema:
  - **falhando:** as 2 últimas execuções falharam. O e-mail mostra o último erro.
  - **sem itens novos:** 3 dias sem nenhum item novo, mesmo rodando sem erro. Só vale para fontes monitoradas há mais de 3 dias, para uma fonte recém-adicionada não disparar o alerta.
- E-mail "MordeNews: N fontes com problema", em HTML e texto, com o texto de fora escapado. Cada problema é avisado **uma vez**. Se continuar, volta a ser avisado depois de 7 dias, para não chegar o mesmo e-mail todo dia. Os avisados ficam no campo `erro` da execução `monitor` em `execucoes`. Uma verificação por dia, no máximo (o `resumo-diario` roda duas vezes). Sem problema novo, não sai e-mail.
- Roda no `resumo-diario.yml`, depois do alerta de prazo.
- **`radar limpar`**: apaga **só o `texto`** dos itens com mais de 90 dias que não estão salvos nem pendentes. Título, resumo, nota, link e campos continuam no banco. A limpeza é registrada em `execucoes` como `limpeza`.
- **`.github/workflows/manutencao.yml`**: no dia 1 de cada mês, às 06:23 BRT, roda `radar limpar` e faz um commit atualizando a linha "Manutenção automática" deste arquivo. O repositório é público, e o GitHub desativa os crons depois de 60 dias sem atividade.
- `banco.py`: `execucoes_desde`, `contar_para_limpeza`, `limpar_textos`.
- Sem dependências e sem variáveis de ambiente novas.

### Validação

- `ruff` e `pytest` passam (inclui `tests/test_monitor.py`).
- Com dados reais, em 2026-11-21: `radar monitorar --simular` verificou 25 fontes, sem problemas (o histórico ainda tem só 3 dias); `radar limpar --simular` encontrou 0 itens, porque nenhum tem mais de 90 dias.

### Como testar

```powershell
uv run ruff check . ; uv run pytest
$env:PYTHONIOENCODING="utf-8"
uv run radar monitorar --simular   # lista os problemas atuais, sem enviar nem registrar
uv run radar limpar --simular      # conta quantos itens seriam limpos
gh workflow run manutencao         # testa o commit mensal (depois: git pull)
```

### Pendências

- [ ] Rodar o `manutencao` via `workflow_dispatch` e conferir o commit do bot.
- [ ] Ver o 1º alerta real do monitor. Fontes calmas (ex.: `gh-qa-brasil`, `iel-tocantins`) podem cair em "sem itens novos". Se isso incomodar, decidir se essas fontes ganham um limite maior de dias.
- [ ] Limitação: se o GitHub não rodar nenhum workflow, o monitor também não roda e não há quem avise.
- [ ] Depois do commit mensal do bot, dê `git pull` antes de trabalhar localmente.

---

## Bloco 5 — Editais de concurso (2026-11-20)

### Decisões do usuário

- **Escopo:** "qualquer concurso do TO ou GO", de qualquer cargo ou escolaridade. Também entram os concursos nacionais que os feeds estaduais publicam (IBGE, ANPD, Ministério da Saúde).
- **Concursos não têm nota.** Todos aparecem no e-mail, sem nota, ordenados pelo prazo de inscrição mais próximo. A IA continua dando uma nota, mas ela só serve de desempate; a função da IA aqui é extrair os campos e escrever o resumo.
- **PCI Concursos incluído assumindo o risco.** Os termos do PCI proíbem "raspagem (scraping) ou coleta automatizada em massa", numa cláusula da seção sobre o servidor MCP deles. O `robots.txt` permite `/concursos/`. Para reduzir o impacto, o coletor faz **uma única requisição por execução** à página de concursos abertos e não abre as notícias.

### Fontes

| Fonte | Tipo | Como coleta |
|---|---|---|
| `cnb-tocantins`, `cnb-goias` (Concursos no Brasil) | `rss-pagina` | Feed RSS oficial por estado. Como o feed traz só uma frase, o coletor abre o artigo de cada concurso novo. O `robots.txt` permite tudo, menos `/wp-admin/` |
| `pci-to-go` (PCI Concursos) | `pci` | 1 requisição à lista `/concursos/`, filtrada pelas UFs TO e GO. Órgão, vagas, salário, cargos, escolaridade e prazo já vêm na lista |

Ficaram de fora: Estratégia Concursos (o filtro por estado do feed não funciona), Gran Cursos (feed por estado vazio), JC Concursos (feed nacional, sem TO/GO) e QConcursos (403 para robôs).

### O que foi feito

- `coletores/html.py::ColetorPCI` e `coletores/rss.py::ColetorRSSPagina` (`tipo: pci` e `tipo: rss-pagina`). O campo novo `ufs` do `fontes.yaml` serve para o PCI.
- `ler_artigo`: texto do artigo sem anúncios, sem "Leia também" e sem menus. As frases sobre inscrição, vagas, salário e banca vão para o começo, porque a IA só recebe os primeiros 1.500 caracteres. Links externos cujo texto cita "edital" viram uma linha "Link do edital: ..."; links para outros artigos do próprio site ficam de fora.
- `modelos.CamposConcurso`: `orgao`, `cargos`, `escolaridade`, `salario_max`, `vagas`, `data_prova`, `link_edital` (seção 4 do `CLAUDE.md`). Valor inválido vira `null` sem derrubar o item.
- `ia/prompts/concursos.md`: extrai os campos e o **último dia de inscrição** como `prazo` (data da prova não é prazo). Só descarta o que não é concurso. O `link_edital` passa pela mesma conferência do `link_inscricao`: só fica se estiver escrito no texto.
- E-mail: seção "Concursos" sem nota, ordenada pelo prazo, com a linha "Órgão · vagas · salário · escolaridade · prova" e o link do edital. Os concursos com inscrição já encerrada saem do e-mail (o PCI lista retificações de concursos antigos). Limite próprio: `CONCURSOS_MAXIMO` (padrão 20), e `NOTA_MINIMA_CONCURSOS` (padrão 0).
- Agrupamento: o mesmo concurso no PCI e no Concursos no Brasil vira uma entrada só. A regra exige fontes diferentes, o mesmo órgão (as mesmas palavras em qualquer ordem, ou o mesmo tipo de órgão com o mesmo nome, sem contar palavras genéricas como "prefeitura" e "câmara") e prazos que não sejam diferentes. Com dados reais: juntou IFG, Câmara de Paraíso do Tocantins e Campo Limpo de Goiás, e manteve separados o estágio e o Jovem Aprendiz da Saneago e o concurso de Faina.
- **`radar alertas-prazo`** (`entrega/alertas.py`): e-mail com as inscrições que terminam em até 3 dias. Entram todos os concursos, as vagas e notícias com nota ≥ `NOTA_MINIMA_RESUMO` e os itens salvos. No máximo um alerta por dia (confere em `execucoes`). O mesmo prazo volta a ser avisado nos dias seguintes até terminar, como lembrete. Roda no `resumo-diario.yml`, depois do resumo. `--simular` mostra sem enviar.
- `banco.com_prazo(inicio, fim)` e o campo `salvo` em `ItemResumo`.
- Sem dependências novas. O coletor de **PDF** (edital em PDF) não foi necessário: as duas fontes já trazem prazo e campos em HTML.

### Validação com dados reais (2026-11-20)

- Coleta: 3 fontes ok, 26 concursos novos. Um concurso nacional que apareceu nos feeds de TO e de GO não foi duplicado.
- Triagem: 26 processados, 0 descartados, 0 sem resposta. Órgão, vagas, salário e escolaridade corretos na revisão. Prazo preenchido em 20 dos 26 (todos os 16 do PCI); os 6 do Concursos no Brasil sem prazo não citam a data de inscrição ou falam de edital previsto.
- Prévia do e-mail: 20 entradas em "Concursos" (26 itens: 3 com inscrição encerrada e 3 repetidos agrupados), da inscrição mais próxima (24/11) à mais distante.
- Alerta: um edital de teste com prazo para o dia seguinte, gravado no banco, gerou "MordeNews: 1 prazo de inscrição terminando" no `radar alertas-prazo --simular`. O item de teste foi apagado depois.

### Como testar

```powershell
uv run ruff check . ; uv run pytest
$env:PYTHONIOENCODING="utf-8"
uv run radar coletar --modulo concursos
uv run radar triar --modulo concursos
uv run radar revisar --modulo concursos --quantidade 30
uv run radar resumo --simular --salvar previa.html
uv run radar alertas-prazo --simular
```

### Pendências

- [ ] Rodar o `resumo-diario` via `workflow_dispatch` e conferir a seção Concursos no e-mail.
- [x] ~~Ver o primeiro alerta de prazo real chegar~~: dispensado pelo usuário em 2026-11-21 ("meio dispensável por enquanto"). O alerta continua ativo no workflow.
- [ ] Opcional: fontes oficiais (TCE-TO, TJTO, UFT, IFTO, UFG) e Diários Oficiais de TO e GO em PDF.
- [ ] Opcional: retificação de um concurso já enviado chega como item novo (o link do PCI muda). Fica como aviso de mudança no edital.

---

## Bloco 4 — Vagas de estágio (2026-11-19 a 2026-11-20)

### Fontes (decididas pelo usuário; detalhes em [`retomar.md`](retomar.md#5-bloco-4--onde-paramos-exatamente))

- **Programathor:** RSS oficial, usando o coletor `rss` que já existia.
- **10 repositórios de vagas no GitHub** (backend-br, frontendbr, react-brasil, nodejsdevbr, phpdevbr, soujava, dotnetdevbr, androiddevbr, DevOps-Brasil, qa-brasil): API REST oficial, uma issue por vaga.
- **IEL Tocantins** (`carreiras.iel.org.br/TO`): lê o `sitemap.xml` oficial e baixa só as páginas de vagas novas. Respeita o `robots.txt`, que bloqueia só `/api/`. Janela de 14 dias, porque as vagas ficam abertas por semanas.
- Ficaram de fora: LinkedIn, Instagram, Indeed, Catho e Vagas.com.br (bloqueiam robôs), Remotar (os termos proíbem robôs) e CIEE (só API interna sem documentação).

### O que foi feito

- `coletores/github.py` (`tipo: github`): issues abertas, sem pull requests, com as labels no texto (nível, modalidade, contrato). Usa `GITHUB_TOKEN` quando existe (no Actions é o token automático; localmente é opcional, com limite de 60 req/h).
- `coletores/html.py` (`tipo: iel`): sitemap → páginas das vagas → texto montado com os campos rotulados (Empresa, Atividades, Requisitos, Cidade, Remuneração...). O mural não informa a data de publicação, então `publicado_em = null`.
- `ia/prompts/estagios.md`: nota de 0 a 10 com prioridade para estágio em TI em TO, GO ou remoto. Extrai `empresa`, `area`, `cidade`, `remoto`, `bolsa`, `requisitos`, `link_inscricao` e `prazo`. Descarta vagas fora de TI. Vagas sênior não são descartadas: ganham nota baixa e o resumo explica a incompatibilidade.
- **Pedidos do usuário (2026-11-20):**
  - **Vaga júnior em TI tem nota 6 ou mais**, nunca 5 ou menos (regra fixa no prompt).
  - **Vagas aparecem no e-mail mesmo com nota baixa.** Variável nova `NOTA_MINIMA_ESTAGIOS` (padrão 0, ou seja, todas as triadas; as fora de TI já foram descartadas) e `ESTAGIOS_MAXIMO` (padrão 15). O limite das vagas é **separado** do `RESUMO_MAXIMO`, para as vagas não disputarem espaço com as notícias. O rodapé do e-mail explica a regra.
- E-mail: a linha "Empresa · Local · Bolsa" aparece em cada vaga.
- Agrupamento de vagas: a **mesma vaga repostada em outro repositório** vira uma entrada só, com "Também em". A regra exige fontes diferentes, a mesma empresa e títulos parecidos **sem contar** empresa, cidade e modalidade. Na mesma fonte nunca junta (ex.: SESI Licenciatura × Bacharelado são duas vagas).
- `banco.para_resumo` ganhou o filtro `modulos`.
- **Novo horário do resumo (pedido do usuário, 2026-11-20):** 08:02 BRT, com **reserva às 15:04 BRT**. O `resumo-diario` agora **coleta e tria no mesmo job, logo antes de enviar**; o `coletar.yml` ficou só manual. A reserva roda `radar resumo --reserva`, que confere em `execucoes` se já houve um `resumo-diario` com `ok = true` desde a meia-noite de Brasília, com ou sem e-mail. Se houve, não faz nada. Se a execução das 08h falhou ou nem rodou (o GitHub chegou a pular e atrasar crons), envia. Função nova: `banco.houve_execucao_ok`.
- Sem dependências novas.

### Validação com dados reais (2026-11-20)

- Coleta: 22 fontes ok, nenhuma duplicada na 2ª execução.
- Triagem: 22 vagas, todas com resposta válida. 8 do IEL descartadas por serem fora de TI (Educação Física, Administração, Pedagogia, Marketing), mesmo assim com empresa, cidade e bolsa extraídas certinho. 14 pleno/sênior com nota de 1 a 5 e o motivo da incompatibilidade no resumo.
- Prévia do e-mail: 10 entradas em "Estágios" (14 vagas, 4 repostadas agrupadas) e 30 assuntos em notícias.

### Como testar

```powershell
uv run ruff check . ; uv run pytest
$env:PYTHONIOENCODING="utf-8"
uv run radar coletar --fonte iel-tocantins
uv run radar triar --modulo estagios
uv run radar revisar --modulo estagios --quantidade 20
uv run radar resumo --simular --salvar previa.html
```

### Pendências

- [x] `coletar` e `resumo-diario` rodados via `workflow_dispatch` em 2026-11-20; e-mail confirmado pelo usuário.
- [ ] Ver o primeiro estágio/júnior de TI real e conferir a nota (≥ 6) e os campos no e-mail.
- [ ] IEL Goiás: ficou para depois (decisão do usuário).
- [ ] Opcional: variáveis `NOTA_MINIMA_ESTAGIOS` e `ESTAGIOS_MAXIMO` na aba Variables (vazio = 0 e 15).

---

## Bloco 3 — Resumo diário por e-mail (2026-11-19)

### Decisão do usuário: e-mail no lugar do Telegram

Em 2026-11-19 o usuário pediu para trocar o Telegram por e-mail (**só e-mail**, com o resumo completo no corpo até o portal existir). O `CLAUDE.md` foi atualizado nas seções 1, 2, 3, 5, 6, 7 (blocos 3, 5, 7 e 9) e 9. O envio sai de uma **conta Gmail comum e dedicada ao projeto**, com verificação em 2 etapas e **senha de app**, para não expor a caixa pessoal se o secret vazar.

### O que foi feito

- `entrega/correio.py`: monta o e-mail em HTML (layout de uma coluna, estilos inline, nota colorida, prazo em destaque) e em texto puro. Todo texto externo passa por `html.escape`. Envia por SMTP com SSL (`smtp.gmail.com:465`, timeout de 30s). Login recusado vira uma mensagem clara, sem expor a senha.
- `entrega/agrupamento.py`: junta a **mesma notícia vinda de fontes diferentes**, sem IA. A regra:
  - Se os dois itens citam CVEs, só são o mesmo assunto se for o mesmo CVE. CVEs diferentes nunca se juntam, mesmo com título parecido.
  - Se ao menos um não cita CVE, juntam quando compartilham um nome com letras e números (`java4shell`) ou quando têm ao menos 2 palavras significativas em comum, cobrindo 60% do título mais curto.
  - A relação é transitiva, e o item de maior nota vira o principal. Os outros aparecem como "Também em: fonte, fonte", com link.
- `entrega/resumo.py`: pega os itens `processado` ainda não enviados, com nota ≥ `NOTA_MINIMA_RESUMO`, coletados nas últimas 36h. Agrupa, envia os `RESUMO_MAXIMO` (30) assuntos de maior nota e **só depois do envio** marca `enviado_em` em todos os itens dos assuntos enviados, incluindo os repetidos. Dia sem itens não gera e-mail. Registra `resumo-diario` em `execucoes`.
- `banco.py`: `para_resumo(desde, nota_minima)`.
- CLI: `radar resumo` e `radar resumo --simular [--salvar previa.html]`. O modo simulação não envia, não marca e não pede credenciais.
- `.github/workflows/resumo-diario.yml`: cron `7 10 * * *` (07:07 BRT) e `workflow_dispatch`. Usa os secrets `EMAIL_REMETENTE`, `EMAIL_SENHA_APP` e `EMAIL_DESTINO`. `NOTA_MINIMA_RESUMO` e `RESUMO_MAXIMO` são opcionais, na aba Variables.
- Variáveis novas: `EMAIL_REMETENTE`, `EMAIL_SENHA_APP`, `EMAIL_DESTINO`, `RESUMO_MAXIMO` e as opcionais `SMTP_HOST` e `SMTP_PORTA`. As do Telegram foram removidas.
- Sem dependências novas: `smtplib`, `email` e `html` são da biblioteca padrão.

### Prévia com dados reais (2026-11-19)

172 itens candidatos viraram 155 assuntos depois do agrupamento. Exemplos de grupos: Java4Shell com 9 itens de 3 fontes, Gemini 4 Neon com 4, Nvidia/China com 3 (PT e EN), DaisyRose-27B com 3. O e-mail leva os 30 assuntos de maior nota (45 itens). Os outros 127 ficam de fora. Como este primeiro envio junta 3 dias de acúmulo, eles saem da janela de 36h e não serão enviados depois. Nos dias normais o volume deve ser bem menor.

**Limitação conhecida:** a mesma notícia em PT e EN com palavras diferentes (ex.: "Falhas no NGINX HTTP/2..." × "10-Year-Old NGINX HTTP/2 Flaw...") nem sempre é agrupada. Melhorar isso sem juntar assuntos diferentes por engano exigiria IA. Fica para o "editor-chefe" (bloco 8).

### Como testar

```powershell
uv run ruff check . ; uv run pytest
$env:PYTHONIOENCODING="utf-8"; uv run radar resumo --simular --salvar previa.html   # abre previa.html no navegador
uv run radar resumo                                                                   # envia de verdade
```

No GitHub: **Actions → resumo-diario → Run workflow** (secrets `EMAIL_REMETENTE`, `EMAIL_SENHA_APP` e `EMAIL_DESTINO`).

### Validação (2026-11-19)

- Envio local: "MordeNews 19/11: 30 itens, 21 em destaque". O usuário confirmou que chegou na caixa de entrada, fora do spam. 45 itens marcados (30 assuntos com os repetidos agrupados).
- `resumo-diario` via `workflow_dispatch` (15:21 UTC): 31 itens, todos diferentes dos 45 anteriores.

### Pendências

- [x] Crons conferidos em 2026-11-20: o `coletar` de 11-19 rodou com ~9h de atraso; o `resumo-diario` nunca disparou pelo cron. O resumo passou para 08:02 BRT, com reserva às 15:04 BRT (ver Bloco 4).
- [ ] `RADAR_CONTATO` (User-Agent): pode usar o Gmail do projeto.
- [ ] Hugging Face sem texto: manter ou trocar (a triagem pelo título está funcionando).
- Monitoramento (bloco 9): os alertas de falha agora vão por e-mail. A função de envio já existe e pode ser reaproveitada.

---

## Bloco 2 — Triagem por IA (2026-11-18 a 2026-11-19)

### O que foi feito

- `config/perfil.md`: perfil escrito pelo usuário, copiado sem alterações. É privado e fica fora do git (veja as decisões abaixo).
- `ia/prompts/noticias.md`: instruções do filtro de notícias. Define a escala da nota (9–10 muito relevante; 7–8 relevante; 5–6 interessante; 3–4 baixa; 0–2 descartar), quando descartar (publicidade, guia de presentes, caça-clique, produto sem impacto), o vocabulário fixo de 35 tags e as regras de não inventar. O resumo tem 2 frases: o fato e por que importa para o usuário.
- `ia/cliente.py`: `classificar_lote(itens, modulo)`, o único lugar que importa o SDK do Gemini. Manda só `id`, `titulo` e os primeiros 1.500 caracteres do `texto`, mais o perfil e a data de hoje. Pede saída JSON com schema (tags restritas ao vocabulário) e valida **item a item**: um item inválido não derruba o lote. Erro 429, 5xx ou de rede tem backoff de 5s, 15s e 45s. Se o 429 persistir, vira `CotaEsgotada`. Erro 4xx (ex.: chave inválida) falha na hora.
- `ia/triagem.py`: `triar(modulo)` busca até 500 pendentes (os **mais novos primeiro**), divide em lotes de 25 e pausa 4s entre lotes. Cada item tem **uma tentativa por execução**. O item sem resposta válida ganha `tentativas_ia + 1` e, na 3ª, vai para `erro`. Cota esgotada encerra sem falhar e os pendentes ficam para a próxima. Falha da API não gasta tentativa do item. Cada execução registra `triagem-noticias` em `execucoes`.
- `banco.py`: `gravar_triagem`, `registrar_falha_ia`, `triados_recentes`. O `pendentes` agora ordena do mais novo para o mais antigo.
- CLI: `radar triar [--modulo] [--max] [--lote]` e `radar revisar [--quantidade 20]`, que lista os últimos triados por nota para conferência.
- `coletar.yml`: novo passo `radar triar` depois da coleta. Precisa do secret `GEMINI_API_KEY`. `GEMINI_MODEL` é opcional, na aba **Variables**.

### Dependência nova

| Dependência | Motivo |
|---|---|
| `google-genai` | Já está na stack (SDK oficial do Gemini). Usado só em `ia/cliente.py`. |

### Decisões do usuário (2026-11-18)

- **Modelo: `gemini-3.5-flash-lite`**, padrão no código, no `.env.example` e no `CLAUDE.md`. O usuário pediu primeiro o `gemini-3.8-flash`, estável e gratuito segundo a doc do AI Studio. No teste real, porém, ele não respondeu nem a um "ok" (504 depois de ~90s, com ou sem *thinking* baixo), e os outros Flash (3.5, 3.6, 3.7) davam 503 "high demand" ou 504. Só o Flash-Lite respondia (~6s). Entre "3.8 com reserva Lite", "só Lite" e "só 3.8 esperando", o usuário escolheu **só o Lite**. A doc também diz que o acesso aos modelos 2.5 está limitado a quem já usava. Observação: no plano gratuito o Google pode usar o conteúdo enviado (incluindo o perfil) para melhorar os produtos dele.
- **Perfil privado:** `config/perfil.md` está no `.gitignore`. O repositório tem só o modelo `config/perfil.exemplo.md`. No GitHub Actions, o passo "Recriar perfil a partir do secret" escreve o arquivo a partir do secret `PERFIL_MD`. **Ao editar o perfil, atualize também o secret.**

### Resultado da triagem real (2026-11-19)

- 186 itens em 8 chamadas (lotes de 25), cerca de 20s por lote. 185 respostas válidas de primeira. 1 veio com id repetido e ficou pendente para a próxima execução, como previsto.
- **Problema encontrado e corrigido:** itens sem texto (Hacker News e Hugging Face) eram descartados com nota 0, mesmo com uma instrução no prompt para não fazer isso. Na correção, o próprio código (`texto_para_ia`) troca o texto vazio por um aviso explícito ("a fonte não fornece texto; avalie pelo título"). Para o Hacker News, os metadados viram "Pontos no Hacker News: N; comentários: M". Os 24 itens dessas duas fontes voltaram para `pendente` e foram re-triados: nenhum descarte por falta de texto.
- Distribuição das notas: 0:4 · 1:9 · 2:6 · 3:11 · 4:19 · 5:34 · 6:41 · 7:24 · 8:21 · 9:10 · 10:8. Com `NOTA_MINIMA_RESUMO=6`, cerca de 100 itens entrariam no resumo desta primeira rodada, que acumulou 72h. Num dia normal devem ser bem menos.
- Amostra de 20 (2 por fonte: maior e menor nota) **aprovada pelo usuário em 2026-11-19** ("se não gostar altero mais pra frente").

### Como testar

```powershell
uv run ruff check . ; uv run pytest
uv run radar triar --max 25       # um lote só
uv run radar triar                # todos os pendentes (até 500)
$env:PYTHONIOENCODING="utf-8"; uv run radar revisar --quantidade 20
```

No GitHub: **Actions → coletar → Run workflow**. Os secrets necessários são `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY` e `PERFIL_MD` (conteúdo inteiro do `config/perfil.md`).

### Pendências observadas

- **Mesma notícia em várias fontes** (ex.: Java4Shell aparece 4 vezes, no HN, no TabNews e no The Hacker News). A deduplicação é por URL. Agrupar por assunto pode entrar no resumo (bloco 3) ou no "editor-chefe" (bloco 8).
- O `revisar` e os scripts de diagnóstico mostram acentos quebrados no PowerShell do Windows se a saída não estiver em UTF-8. Use `$env:PYTHONIOENCODING="utf-8"`. No GitHub Actions (Linux) isso não acontece.

### Decisões que tomei e que você pode mudar

- A escala de notas e o vocabulário de tags saíram do seu perfil. Ficam em `ia/prompts/noticias.md`.
- Só `id`, título e texto vão para a IA, como pede o `CLAUDE.md`. O nome da fonte **não** vai, embora o perfil dê 20% de peso à confiabilidade da fonte. Se quiser, incluo.
- O formato do resumo segue o `CLAUDE.md` (até 2 frases). Os campos "O que fazer" e "Confiabilidade" do formato do seu perfil não existem na tabela. Dá para acrescentar depois, numa migração nova.

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

### GitHub

- Repositório público: `LucasMords/MordeNews`. Commits com o e-mail noreply do GitHub, configurado só neste repositório.
- Secrets em **Settings → Secrets and variables → Actions → Secrets**: `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` criados. `RADAR_CONTATO` ainda não.
- `testes` passou no push. `coletar` passou via `workflow_dispatch` em 2026-11-18 15:48 UTC.
- `.gitattributes` força quebras de linha LF, porque o CI roda em Linux e o desenvolvimento é no Windows.

### Pendências e decisões

- [x] Publicar no GitHub e rodar o `coletar` via `workflow_dispatch`.
- [ ] Conferir amanhã (2026-11-19) se a execução **agendada** das 06:13 BRT rodou em **Actions → coletar**. O GitHub pode atrasar crons alguns minutos.
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
