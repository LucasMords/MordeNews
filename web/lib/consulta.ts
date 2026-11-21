import type { SupabaseClient } from "@supabase/supabase-js";
import { type Filtros, juntarGrupos, ordenaPorPrazo, POR_PAGINA } from "./filtros";
import { hojeBrasilia } from "./formato";
import { COLUNAS_ITEM, type Item } from "./tipos";

export interface Pagina {
  itens: Item[];
  total: number;
}

/** Itens triados (status processado) do módulo, com os filtros da URL. */
export async function buscarItens(supabase: SupabaseClient, filtros: Filtros): Promise<Pagina> {
  const inicio = (filtros.pagina - 1) * POR_PAGINA;
  let consulta = supabase
    .from("itens")
    .select(COLUNAS_ITEM, { count: "exact" })
    .eq("modulo", filtros.modulo)
    .eq("status", "processado");

  if (filtros.notaMinima > 0) consulta = consulta.gte("nota", filtros.notaMinima);
  if (filtros.estado === "nao-lidos") consulta = consulta.eq("lido", false);
  if (filtros.estado === "salvos") consulta = consulta.eq("salvo", true);

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
  if (error) throw new Error(`Falha ao ler os itens: ${error.message}`);
  return { itens: (data ?? []) as unknown as Item[], total: count ?? 0 };
}

/** Se a conta logada está em `usuarios_portal` (sem isso, o RLS devolve tudo vazio). */
export async function temAcesso(supabase: SupabaseClient): Promise<boolean> {
  const { data, error } = await supabase.rpc("e_usuario_portal");
  if (error) throw new Error(`Falha ao conferir o acesso: ${error.message}`);
  return data === true;
}
