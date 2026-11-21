"use server";

import { redirect } from "next/navigation";
import { clienteSupabase } from "@/lib/supabase/servidor";

export interface EstadoLogin {
  erro: string | null;
}

/** Entra com e-mail e senha. A conta é criada à mão no painel do Supabase. */
export async function entrar(_anterior: EstadoLogin, formulario: FormData): Promise<EstadoLogin> {
  const email = String(formulario.get("email") ?? "").trim();
  const senha = String(formulario.get("senha") ?? "");
  if (!email || !senha) return { erro: "Informe e-mail e senha." };

  const supabase = await clienteSupabase();
  const { error } = await supabase.auth.signInWithPassword({ email, password: senha });
  if (error) {
    // Mensagem genérica: não revela se o e-mail existe.
    return { erro: "E-mail ou senha incorretos." };
  }
  redirect("/");
}
