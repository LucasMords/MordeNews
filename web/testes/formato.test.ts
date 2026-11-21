import { describe, expect, it } from "vitest";
import {
  agruparPor,
  dataPorExtenso,
  formatarData,
  hojeBrasilia,
  linhaDados,
  linkExtra,
  linkSeguro,
  prazoUrgente,
  rotuloDia,
  textoPrazo,
} from "@/lib/formato";

describe("datas", () => {
  it("hoje é calculado no fuso de Brasília", () => {
    // 01:30 UTC do dia 22 ainda é dia 21 em Brasília
    expect(hojeBrasilia(new Date("2026-11-22T01:30:00Z"))).toBe("2026-11-21");
  });

  it("formata data simples e timestamp", () => {
    expect(formatarData("2026-11-24")).toBe("24/11/2026");
    expect(formatarData("2026-11-22T01:30:00+00:00")).toBe("21/11/2026");
    expect(formatarData(null)).toBe("");
    expect(formatarData("lixo")).toBe("");
  });

  it("descreve o prazo como no e-mail", () => {
    const hoje = "2026-11-21";
    expect(textoPrazo("2026-11-20", hoje)).toBe("encerrado em 20/11/2026");
    expect(textoPrazo("2026-11-21", hoje)).toBe("termina HOJE (21/11/2026)");
    expect(textoPrazo("2026-11-22", hoje)).toBe("termina amanhã (22/11/2026)");
    expect(textoPrazo("2026-12-01", hoje)).toBe("até 01/12/2026 (10 dias)");
    expect(prazoUrgente("2026-11-24", hoje)).toBe(true);
    expect(prazoUrgente("2026-11-25", hoje)).toBe(false);
    expect(prazoUrgente("2026-11-20", hoje)).toBe(false);
  });
});

describe("grupos por dia", () => {
  const hoje = "2026-11-21";

  it("rotula hoje, ontem e dias anteriores no fuso de Brasília", () => {
    expect(rotuloDia("2026-11-21T12:00:00Z", hoje)).toBe("Hoje");
    expect(rotuloDia("2026-11-21T02:00:00Z", hoje)).toBe("Ontem"); // 23h do dia 20 em Brasília
    expect(rotuloDia("2026-11-19T12:00:00Z", hoje)).toBe("quinta-feira, 19 de novembro");
    expect(rotuloDia("lixo", hoje)).toBe("Sem data");
  });

  it("agrupa itens seguidos com o mesmo rótulo", () => {
    const grupos = agruparPor(["a1", "a2", "b1", "a3"], (s) => s[0]);
    expect(grupos).toEqual([
      { rotulo: "a", itens: ["a1", "a2"] },
      { rotulo: "b", itens: ["b1"] },
      { rotulo: "a", itens: ["a3"] },
    ]);
  });

  it("escreve a data por extenso", () => {
    expect(dataPorExtenso(new Date("2026-11-21T12:00:00Z"))).toBe("sábado, 21 de novembro");
  });
});

describe("campos do módulo", () => {
  it("monta a linha da vaga", () => {
    const item = {
      modulo: "estagios" as const,
      campos: { empresa: "Acme", cidade: "Palmas", remoto: true, bolsa: "R$ 1.200" },
    };
    expect(linhaDados(item)).toBe("Acme · Palmas · remoto · bolsa R$ 1.200");
  });

  it("monta a linha do concurso", () => {
    const item = {
      modulo: "concursos" as const,
      campos: {
        orgao: "Prefeitura X",
        vagas: 1,
        salario_max: "R$ 4.508,28",
        escolaridade: "superior",
        data_prova: "2027-02-01",
      },
    };
    expect(linhaDados(item)).toBe(
      "Prefeitura X · 1 vaga · até R$ 4.508,28 · superior · prova em 01/02/2027",
    );
  });

  it("notícia e campos vazios não geram linha", () => {
    expect(linhaDados({ modulo: "noticias", campos: {} })).toBeNull();
    expect(linhaDados({ modulo: "concursos", campos: null })).toBeNull();
  });
});

describe("links", () => {
  it("só aceita http e https", () => {
    expect(linkSeguro("https://e.com/a")).toBe("https://e.com/a");
    expect(linkSeguro("javascript:alert(1)")).toBeNull();
    expect(linkSeguro("não é url")).toBeNull();
    expect(linkSeguro(42)).toBeNull();
  });

  it("link de inscrição e de edital", () => {
    expect(
      linkExtra({ modulo: "estagios", campos: { link_inscricao: "https://v.com/1" } }),
    ).toEqual({ rotulo: "Inscrição", url: "https://v.com/1" });
    expect(
      linkExtra({ modulo: "concursos", campos: { link_edital: "javascript:x" } }),
    ).toBeNull();
    expect(linkExtra({ modulo: "noticias", campos: { link_edital: "https://x.com" } })).toBeNull();
  });
});
