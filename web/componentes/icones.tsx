import type { ReactNode, SVGProps } from "react";

type Props = SVGProps<SVGSVGElement>;

/** Ícones em SVG embutido (traço de 1,8 px, herdam a cor do texto). Sem biblioteca externa. */
function Icone({ children, ...props }: Props & { children: ReactNode }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export const IconeNoticias = (p: Props) => (
  <Icone {...p}>
    <path d="M4 5h13a1 1 0 0 1 1 1v12a2 2 0 0 0 2 2H6a2 2 0 0 1-2-2Z" />
    <path d="M18 9h2v9a2 2 0 0 1-2 2" />
    <path d="M8 9h6M8 13h6M8 17h3" />
  </Icone>
);

export const IconeEstagios = (p: Props) => (
  <Icone {...p}>
    <rect x="3" y="7" width="18" height="13" rx="2" />
    <path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 13h18" />
  </Icone>
);

export const IconeConcursos = (p: Props) => (
  <Icone {...p}>
    <path d="m3 9 9-5 9 5" />
    <path d="M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18" />
  </Icone>
);

export const IconeSalvo = ({ cheio, ...p }: Props & { cheio?: boolean }) => (
  <Icone {...p}>
    <path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4.5L5 21V4a1 1 0 0 1 1-1Z" fill={cheio ? "currentColor" : "none"} />
  </Icone>
);

export const IconeLido = (p: Props) => (
  <Icone {...p}>
    <path d="m4 12.5 5 5L20 6.5" />
  </Icone>
);

export const IconeRelogio = (p: Props) => (
  <Icone {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </Icone>
);

export const IconeExterno = (p: Props) => (
  <Icone {...p}>
    <path d="M14 4h6v6M20 4l-9 9" />
    <path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
  </Icone>
);

export const IconeBusca = (p: Props) => (
  <Icone {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-4-4" />
  </Icone>
);

export const IconeSair = (p: Props) => (
  <Icone {...p}>
    <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 16l4-4-4-4M14 12H4" />
  </Icone>
);

export const IconeNovo = (p: Props) => (
  <Icone {...p}>
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6" />
  </Icone>
);


export const IconeInicio = (p: Props) => (
  <Icone {...p}>
    <path d="M3 10.5 12 3l9 7.5" />
    <path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5" />
  </Icone>
);

export const IconeSol = (p: Props) => (
  <Icone {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </Icone>
);

export const IconeLua = (p: Props) => (
  <Icone {...p}>
    <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z" />
  </Icone>
);

export const IconeSino = (p: Props) => (
  <Icone {...p}>
    <path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15Z" />
    <path d="M10 20.5a2 2 0 0 0 4 0" />
  </Icone>
);

export const IconeSeta = (p: Props) => (
  <Icone {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Icone>
);

export const IconeCalendario = (p: Props) => (
  <Icone {...p}>
    <rect x="3.5" y="5" width="17" height="15.5" rx="2" />
    <path d="M3.5 10h17M8 3v4M16 3v4" />
  </Icone>
);

export const IconeEstrela = (p: Props) => (
  <Icone {...p}>
    <path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9Z" />
  </Icone>
);

export const IconeTag = (p: Props) => (
  <Icone {...p}>
    <path d="M3.5 12.2V4.5a1 1 0 0 1 1-1h7.7l8.3 8.3a1.5 1.5 0 0 1 0 2.1l-6.1 6.1a1.5 1.5 0 0 1-2.1 0Z" />
    <circle cx="8" cy="8" r="1.4" />
  </Icone>
);

export const IconeGostei = ({ cheio, ...p }: Props & { cheio?: boolean }) => (
  <Icone {...p}>
    <path d="M7 10v11H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1Z" fill={cheio ? "currentColor" : "none"} />
    <path
      d="M7 10l4-7a2.5 2.5 0 0 1 2.6 3L13 10h6a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 17.8 21H7"
      fill={cheio ? "currentColor" : "none"}
      fillOpacity={cheio ? 0.25 : 0}
    />
  </Icone>
);

export const IconeNaoGostei = ({ cheio, ...p }: Props & { cheio?: boolean }) => (
  <IconeGostei cheio={cheio} {...p} style={{ transform: "rotate(180deg)", ...p.style }} />
);

/** Marca do MordeNews: "</>" em degradê roxo. */
export function Logo({ tamanho = 40 }: { tamanho?: number }) {
  return (
    <svg width={tamanho} height={tamanho * 0.75} viewBox="0 0 64 48" aria-hidden="true" className="logo">
      <defs>
        <linearGradient id="logo-gradiente" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#8b5cf6" />
          <stop offset="1" stopColor="#6d28d9" />
        </linearGradient>
      </defs>
      <g fill="none" stroke="url(#logo-gradiente)" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 10 5 24l13 14" />
        <path d="M46 10l13 14-13 14" />
        <path d="M37 6 27 42" />
      </g>
    </svg>
  );
}

/** Logo + nome, como no topo do menu. */
export function Marca({ tamanho = 56 }: { tamanho?: number }) {
  return (
    <span className="marca">
      <Logo tamanho={tamanho} />
      <span className="marca-nome">
        Morde<span>News</span>
      </span>
    </span>
  );
}
