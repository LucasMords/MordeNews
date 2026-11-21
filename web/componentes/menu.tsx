import Link from "next/link";
import type { ComponentType, SVGProps } from "react";
import { sair, trocarTema } from "@/app/acoes";
import { ICONES_MODULO } from "@/componentes/arte";
import { IconeBusca, IconeInicio, IconeLua, IconeSair, IconeSalvo, IconeSol, Marca } from "@/componentes/icones";
import type { Painel, Usuario } from "@/lib/consulta";
import { type Filtros, filtrosDe, urlFeed } from "@/lib/filtros";
import { MODULOS, type Modulo, TITULOS_MODULO } from "@/lib/tipos";

export type Ativo = "inicio" | Modulo | "salvos" | "busca";

interface Entrada {
  chave: Ativo;
  rotulo: string;
  href: string;
  Icone: ComponentType<SVGProps<SVGSVGElement>>;
  contador?: number;
}

/** Menu lateral (vira barra no topo no celular). */
export function Menu({ ativo, painel, usuario }: { ativo: Ativo; painel: Painel; usuario: Usuario }) {
  const entradas: Entrada[] = [
    { chave: "inicio", rotulo: "Início", href: "/", Icone: IconeInicio },
    ...MODULOS.map((modulo) => ({
      chave: modulo,
      rotulo: TITULOS_MODULO[modulo],
      href: urlFeed(filtrosDe(modulo)),
      Icone: ICONES_MODULO[modulo],
      contador: painel.naoLidos[modulo],
    })),
    {
      chave: "salvos",
      rotulo: "Salvos",
      href: urlFeed(filtrosDe("todos", { estado: "salvos" })),
      Icone: IconeSalvo,
      contador: painel.salvos,
    },
  ];
  const inicial = usuario.nome.charAt(0).toUpperCase() || "?";

  return (
    <aside className="menu">
      <Link href="/" className="menu-marca" aria-label="MordeNews, início">
        <Marca />
      </Link>

      <nav className="menu-nav" aria-label="Seções">
        {entradas.map(({ chave, rotulo, href, Icone, contador }) => (
          <Link key={chave} href={href} prefetch className="menu-item" aria-current={ativo === chave ? "page" : undefined}>
            <Icone width={22} height={22} />
            <span>{rotulo}</span>
            {contador ? (
              <span className="menu-contador" title={chave === "salvos" ? "Salvos" : "Não lidos"}>
                {contador > 99 ? "99+" : contador}
              </span>
            ) : null}
          </Link>
        ))}
      </nav>

      <span className="menu-risco" aria-hidden="true" />

      <div className="menu-usuario">
        <span className="avatar">{inicial}</span>
        <span className="menu-usuario-texto">
          <strong title={usuario.email}>{usuario.nome}</strong>
          <span className="online">Online</span>
        </span>
        <form action={sair}>
          <button type="submit" className="botao-icone" title="Sair" aria-label="Sair">
            <IconeSair />
          </button>
        </form>
      </div>
    </aside>
  );
}

/** Busca geral (todas as seções) e troca de tema. */
export function BarraTopo({ filtros }: { filtros: Filtros | null }) {
  return (
    <div className="barra-topo">
      <form className="busca-geral" method="get" action="/">
        <input type="hidden" name="modulo" value={filtros?.modulo ?? "todos"} />
        {filtros?.estado && filtros.estado !== "todos" && <input type="hidden" name="ver" value={filtros.estado} />}
        <IconeBusca width={20} height={20} />
        <input
          type="search"
          name="q"
          defaultValue={filtros?.busca ?? ""}
          placeholder="Buscar notícias, vagas, editais..."
          aria-label="Buscar no título e no resumo"
        />
      </form>
      <form action={trocarTema} className="tema">
        <button type="submit" name="tema" value="claro" className="tema-botao tema-claro" title="Tema claro" aria-label="Tema claro">
          <IconeSol width={20} height={20} />
        </button>
        <button type="submit" name="tema" value="escuro" className="tema-botao tema-escuro" title="Tema escuro" aria-label="Tema escuro">
          <IconeLua width={20} height={20} />
        </button>
      </form>
    </div>
  );
}
