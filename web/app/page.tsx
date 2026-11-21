import { sair, marcarPaginaLida } from "@/app/acoes";
import { CartaoItem } from "@/componentes/cartao-item";
import { Abas, BarraFiltros, Paginacao } from "@/componentes/filtros";
import { buscarItens, temAcesso } from "@/lib/consulta";
import { lerFiltros, type Parametros, POR_PAGINA } from "@/lib/filtros";
import { hojeBrasilia } from "@/lib/formato";
import { clienteSupabase } from "@/lib/supabase/servidor";
import { TITULOS_MODULO } from "@/lib/tipos";

export const dynamic = "force-dynamic"; // dados por usuário: nada de cache

export default async function Feed({ searchParams }: { searchParams: Promise<Parametros> }) {
  const filtros = lerFiltros(await searchParams);
  const supabase = await clienteSupabase();

  const topo = (
    <header className="topo">
      <h1>MordeNews</h1>
      <form action={sair}>
        <button type="submit" className="discreto">
          Sair
        </button>
      </form>
    </header>
  );

  if (!(await temAcesso(supabase))) {
    return (
      <main>
        {topo}
        <p className="erro">
          Esta conta não tem acesso ao portal. Cadastre-a em <code>usuarios_portal</code> pelo SQL
          Editor do Supabase (veja <code>db/migrations/002_portal.sql</code>).
        </p>
      </main>
    );
  }

  const { itens, total } = await buscarItens(supabase, filtros);
  const hoje = hojeBrasilia();
  const naoLidos = itens.filter((item) => !item.lido).map((item) => item.id);

  return (
    <main>
      {topo}
      <Abas filtros={filtros} />
      <BarraFiltros filtros={filtros} />

      <div className="resumo-lista">
        <span>
          {total} {total === 1 ? "item" : "itens"} em {TITULOS_MODULO[filtros.modulo]}
        </span>
        {naoLidos.length > 0 && (
          <form action={marcarPaginaLida}>
            <input type="hidden" name="ids" value={naoLidos.join(",")} />
            <button type="submit" className="discreto">
              Marcar página como lida
            </button>
          </form>
        )}
      </div>

      {itens.length === 0 ? (
        <p className="discreto vazio">Nenhum item com esses filtros.</p>
      ) : (
        itens.map((item) => <CartaoItem key={item.id} item={item} hoje={hoje} />)
      )}

      <Paginacao filtros={filtros} total={total} porPagina={POR_PAGINA} />
    </main>
  );
}
