import type { Metadata } from "next";
import Link from "next/link";
import { IconeGostei, IconeNaoGostei, Marca } from "@/componentes/icones";
import { temAcesso } from "@/lib/consulta";
import { linkSeguro } from "@/lib/formato";
import { clienteSupabase } from "@/lib/supabase/servidor";
import { lerIdItem, lerVotoPedido, registrarVoto } from "@/lib/votos";

export const metadata: Metadata = { title: "Voto · MordeNews" };
export const dynamic = "force-dynamic";

type Parametros = Record<string, string | string[] | undefined>;

function primeiro(valor: string | string[] | undefined): string | undefined {
  return Array.isArray(valor) ? valor[0] : valor;
}

/**
 * Destino dos links 👍/👎 do e-mail: grava o voto com a sessão do portal (quem não está
 * logado passa pelo login e volta para cá) e mostra a confirmação.
 */
export default async function PaginaVoto({ searchParams }: { searchParams: Promise<Parametros> }) {
  const params = await searchParams;
  const id = lerIdItem(primeiro(params.item));
  const voto = lerVotoPedido(primeiro(params.voto));
  const supabase = await clienteSupabase();

  let mensagem: string;
  let titulo: string | null = null;
  let url: string | null = null;
  if (id === null || voto === undefined) {
    mensagem = "Link de voto inválido.";
  } else if (!(await temAcesso(supabase))) {
    mensagem = "Esta conta não tem acesso ao portal.";
  } else {
    const { data } = await supabase.from("itens").select("titulo,url").eq("id", id).maybeSingle();
    if (!data) {
      mensagem = "Item não encontrado.";
    } else {
      await registrarVoto(supabase, id, voto);
      titulo = data.titulo as string;
      url = linkSeguro(data.url);
      mensagem =
        voto === 1
          ? "Anotado: 👍 mais itens assim."
          : voto === -1
            ? "Anotado: 👎 menos itens assim."
            : "Voto retirado.";
    }
  }

  return (
    <main className="login-fundo">
      <div className="login-cartao voto-cartao">
        <Marca tamanho={48} />
        <h1 className="voto-mensagem">{mensagem}</h1>
        {titulo && (
          <p className="voto-titulo">
            {url ? (
              <a href={url} target="_blank" rel="noopener noreferrer">
                {titulo}
              </a>
            ) : (
              titulo
            )}
          </p>
        )}
        {titulo && id !== null && (
          <div className="voto-trocar">
            {voto !== 1 && (
              <Link className="botao-fantasma" href={`/votar?item=${id}&voto=1`}>
                <IconeGostei /> Mudar para 👍
              </Link>
            )}
            {voto !== -1 && (
              <Link className="botao-fantasma" href={`/votar?item=${id}&voto=-1`}>
                <IconeNaoGostei /> Mudar para 👎
              </Link>
            )}
          </div>
        )}
        <p className="discreto">Os votos recentes entram como exemplos na próxima triagem da IA.</p>
        <Link className="botao-primario largo" href="/">
          Abrir o portal
        </Link>
      </div>
    </main>
  );
}
