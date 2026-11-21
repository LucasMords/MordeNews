"use client";

import { useActionState } from "react";
import { type EstadoLogin, entrar } from "./acoes";

const INICIAL: EstadoLogin = { erro: null };

export function FormularioLogin({ proximo }: { proximo: string }) {
  const [estado, acao, enviando] = useActionState(entrar, INICIAL);
  return (
    <form action={acao} className="formulario-login">
      <input type="hidden" name="proximo" value={proximo} />
      <label>
        E-mail
        <input name="email" type="email" autoComplete="username" placeholder="voce@exemplo.com" required />
      </label>
      <label>
        Senha
        <input name="senha" type="password" autoComplete="current-password" placeholder="••••••••" required />
      </label>
      {estado.erro && (
        <p className="erro" role="alert">
          {estado.erro}
        </p>
      )}
      <button type="submit" className="botao-primario" disabled={enviando}>
        {enviando ? "Entrando…" : "Entrar"}
      </button>
    </form>
  );
}
