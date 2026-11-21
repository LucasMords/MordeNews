import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { cookies } from "next/headers";
import type { ReactNode } from "react";
import "./globals.css";

// Servida pelo próprio Next (baixada no build), sem chamada ao Google no navegador.
const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--fonte" });

export const metadata: Metadata = {
  title: "MordeNews",
  description: "Radar pessoal de notícias, vagas e concursos.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0d0b1f",
};

/** Tema escuro por padrão; o claro fica salvo num cookie (ver `trocarTema`). */
export default async function Layout({ children }: { children: ReactNode }) {
  const tema = (await cookies()).get("tema")?.value === "claro" ? "claro" : "escuro";
  return (
    <html lang="pt-BR" className={inter.variable} data-tema={tema}>
      <body>{children}</body>
    </html>
  );
}
