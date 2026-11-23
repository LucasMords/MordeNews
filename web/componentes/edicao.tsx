import { Fragment } from "react";
import { IconeBusca, IconeEditor } from "@/componentes/icones";
import type { Edicao } from "@/lib/consulta";
import { formatarData } from "@/lib/formato";
import { type Bloco, lerMarkdown, type Trecho } from "@/lib/markdown";

const ROTULOS = {
  diaria: { nome: "Editor-chefe", Icone: IconeEditor },
  semanal: { nome: "Busca da semana", Icone: IconeBusca },
} as const;

function Trechos({ trechos }: { trechos: Trecho[] }) {
  return trechos.map((t, i) => {
    if (t.url) {
      return (
        <a key={i} href={t.url} target="_blank" rel="noopener noreferrer">
          {t.texto}
        </a>
      );
    }
    return t.negrito ? <strong key={i}>{t.texto}</strong> : <Fragment key={i}>{t.texto}</Fragment>;
  });
}

function Blocos({ blocos }: { blocos: Bloco[] }) {
  return blocos.map((bloco, i) => {
    switch (bloco.tipo) {
      case "titulo":
        return <h3 key={i}><Trechos trechos={bloco.trechos} /></h3>;
      case "subtitulo":
        return <h4 key={i}><Trechos trechos={bloco.trechos} /></h4>;
      case "lista":
        return (
          <ul key={i}>
            {bloco.itens.map((item, j) => (
              <li key={j}>
                <Trechos trechos={item} />
              </li>
            ))}
          </ul>
        );
      default:
        return <p key={i}><Trechos trechos={bloco.trechos} /></p>;
    }
  });
}

/** Edição escrita pelas rotinas do Claude (bloco 8). A diária abre aberta; a semanal, recolhida. */
export function CartaoEdicao({ edicao }: { edicao: Edicao }) {
  const { nome, Icone } = ROTULOS[edicao.tipo];
  return (
    <details className={`edicao edicao-${edicao.tipo}`} open={edicao.tipo === "diaria"}>
      <summary>
        <span className="edicao-icone">
          <Icone width={22} height={22} />
        </span>
        <span className="edicao-cabecalho">
          <small>
            {nome} · {formatarData(edicao.referencia)}
          </small>
          <strong>{edicao.titulo}</strong>
        </span>
        <span className="edicao-abrir" aria-hidden="true" />
      </summary>
      <div className="edicao-corpo">
        <Blocos blocos={lerMarkdown(edicao.conteudo)} />
      </div>
    </details>
  );
}
