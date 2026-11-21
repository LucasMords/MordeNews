from collections.abc import Callable, Sequence

import pytest

from radar import banco
from radar.ia import cliente, triagem
from radar.modelos import Item, ItemPendente, Modulo, Resultado
from tests.conftest import SupabaseFalso

Classificador = Callable[[Sequence[ItemPendente], Modulo], list[Resultado]]


def _semear(quantidade: int) -> None:
    banco.salvar_itens(
        Item(modulo="noticias", fonte="t", titulo=f"Notícia {n}", url=f"https://e.com/{n}")
        for n in range(1, quantidade + 1)
    )


def _resultado(id_: int, nota: int = 7, descartar: bool = False) -> Resultado:
    return Resultado(id=id_, nota=nota, resumo=f"Resumo {id_}", tags=["ia"], descartar=descartar)


def _linhas(supabase: SupabaseFalso) -> dict[int, dict]:
    return {linha["id"]: linha for linha in supabase.tabelas["itens"]}


def _usar(monkeypatch: pytest.MonkeyPatch, classificador: Classificador) -> list[list[int]]:
    """Troca classificar_lote e devolve a lista de lotes recebidos (ids)."""
    lotes: list[list[int]] = []

    def falso(itens: Sequence[ItemPendente], modulo: Modulo, **_: object) -> list[Resultado]:
        lotes.append([i.id for i in itens])
        return classificador(itens, modulo)

    monkeypatch.setattr(cliente, "classificar_lote", falso)
    return lotes


def test_grava_triagem_e_conta_faltantes(
    supabase: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    _semear(3)
    # responde só para os ids 3 e 2 (o 2 descartado); o 1 fica sem resposta
    _usar(monkeypatch, lambda itens, _m: [_resultado(3, 9), _resultado(2, 1, descartar=True)])

    resumo = triagem.triar("noticias", pausa=0)

    linhas = _linhas(supabase)
    assert (linhas[3]["status"], linhas[3]["nota"], linhas[3]["resumo"]) == (
        "processado",
        9,
        "Resumo 3",
    )
    assert (linhas[2]["status"], linhas[2]["nota"]) == ("descartado", 1)
    assert (linhas[1]["status"], linhas[1]["tentativas_ia"]) == ("pendente", 1)
    assert (resumo.processados, resumo.descartados, resumo.sem_resposta) == (1, 1, 1)
    execucao = supabase.tabelas["execucoes"][-1]
    assert (execucao["coletor"], execucao["ok"], execucao["itens_novos"]) == (
        "triagem-noticias",
        True,
        2,
    )


def test_terceira_falha_vai_para_erro(
    supabase: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    _semear(1)
    supabase.tabelas["itens"][0]["tentativas_ia"] = 2
    _usar(monkeypatch, lambda itens, _m: [])

    resumo = triagem.triar("noticias", pausa=0)

    assert (_linhas(supabase)[1]["status"], _linhas(supabase)[1]["tentativas_ia"]) == ("erro", 3)
    assert resumo.para_erro == 1


def test_cada_item_tem_uma_tentativa_por_execucao(
    supabase: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    _semear(3)
    lotes = _usar(monkeypatch, lambda itens, _m: [])
    triagem.triar("noticias", tamanho_lote=1, pausa=0)
    assert sorted(i for lote in lotes for i in lote) == [1, 2, 3]
    assert all(linha["tentativas_ia"] == 1 for linha in supabase.tabelas["itens"])


def test_divide_em_lotes_com_pausa_e_mais_novos_primeiro(
    supabase: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    _semear(5)
    lotes = _usar(monkeypatch, lambda itens, _m: [_resultado(i.id) for i in itens])
    pausas: list[float] = []

    triagem.triar("noticias", tamanho_lote=2, pausa=4.0, dormir=pausas.append)

    assert lotes == [[5, 4], [3, 2], [1]]
    assert pausas == [4.0, 4.0]


def test_respeita_maximo_por_execucao(
    supabase: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    _semear(5)
    lotes = _usar(monkeypatch, lambda itens, _m: [_resultado(i.id) for i in itens])
    triagem.triar("noticias", maximo=3, pausa=0)
    assert sum(len(lote) for lote in lotes) == 3


def test_cota_esgotada_para_sem_erro_e_preserva_pendentes(
    supabase: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    _semear(4)
    chamadas = {"n": 0}

    def classificador(itens: Sequence[ItemPendente], _m: Modulo) -> list[Resultado]:
        chamadas["n"] += 1
        if chamadas["n"] == 2:
            raise cliente.CotaEsgotada("429")
        return [_resultado(i.id) for i in itens]

    _usar(monkeypatch, classificador)
    resumo = triagem.triar("noticias", tamanho_lote=2, pausa=0)

    assert resumo.interrompido == "cota esgotada" and resumo.processados == 2
    linhas = _linhas(supabase)
    assert [linhas[i]["status"] for i in (4, 3)] == ["processado", "processado"]
    assert [(linhas[i]["status"], linhas[i]["tentativas_ia"]) for i in (2, 1)] == [
        ("pendente", 0),
        ("pendente", 0),
    ]
    execucao = supabase.tabelas["execucoes"][-1]
    assert execucao["ok"] is True and "cota" in execucao["erro"]


def test_erro_da_ia_propaga_e_registra_falha(
    supabase: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    _semear(1)

    def quebrado(_i: Sequence[ItemPendente], _m: Modulo) -> list[Resultado]:
        raise cliente.ErroIA("chave inválida")

    _usar(monkeypatch, quebrado)
    with pytest.raises(cliente.ErroIA):
        triagem.triar("noticias", pausa=0)
    execucao = supabase.tabelas["execucoes"][-1]
    assert execucao["ok"] is False and "chave inválida" in execucao["erro"]
    assert _linhas(supabase)[1]["tentativas_ia"] == 0  # falha da API não gasta tentativa do item


def test_sem_pendentes_nao_chama_a_ia(
    supabase: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    lotes = _usar(monkeypatch, lambda itens, _m: [])
    resumo = triagem.triar("noticias", pausa=0)
    assert lotes == [] and resumo.triados == 0
