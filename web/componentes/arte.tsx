import type { ComponentType, SVGProps } from "react";
import { IconeConcursos, IconeEstagios, IconeNoticias } from "@/componentes/icones";
import { Ilustracao } from "@/componentes/ilustracoes";
import { temaDoItem } from "@/lib/temas";
import type { Item, Modulo } from "@/lib/tipos";

export const ICONES_MODULO: Record<Modulo, ComponentType<SVGProps<SVGSVGElement>>> = {
  noticias: IconeNoticias,
  estagios: IconeEstagios,
  concursos: IconeConcursos,
};

/** Gerador pseudoaleatório com semente: a arte sai igual em todo render (sem hydration diff). */
function aleatorio(semente: number) {
  let s = semente;
  return () => {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  };
}

interface Predio {
  x: number;
  largura: number;
  altura: number;
  janelas: { x: number; y: number; cor: string }[];
}

function predios(semente: number, base: number, alturaMin: number, alturaMax: number, acesas: number): Predio[] {
  const r = aleatorio(semente);
  const lista: Predio[] = [];
  let x = -10;
  while (x < 820) {
    const largura = 28 + Math.floor(r() * 46);
    const altura = alturaMin + Math.floor(r() * (alturaMax - alturaMin));
    const janelas: Predio["janelas"] = [];
    for (let jy = base - altura + 10; jy < base - 8; jy += 9) {
      for (let jx = x + 5; jx < x + largura - 6; jx += 8) {
        if (r() < acesas) {
          const tom = r();
          janelas.push({ x: jx, y: jy, cor: tom < 0.6 ? "#c4b5fd" : tom < 0.85 ? "#f0abfc" : "#fde68a" });
        }
      }
    }
    lista.push({ x, largura, altura, janelas });
    x += largura + 2 + Math.floor(r() * 8);
  }
  return lista;
}

const FUNDO = predios(7, 300, 90, 210, 0.16);
const FRENTE = predios(42, 300, 50, 150, 0.22);
const ESTRELAS = (() => {
  const r = aleatorio(99);
  return Array.from({ length: 60 }, () => ({ x: r() * 800, y: r() * 140, raio: 0.4 + r() * 1.1, o: 0.3 + r() * 0.7 }));
})();

/** Cidade à noite, desenhada em SVG (sem imagem externa). Decorativa. */
export function ArteCidade() {
  return (
    <svg className="arte-cidade" viewBox="0 0 800 300" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
      <defs>
        <linearGradient id="ceu" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0f0a2e" />
          <stop offset=".45" stopColor="#3b1d8f" />
          <stop offset=".75" stopColor="#9d3fbf" />
          <stop offset="1" stopColor="#f472b6" />
        </linearGradient>
        <linearGradient id="predio-fundo" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2e1a6b" />
          <stop offset="1" stopColor="#1a1040" />
        </linearGradient>
        <linearGradient id="predio-frente" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1a1238" />
          <stop offset="1" stopColor="#0c0820" />
        </linearGradient>
        <radialGradient id="lua" cx=".5" cy=".5" r=".5">
          <stop offset="0" stopColor="#fdf4ff" />
          <stop offset=".6" stopColor="#f5d0fe" stopOpacity=".9" />
          <stop offset="1" stopColor="#f5d0fe" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="800" height="300" fill="url(#ceu)" />
      {ESTRELAS.map((e, i) => (
        <circle key={i} cx={e.x} cy={e.y} r={e.raio} fill="#fff" opacity={e.o} className={i % 7 === 0 ? "estrela-pisca" : undefined} />
      ))}
      <circle cx="640" cy="70" r="34" fill="url(#lua)" />
      <circle cx="640" cy="70" r="16" fill="#fdf4ff" />
      {FUNDO.map((p) => (
        <g key={`f${p.x}`}>
          <rect x={p.x} y={300 - p.altura} width={p.largura} height={p.altura} fill="url(#predio-fundo)" />
          {p.janelas.map((j) => (
            <rect key={`${j.x}-${j.y}`} x={j.x} y={j.y} width="3" height="4" fill={j.cor} opacity=".55" />
          ))}
        </g>
      ))}
      {FRENTE.map((p) => (
        <g key={`p${p.x}`}>
          <rect x={p.x} y={300 - p.altura} width={p.largura} height={p.altura} fill="url(#predio-frente)" />
          {p.janelas.map((j) => (
            <rect key={`${j.x}-${j.y}`} x={j.x} y={j.y} width="3" height="4" fill={j.cor} opacity=".85" />
          ))}
        </g>
      ))}
      {/* moldura de janela, como se a cena fosse vista de dentro */}
      <g stroke="#0b0820" strokeWidth="10" fill="none" opacity=".9">
        <path d="M260 0v300M540 0v300M0 190h800" />
      </g>
    </svg>
  );
}

/** Capa do item: ilustração genérica do assunto (pelas tags), com o nome da fonte por cima. */
export function Capa({ item, grande = false }: { item: Pick<Item, "modulo" | "tags" | "titulo" | "fonte">; grande?: boolean }) {
  const tema = temaDoItem(item);
  return (
    <div className={`capa capa-${tema}${grande ? " capa-grande" : ""}`} aria-hidden="true">
      <Ilustracao tema={tema} />
      <span className="capa-fonte">{item.fonte}</span>
    </div>
  );
}
