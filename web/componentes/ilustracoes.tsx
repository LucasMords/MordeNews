import type { ReactNode } from "react";
import type { Tema } from "@/lib/temas";

/**
 * Ilustrações genéricas por assunto, desenhadas em SVG (sem imagem externa, sem direito
 * autoral de terceiros). Todas no mesmo estilo: fundo em degradê, grade de pontos, brilho
 * e um objeto central que lembra o tema.
 */

const CORES: Record<Tema, [string, string, string]> = {
  // [fundo escuro, fundo claro, destaque]
  ia: ["#1e1065", "#6d28d9", "#c4b5fd"],
  seguranca: ["#1a0b2e", "#9f1239", "#fda4af"],
  hardware: ["#042f2e", "#0f766e", "#5eead4"],
  codigo: ["#1e1b4b", "#4f46e5", "#a5b4fc"],
  terminal: ["#0a0f1c", "#14532d", "#86efac"],
  nuvem: ["#0c1e4a", "#2563eb", "#93c5fd"],
  mercado: ["#052e2b", "#047857", "#6ee7b7"],
  ciencia: ["#2e1065", "#a21caf", "#f0abfc"],
  games: ["#3b0764", "#db2777", "#fbcfe8"],
  carreira: ["#312e81", "#b45309", "#fde68a"],
  estagio: ["#064e3b", "#059669", "#a7f3d0"],
  concurso: ["#431407", "#c2410c", "#fed7aa"],
  geral: ["#1e1b4b", "#7c3aed", "#ddd6fe"],
};

function Fundo({ tema }: { tema: Tema }) {
  const [a, b, c] = CORES[tema];
  return (
    <>
      <defs>
        <linearGradient id={`il-f-${tema}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={a} />
          <stop offset="1" stopColor={b} />
        </linearGradient>
        <radialGradient id={`il-b-${tema}`} cx=".7" cy=".35" r=".6">
          <stop offset="0" stopColor={c} stopOpacity=".45" />
          <stop offset="1" stopColor={c} stopOpacity="0" />
        </radialGradient>
        <pattern id={`il-p-${tema}`} width="16" height="16" patternUnits="userSpaceOnUse">
          <circle cx="2" cy="2" r="1" fill="#fff" opacity=".12" />
        </pattern>
      </defs>
      <rect width="320" height="200" fill={`url(#il-f-${tema})`} />
      <rect width="320" height="200" fill={`url(#il-p-${tema})`} />
      <rect width="320" height="200" fill={`url(#il-b-${tema})`} />
      <circle cx="40" cy="170" r="70" fill={c} opacity=".07" />
      <circle cx="290" cy="20" r="50" fill="#fff" opacity=".05" />
    </>
  );
}

const B = "#fff"; // traço claro

const CENAS: Record<Tema, (c: string) => ReactNode> = {
  ia: (c) => {
    const camadas = [
      [70, [60, 100, 140]],
      [130, [40, 80, 120, 160]],
      [190, [40, 80, 120, 160]],
      [250, [70, 130]],
    ] as const;
    const linhas: ReactNode[] = [];
    camadas.slice(0, -1).forEach(([x, ys], i) => {
      const [x2, ys2] = camadas[i + 1];
      for (const y of ys) for (const y2 of ys2) linhas.push(<line key={`${x}${y}${y2}`} x1={x} y1={y} x2={x2} y2={y2} />);
    });
    return (
      <>
        <g stroke={c} strokeWidth="1" opacity=".45">{linhas}</g>
        {camadas.map(([x, ys]) =>
          ys.map((y) => (
            <g key={`${x}-${y}`}>
              <circle cx={x} cy={y} r="9" fill={c} opacity=".25" />
              <circle cx={x} cy={y} r="5" fill={B} />
            </g>
          )),
        )}
        <rect x="150" y="78" width="44" height="44" rx="10" fill="#0b0820" stroke={c} strokeWidth="2" />
        <text x="172" y="107" textAnchor="middle" fontSize="18" fontWeight="800" fill={B} fontFamily="system-ui">
          AI
        </text>
      </>
    );
  },
  seguranca: (c) => (
    <>
      <g fill={c} opacity=".18" fontFamily="monospace" fontSize="11">
        {["01101001 10010110 0110", "1001 01101100 10100101", "0110100 1101 00101101", "11010010 0101 1001011"].map((t, i) => (
          <text key={i} x="14" y={40 + i * 40}>
            {t}
          </text>
        ))}
      </g>
      <path d="M160 32 212 52v42c0 36-24 62-52 74-28-12-52-38-52-74V52Z" fill="#0b0820" opacity=".55" />
      <path d="M160 32 212 52v42c0 36-24 62-52 74-28-12-52-38-52-74V52Z" fill="none" stroke={c} strokeWidth="3" />
      <rect x="140" y="92" width="40" height="32" rx="6" fill={B} />
      <path d="M148 92v-10a12 12 0 0 1 24 0v10" fill="none" stroke={B} strokeWidth="5" />
      <circle cx="160" cy="105" r="4" fill="#9f1239" />
      <rect x="158" y="106" width="4" height="9" rx="2" fill="#9f1239" />
    </>
  ),
  hardware: (c) => (
    <>
      <g stroke={c} strokeWidth="2" opacity=".5" fill="none">
        <path d="M20 60h70l20 20M20 140h60l30-30M300 50h-70l-20 30M300 150h-60l-30-30" />
      </g>
      {[[20, 60], [20, 140], [300, 50], [300, 150]].map(([x, y]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r="4" fill={c} />
      ))}
      <g stroke={B} strokeWidth="4" strokeLinecap="round">
        {[0, 1, 2, 3, 4].map((i) => (
          <g key={i}>
            <line x1={124 + i * 18} y1="44" x2={124 + i * 18} y2="56" />
            <line x1={124 + i * 18} y1="144" x2={124 + i * 18} y2="156" />
            <line x1="104" y1={64 + i * 18} x2="116" y2={64 + i * 18} />
            <line x1="204" y1={64 + i * 18} x2="216" y2={64 + i * 18} />
          </g>
        ))}
      </g>
      <rect x="114" y="54" width="92" height="92" rx="12" fill="#06201f" stroke={c} strokeWidth="2.5" />
      <rect x="134" y="74" width="52" height="52" rx="6" fill={c} opacity=".9" />
      <path d="M144 100h32M160 84v32" stroke="#06201f" strokeWidth="3" opacity=".6" />
    </>
  ),
  codigo: (c) => (
    <>
      <rect x="62" y="34" width="196" height="132" rx="12" fill="#0b0a24" opacity=".85" stroke={c} strokeOpacity=".5" />
      <rect x="62" y="34" width="196" height="24" rx="12" fill={c} opacity=".18" />
      {["#f87171", "#fbbf24", "#34d399"].map((cor, i) => (
        <circle key={cor} cx={78 + i * 14} cy="46" r="4" fill={cor} />
      ))}
      {[
        [80, 74, 40, "#c4b5fd"],
        [126, 74, 60, B],
        [92, 92, 54, "#7dd3fc"],
        [152, 92, 36, "#fda4af"],
        [104, 110, 70, "#86efac"],
        [92, 128, 30, "#fde68a"],
        [128, 128, 58, B],
        [80, 146, 24, "#c4b5fd"],
      ].map(([x, y, w, cor], i) => (
        <rect key={i} x={x} y={y} width={w} height="7" rx="3.5" fill={cor as string} opacity=".85" />
      ))}
      <text x="240" y="150" textAnchor="end" fontSize="30" fontWeight="800" fill={c} opacity=".9" fontFamily="monospace">
        {"</>"}
      </text>
    </>
  ),
  terminal: (c) => (
    <>
      <rect x="56" y="36" width="208" height="128" rx="12" fill="#030712" opacity=".9" stroke={c} strokeOpacity=".5" />
      <rect x="56" y="36" width="208" height="22" rx="12" fill={c} opacity=".15" />
      <g fontFamily="monospace" fontSize="13" fill={c}>
        <text x="72" y="82">$ uname -a</text>
        <text x="72" y="102" opacity=".6">kernel 6.x x86_64</text>
        <text x="72" y="122">$ sudo apt upgrade</text>
        <text x="72" y="146">{">"}</text>
      </g>
      <rect x="86" y="136" width="10" height="14" fill={c} className="cursor-pisca" />
    </>
  ),
  nuvem: (c) => (
    <>
      <path
        d="M108 92a30 30 0 0 1 56-18 26 26 0 0 1 48 14 22 22 0 0 1-4 44h-96a22 22 0 0 1-4-40Z"
        fill={B}
        opacity=".95"
      />
      <path d="M128 132v18M160 132v18M192 132v18" stroke={c} strokeWidth="2.5" strokeDasharray="4 4" />
      {[110, 142, 174].map((x) => (
        <g key={x}>
          <rect x={x} y="150" width="36" height="30" rx="5" fill="#0b1a3d" stroke={c} strokeWidth="1.5" />
          <circle cx={x + 8} cy="160" r="2.5" fill="#34d399" />
          <rect x={x + 14} y="158" width="16" height="4" rx="2" fill={c} opacity=".6" />
          <rect x={x + 6} y="168" width="24" height="4" rx="2" fill={c} opacity=".35" />
        </g>
      ))}
      <path d="M140 104l10 10 22-22" fill="none" stroke="#2563eb" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  mercado: (c) => (
    <>
      {[40, 70, 55, 95, 80, 120].map((h, i) => (
        <rect key={i} x={70 + i * 32} y={170 - h} width="20" height={h} rx="4" fill={B} opacity={0.25 + i * 0.12} />
      ))}
      <path d="M70 140 110 118l32 12 32-36 32 10 44-50" fill="none" stroke={c} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M232 46h22v22" fill="none" stroke={c} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
      {[[52, 60], [270, 140]].map(([x, y]) => (
        <g key={x}>
          <circle cx={x} cy={y} r="14" fill="#fbbf24" />
          <text x={x} y={y + 5} textAnchor="middle" fontSize="14" fontWeight="800" fill="#78350f" fontFamily="system-ui">
            $
          </text>
        </g>
      ))}
    </>
  ),
  ciencia: (c) => (
    <>
      {[[30, 30], [280, 40], [250, 170], [60, 160], [140, 20]].map(([x, y]) => (
        <circle key={x} cx={x} cy={y} r="1.6" fill={B} opacity=".8" />
      ))}
      <g fill="none" stroke={c} strokeWidth="3" opacity=".9">
        <ellipse cx="160" cy="100" rx="78" ry="26" />
        <ellipse cx="160" cy="100" rx="78" ry="26" transform="rotate(60 160 100)" />
        <ellipse cx="160" cy="100" rx="78" ry="26" transform="rotate(-60 160 100)" />
      </g>
      <circle cx="160" cy="100" r="14" fill={B} />
      <circle cx="160" cy="100" r="22" fill={c} opacity=".3" />
      <circle cx="238" cy="100" r="6" fill={B} />
      <circle cx="121" cy="33" r="6" fill={B} />
      <circle cx="121" cy="167" r="6" fill={B} />
    </>
  ),
  games: (c) => (
    <>
      <path
        d="M104 72h112c22 0 34 22 40 56 4 24-14 36-30 22l-22-20h-88l-22 20c-16 14-34 2-30-22 6-34 18-56 40-56Z"
        fill="#1a0533"
        stroke={c}
        strokeWidth="2.5"
      />
      <path d="M118 96v28M104 110h28" stroke={B} strokeWidth="7" strokeLinecap="round" />
      <circle cx="206" cy="98" r="7" fill="#34d399" />
      <circle cx="222" cy="112" r="7" fill="#f87171" />
      <circle cx="190" cy="112" r="7" fill="#60a5fa" />
      <circle cx="206" cy="126" r="7" fill="#fbbf24" />
      {[[50, 44], [270, 50], [56, 150]].map(([x, y]) => (
        <path key={x} d={`M${x} ${y - 8}v16M${x - 8} ${y}h16`} stroke={c} strokeWidth="3" strokeLinecap="round" opacity=".6" />
      ))}
    </>
  ),
  carreira: (c) => (
    <>
      <path d="M160 46 250 84l-90 38-90-38Z" fill="#1c1442" stroke={c} strokeWidth="2.5" />
      <path d="M114 102v30c0 12 22 22 46 22s46-10 46-22v-30l-46 20Z" fill="#1c1442" stroke={c} strokeWidth="2.5" />
      <path d="M250 84v44" stroke={c} strokeWidth="3" />
      <circle cx="250" cy="134" r="7" fill="#fbbf24" />
      <g opacity=".5" fill={B}>
        <rect x="40" y="150" width="48" height="8" rx="2" />
        <rect x="46" y="140" width="40" height="8" rx="2" />
        <rect x="42" y="130" width="44" height="8" rx="2" />
      </g>
    </>
  ),
  estagio: (c) => (
    <>
      <g fill={B} opacity=".22">
        {[0, 1, 2, 3].map((i) => (
          <rect key={i} x={40 + i * 26} y={160 - i * 22} width="26" height={20 + i * 22} />
        ))}
      </g>
      <path d="M50 150 150 70" stroke={c} strokeWidth="3" strokeDasharray="6 6" />
      <rect x="146" y="78" width="120" height="84" rx="12" fill="#052e22" stroke={c} strokeWidth="2.5" />
      <path d="M186 78V66a8 8 0 0 1 8-8h24a8 8 0 0 1 8 8v12" fill="none" stroke={c} strokeWidth="5" />
      <path d="M146 112h120" stroke={c} strokeWidth="2.5" />
      <rect x="196" y="104" width="20" height="16" rx="4" fill={c} />
      <path d="M240 40l4 10 10 4-10 4-4 10-4-10-10-4 10-4Z" fill="#fde68a" />
    </>
  ),
  concurso: (c) => (
    <>
      <path d="M84 70 150 36l66 34Z" fill="#2a0d04" stroke={c} strokeWidth="2.5" strokeLinejoin="round" />
      <rect x="88" y="70" width="124" height="10" fill={c} opacity=".9" />
      {[0, 1, 2, 3, 4].map((i) => (
        <rect key={i} x={96 + i * 24} y="84" width="12" height="62" rx="3" fill={B} opacity=".9" />
      ))}
      <rect x="80" y="148" width="140" height="12" rx="3" fill={c} opacity=".9" />
      <g transform="translate(206 92) rotate(8)">
        <rect width="62" height="80" rx="8" fill={B} />
        <rect x="10" y="14" width="42" height="5" rx="2.5" fill="#c2410c" opacity=".7" />
        <rect x="10" y="26" width="34" height="5" rx="2.5" fill="#c2410c" opacity=".4" />
        <rect x="10" y="38" width="38" height="5" rx="2.5" fill="#c2410c" opacity=".4" />
        <circle cx="44" cy="62" r="10" fill="#16a34a" />
        <path d="m39 62 4 4 7-8" fill="none" stroke={B} strokeWidth="2.5" strokeLinecap="round" />
      </g>
    </>
  ),
  geral: (c) => (
    <>
      <circle cx="140" cy="100" r="58" fill="#120c35" stroke={c} strokeWidth="2.5" />
      <g fill="none" stroke={c} strokeWidth="1.6" opacity=".7">
        <ellipse cx="140" cy="100" rx="24" ry="58" />
        <path d="M82 100h116M90 72h100M90 128h100" />
      </g>
      <g transform="translate(184 70)">
        <rect width="86" height="92" rx="8" fill={B} />
        <rect x="10" y="12" width="66" height="10" rx="3" fill="#7c3aed" />
        <rect x="10" y="30" width="30" height="26" rx="3" fill="#c4b5fd" />
        {[30, 38, 46].map((y) => (
          <rect key={y} x="46" y={y} width="30" height="4" rx="2" fill="#a1a1aa" />
        ))}
        {[64, 72, 80].map((y) => (
          <rect key={y} x="10" y={y} width="66" height="4" rx="2" fill="#a1a1aa" />
        ))}
      </g>
    </>
  ),
};

export function Ilustracao({ tema }: { tema: Tema }) {
  return (
    <svg className="ilustracao" viewBox="0 0 320 200" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <Fundo tema={tema} />
      <g className="ilustracao-cena">{CENAS[tema](CORES[tema][2])}</g>
    </svg>
  );
}
