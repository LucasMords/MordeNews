import { marcarPaginaLida } from "@/app/acoes";
import { CartaoDestaque, CartaoItem } from "@/componentes/cartao-item";
import { BarraFiltros, Paginacao } from "@/componentes/filtros";
import { IconeBusca, IconeLido } from "@/componentes/icones";
import { ColunaLateral, Saudacao, TituloSecao } from "@/componentes/inicio";
import { type Ativo, BarraTopo, Menu } from "@/componentes/menu";
import {
  buscarInicio,
  buscarItens,
  buscarPrazos,
  buscarTags,
  contarPainel,
  type Inicio as DadosInicio,
  type Pagina,
  temAcesso,
  usuarioAtual,
} from "@/lib/consulta";
import { eInicio, type Filtros, filtrosDe, lerFiltros, type Parametros, POR_PAGINA, urlFeed } from "@/lib/filtros";
import { agruparPor, hojeBrasilia, rotuloDia } from "@/lib/formato";
import { clienteSupabase } from "@/lib/supabase/servidor";
import { type Item, TITULOS_MODULO } from "@/lib/tipos";

export const dynamic = "force-dynamic"; // dados por usuário: nada de cache

/** Itens por data viram grupos "Hoje", "Ontem"...; vagas e concursos (por prazo) são uma lista só. */
function grupos(itens: Item[], filtros: Filtros, hoje: string) {
  if ((filtros.modulo === "noticias" || filtros.modulo === "todos") && filtros.ordem === "recentes") {
    return agruparPor(itens, (item) => rotuloDia(item.coletado_em, hoje));
  }
  return [{ rotulo: "", itens }];
}

function ativoDe(filtros: Filtros): Ativo {
  if (filtros.modulo !== "todos") return filtros.modulo;
  return filtros.estado === "salvos" && !filtros.busca && !filtros.tag ? "salvos" : "busca";
}

function tituloDe(filtros: Filtros): string {
  if (filtros.tag) return `#${filtros.tag}`;
  if (filtros.modulo === "todos") return filtros.estado === "salvos" ? "Salvos" : "Busca";
  return TITULOS_MODULO[filtros.modulo];
}

export default async function Pagina({ searchParams }: { searchParams: Promise<Parametros> }) {
  const params = await searchParams;
  const inicio = eInicio(params);
  const filtros = lerFiltros(params);
  const supabase = await clienteSupabase();
  const hoje = hojeBrasilia();

  // Tudo numa leva só, em paralelo: cada ida ao Supabase custa centenas de ms.
  const [acesso, painel, usuario, prazos, tags, dados] = await Promise.all([
    temAcesso(supabase),
    contarPainel(supabase),
    usuarioAtual(supabase),
    buscarPrazos(supabase),
    buscarTags(supabase),
    inicio ? buscarInicio(supabase) : buscarItens(supabase, filtros),
  ]);

  if (!acesso) {
    return (
      <main className="sem-acesso">
        <div className="lateral-cartao">
          <h2>Esta conta não tem acesso ao portal</h2>
          <p>
            Cadastre-a em <code>usuarios_portal</code> pelo SQL Editor do Supabase (veja{" "}
            <code>db/migrations/002_portal.sql</code>).
          </p>
        </div>
      </main>
    );
  }

  return (
    <div className="app">
      <Menu ativo={inicio ? "inicio" : ativoDe(filtros)} painel={painel} usuario={usuario} />
      <main className="conteudo">
        <BarraTopo filtros={inicio ? null : filtros} />
        <Saudacao nome={usuario.nome} painel={painel} compacta={!inicio} />
        <div className="colunas">
          <div className="principal">
            {"destaque" in dados ? (
              <Inicio dados={dados} hoje={hoje} />
            ) : (
              <Feed pagina={dados} filtros={filtros} hoje={hoje} />
            )}
          </div>
          <ColunaLateral prazos={prazos} tags={tags} hoje={hoje} urgentes={painel.prazosProximos} />
        </div>
        <footer className="rodape">MordeNews · radar pessoal · cada item tem link para a fonte original</footer>
      </main>
    </div>
  );
}

function Inicio({ dados, hoje }: { dados: DadosInicio; hoje: string }) {
  const { destaque, ultimas } = dados;
  if (!destaque) return <Vazio texto="Ainda não há notícias triadas. Elas aparecem aqui depois da próxima coleta." />;
  return (
    <>
      <TituloSecao href={urlFeed(filtrosDe("noticias", { ordem: "nota" }))}>Destaque do momento</TituloSecao>
      <CartaoDestaque item={destaque} />
      <TituloSecao href={urlFeed(filtrosDe("noticias"))}>Últimas notícias</TituloSecao>
      <div className="lista">
        {ultimas.map((item) => (
          <CartaoItem key={item.id} item={item} hoje={hoje} />
        ))}
      </div>
    </>
  );
}

function Feed({ pagina, filtros, hoje }: { pagina: Pagina; filtros: Filtros; hoje: string }) {
  const { itens, total } = pagina;
  const naoLidos = itens.filter((item) => !item.lido).map((item) => item.id);

  return (
    <>
      <TituloSecao>{tituloDe(filtros)}</TituloSecao>
      <BarraFiltros filtros={filtros} />

      <div className="lista-cabecalho">
        <span>
          <strong>{total}</strong> {total === 1 ? "item" : "itens"}
        </span>
        {naoLidos.length > 0 && (
          <form action={marcarPaginaLida}>
            <input type="hidden" name="ids" value={naoLidos.join(",")} />
            <button type="submit" className="botao-fantasma pequeno">
              <IconeLido width={15} height={15} />
              Marcar página como lida
            </button>
          </form>
        )}
      </div>

      {itens.length === 0 ? (
        <Vazio texto="Nenhum item com esses filtros. Tente outra busca ou mude os filtros." />
      ) : (
        grupos(itens, filtros, hoje).map((grupo, indice) => (
          <section key={`${grupo.rotulo}-${indice}`} className="lista">
            {grupo.rotulo && <h3 className="grupo-titulo">{grupo.rotulo}</h3>}
            {grupo.itens.map((item) => (
              <CartaoItem key={item.id} item={item} hoje={hoje} />
            ))}
          </section>
        ))
      )}

      <Paginacao filtros={filtros} total={total} porPagina={POR_PAGINA} />
    </>
  );
}

function Vazio({ texto }: { texto: string }) {
  return (
    <div className="vazio">
      <IconeBusca width={40} height={40} />
      <h2>Nada por aqui</h2>
      <p>{texto}</p>
    </div>
  );
}
