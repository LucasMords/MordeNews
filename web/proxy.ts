import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";
import { configSupabase } from "@/lib/supabase/config";

/**
 * Roda antes de cada página: renova a sessão do Supabase nos cookies e manda para /login
 * quem não está logado. A permissão de ver os dados é conferida de novo no banco (RLS).
 */
export async function proxy(requisicao: NextRequest) {
  const { url, chave } = configSupabase();
  let resposta = NextResponse.next({ request: requisicao });

  const supabase = createServerClient(url, chave, {
    cookies: {
      getAll() {
        return requisicao.cookies.getAll();
      },
      setAll(novos) {
        for (const { name, value } of novos) requisicao.cookies.set(name, value);
        resposta = NextResponse.next({ request: requisicao });
        for (const { name, value, options } of novos) resposta.cookies.set(name, value, options);
      },
    },
  });

  // getUser() valida o token no Supabase (getSession() só leria o cookie).
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const naLogin = requisicao.nextUrl.pathname.startsWith("/login");
  if (!user && !naLogin) {
    return redirecionar(requisicao, "/login", resposta);
  }
  if (user && naLogin) {
    return redirecionar(requisicao, "/", resposta);
  }
  return resposta;
}

/** Redireciona mantendo os cookies de sessão que o Supabase acabou de renovar. */
function redirecionar(requisicao: NextRequest, caminho: string, base: NextResponse) {
  const destino = requisicao.nextUrl.clone();
  destino.pathname = caminho;
  destino.search = "";
  const resposta = NextResponse.redirect(destino);
  for (const cookie of base.cookies.getAll()) resposta.cookies.set(cookie);
  return resposta;
}

export const config = {
  // Tudo, menos arquivos estáticos do Next e o favicon.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|ico)$).*)"],
};
