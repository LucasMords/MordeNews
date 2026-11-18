-- 001_inicial.sql — esquema inicial do Radar pessoal.
-- Aplicar uma única vez no SQL Editor do Supabase. Não altere depois de aplicada:
-- mudanças futuras entram em 002_*.sql, 003_*.sql, ...

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
