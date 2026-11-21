"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { clienteSupabase } from "@/lib/supabase/servidor";
import { lerIdItem, lerVotoPedido, registrarVoto } from "@/lib/votos";

type Marca = "lido" | "salvo";

function lerId(formulario: FormData): number {
  const id = Number(formulario.get("id"));
  if (!Number.isSafeInteger(id) || id <= 0) throw new Error("id de item inválido");
  return id;
}

/** Liga ou desliga `lido`/`salvo` de um item. O RLS e o grant de coluna garantem o resto. */
async function marcar(marca: Marca, formulario: FormData): Promise<void> {
  const id = lerId(formulario);
  const valor = formulario.get("valor") === "1";
  const supabase = await clienteSupabase();
  const { error } = await supabase
    .from("itens")
    .update({ [marca]: valor })
    .eq("id", id);
  if (error) throw new Error(`Falha ao marcar o item como ${marca}: ${error.message}`);
  revalidatePath("/");
}

export async function marcarLido(formulario: FormData): Promise<void> {
  await marcar("lido", formulario);
}

export async function marcarSalvo(formulario: FormData): Promise<void> {
  await marcar("salvo", formulario);
}

/** Marca como lidos todos os itens mostrados na página atual. */
export async function marcarPaginaLida(formulario: FormData): Promise<void> {
  const ids = String(formulario.get("ids") ?? "")
    .split(",")
    .map(Number)
    .filter((id) => Number.isSafeInteger(id) && id > 0)
    .slice(0, 100);
  if (ids.length === 0) return;
  const supabase = await clienteSupabase();
  const { error } = await supabase.from("itens").update({ lido: true }).in("id", ids);
  if (error) throw new Error(`Falha ao marcar a página como lida: ${error.message}`);
  revalidatePath("/");
}

export async function sair(): Promise<void> {
  const supabase = await clienteSupabase();
  await supabase.auth.signOut();
  redirect("/login");
}

/** Troca entre tema escuro e claro (cookie lido pelo layout; funciona sem JavaScript). */
export async function trocarTema(formulario: FormData): Promise<void> {
  const tema = formulario.get("tema") === "claro" ? "claro" : "escuro";
  const loja = await cookies();
  loja.set("tema", tema, { path: "/", maxAge: 60 * 60 * 24 * 365, sameSite: "lax", httpOnly: true });
  revalidatePath("/", "layout");
}

/** 👍/👎 de um item (bloco 7). Votar no mesmo de novo tira o voto ("0"). */
export async function votar(formulario: FormData): Promise<void> {
  const id = lerIdItem(formulario.get("id"));
  const voto = lerVotoPedido(formulario.get("voto"));
  if (id === null || voto === undefined) throw new Error("voto inválido");
  await registrarVoto(await clienteSupabase(), id, voto);
  revalidatePath("/");
}
