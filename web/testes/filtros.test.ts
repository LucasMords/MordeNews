import { describe, expect, it } from "vitest";
import {
  eInicio,
  filtrosDe,
  juntarGrupos,
  lerFiltros,
  limparBusca,
  limparTag,
  urlFeed,
} from "@/lib/filtros";

describe("lerFiltros", () => {
  it("usa os padrões quando a URL está vazia", () => {
    expect(lerFiltros({})).toEqual({
      modulo: "noticias",
      busca: "",
      tag: "",
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
      tag: "ia",
      nota: "7",
      ver: "salvos",
      encerrados: "1",
      pagina: "3",
    });
    expect(filtros).toMatchObject({
      modulo: "concursos",
      busca: "prefeitura palmas",
      tag: "ia",
      notaMinima: 7,
      estado: "salvos",
      encerrados: true,
      pagina: 3,
    });
  });

  it("aceita a seção todos", () => {
    expect(lerFiltros({ modulo: "todos" }).modulo).toBe("todos");
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

describe("eInicio", () => {
  it("só a raiz sem filtros é a página inicial", () => {
    expect(eInicio({})).toBe(true);
    expect(eInicio({ q: "" })).toBe(true);
    expect(eInicio({ modulo: "noticias" })).toBe(false);
    expect(eInicio({ q: "rust" })).toBe(false);
  });
});

describe("limparBusca", () => {
  it("remove o que mudaria o sentido do filtro or do PostgREST", () => {
    expect(limparBusca("ia),status.eq.erro,(x")).toBe("ia status.eq.erro x");
    expect(limparBusca('50% "remoto" *_\:')).toBe("50 remoto");
  });

  it("limita o tamanho", () => {
    expect(limparBusca("a".repeat(500))).toHaveLength(80);
  });
});

describe("limparTag", () => {
  it("tira chaves, vírgulas e aspas", () => {
    expect(limparTag('ia},{"x')).toBe("iax");
    expect(limparTag("c++ e #dev")).toBe("c++ e #dev");
  });
});

describe("urlFeed", () => {
  it("leva sempre o módulo e omite o resto que está no padrão", () => {
    expect(urlFeed(lerFiltros({}))).toBe("/?modulo=noticias");
    expect(urlFeed(filtrosDe("todos", { estado: "salvos" }))).toBe("/?modulo=todos&ver=salvos");
  });

  it("monta a URL com as mudanças pedidas", () => {
    const filtros = lerFiltros({ q: "rust", nota: "6" });
    expect(urlFeed(filtros, { pagina: 2 })).toBe("/?modulo=noticias&q=rust&nota=6&pagina=2");
    expect(urlFeed(filtros, { modulo: "estagios" })).toBe("/?modulo=estagios&q=rust&nota=6");
    expect(urlFeed(filtros, { tag: "ia" })).toBe("/?modulo=noticias&q=rust&tag=ia&nota=6");
  });
});

describe("juntarGrupos", () => {
  it("junta os grupos com E", () => {
    expect(juntarGrupos([])).toBeNull();
    expect(juntarGrupos(["a,b"])).toBe("a,b");
    expect(juntarGrupos(["a,b", "c,d"])).toBe("and(or(a,b),or(c,d))");
  });
});
