import { describe, expect, it } from "vitest";
import { lerMarkdown, trechos } from "@/lib/markdown";

describe("trechos", () => {
  it("links http(s) e negrito", () => {
    expect(trechos("Veja **isto** em [fonte](https://e.com/a) hoje")).toEqual([
      { texto: "Veja " },
      { texto: "isto", negrito: true },
      { texto: " em " },
      { texto: "fonte", url: "https://e.com/a" },
      { texto: " hoje" },
    ]);
  });

  it("link perigoso fica como texto", () => {
    expect(trechos("[x](javascript:alert(1))")).toEqual([{ texto: "[x](javascript:alert(1)" }, { texto: ")" }]);
    expect(trechos("<script>oi</script>")).toEqual([{ texto: "<script>oi</script>" }]);
  });
});

describe("lerMarkdown", () => {
  it("títulos, listas e parágrafos", () => {
    const blocos = lerMarkdown("## Destaques\n- um\n* dois\n\nLinha 1\nlinha 2\n### Prazos\r\n- três");
    expect(blocos.map((b) => b.tipo)).toEqual(["titulo", "lista", "paragrafo", "subtitulo", "lista"]);
    expect(blocos[1]).toEqual({ tipo: "lista", itens: [[{ texto: "um" }], [{ texto: "dois" }]] });
    expect(blocos[2]).toEqual({ tipo: "paragrafo", trechos: [{ texto: "Linha 1 linha 2" }] });
  });

  it("texto vazio não gera blocos", () => {
    expect(lerMarkdown("\n  \n")).toEqual([]);
  });
});
