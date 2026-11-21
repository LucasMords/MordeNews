import { describe, expect, it } from "vitest";
import { destinoSeguro } from "@/lib/destino";
import { lerVoto } from "@/lib/tipos";
import { lerIdItem, lerVotoPedido } from "@/lib/votos";

describe("lerVoto", () => {
  it("aceita objeto, lista ou nada", () => {
    expect(lerVoto({ voto: 1 })).toBe(1);
    expect(lerVoto([{ voto: -1 }])).toBe(-1);
    expect(lerVoto([])).toBeNull();
    expect(lerVoto(null)).toBeNull();
    expect(lerVoto({ voto: 5 })).toBeNull();
  });
});

describe("pedido de voto", () => {
  it("lê só 1, -1 e 0", () => {
    expect(lerVotoPedido("1")).toBe(1);
    expect(lerVotoPedido("-1")).toBe(-1);
    expect(lerVotoPedido("0")).toBeNull();
    expect(lerVotoPedido("2")).toBeUndefined();
    expect(lerVotoPedido(null)).toBeUndefined();
  });

  it("id precisa ser inteiro positivo", () => {
    expect(lerIdItem("42")).toBe(42);
    expect(lerIdItem("-1")).toBeNull();
    expect(lerIdItem("1.5")).toBeNull();
    expect(lerIdItem("abc")).toBeNull();
  });
});

describe("destinoSeguro", () => {
  it("só aceita caminhos internos", () => {
    expect(destinoSeguro("/votar?item=1&voto=1")).toBe("/votar?item=1&voto=1");
    expect(destinoSeguro("//malicioso.com")).toBe("/");
    expect(destinoSeguro("/\\malicioso.com")).toBe("/");
    expect(destinoSeguro("https://malicioso.com")).toBe("/");
    expect(destinoSeguro(undefined)).toBe("/");
  });
});
