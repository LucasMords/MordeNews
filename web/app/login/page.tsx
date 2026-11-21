import type { Metadata } from "next";
import { ArteCidade } from "@/componentes/arte";
import { Marca } from "@/componentes/icones";
import { FormularioLogin } from "./formulario";

export const metadata: Metadata = { title: "Entrar · MordeNews" };

export default function PaginaLogin() {
  return (
    <main className="login-fundo">
      <div className="login-arte">
        <ArteCidade />
      </div>
      <div className="login-cartao">
        <Marca tamanho={64} />
        <p className="discreto">Notícias, vagas e concursos que importam, num lugar só.</p>
        <FormularioLogin />
      </div>
    </main>
  );
}
