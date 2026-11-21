"use client";

import { type ReactNode, useOptimistic } from "react";
import { marcarLido, marcarSalvo } from "@/app/acoes";
import { IconeLido, IconeSalvo, IconeSeta } from "@/componentes/icones";

interface Marcas {
  lido: boolean;
  salvo: boolean;
}

/**
 * Casca do cartão com os botões salvar/lido. A mudança aparece na hora (useOptimistic) e a
 * Server Action grava em segundo plano; se ela falhar, o React volta ao estado verdadeiro.
 */
export function CartaoInterativo({
  id,
  lido,
  salvo,
  classe,
  url,
  children,
}: Marcas & { id: number; classe: string; url: string | null; children: ReactNode }) {
  const [marcas, mudar] = useOptimistic<Marcas, Partial<Marcas>>({ lido, salvo }, (atual, m) => ({ ...atual, ...m }));

  function acao(marca: keyof Marcas, gravar: (f: FormData) => Promise<void>) {
    return async (formulario: FormData) => {
      mudar({ [marca]: !marcas[marca] });
      try {
        await gravar(formulario);
      } catch {
        // estado otimista é descartado ao fim da transição: o cartão volta ao valor do banco
      }
    };
  }

  const classes = [classe, marcas.lido ? "lido" : "", marcas.salvo ? "salvo" : ""].filter(Boolean).join(" ");

  return (
    <article className={classes}>
      {children}
      <div className="cartao-acoes">
        {url && (
          <a className="botao-seta" href={url} target="_blank" rel="noopener noreferrer" title="Abrir na fonte" aria-label="Abrir na fonte">
            <IconeSeta width={20} height={20} />
          </a>
        )}
        <Botao acao={acao("salvo", marcarSalvo)} id={id} ativo={marcas.salvo} rotulo="Salvar" rotuloAtivo="Tirar dos salvos" classeAtiva="salvo-ativo">
          <IconeSalvo cheio={marcas.salvo} />
        </Botao>
        <Botao acao={acao("lido", marcarLido)} id={id} ativo={marcas.lido} rotulo="Marcar como lido" rotuloAtivo="Marcar como não lido" classeAtiva="ativo">
          <IconeLido />
        </Botao>
      </div>
    </article>
  );
}

function Botao({
  acao,
  id,
  ativo,
  rotulo,
  rotuloAtivo,
  classeAtiva,
  children,
}: {
  acao: (f: FormData) => Promise<void>;
  id: number;
  ativo: boolean;
  rotulo: string;
  rotuloAtivo: string;
  classeAtiva: string;
  children: ReactNode;
}) {
  const texto = ativo ? rotuloAtivo : rotulo;
  return (
    <form action={acao}>
      <input type="hidden" name="id" value={id} />
      <input type="hidden" name="valor" value={ativo ? "0" : "1"} />
      <button type="submit" className={ativo ? `botao-icone ${classeAtiva}` : "botao-icone"} title={texto} aria-label={texto} aria-pressed={ativo}>
        {children}
      </button>
    </form>
  );
}
