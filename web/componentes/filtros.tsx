import Link from "next/link";
import { IconeTag } from "@/componentes/icones";
import { type Estado, type Filtros, ordenaPorPrazo, urlFeed } from "@/lib/filtros";

const ESTADOS: { valor: Estado; rotulo: string }[] = [
  { valor: "todos", rotulo: "Todos" },
  { valor: "nao-lidos", rotulo: "Não lidos" },
  { valor: "salvos", rotulo: "Salvos" },
];

/** Filtros da seção. Tudo fica na URL e funciona sem JavaScript. */
export function BarraFiltros({ filtros }: { filtros: Filtros }) {
  const porPrazo = ordenaPorPrazo(filtros.modulo);
  return (
    <div className="barra-filtros">
      <nav className="segmentos" aria-label="Quais itens">
        {ESTADOS.map(({ valor, rotulo }) => (
          <Link
            key={valor}
            href={urlFeed(filtros, { estado: valor, pagina: 1 })}
            aria-current={filtros.estado === valor ? "true" : undefined}
          >
            {rotulo}
          </Link>
        ))}
      </nav>

      {filtros.tag && (
        <Link className="chip chip-filtro" href={urlFeed(filtros, { tag: "", pagina: 1 })} title="Tirar o filtro de tag">
          <IconeTag width={14} height={14} />
          {filtros.tag} ✕
        </Link>
      )}
      {filtros.busca && (
        <Link className="chip chip-filtro" href={urlFeed(filtros, { busca: "", pagina: 1 })} title="Limpar a busca">
          “{filtros.busca}” ✕
        </Link>
      )}

      <form className="filtros" method="get" action="/">
        <input type="hidden" name="modulo" value={filtros.modulo} />
        {filtros.estado !== "todos" && <input type="hidden" name="ver" value={filtros.estado} />}
        {filtros.busca && <input type="hidden" name="q" value={filtros.busca} />}
        {filtros.tag && <input type="hidden" name="tag" value={filtros.tag} />}
        <select name="nota" defaultValue={String(filtros.notaMinima)} aria-label="Nota mínima">
          <option value="0">Qualquer nota</option>
          {[5, 6, 7, 8, 9].map((nota) => (
            <option key={nota} value={nota}>
              Nota ≥ {nota}
            </option>
          ))}
        </select>
        {porPrazo ? (
          <label className="caixa">
            <input type="checkbox" name="encerrados" value="1" defaultChecked={filtros.encerrados} />
            Encerrados
          </label>
        ) : (
          <select name="ordem" defaultValue={filtros.ordem} aria-label="Ordem">
            <option value="recentes">Mais recentes</option>
            <option value="nota">Maior nota</option>
          </select>
        )}
        <button type="submit" className="botao-primario">
          Filtrar
        </button>
      </form>
    </div>
  );
}

export function Paginacao({ filtros, total, porPagina }: { filtros: Filtros; total: number; porPagina: number }) {
  const paginas = Math.max(1, Math.ceil(total / porPagina));
  if (paginas <= 1) return null;
  const atual = Math.min(filtros.pagina, paginas);
  return (
    <nav className="paginacao" aria-label="Páginas">
      {atual > 1 ? (
        <Link className="botao-fantasma" href={urlFeed(filtros, { pagina: atual - 1 })}>
          ← Anteriores
        </Link>
      ) : (
        <span />
      )}
      <span className="discreto">
        Página {atual} de {paginas}
      </span>
      {atual < paginas ? (
        <Link className="botao-fantasma" href={urlFeed(filtros, { pagina: atual + 1 })}>
          Próximos →
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}
