import type { Campos, Item } from "./tipos";

const FUSO = "America/Sao_Paulo";

/** Data de hoje em Brasília, no formato AAAA-MM-DD. */
export function hojeBrasilia(agora: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: FUSO }).format(agora);
}

/** "21/11/2026" a partir de um timestamp ou de uma data AAAA-MM-DD. */
export function formatarData(valor: string | null): string {
  if (!valor) return "";
  const soData = /^\d{4}-\d{2}-\d{2}$/.exec(valor);
  if (soData) {
    const [ano, mes, dia] = valor.split("-");
    return `${dia}/${mes}/${ano}`;
  }
  const data = new Date(valor);
  if (Number.isNaN(data.getTime())) return "";
  return new Intl.DateTimeFormat("pt-BR", { timeZone: FUSO }).format(data);
}

function diasEntre(de: string, ate: string): number {
  return Math.round((Date.parse(`${ate}T00:00:00Z`) - Date.parse(`${de}T00:00:00Z`)) / 86_400_000);
}

/** Texto do prazo de inscrição, como no e-mail: "termina amanhã", "encerrado" etc. */
export function textoPrazo(prazo: string, hoje: string): string {
  const dias = diasEntre(hoje, prazo);
  const data = formatarData(prazo);
  if (dias < 0) return `encerrado em ${data}`;
  if (dias === 0) return `termina HOJE (${data})`;
  if (dias === 1) return `termina amanhã (${data})`;
  return `até ${data} (${dias} dias)`;
}

export function prazoUrgente(prazo: string, hoje: string): boolean {
  const dias = diasEntre(hoje, prazo);
  return dias >= 0 && dias <= 3;
}

function texto(valor: unknown): string | null {
  if (typeof valor === "string" && valor.trim()) return valor.trim();
  if (typeof valor === "number" && Number.isFinite(valor)) return String(valor);
  return null;
}

/** Linha "Empresa · Cidade · remoto · bolsa" das vagas. */
function linhaVaga(campos: Campos): string[] {
  const partes = [texto(campos.empresa), texto(campos.cidade)];
  if (campos.remoto === true) partes.push("remoto");
  const bolsa = texto(campos.bolsa);
  if (bolsa) partes.push(`bolsa ${bolsa}`);
  return partes.filter((p): p is string => p !== null);
}

/** Linha "Órgão · N vagas · até R$ X · escolaridade · prova em D" dos concursos. */
function linhaConcurso(campos: Campos): string[] {
  const vagas = texto(campos.vagas);
  const salario = texto(campos.salario_max);
  const prova = texto(campos.data_prova);
  return [
    texto(campos.orgao),
    vagas ? `${vagas} ${vagas === "1" ? "vaga" : "vagas"}` : null,
    salario ? `até ${salario}` : null,
    texto(campos.escolaridade),
    prova ? `prova em ${formatarData(prova) || prova}` : null,
  ].filter((p): p is string => p !== null);
}

export function linhaDados(item: Pick<Item, "modulo" | "campos">): string | null {
  const campos = item.campos ?? {};
  const partes =
    item.modulo === "estagios"
      ? linhaVaga(campos)
      : item.modulo === "concursos"
        ? linhaConcurso(campos)
        : [];
  return partes.length ? partes.join(" · ") : null;
}

/** Só aceita links http(s): um `javascript:` vindo da fonte nunca vira link clicável. */
export function linkSeguro(valor: unknown): string | null {
  if (typeof valor !== "string") return null;
  try {
    const url = new URL(valor);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

/** Link extra do item: inscrição (vagas) ou edital (concursos). */
export function linkExtra(item: Pick<Item, "modulo" | "campos">): { rotulo: string; url: string } | null {
  const campos = item.campos ?? {};
  if (item.modulo === "estagios") {
    const url = linkSeguro(campos.link_inscricao);
    return url ? { rotulo: "Inscrição", url } : null;
  }
  if (item.modulo === "concursos") {
    const url = linkSeguro(campos.link_edital);
    return url ? { rotulo: "Edital", url } : null;
  }
  return null;
}
