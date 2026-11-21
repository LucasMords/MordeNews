/** URL e chave pública do Supabase. A service role key nunca entra no portal. */
export function configSupabase(): { url: string; chave: string } {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const chave = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !chave) {
    throw new Error(
      "Defina NEXT_PUBLIC_SUPABASE_URL e NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY (veja web/.env.example).",
    );
  }
  if (chave.startsWith("sb_secret_") || papelDaChave(chave) === "service_role") {
    throw new Error("A chave do portal deve ser a pública (anon/publishable), nunca a service role.");
  }
  return { url, chave };
}

/** Papel de uma chave antiga em formato JWT (anon ou service_role). */
function papelDaChave(chave: string): string | null {
  const partes = chave.split(".");
  if (partes.length !== 3) return null;
  try {
    const carga = JSON.parse(Buffer.from(partes[1], "base64url").toString("utf8")) as {
      role?: string;
    };
    return carga.role ?? null;
  } catch {
    return null;
  }
}
