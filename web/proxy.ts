import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";
import { destinoSeguro } from "@/lib/destino";
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

  // getClaims() renova a sessão se preciso e confere a assinatura do token localmente (chave
  // pública ES256 do projeto, em cache por 10 min): sem ida ao Supabase a cada página.
  const { data } = await supabase.auth.getClaims();
  const user = data?.claims.sub ? data.claims : null;

  const naLogin = requisicao.nextUrl.pathname.startsWith("/login");
  if (!user && !naLogin) {
    // Guarda o destino (ex.: um link de voto do e-mail) para voltar a ele depois do login.
    const { pathname, search } = requisicao.nextUrl;
    const proximo = pathname === "/" && !search ? "" : `${pathname}${search}`;
    return redirecionar(requisicao, "/login", resposta, proximo ? { proximo } : {});
  }
  if (user && naLogin) {
    return redirecionar(requisicao, destinoSeguro(requisicao.nextUrl.searchParams.get("proximo")), resposta);
  }
  return resposta;
}

/** Redireciona mantendo os cookies de sessão que o Supabase acabou de renovar. */
function redirecionar(
  requisicao: NextRequest,
  caminho: string,
  base: NextResponse,
  parametros: Record<string, string> = {},
) {
  const destino = new URL(caminho, requisicao.nextUrl.origin);
  for (const [chave, valor] of Object.entries(parametros)) destino.searchParams.set(chave, valor);
  const resposta = NextResponse.redirect(destino);
  for (const cookie of base.cookies.getAll()) resposta.cookies.set(cookie);
  return resposta;
}

export const config = {
  // Tudo, menos arquivos estáticos do Next e o favicon.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|ico)$).*)"],
};
