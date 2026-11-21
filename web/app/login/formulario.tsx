"use client";

import { useActionState } from "react";
import { type EstadoLogin, entrar } from "./acoes";

const INICIAL: EstadoLogin = { erro: null };

export function FormularioLogin() {
  const [estado, acao, enviando] = useActionState(entrar, INICIAL);
  return (
    <form action={acao} className="formulario-login">
      <label>
        E-mail
        <input name="email" type="email" autoComplete="username" required />
      </label>
      <label>
        Senha
        <input name="senha" type="password" autoComplete="current-password" required />
      </label>
      {estado.erro && (
        <p className="erro" role="alert">
          {estado.erro}
        </p>
      )}
      <button type="submit" disabled={enviando}>
        {enviando ? "Entrando…" : "Entrar"}
      </button>
    </form>
  );
}
