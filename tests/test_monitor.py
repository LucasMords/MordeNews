"""Bloco 9: alerta de fontes com problema e limpeza mensal do texto."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from radar import banco, cli, config, monitor
from radar.entrega import correio
from radar.modelos import Item
from tests.conftest import SupabaseFalso, fonte
from tests.test_resumo import CFG

AGORA = datetime(2026, 11, 21, 11, 30, tzinfo=UTC)  # 08:30 BRT
FONTES = ["ok", "quebrada", "parada", "nova"]


def _execucao(coletor: str, dias_atras: float, ok: bool = True, novos: int = 0, **extra: Any):
    quando = AGORA - timedelta(days=dias_atras)
    return {
        "coletor": coletor,
        "iniciado_em": quando.isoformat(),
        "finalizado_em": quando.isoformat(),
        "ok": ok,
        "itens_novos": novos,
        "erro": extra.get("erro"),
    }


def _historico() -> list[dict[str, Any]]:
    return [
        # rodando bem e trazendo itens
        _execucao("ok", 3.5, novos=4),
        _execucao("ok", 0.5, novos=2),
        # 1 sucesso antigo e as 2 últimas falharam
        _execucao("quebrada", 2, novos=3),
        _execucao("quebrada", 1, ok=False, erro="HTTPStatusError: 500"),
        _execucao("quebrada", 0.2, ok=False, erro="HTTPStatusError: 503"),
        # roda sem erro, mas não traz nada há mais de 3 dias
        _execucao("parada", 3.8, novos=5),
        _execucao("parada", 2.5),
        _execucao("parada", 1.5),
        _execucao("parada", 0.5),
        # adicionada há 2 dias: ainda não conta como parada
        _execucao("nova", 2),
        _execucao("nova", 1),
    ]


def test_diagnostico_falhas_seguidas_e_fonte_parada() -> None:
    problemas = monitor.diagnosticar(_historico(), FONTES, AGORA)
    assert [(p.fonte, p.tipo) for p in problemas] == [
        ("quebrada", "falha"),
        ("parada", "sem-itens"),
    ]
    assert "HTTPStatusError: 503" in problemas[0].detalhe  # mostra o último erro


def test_uma_falha_so_nao_e_problema() -> None:
    execucoes = [_execucao("x", 1, novos=2), _execucao("x", 0.1, ok=False)]
    assert monitor.diagnosticar(execucoes, ["x"], AGORA) == []


def test_fonte_sem_nenhuma_execucao_no_periodo_nao_gera_alerta() -> None:
    assert monitor.diagnosticar([], ["sumida"], AGORA) == []


@pytest.fixture
def caixa(monkeypatch: pytest.MonkeyPatch, supabase: SupabaseFalso) -> list[correio.Mensagem]:
    enviados: list[correio.Mensagem] = []
    monkeypatch.setattr(config, "carregar", lambda: CFG)
    monkeypatch.setattr(config, "carregar_fontes_validas", lambda: [fonte(nome=n) for n in FONTES])
    monkeypatch.setattr(correio, "enviar", lambda mensagem, **_: enviados.append(mensagem))
    supabase.tabelas["execucoes"] = _historico()
    return enviados


def test_monitorar_envia_e_nao_repete_no_dia_seguinte(
    supabase: SupabaseFalso, caixa: list[correio.Mensagem]
) -> None:
    resultado = monitor.monitorar(agora=AGORA)

    assert len(caixa) == 1 and len(resultado.novos) == 2
    assert caixa[0].assunto == "MordeNews: 2 fontes com problema"
    assert "• quebrada (falhando)" in caixa[0].texto
    assert "• parada (sem itens novos)" in caixa[0].texto
    registro = supabase.tabelas["execucoes"][-1]
    assert (
        registro["coletor"] == "monitor" and registro["erro"] == "falha:quebrada sem-itens:parada"
    )
    registro["iniciado_em"] = AGORA.isoformat()

    # mais tarde no mesmo dia (reserva das 15h): não verifica de novo
    assert monitor.monitorar(agora=AGORA + timedelta(hours=7)).mensagem is None

    # no dia seguinte, os mesmos problemas não são avisados de novo
    amanha = monitor.monitorar(agora=AGORA + timedelta(days=1))
    assert len(amanha.problemas) == 2 and amanha.novos == [] and len(caixa) == 1


def test_problema_que_continua_volta_a_ser_avisado_depois_de_7_dias(
    supabase: SupabaseFalso, caixa: list[correio.Mensagem]
) -> None:
    supabase.tabelas["execucoes"].append(
        _execucao("monitor", 8, erro="falha:quebrada sem-itens:parada")
    )
    resultado = monitor.monitorar(agora=AGORA)
    assert len(resultado.novos) == 2 and len(caixa) == 1


def test_sem_problemas_nao_envia_mas_registra(
    supabase: SupabaseFalso, caixa: list[correio.Mensagem]
) -> None:
    supabase.tabelas["execucoes"] = [_execucao("ok", 0.5, novos=1)]
    resultado = monitor.monitorar(agora=AGORA)
    assert resultado.mensagem is None and caixa == []
    assert supabase.tabelas["execucoes"][-1]["coletor"] == "monitor"


def test_simular_nao_envia_nem_registra(
    supabase: SupabaseFalso, caixa: list[correio.Mensagem]
) -> None:
    antes = len(supabase.tabelas["execucoes"])
    resultado = monitor.monitorar(simular=True, agora=AGORA)
    assert len(resultado.problemas) == 2 and caixa == []
    assert len(supabase.tabelas["execucoes"]) == antes


def test_texto_do_erro_e_escapado_no_html() -> None:
    problema = monitor.Problema("f", "falha", "erro <b>&</b>")
    html = correio.montar_monitor([problema], AGORA.date()).html
    assert "<b>&" not in html and "erro &lt;b&gt;&amp;&lt;/b&gt;" in html


def test_cli_monitorar_simular(
    caixa: list[correio.Mensagem], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["monitorar", "--simular"]) == 0
    assert "quebrada [falha]" in capsys.readouterr().out


# ------------------------------------------------------------------------ limpeza


def _semear_para_limpeza(supabase: SupabaseFalso) -> None:
    banco.salvar_itens(
        Item(modulo="noticias", fonte="t", titulo=f"Item {n}", url=f"https://e.com/{n}", texto="x")
        for n in range(1, 6)
    )
    velho = (AGORA - timedelta(days=91)).isoformat()
    novo = (AGORA - timedelta(days=10)).isoformat()
    ajustes = [
        {"coletado_em": velho, "status": "processado"},  # limpa
        {"coletado_em": velho, "status": "descartado"},  # limpa
        {"coletado_em": velho, "status": "processado", "salvo": True},  # salvo: mantém
        {"coletado_em": velho, "status": "pendente"},  # ainda não triado: mantém
        {"coletado_em": novo, "status": "processado"},  # recente: mantém
    ]
    for linha, ajuste in zip(supabase.tabelas["itens"], ajustes, strict=True):
        linha.update({"salvo": False, **ajuste})


def test_limpeza_apaga_so_o_texto_dos_antigos_nao_salvos(supabase: SupabaseFalso) -> None:
    _semear_para_limpeza(supabase)

    assert monitor.limpar(simular=True, agora=AGORA) == 2
    assert all(linha["texto"] == "x" for linha in supabase.tabelas["itens"])

    assert monitor.limpar(agora=AGORA) == 2
    textos = [linha["texto"] for linha in supabase.tabelas["itens"]]
    assert textos == [None, None, "x", "x", "x"]
    assert all(linha["titulo"] for linha in supabase.tabelas["itens"])  # o resto fica
    assert supabase.tabelas["execucoes"][-1]["coletor"] == "limpeza"

    assert monitor.limpar(agora=AGORA) == 0  # rodar de novo não faz nada
