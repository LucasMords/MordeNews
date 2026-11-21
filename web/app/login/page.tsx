import type { Metadata } from "next";
import { FormularioLogin } from "./formulario";

export const metadata: Metadata = { title: "Entrar · MordeNews" };

export default function PaginaLogin() {
  return (
    <main className="login">
      <h1>MordeNews</h1>
      <p className="discreto">Portal pessoal. Entre com a conta cadastrada no Supabase.</p>
      <FormularioLogin />
    </main>
  );
}
