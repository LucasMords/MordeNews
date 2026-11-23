import { linkSeguro } from "./formato";

/**
 * Markdown mínimo das edições do editor-chefe (bloco 8): títulos `##`/`###`, listas `-`/`*`,
 * parágrafos, **negrito** e [links](https://...). Nada de HTML: o texto vira nós do React,
 * e links que não são http(s) ficam como texto puro.
 */
export interface Trecho {
  texto: string;
  negrito?: boolean;
  url?: string;
}

export type Bloco =
  | { tipo: "titulo"; trechos: Trecho[] }
  | { tipo: "subtitulo"; trechos: Trecho[] }
  | { tipo: "lista"; itens: Trecho[][] }
  | { tipo: "paragrafo"; trechos: Trecho[] };

const INLINE = /\[([^\]\n]+)\]\(([^)\s]+)\)|\*\*([^*\n]+)\*\*/g;

export function trechos(linha: string): Trecho[] {
  const saida: Trecho[] = [];
  let ultimo = 0;
  for (const achado of linha.matchAll(INLINE)) {
    const inicio = achado.index ?? 0;
    if (inicio > ultimo) saida.push({ texto: linha.slice(ultimo, inicio) });
    const [inteiro, rotulo, endereco, negrito] = achado;
    if (rotulo !== undefined) {
      const url = linkSeguro(endereco);
      saida.push(url ? { texto: rotulo, url } : { texto: inteiro });
    } else {
      saida.push({ texto: negrito, negrito: true });
    }
    ultimo = inicio + inteiro.length;
  }
  if (ultimo < linha.length) saida.push({ texto: linha.slice(ultimo) });
  return saida;
}

export function lerMarkdown(texto: string): Bloco[] {
  const blocos: Bloco[] = [];
  let paragrafo: string[] = [];
  const fecharParagrafo = () => {
    if (paragrafo.length) blocos.push({ tipo: "paragrafo", trechos: trechos(paragrafo.join(" ")) });
    paragrafo = [];
  };

  for (const bruta of texto.replace(/\r\n?/g, "\n").split("\n")) {
    const linha = bruta.trim();
    const titulo = /^(#{1,3})\s+(.+)$/.exec(linha);
    const itemLista = /^[-*]\s+(.+)$/.exec(linha);
    if (!linha) {
      fecharParagrafo();
    } else if (titulo) {
      fecharParagrafo();
      blocos.push({ tipo: titulo[1].length <= 2 ? "titulo" : "subtitulo", trechos: trechos(titulo[2]) });
    } else if (itemLista) {
      fecharParagrafo();
      const anterior = blocos.at(-1);
      if (anterior?.tipo === "lista") anterior.itens.push(trechos(itemLista[1]));
      else blocos.push({ tipo: "lista", itens: [trechos(itemLista[1])] });
    } else {
      paragrafo.push(linha);
    }
  }
  fecharParagrafo();
  return blocos;
}
