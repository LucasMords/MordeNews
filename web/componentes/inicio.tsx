import Link from "next/link";
import type { ReactNode } from "react";
import { ArteCidade, ICONES_MODULO } from "@/componentes/arte";
import { IconeSeta, IconeSino, IconeTag } from "@/componentes/icones";
import type { Painel } from "@/lib/consulta";
import { filtrosDe, urlFeed } from "@/lib/filtros";
import { dataPorExtenso, formatarData, linkSeguro, prazoUrgente, textoPrazo } from "@/lib/formato";
import { type Item, MODULOS } from "@/lib/tipos";

const ROTULOS_NUMERO = {
  noticias: "Notícias não lidas",
  estagios: "Vagas e estágios",
  concursos: "Concursos abertos",
} as const;

function saudacao(agora = new Date()): string {
  const hora = Number(
    new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", hour: "numeric", hour12: false }).format(agora),
  );
  if (hora < 5 || hora >= 18) return "Boa noite";
  if (hora < 12) return "Bom dia";
  return "Boa tarde";
}

/** Cabeçalho com saudação, números por módulo e a cidade à noite ao fundo. */
export function Saudacao({ nome, painel, compacta = false }: { nome: string; painel: Painel; compacta?: boolean }) {
  return (
    <section className={compacta ? "heroi heroi-compacto" : "heroi"}>
      <div className="heroi-arte">
        <ArteCidade />
      </div>
      <div className="heroi-texto">
        <p className="heroi-data">{dataPorExtenso()}</p>
        <h1>
          {saudacao()}, {nome}! <span className="aceno">👋</span>
        </h1>
        {!compacta && <p className="heroi-sub">Fique por dentro do mundo tech, oportunidades e novidades importantes.</p>}
      </div>
      <div className="numeros">
        {MODULOS.map((modulo) => {
          const Icone = ICONES_MODULO[modulo];
          return (
            <Link
              key={modulo}
              href={urlFeed(filtrosDe(modulo, { estado: "nao-lidos" }))}
              className={`numero numero-${modulo}`}
            >
              <span className="numero-icone">
                <Icone width={26} height={26} />
              </span>
              <span>
                <strong>{painel.naoLidos[modulo]}</strong>
                <span>{ROTULOS_NUMERO[modulo]}</span>
              </span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

export function TituloSecao({ children, href, link = "Ver todas" }: { children: ReactNode; href?: string; link?: string }) {
  return (
    <div className="titulo-secao">
      <h2>{children}</h2>
      {href && (
        <Link href={href}>
          {link} <IconeSeta width={16} height={16} />
        </Link>
      )}
    </div>
  );
}

/** Coluna da direita: prazos se aproximando e tags da semana. */
export function ColunaLateral({ prazos, tags, hoje, urgentes }: { prazos: Item[]; tags: string[]; hoje: string; urgentes: number }) {
  return (
    <aside className="lateral">
      <section className="lateral-cartao cartao-prazos">
        <span className="raios" aria-hidden="true" />
        <IconeSino width={30} height={30} className={urgentes > 0 ? "sino tocando" : "sino"} />
        <h2>{urgentes > 0 ? `${urgentes} ${urgentes === 1 ? "prazo termina" : "prazos terminam"} em 3 dias` : "Prazos chegando"}</h2>
        {prazos.length === 0 ? (
          <p className="discreto">Nenhuma inscrição terminando nas próximas duas semanas.</p>
        ) : (
          <ul className="lista-prazos">
            {prazos.map((item) => {
              const url = linkSeguro(item.url);
              return (
                <li key={item.id} className={prazoUrgente(item.prazo ?? "", hoje) ? "urgente" : undefined}>
                  <span className="prazo-data">{formatarData(item.prazo).slice(0, 5)}</span>
                  <span className="prazo-texto">
                    {url ? (
                      <a href={url} target="_blank" rel="noopener noreferrer">
                        {item.titulo}
                      </a>
                    ) : (
                      item.titulo
                    )}
                    <small>{textoPrazo(item.prazo ?? "", hoje)}</small>
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        <Link className="botao-primario largo" href={urlFeed(filtrosDe("concursos"))}>
          <IconeSino width={18} height={18} />
          Ver concursos
        </Link>
      </section>

      {tags.length > 0 && (
        <section className="lateral-cartao">
          <h2>Acompanhe também</h2>
          <div className="lista-tags">
            {tags.map((tag) => (
              <Link key={tag} className="tag-atalho" href={urlFeed(filtrosDe("todos", { tag }))}>
                <IconeTag width={16} height={16} />
                {tag}
              </Link>
            ))}
          </div>
        </section>
      )}
    </aside>
  );
}
