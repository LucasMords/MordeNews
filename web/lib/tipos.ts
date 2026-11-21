export const MODULOS = ["noticias", "estagios", "concursos"] as const;
export type Modulo = (typeof MODULOS)[number];

export const TITULOS_MODULO: Record<Modulo, string> = {
  noticias: "Notícias",
  estagios: "Estágios",
  concursos: "Concursos",
};

/** Colunas que o portal lê de `itens` (o `texto` bruto fica de fora: pesa e não é mostrado). */
export const COLUNAS_ITEM =
  "id,modulo,fonte,titulo,url,publicado_em,coletado_em,nota,resumo,tags,campos,prazo,lido,salvo";

export type Campos = Record<string, unknown>;

export interface Item {
  id: number;
  modulo: Modulo;
  fonte: string;
  titulo: string;
  url: string;
  publicado_em: string | null;
  coletado_em: string;
  nota: number | null;
  resumo: string | null;
  tags: string[] | null;
  campos: Campos | null;
  prazo: string | null; // AAAA-MM-DD
  lido: boolean;
  salvo: boolean;
}
