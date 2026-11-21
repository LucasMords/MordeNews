import { describe, expect, it } from "vitest";
import { juntarGrupos, lerFiltros, limparBusca, urlFeed } from "@/lib/filtros";

describe("lerFiltros", () => {
  it("usa os padrões quando a URL está vazia", () => {
    expect(lerFiltros({})).toEqual({
      modulo: "noticias",
      busca: "",
      notaMinima: 0,
      estado: "todos",
      encerrados: false,
      ordem: "recentes",
      pagina: 1,
    });
  });

  it("lê os filtros válidos", () => {
    const filtros = lerFiltros({
      modulo: "concursos",
      q: "  prefeitura   palmas ",
      nota: "7",
      ver: "salvos",
      encerrados: "1",
      pagina: "3",
    });
    expect(filtros).toMatchObject({
      modulo: "concursos",
      busca: "prefeitura palmas",
      notaMinima: 7,
      estado: "salvos",
      encerrados: true,
      pagina: 3,
    });
  });

  it("valores inválidos voltam ao padrão ou ao limite", () => {
    const filtros = lerFiltros({ modulo: "x", nota: "99", ver: "y", pagina: "-2", ordem: "z" });
    expect(filtros).toMatchObject({
      modulo: "noticias",
      notaMinima: 10,
      estado: "todos",
      pagina: 1,
      ordem: "recentes",
    });
  });

  it("pega o primeiro valor de parâmetro repetido", () => {
    expect(lerFiltros({ modulo: ["estagios", "concursos"] }).modulo).toBe("estagios");
  });
});

describe("limparBusca", () => {
  it("remove o que mudaria o sentido do filtro or do PostgREST", () => {
    expect(limparBusca("ia),status.eq.erro,(x")).toBe("ia status.eq.erro x");
    expect(limparBusca('50% "remoto" *_\\:')).toBe("50 remoto");
  });

  it("limita o tamanho", () => {
    expect(limparBusca("a".repeat(500))).toHaveLength(80);
  });
});

describe("urlFeed", () => {
  it("omite os filtros no padrão", () => {
    expect(urlFeed(lerFiltros({}))).toBe("/");
  });

  it("monta a URL com as mudanças pedidas", () => {
    const filtros = lerFiltros({ q: "rust", nota: "6" });
    expect(urlFeed(filtros, { pagina: 2 })).toBe("/?q=rust&nota=6&pagina=2");
    expect(urlFeed(filtros, { modulo: "estagios" })).toBe("/?modulo=estagios&q=rust&nota=6");
  });
});

describe("juntarGrupos", () => {
  it("junta os grupos com E", () => {
    expect(juntarGrupos([])).toBeNull();
    expect(juntarGrupos(["a,b"])).toBe("a,b");
    expect(juntarGrupos(["a,b", "c,d"])).toBe("and(or(a,b),or(c,d))");
  });
});
