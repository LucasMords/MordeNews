import type { Metadata } from "next";
import { ArteCidade } from "@/componentes/arte";
import { Marca } from "@/componentes/icones";
import { destinoSeguro } from "@/lib/destino";
import { FormularioLogin } from "./formulario";

export const metadata: Metadata = { title: "Entrar · MordeNews" };

export default async function PaginaLogin({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { proximo } = await searchParams;
  return (
    <main className="login-fundo">
      <div className="login-arte">
        <ArteCidade />
      </div>
      <div className="login-cartao">
        <Marca tamanho={64} />
        <p className="discreto">Notícias, vagas e concursos que importam, num lugar só.</p>
        <FormularioLogin proximo={destinoSeguro(Array.isArray(proximo) ? proximo[0] : proximo)} />
      </div>
    </main>
  );
}
