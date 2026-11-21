import type { SupabaseClient } from "@supabase/supabase-js";
import type { Voto } from "./tipos";

/** Lê "1", "-1" ou "0" (tirar o voto). Qualquer outra coisa é inválida. */
export function lerVotoPedido(valor: unknown): Voto | undefined {
  if (valor === "1") return 1;
  if (valor === "-1") return -1;
  if (valor === "0") return null;
  return undefined;
}

export function lerIdItem(valor: unknown): number | null {
  const id = Number(valor);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

/**
 * Grava o voto (um por item: votar de novo troca) ou o apaga quando `voto` é null.
 * Roda com a sessão do usuário: o RLS da migração 003 é quem autoriza.
 */
export async function registrarVoto(supabase: SupabaseClient, itemId: number, voto: Voto): Promise<void> {
  const { error } =
    voto === null
      ? await supabase.from("feedback").delete().eq("item_id", itemId)
      : await supabase
          .from("feedback")
          .upsert({ item_id: itemId, voto, criado_em: new Date().toISOString() }, { onConflict: "item_id" });
  if (error) throw new Error(`Falha ao registrar o voto: ${error.message}`);
}
