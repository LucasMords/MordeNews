import { describe, expect, it } from "vitest";
import { temaDoItem } from "@/lib/temas";

const noticia = (tags: string[], titulo = "Qualquer coisa") => ({ modulo: "noticias" as const, tags, titulo });

describe("temaDoItem", () => {
  it("usa a primeira tag reconhecida", () => {
    expect(temaDoItem(noticia(["outros", "seguranca", "ia"]))).toBe("seguranca");
    expect(temaDoItem(noticia(["llm"]))).toBe("ia");
    expect(temaDoItem(noticia(["banco-de-dados"]))).toBe("nuvem");
  });

  it("cai para palavras do título e depois para o tema geral", () => {
    expect(temaDoItem(noticia(["outros"], "Nvidia anuncia nova GPU"))).toBe("hardware");
    expect(temaDoItem(noticia([], "Resultado da eleição"))).toBe("geral");
  });

  it("vagas e concursos têm tema próprio", () => {
    expect(temaDoItem({ modulo: "estagios", tags: ["ia"], titulo: "x" })).toBe("estagio");
    expect(temaDoItem({ modulo: "concursos", tags: null, titulo: "x" })).toBe("concurso");
  });
});
