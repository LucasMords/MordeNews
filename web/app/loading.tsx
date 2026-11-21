import { IconeBusca, Marca } from "@/componentes/icones";

/** Esqueleto mostrado no instante do clique, enquanto o servidor busca os dados. */
export default function Carregando() {
  return (
    <div className="app" aria-busy="true" aria-label="Carregando">
      <aside className="menu">
        <span className="menu-marca">
          <Marca />
        </span>
        <div className="menu-nav">
          {[0, 1, 2, 3, 4].map((i) => (
            <span key={i} className="esqueleto esqueleto-menu" />
          ))}
        </div>
      </aside>
      <main className="conteudo">
        <div className="barra-topo">
          <div className="busca-geral">
            <IconeBusca width={20} height={20} />
            <span className="discreto">Carregando…</span>
          </div>
        </div>
        <div className="numeros">
          {[0, 1, 2].map((i) => (
            <span key={i} className="esqueleto esqueleto-numero" />
          ))}
        </div>
        <div className="colunas" style={{ marginTop: "2rem" }}>
          <div className="lista">
            {[0, 1, 2, 3].map((i) => (
              <span key={i} className="esqueleto esqueleto-cartao" />
            ))}
          </div>
          <span className="esqueleto esqueleto-lateral" />
        </div>
      </main>
    </div>
  );
}
