-- Bloco 6: acesso do portal web.
--
-- O portal usa a chave pública (anon/publishable) e o login do Supabase. Só lê os itens e
-- muda `lido` e `salvo`, e só para contas listadas em `usuarios_portal`. Os scripts Python
-- continuam com a service role key, que ignora RLS.
--
-- Rode no SQL Editor do Supabase. Depois, cadastre sua conta (troque o e-mail; ele não fica
-- no repositório, que é público):
--   insert into public.usuarios_portal (user_id)
--   select id from auth.users where email = 'SEU_EMAIL_AQUI';

create table public.usuarios_portal (
  user_id   uuid primary key references auth.users (id) on delete cascade,
  criado_em timestamptz not null default now()
);
-- RLS ligado e nenhuma política: a tabela não é lida nem alterada pela API, só pelo SQL Editor.
alter table public.usuarios_portal enable row level security;

-- `security definer` para consultar usuarios_portal sem expor a tabela.
create function public.e_usuario_portal()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.usuarios_portal where user_id = (select auth.uid())
  );
$$;
revoke all on function public.e_usuario_portal() from public, anon;
grant execute on function public.e_usuario_portal() to authenticated;

-- Privilégios: anon (sem login) não acessa nada; authenticated só lê itens e muda lido/salvo.
revoke all on public.itens, public.execucoes, public.feedback, public.usuarios_portal
  from anon, authenticated;
grant select on public.itens to authenticated;
grant update (lido, salvo) on public.itens to authenticated;

create policy "portal le itens"
  on public.itens for select
  to authenticated
  using ((select public.e_usuario_portal()));

create policy "portal marca lido e salvo"
  on public.itens for update
  to authenticated
  using ((select public.e_usuario_portal()))
  with check ((select public.e_usuario_portal()));

-- Listagem do portal por módulo, dos mais recentes.
create index on public.itens (modulo, coletado_em desc);
