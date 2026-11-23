# Rotinas do Claude (bloco 8)

Duas rotinas agendadas no seu plano do Claude, que rodam na nuvem da Anthropic com este
repositório:

| Rotina | Quando | O que faz | Prompt |
|---|---|---|---|
| Editor-chefe | todo dia, 09:00 BRT | junta as repetidas, escolhe o que importa e escreve a edição do dia | [editor-chefe.md](editor-chefe.md) |
| Busca aberta | domingo, 10:00 BRT | procura na web vagas, editais e notícias que os coletores não pegaram e sugere fontes | [busca-semanal.md](busca-semanal.md) |

As duas publicam no portal: a edição do dia aparece no topo do Início; a da semana, no fim.

## Como as rotinas falam com o banco

As rotinas **não** recebem a service role key. Elas usam `scripts/rotina.py` (só biblioteca
padrão do Python), que chama duas funções do Supabase com a chave pública e um token próprio:

- `rotina_itens(token, desde)`: lê os itens **triados** (no máximo 14 dias e 400 itens), com voto e salvo.
- `rotina_publicar(token, tipo, referencia, titulo, conteudo)`: grava a edição (`diaria` ou `semanal`).

O token não pode mais nada: não lê `texto`, `execucoes` nem usuários, não muda itens e não apaga
nada. O banco guarda só o sha256 dele (`rotina_acesso`).

## Configuração (uma vez)

1. **Supabase → SQL Editor:** rode `db/migrations/004_rotinas.sql`.
2. **Na sua máquina**, gere o token:
   ```
   uv run python scripts/rotina.py gerar-token
   ```
   Rode no SQL Editor o `insert into public.rotina_acesso ...` que ele imprime. Guarde o token
   (gerenciador de senhas); ele não vai para o repositório.
3. **claude.ai/code → ambiente de nuvem** (crie um, por exemplo "MordeNews rotinas"):
   - Variáveis de ambiente:
     ```
     SUPABASE_URL=https://SEU-PROJETO.supabase.co
     SUPABASE_PUBLISHABLE_KEY=sb_publishable_...   (a mesma do portal na Vercel)
     ROTINA_TOKEN=o token do passo 2
     ```
   - Acesso à rede: precisa alcançar `SEU-PROJETO.supabase.co`. Se o nível "confiável" bloquear,
     use "personalizado" com esse domínio. Se a busca semanal não conseguir abrir as páginas que
     encontra, libere acesso total nesse ambiente.
4. **Crie as duas rotinas** (claude.ai/code → Rotinas, ou `/schedule` no Claude Code):
   repositório `LucasMords/MordeNews`, o ambiente do passo 3, o horário da tabela acima e o
   prompt do arquivo correspondente. Na busca semanal, cole o seu `config/perfil.md` no lugar indicado.
5. Use **"Executar agora"** em cada uma e abra o Início do portal: a edição deve aparecer.

## Testar na sua máquina

No PowerShell, com as mesmas três variáveis:

```
$env:SUPABASE_URL="https://SEU-PROJETO.supabase.co"
$env:SUPABASE_PUBLISHABLE_KEY="sb_publishable_..."
$env:ROTINA_TOKEN="..."
uv run python scripts/rotina.py ler --horas 30
```

## Trocar ou revogar o token

No SQL Editor: `delete from public.rotina_acesso;` revoga na hora. Para trocar, gere outro
(passo 2), cadastre o hash novo e atualize `ROTINA_TOKEN` no ambiente das rotinas.
