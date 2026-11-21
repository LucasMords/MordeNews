"use client";

import { type ReactNode, useOptimistic } from "react";
import { marcarLido, marcarSalvo, votar } from "@/app/acoes";
import { IconeGostei, IconeLido, IconeNaoGostei, IconeSalvo, IconeSeta } from "@/componentes/icones";
import type { Voto } from "@/lib/tipos";

interface Marcas {
  lido: boolean;
  salvo: boolean;
  voto: Voto;
}

/**
 * Casca do cartão com os botões salvar, lido e 👍/👎. A mudança aparece na hora
 * (useOptimistic) e a Server Action grava em segundo plano; se falhar, o React volta ao
 * estado verdadeiro.
 */
export function CartaoInterativo({
  id,
  lido,
  salvo,
  voto,
  classe,
  url,
  children,
}: Marcas & { id: number; classe: string; url: string | null; children: ReactNode }) {
  const [marcas, mudar] = useOptimistic<Marcas, Partial<Marcas>>({ lido, salvo, voto }, (atual, m) => ({
    ...atual,
    ...m,
  }));

  function acao(mudanca: Partial<Marcas>, gravar: (f: FormData) => Promise<void>) {
    return async (formulario: FormData) => {
      mudar(mudanca);
      try {
        await gravar(formulario);
      } catch {
        // estado otimista é descartado ao fim da transição: o cartão volta ao valor do banco
      }
    };
  }

  const classes = [classe, marcas.lido ? "lido" : "", marcas.salvo ? "salvo" : ""].filter(Boolean).join(" ");
  // Clicar no voto que já está marcado tira o voto.
  const votoGostei: Voto = marcas.voto === 1 ? null : 1;
  const votoNaoGostei: Voto = marcas.voto === -1 ? null : -1;

  return (
    <article className={classes}>
      {children}
      <div className="cartao-acoes">
        {url && (
          <a className="botao-seta" href={url} target="_blank" rel="noopener noreferrer" title="Abrir na fonte" aria-label="Abrir na fonte">
            <IconeSeta width={20} height={20} />
          </a>
        )}
        <div className="cartao-botoes">
          <Botao acao={acao({ salvo: !marcas.salvo }, marcarSalvo)} id={id} campo="valor" valor={marcas.salvo ? "0" : "1"} ativo={marcas.salvo} texto={marcas.salvo ? "Tirar dos salvos" : "Salvar"} classeAtiva="salvo-ativo">
            <IconeSalvo cheio={marcas.salvo} />
          </Botao>
          <Botao acao={acao({ lido: !marcas.lido }, marcarLido)} id={id} campo="valor" valor={marcas.lido ? "0" : "1"} ativo={marcas.lido} texto={marcas.lido ? "Marcar como não lido" : "Marcar como lido"} classeAtiva="ativo">
            <IconeLido />
          </Botao>
          <Botao acao={acao({ voto: votoGostei }, votar)} id={id} campo="voto" valor={String(votoGostei ?? 0)} ativo={marcas.voto === 1} texto={marcas.voto === 1 ? "Tirar o 👍" : "Gostei: mais assim"} classeAtiva="gostei-ativo">
            <IconeGostei cheio={marcas.voto === 1} />
          </Botao>
          <Botao acao={acao({ voto: votoNaoGostei }, votar)} id={id} campo="voto" valor={String(votoNaoGostei ?? 0)} ativo={marcas.voto === -1} texto={marcas.voto === -1 ? "Tirar o 👎" : "Não gostei: menos assim"} classeAtiva="nao-gostei-ativo">
            <IconeNaoGostei cheio={marcas.voto === -1} />
          </Botao>
        </div>
      </div>
    </article>
  );
}

function Botao({
  acao,
  id,
  campo,
  valor,
  ativo,
  texto,
  classeAtiva,
  children,
}: {
  acao: (f: FormData) => Promise<void>;
  id: number;
  campo: "valor" | "voto";
  valor: string;
  ativo: boolean;
  texto: string;
  classeAtiva: string;
  children: ReactNode;
}) {
  return (
    <form action={acao}>
      <input type="hidden" name="id" value={id} />
      <input type="hidden" name={campo} value={valor} />
      <button type="submit" className={ativo ? `botao-icone ${classeAtiva}` : "botao-icone"} title={texto} aria-label={texto} aria-pressed={ativo}>
        {children}
      </button>
    </form>
  );
}
