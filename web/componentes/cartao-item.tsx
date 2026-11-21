import { Capa } from "@/componentes/arte";
import { CartaoInterativo } from "@/componentes/cartao-interativo";
import { IconeCalendario, IconeEstrela, IconeExterno, IconeRelogio } from "@/componentes/icones";
import { filtrosDe, urlFeed } from "@/lib/filtros";
import { formatarData, linhaDados, linkExtra, linkSeguro, prazoUrgente, textoPrazo } from "@/lib/formato";
import { type Item, TITULOS_MODULO } from "@/lib/tipos";

function faixaNota(nota: number): "alta" | "media" | "baixa" {
  if (nota >= 8) return "alta";
  if (nota >= 6) return "media";
  return "baixa";
}

/** Pílula do topo do cartão: a primeira tag (link para o filtro) ou o nome do módulo. */
function Pilula({ item }: { item: Item }) {
  const tag = item.tags?.[0];
  if (!tag) return <span className={`pilula pilula-${item.modulo}`}>{TITULOS_MODULO[item.modulo]}</span>;
  return (
    <a className={`pilula pilula-${item.modulo}`} href={urlFeed(filtrosDe("todos", { tag }))}>
      {tag}
    </a>
  );
}

function Meta({ item }: { item: Item }) {
  const data = formatarData(item.publicado_em ?? item.coletado_em);
  const mostraNota = item.modulo !== "concursos" && item.nota !== null;
  return (
    <p className="cartao-meta">
      {data && (
        <span>
          <IconeCalendario width={16} height={16} />
          {data}
        </span>
      )}
      <span className="fonte">{item.fonte}</span>
      {mostraNota && (
        <span className={`nota nota-${faixaNota(item.nota ?? 0)}`} title={`Nota ${item.nota} de 10`}>
          <IconeEstrela width={15} height={15} />
          {item.nota}/10
        </span>
      )}
      <span className="selo-novo">novo</span>
    </p>
  );
}

function Titulo({ item, url, nivel }: { item: Item; url: string | null; nivel: "h2" | "h3" }) {
  const Tag = nivel;
  return (
    <Tag className="cartao-titulo">
      {url ? (
        <a href={url} target="_blank" rel="noopener noreferrer">
          {item.titulo}
        </a>
      ) : (
        item.titulo
      )}
    </Tag>
  );
}

/** Um item do feed. O React escapa todo o texto; links só se forem http(s). */
export function CartaoItem({ item, hoje }: { item: Item; hoje: string }) {
  const url = linkSeguro(item.url);
  const dados = linhaDados(item);
  const extra = linkExtra(item);
  return (
    <CartaoInterativo id={item.id} lido={item.lido} salvo={item.salvo} voto={item.voto} classe={`cartao modulo-${item.modulo}`} url={url}>
      <Capa item={item} />
      <div className="cartao-corpo">
        <Pilula item={item} />
        <Titulo item={item} url={url} nivel="h3" />
        {dados && <p className="cartao-dados">{dados}</p>}
        {item.resumo && <p className="cartao-resumo">{item.resumo}</p>}
        {(item.prazo || extra) && (
          <div className="cartao-chips">
            {item.prazo && (
              <span className={prazoUrgente(item.prazo, hoje) ? "chip chip-urgente" : "chip chip-prazo"}>
                <IconeRelogio width={14} height={14} />
                Inscrição {textoPrazo(item.prazo, hoje)}
              </span>
            )}
            {extra && (
              <a className="chip chip-link" href={extra.url} target="_blank" rel="noopener noreferrer">
                {extra.rotulo}
                <IconeExterno width={13} height={13} />
              </a>
            )}
          </div>
        )}
        <Meta item={item} />
      </div>
    </CartaoInterativo>
  );
}

/** O destaque da página inicial: capa grande e título maior. */
export function CartaoDestaque({ item }: { item: Item }) {
  const url = linkSeguro(item.url);
  return (
    <CartaoInterativo
      id={item.id}
      lido={item.lido}
      salvo={item.salvo}
      voto={item.voto}
      classe={`cartao cartao-destaque modulo-${item.modulo}`}
      url={url}
    >
      <Capa item={item} grande />
      <div className="cartao-corpo">
        <Pilula item={item} />
        <Titulo item={item} url={url} nivel="h2" />
        {item.resumo && <p className="cartao-resumo">{item.resumo}</p>}
        <Meta item={item} />
      </div>
    </CartaoInterativo>
  );
}
