import Link from "next/link";
import { type Filtros, ordenaPorPrazo, urlFeed } from "@/lib/filtros";
import { MODULOS, TITULOS_MODULO } from "@/lib/tipos";

/** Abas por módulo. Trocar de aba mantém a busca e volta para a página 1. */
export function Abas({ filtros }: { filtros: Filtros }) {
  return (
    <nav className="abas" aria-label="Módulos">
      {MODULOS.map((modulo) => (
        <Link
          key={modulo}
          href={urlFeed(filtros, { modulo, pagina: 1, encerrados: false })}
          aria-current={modulo === filtros.modulo ? "page" : undefined}
        >
          {TITULOS_MODULO[modulo]}
        </Link>
      ))}
    </nav>
  );
}

/** Formulário GET: os filtros ficam na URL e funcionam sem JavaScript. */
export function BarraFiltros({ filtros }: { filtros: Filtros }) {
  const porPrazo = ordenaPorPrazo(filtros.modulo);
  return (
    <form className="filtros" method="get" action="/">
      {filtros.modulo !== "noticias" && (
        <input type="hidden" name="modulo" value={filtros.modulo} />
      )}
      <input
        type="search"
        name="q"
        defaultValue={filtros.busca}
        placeholder="Buscar no título e no resumo"
        aria-label="Buscar"
      />
      <select name="ver" defaultValue={filtros.estado} aria-label="Quais itens">
        <option value="todos">Todos</option>
        <option value="nao-lidos">Não lidos</option>
        <option value="salvos">Salvos</option>
      </select>
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
          Incluir encerrados
        </label>
      ) : (
        <select name="ordem" defaultValue={filtros.ordem} aria-label="Ordem">
          <option value="recentes">Mais recentes</option>
          <option value="nota">Maior nota</option>
        </select>
      )}
      <button type="submit">Filtrar</button>
    </form>
  );
}

export function Paginacao({ filtros, total, porPagina }: { filtros: Filtros; total: number; porPagina: number }) {
  const paginas = Math.max(1, Math.ceil(total / porPagina));
  if (paginas <= 1) return null;
  return (
    <nav className="paginacao" aria-label="Páginas">
      {filtros.pagina > 1 && (
        <Link href={urlFeed(filtros, { pagina: filtros.pagina - 1 })}>← Anteriores</Link>
      )}
      <span>
        Página {Math.min(filtros.pagina, paginas)} de {paginas}
      </span>
      {filtros.pagina < paginas && (
        <Link href={urlFeed(filtros, { pagina: filtros.pagina + 1 })}>Próximos →</Link>
      )}
    </nav>
  );
}
