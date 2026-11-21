import type { Item } from "./tipos";

/** Assunto visual de um item: escolhe a ilustração genérica da capa. */
export type Tema =
  | "ia"
  | "seguranca"
  | "hardware"
  | "codigo"
  | "terminal"
  | "nuvem"
  | "mercado"
  | "ciencia"
  | "games"
  | "carreira"
  | "estagio"
  | "concurso"
  | "geral";

/** Tag (como a triagem grava) → tema. A primeira tag reconhecida vence. */
const POR_TAG: Record<string, Tema> = {
  ia: "ia",
  llm: "ia",
  agentes: "ia",
  seguranca: "seguranca",
  vulnerabilidade: "seguranca",
  privacidade: "seguranca",
  hardware: "hardware",
  dev: "codigo",
  backend: "codigo",
  frontend: "codigo",
  "full-stack": "codigo",
  "ferramentas-dev": "codigo",
  "open-source": "codigo",
  java: "codigo",
  javascript: "codigo",
  python: "codigo",
  testes: "codigo",
  qa: "codigo",
  arquitetura: "codigo",
  "sistemas-operacionais": "terminal",
  linux: "terminal",
  cloud: "nuvem",
  devops: "nuvem",
  infra: "nuvem",
  redes: "nuvem",
  "banco-de-dados": "nuvem",
  mercado: "mercado",
  "big-tech": "mercado",
  regulacao: "mercado",
  brasil: "mercado",
  ciencia: "ciencia",
  games: "games",
  carreira: "carreira",
  educacao: "carreira",
  certificacoes: "carreira",
};

/** Palavras do título usadas quando nenhuma tag decide. */
const POR_PALAVRA: [RegExp, Tema][] = [
  [/\b(ia|ai|gpt|llm|gemini|claude|openai|intelig[eê]ncia artificial)\b/i, "ia"],
  [/\b(hack|ataque|malware|ransomware|vulnerab|falha de seguran|senha|phishing)/i, "seguranca"],
  [/\b(chip|cpu|gpu|nvidia|intel|amd|processador|placa)\b/i, "hardware"],
  [/\b(cloud|nuvem|aws|azure|kubernetes|servidor|data ?center)\b/i, "nuvem"],
  [/\b(jogo|game|playstation|xbox|nintendo|steam)\b/i, "games"],
  [/\b(linux|windows|macos|android|ios|kernel)\b/i, "terminal"],
];

export function temaDoItem(item: Pick<Item, "modulo" | "tags" | "titulo">): Tema {
  if (item.modulo === "estagios") return "estagio";
  if (item.modulo === "concursos") return "concurso";
  for (const tag of item.tags ?? []) {
    const tema = POR_TAG[tag.toLowerCase()];
    if (tema) return tema;
  }
  for (const [regra, tema] of POR_PALAVRA) if (regra.test(item.titulo)) return tema;
  return "geral";
}
