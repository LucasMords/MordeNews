-- Bloco 7: votos 👍/👎 no portal (e pelos links do e-mail, que abrem o portal).
-- Rode uma vez no SQL Editor do Supabase, depois da 002.

-- Um voto por item: votar de novo troca o voto (upsert por item_id).
-- (Se a tabela tiver votos repetidos de testes, apague-os antes: delete from feedback;)
alter table public.feedback
  add constraint feedback_item_unico unique (item_id);

create index if not exists feedback_criado_em on public.feedback (criado_em desc);

-- A conta do portal lê, cria, troca e apaga os próprios votos. A chave pública sem login
-- (anon) continua sem acesso (revogado na 002). Os scripts Python usam a service role.
grant select, insert, delete on public.feedback to authenticated;
grant update (item_id, voto, criado_em) on public.feedback to authenticated;

create policy "portal le votos" on public.feedback
  for select to authenticated
  using ((select public.e_usuario_portal()));

create policy "portal vota" on public.feedback
  for insert to authenticated
  with check ((select public.e_usuario_portal()));

create policy "portal troca voto" on public.feedback
  for update to authenticated
  using ((select public.e_usuario_portal()))
  with check ((select public.e_usuario_portal()));

create policy "portal apaga voto" on public.feedback
  for delete to authenticated
  using ((select public.e_usuario_portal()));
