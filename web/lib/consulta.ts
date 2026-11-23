import type { SupabaseClient } from "@supabase/supabase-js";
import { type Filtros, juntarGrupos, ordenaPorPrazo, POR_PAGINA } from "./filtros";
import { hojeBrasilia } from "./formato";
import { COLUNAS_ITEM, type Item, lerVoto, MODULOS, type Modulo } from "./tipos";

const DIA = 86_400_000;

export interface Pagina {
  itens: Item[];
  total: number;
}

function itens(supabase: SupabaseClient) {
  return supabase.from("itens").select(COLUNAS_ITEM).eq("status", "processado");
}

function lista(data: unknown, error: { message: string } | null, oque: string): Item[] {
  if (error) throw new Error(`Falha ao ler ${oque}: ${error.message}`);
  return ((data ?? []) as (Omit<Item, "voto"> & { feedback?: unknown })[]).map(({ feedback, ...item }) => ({
    ...item,
    voto: lerVoto(feedback),
  }));
}

/** Itens triados (status processado) da seção, com os filtros da URL. */
export async function buscarItens(supabase: SupabaseClient, filtros: Filtros): Promise<Pagina> {
  const inicio = (filtros.pagina - 1) * POR_PAGINA;
  let consulta = supabase
    .from("itens")
    .select(COLUNAS_ITEM, { count: "exact" })
    .eq("status", "processado");

  if (filtros.modulo !== "todos") consulta = consulta.eq("modulo", filtros.modulo);
  if (filtros.notaMinima > 0) consulta = consulta.gte("nota", filtros.notaMinima);
  if (filtros.estado === "nao-lidos") consulta = consulta.eq("lido", false);
  if (filtros.estado === "salvos") consulta = consulta.eq("salvo", true);
  if (filtros.tag) consulta = consulta.contains("tags", [filtros.tag]);

  // Os filtros "ou" vão num único parâmetro `or` (ver juntarGrupos).
  const grupos: string[] = [];
  if (filtros.busca) {
    const termo = `%${filtros.busca}%`;
    grupos.push(`titulo.ilike.${termo},resumo.ilike.${termo}`);
  }

  if (ordenaPorPrazo(filtros.modulo)) {
    if (!filtros.encerrados) grupos.push(`prazo.is.null,prazo.gte.${hojeBrasilia()}`);
    consulta = consulta
      .order("prazo", { ascending: true, nullsFirst: false })
      .order("nota", { ascending: false, nullsFirst: false });
  } else if (filtros.ordem === "nota") {
    consulta = consulta
      .order("nota", { ascending: false, nullsFirst: false })
      .order("coletado_em", { ascending: false });
  } else {
    consulta = consulta.order("coletado_em", { ascending: false });
  }

  const condicoes = juntarGrupos(grupos);
  if (condicoes) consulta = consulta.or(condicoes);

  const { data, error, count } = await consulta
    .order("id", { ascending: false })
    .range(inicio, inicio + POR_PAGINA - 1);
  return { itens: lista(data, error, "os itens"), total: count ?? 0 };
}

export interface Inicio {
  destaque: Item | null; // notícia de maior nota dos últimos 2 dias
  ultimas: Item[];
}

/** Dados da página inicial: o destaque e as últimas notícias (sem repetir o destaque). */
export async function buscarInicio(supabase: SupabaseClient, agora = new Date()): Promise<Inicio> {
  const desde = new Date(agora.getTime() - 2 * DIA).toISOString();
  const [destaques, recentes] = await Promise.all([
    itens(supabase)
      .eq("modulo", "noticias")
      .gte("coletado_em", desde)
      .order("nota", { ascending: false, nullsFirst: false })
      .order("coletado_em", { ascending: false })
      .limit(1),
    itens(supabase).eq("modulo", "noticias").order("coletado_em", { ascending: false }).limit(9),
  ]);
  const ultimas = lista(recentes.data, recentes.error, "as últimas notícias");
  const destaque = lista(destaques.data, destaques.error, "o destaque")[0] ?? ultimas[0] ?? null;
  return { destaque, ultimas: ultimas.filter((item) => item.id !== destaque?.id).slice(0, 8) };
}

/** Próximos prazos de inscrição (vagas e concursos), dos mais próximos aos mais distantes. */
export async function buscarPrazos(supabase: SupabaseClient, agora = new Date(), limite = 5): Promise<Item[]> {
  const hoje = hojeBrasilia(agora);
  const ate = hojeBrasilia(new Date(agora.getTime() + 15 * DIA));
  const { data, error } = await itens(supabase)
    .gte("prazo", hoje)
    .lte("prazo", ate)
    .order("prazo", { ascending: true })
    .order("nota", { ascending: false, nullsFirst: false })
    .limit(limite);
  return lista(data, error, "os prazos");
}

/** Tags mais frequentes da última semana, para os atalhos "Acompanhe também". */
export async function buscarTags(supabase: SupabaseClient, agora = new Date(), limite = 8): Promise<string[]> {
  const desde = new Date(agora.getTime() - 7 * DIA).toISOString();
  const { data, error } = await supabase
    .from("itens")
    .select("tags")
    .eq("status", "processado")
    .gte("coletado_em", desde)
    .limit(500);
  if (error) throw new Error(`Falha ao ler as tags: ${error.message}`);
  const contagem = new Map<string, number>();
  for (const linha of (data ?? []) as { tags: string[] | null }[]) {
    for (const tag of linha.tags ?? []) contagem.set(tag, (contagem.get(tag) ?? 0) + 1);
  }
  return [...contagem.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limite)
    .map(([tag]) => tag);
}

export interface Painel {
  naoLidos: Record<Modulo, number>;
  salvos: number;
  prazosProximos: number; // inscrições que terminam em até 3 dias
  novos24h: number;
}

/** Números do painel, em consultas só de contagem (`head`), todas em paralelo. */
export async function contarPainel(supabase: SupabaseClient, agora = new Date()): Promise<Painel> {
  const hoje = hojeBrasilia(agora);
  const daqui3 = hojeBrasilia(new Date(agora.getTime() + 3 * DIA));
  const ontem = new Date(agora.getTime() - DIA).toISOString();
  const base = () =>
    supabase.from("itens").select("id", { count: "exact", head: true }).eq("status", "processado");

  const naoLidos = MODULOS.map((modulo) => {
    let consulta = base().eq("modulo", modulo).eq("lido", false);
    if (ordenaPorPrazo(modulo)) consulta = consulta.or(`prazo.is.null,prazo.gte.${hoje}`);
    return consulta;
  });
  const respostas = await Promise.all([
    ...naoLidos,
    base().eq("salvo", true),
    base().gte("prazo", hoje).lte("prazo", daqui3),
    base().gte("coletado_em", ontem),
  ]);
  const erro = respostas.find((r) => r.error)?.error;
  if (erro) throw new Error(`Falha ao contar os itens: ${erro.message}`);
  const contagens = respostas.map((r) => r.count ?? 0);
  return {
    naoLidos: Object.fromEntries(MODULOS.map((m, i) => [m, contagens[i]])) as Record<Modulo, number>,
    salvos: contagens[3],
    prazosProximos: contagens[4],
    novos24h: contagens[5],
  };
}

/** Se a conta logada está em `usuarios_portal` (sem isso, o RLS devolve tudo vazio). */
export async function temAcesso(supabase: SupabaseClient): Promise<boolean> {
  const { data, error } = await supabase.rpc("e_usuario_portal");
  if (error) throw new Error(`Falha ao conferir o acesso: ${error.message}`);
  return data === true;
}

export interface Usuario {
  nome: string; // NOME_USUARIO do .env.local ou a parte antes do @ do e-mail
  email: string;
}

/** Quem está logado, para a saudação e o cartão do menu (lido do token, sem ida à rede). */
export async function usuarioAtual(supabase: SupabaseClient): Promise<Usuario> {
  const { data } = await supabase.auth.getClaims();
  const email = typeof data?.claims.email === "string" ? data.claims.email : "";
  const nome = process.env.NOME_USUARIO?.trim() || email.split("@")[0] || "você";
  return { nome, email };
}

export interface Edicao {
  tipo: "diaria" | "semanal";
  referencia: string; // AAAA-MM-DD
  titulo: string;
  conteudo: string; // markdown simples (ver lib/markdown.ts)
  atualizado_em: string;
}

export interface Edicoes {
  diaria: Edicao | null; // dos últimos 3 dias
  semanal: Edicao | null; // dos últimos 10 dias
}

/**
 * Últimas edições das rotinas do Claude (bloco 8). Elas são um extra: se a tabela ainda não
 * existe (migração 004 não rodou) ou a leitura falha, o Início abre sem elas.
 */
export async function buscarEdicoes(supabase: SupabaseClient, agora = new Date()): Promise<Edicoes> {
  const desde = hojeBrasilia(new Date(agora.getTime() - 10 * DIA));
  const { data, error } = await supabase
    .from("edicoes")
    .select("tipo,referencia,titulo,conteudo,atualizado_em")
    .gte("referencia", desde)
    .order("referencia", { ascending: false })
    .limit(10);
  if (error) {
    console.error(`Falha ao ler as edições: ${error.message}`);
    return { diaria: null, semanal: null };
  }
  const edicoes = (data ?? []) as Edicao[];
  const limiteDiaria = hojeBrasilia(new Date(agora.getTime() - 3 * DIA));
  return {
    diaria: edicoes.find((e) => e.tipo === "diaria" && e.referencia >= limiteDiaria) ?? null,
    semanal: edicoes.find((e) => e.tipo === "semanal") ?? null,
  };
}
