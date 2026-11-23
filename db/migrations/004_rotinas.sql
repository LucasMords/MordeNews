-- Bloco 8: rotinas do Claude ("editor-chefe" diário e busca aberta semanal).
--
-- As rotinas rodam na nuvem da Anthropic e NÃO recebem a service role key. Elas chamam só
-- duas funções, com a chave pública (publishable) e um token próprio:
--   rotina_itens(token, desde)  -> lê os itens triados desde a data (com voto e salvo)
--   rotina_publicar(token, ...) -> grava a edição do dia/semana, que o portal mostra
-- O token não fica no banco: guardamos só o sha256 dele em `rotina_acesso`.
--
-- Rode no SQL Editor do Supabase. Depois gere o token (`uv run python scripts/rotina.py
-- gerar-token`) e rode o `insert` que o script imprime.

create table public.rotina_acesso (
  hash      text primary key check (hash ~ '^[0-9a-f]{64}$'),
  criado_em timestamptz not null default now()
);
-- RLS ligado e nenhuma política: só o SQL Editor e as funções abaixo enxergam a tabela.
alter table public.rotina_acesso enable row level security;

create table public.edicoes (
  id            bigint generated always as identity primary key,
  tipo          text not null check (tipo in ('diaria', 'semanal')),
  referencia    date not null,                       -- dia da edição (semanal: o domingo)
  titulo        text not null check (char_length(titulo) between 1 and 200),
  conteudo      text not null check (char_length(conteudo) between 1 and 20000), -- markdown simples
  criado_em     timestamptz not null default now(),
  atualizado_em timestamptz not null default now(),
  constraint edicoes_tipo_referencia_key unique (tipo, referencia)
);
alter table public.edicoes enable row level security;
create index on public.edicoes (tipo, referencia desc);

-- Portal: só lê as edições, com a mesma regra dos itens.
revoke all on public.edicoes, public.rotina_acesso from anon, authenticated;
grant select on public.edicoes to authenticated;
create policy "portal le edicoes"
  on public.edicoes for select
  to authenticated
  using ((select public.e_usuario_portal()));

-- Confere o token (sha256 em hex). Interna: não pode ser chamada pela API.
create function public.rotina_token_valido(token text)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select token is not null
     and char_length(token) between 32 and 200
     and exists (
       select 1 from public.rotina_acesso
       where hash = encode(pg_catalog.sha256(convert_to(token, 'UTF8')), 'hex')
     );
$$;
revoke all on function public.rotina_token_valido(text) from public, anon, authenticated;

create function public.rotina_itens(token text, desde timestamptz)
returns table (
  id bigint, modulo text, fonte text, titulo text, url text, publicado_em timestamptz,
  coletado_em timestamptz, nota smallint, resumo text, tags text[], campos jsonb, prazo date,
  salvo boolean, voto smallint
)
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if not public.rotina_token_valido(rotina_itens.token) then
    raise exception 'token da rotina inválido' using errcode = '28000';
  end if;
  return query
    select i.id, i.modulo, i.fonte, i.titulo, i.url, i.publicado_em, i.coletado_em, i.nota,
           i.resumo, i.tags, i.campos, i.prazo, i.salvo, f.voto
    from public.itens i
    left join public.feedback f on f.item_id = i.id
    where i.status = 'processado'
      and i.coletado_em >= greatest(rotina_itens.desde, now() - interval '14 days')
    order by i.nota desc nulls last, i.coletado_em desc
    limit 400;
end;
$$;

create function public.rotina_publicar(
  token text, tipo text, referencia date, titulo text, conteudo text
)
returns bigint
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  novo_id bigint;
begin
  if not public.rotina_token_valido(rotina_publicar.token) then
    raise exception 'token da rotina inválido' using errcode = '28000';
  end if;
  insert into public.edicoes as e (tipo, referencia, titulo, conteudo)
  values (rotina_publicar.tipo, rotina_publicar.referencia, rotina_publicar.titulo,
          rotina_publicar.conteudo)
  on conflict on constraint edicoes_tipo_referencia_key
  do update set titulo = excluded.titulo, conteudo = excluded.conteudo, atualizado_em = now()
  returning e.id into novo_id;
  return novo_id;
end;
$$;

-- As rotinas chamam sem login (role anon). O token é a única credencial.
revoke all on function public.rotina_itens(text, timestamptz) from public;
revoke all on function public.rotina_publicar(text, text, date, text, text) from public;
grant execute on function public.rotina_itens(text, timestamptz) to anon;
grant execute on function public.rotina_publicar(text, text, date, text, text) to anon;
