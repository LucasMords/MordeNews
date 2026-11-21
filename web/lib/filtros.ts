import { MODULOS, type Modulo } from "./tipos";

export const POR_PAGINA = 30;
const BUSCA_MAXIMA = 80;

export type Estado = "todos" | "nao-lidos" | "salvos";
const ESTADOS: readonly Estado[] = ["todos", "nao-lidos", "salvos"];

export type Ordem = "recentes" | "nota";

/** Um módulo ou "todos" (busca geral e salvos de todos os módulos). */
export type Secao = Modulo | "todos";

export interface Filtros {
  modulo: Secao;
  busca: string; // já limpa, pronta para o filtro ilike
  tag: string; // uma tag exata ("" = qualquer)
  notaMinima: number; // 0 a 10
  estado: Estado;
  encerrados: boolean; // vagas/concursos com prazo vencido
  ordem: Ordem; // só para notícias e "todos"
  pagina: number; // começa em 1
}

export type Parametros = Record<string, string | string[] | undefined>;

function primeiro(valor: string | string[] | undefined): string {
  return (Array.isArray(valor) ? valor[0] : valor) ?? "";
}

function inteiro(valor: string, padrao: number, minimo: number, maximo: number): number {
  const numero = Number.parseInt(valor, 10);
  if (Number.isNaN(numero)) return padrao;
  return Math.min(maximo, Math.max(minimo, numero));
}

/**
 * Limpa o texto da busca para o filtro `or` do PostgREST: vírgula, parênteses, aspas,
 * barra invertida, dois-pontos e curingas (`%`, `*`, `_`) mudam o sentido do filtro, então
 * viram espaço.
 */
export function limparBusca(texto: string): string {
  return texto
    .replace(/[,()"'\\:%*_]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, BUSCA_MAXIMA);
}

/** Tag só com letras, números, espaço, ponto, hífen, + e #: nada que mude o filtro `cs`. */
export function limparTag(texto: string): string {
  return texto
    .replace(/[^\p{L}\p{N} .+#-]/gu, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 40);
}

/** Sem nenhum parâmetro, a raiz mostra a página inicial (painel) em vez de um feed. */
export function eInicio(params: Parametros): boolean {
  return !["modulo", "q", "tag", "nota", "ver", "encerrados", "ordem", "pagina"].some((chave) =>
    primeiro(params[chave]),
  );
}

/** Lê os filtros da URL. Valor inválido volta ao padrão, sem erro. */
export function lerFiltros(params: Parametros): Filtros {
  const modulo = primeiro(params.modulo) as Secao;
  const estado = primeiro(params.ver) as Estado;
  return {
    modulo: modulo === "todos" || MODULOS.includes(modulo as Modulo) ? modulo : "noticias",
    busca: limparBusca(primeiro(params.q)),
    tag: limparTag(primeiro(params.tag)),
    notaMinima: inteiro(primeiro(params.nota), 0, 0, 10),
    estado: ESTADOS.includes(estado) ? estado : "todos",
    encerrados: primeiro(params.encerrados) === "1",
    ordem: primeiro(params.ordem) === "nota" ? "nota" : "recentes",
    pagina: inteiro(primeiro(params.pagina), 1, 1, 1000),
  };
}

/** Filtros "limpos" de uma seção: base para os links do menu e do painel. */
export function filtrosDe(modulo: Secao, mudancas: Partial<Filtros> = {}): Filtros {
  return { ...lerFiltros({}), modulo, ...mudancas };
}

/** Monta a URL do feed com os filtros. O módulo vai sempre (a raiz sem nada é a página inicial). */
export function urlFeed(filtros: Filtros, mudancas: Partial<Filtros> = {}): string {
  const f = { ...filtros, ...mudancas };
  const params = new URLSearchParams();
  params.set("modulo", f.modulo);
  if (f.busca) params.set("q", f.busca);
  if (f.tag) params.set("tag", f.tag);
  if (f.notaMinima > 0) params.set("nota", String(f.notaMinima));
  if (f.estado !== "todos") params.set("ver", f.estado);
  if (f.encerrados) params.set("encerrados", "1");
  if (f.ordem !== "recentes") params.set("ordem", f.ordem);
  if (f.pagina > 1) params.set("pagina", String(f.pagina));
  return `/?${params.toString()}`;
}

/** Vagas e concursos são ordenados pelo prazo; notícias e "todos", pela data ou pela nota. */
export function ordenaPorPrazo(modulo: Secao): boolean {
  return modulo === "estagios" || modulo === "concursos";
}

/**
 * Junta grupos de condições "ou" num único filtro `or` do PostgREST, todos obrigatórios:
 * ["a,b", "c,d"] → "and(or(a,b),or(c,d))". Devolve null se não houver grupo.
 */
export function juntarGrupos(grupos: string[]): string | null {
  if (grupos.length === 0) return null;
  if (grupos.length === 1) return grupos[0];
  return `and(${grupos.map((g) => `or(${g})`).join(",")})`;
}
