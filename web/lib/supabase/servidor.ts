import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { configSupabase } from "./config";

/** Cliente do Supabase para Server Components e Server Actions, com a sessão dos cookies. */
export async function clienteSupabase() {
  const { url, chave } = configSupabase();
  const loja = await cookies();
  return createServerClient(url, chave, {
    cookies: {
      getAll() {
        return loja.getAll();
      },
      setAll(novos) {
        try {
          for (const { name, value, options } of novos) loja.set(name, value, options);
        } catch {
          // Server Components não podem gravar cookies; o proxy.ts renova a sessão.
        }
      },
    },
  });
}
