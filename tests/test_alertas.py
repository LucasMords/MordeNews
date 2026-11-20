"""Bloco 5: concursos no resumo (sem nota, por prazo) e o alerta de prazo."""

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest

from radar import banco, config
from radar.entrega import alertas, correio, resumo
from radar.modelos import Item
from tests.conftest import SupabaseFalso
from tests.test_resumo import CFG

AGORA = datetime(2026, 11, 19, 11, 2, tzinfo=UTC)  # 08:02 BRT
HOJE = date(2026, 11, 19)


def _semear(supabase: SupabaseFalso, itens: list[dict[str, Any]]) -> None:
    banco.salvar_itens(
        Item(
            modulo=dados.get("modulo", "concursos"),
            fonte=dados.get("fonte", "pci-to-go"),
            titulo=dados["titulo"],
            url=f"https://e.com/{n}",
        )
        for n, dados in enumerate(itens, start=1)
    )
    for linha, dados in zip(supabase.tabelas["itens"], itens, strict=True):
        linha.update(
            {
                "nota": dados.get("nota", 5),
                "resumo": f"Resumo de {dados['titulo']}",
                "status": dados.get("status", "processado"),
                "coletado_em": "2026-11-19T09:20:00+00:00",
                "prazo": dados.get("prazo"),
                "campos": dados.get("campos", {}),
                "salvo": dados.get("salvo", False),
            }
        )


@pytest.fixture
def caixa(monkeypatch: pytest.MonkeyPatch) -> list[correio.Mensagem]:
    enviados: list[correio.Mensagem] = []
    monkeypatch.setattr(config, "carregar", lambda: CFG)
    monkeypatch.setattr(correio, "enviar", lambda mensagem, **_: enviados.append(mensagem))
    return enviados


# ------------------------------------------------------------------ resumo diário


def test_concursos_entram_sem_nota_e_pelo_prazo_mais_proximo(
    supabase: SupabaseFalso, caixa: list[correio.Mensagem]
) -> None:
    _semear(
        supabase,
        [
            {"titulo": "Concurso Sem Prazo", "nota": 9},
            {"titulo": "Concurso Distante", "nota": 1, "prazo": "2027-01-13"},
            {
                "titulo": "Concurso Próximo",
                "nota": 0,
                "prazo": "2026-12-09",
                "campos": {
                    "orgao": "Prefeitura X",
                    "vagas": 2956,
                    "salario_max": "R$ 4.508,28",
                    "data_prova": "2027-02-01",
                    "link_edital": "https://banca.com/ed.pdf",
                },
            },
        ],
    )

    resumo.enviar_resumo(agora=AGORA)

    texto = caixa[0].texto
    ordem = [
        texto.index(t) for t in ("Concurso Próximo", "Concurso Distante", "Concurso Sem Prazo")
    ]
    assert ordem == sorted(ordem)
    assert "• Concurso Próximo" in texto and "[0]" not in texto and "[9]" not in texto
    assert "Prefeitura X · 2956 vagas · até R$ 4.508,28 · prova em 01/02/2027" in texto
    assert "Edital: https://banca.com/ed.pdf" in texto
    assert "Concursos aparecem todos" in texto
    assert "em destaque" not in caixa[0].assunto  # nota 9 de concurso não conta como destaque
    assert ">9<" not in caixa[0].html


def test_concursos_tem_limite_proprio(
    supabase: SupabaseFalso, caixa: list[correio.Mensagem], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "carregar", lambda: replace(CFG, concursos_maximo=1))
    _semear(
        supabase,
        [
            {"titulo": "Notícia A", "modulo": "noticias", "fonte": "t", "nota": 9},
            {"titulo": "Notícia B", "modulo": "noticias", "fonte": "t", "nota": 8},
            {"titulo": "Concurso Tarde", "prazo": "2026-12-30"},
            {"titulo": "Concurso Cedo", "prazo": "2026-12-01"},
        ],
    )
    resultado = resumo.enviar_resumo(agora=AGORA)
    texto = caixa[0].texto
    assert "Notícia A" in texto and "Notícia B" in texto  # RESUMO_MAXIMO=2 só para notícias
    assert "Concurso Cedo" in texto and "Concurso Tarde" not in texto
    assert resultado.fora == 1


# ------------------------------------------------------------------- alerta de prazo


def test_alerta_pega_concursos_vagas_boas_e_salvos_em_ate_3_dias(
    supabase: SupabaseFalso, caixa: list[correio.Mensagem]
) -> None:
    _semear(
        supabase,
        [
            {"titulo": "Concurso Hoje", "prazo": "2026-11-19", "nota": 0},
            {"titulo": "Concurso Daqui 3 Dias", "prazo": "2026-11-22"},
            {"titulo": "Concurso Daqui 4 Dias", "prazo": "2026-11-23"},
            {"titulo": "Concurso Vencido", "prazo": "2026-11-18"},
            {"titulo": "Vaga Boa", "modulo": "estagios", "fonte": "gh", "nota": 8,
             "prazo": "2026-11-20"},
            {"titulo": "Vaga Fraca", "modulo": "estagios", "fonte": "gh", "nota": 2,
             "prazo": "2026-11-20"},
            {"titulo": "Vaga Salva", "modulo": "estagios", "fonte": "gh", "nota": 2,
             "prazo": "2026-11-21", "salvo": True},
            {"titulo": "Concurso Descartado", "prazo": "2026-11-20", "status": "descartado"},
        ],
    )  # fmt: skip

    resultado = alertas.enviar_alertas(agora=AGORA)

    assert resultado.itens == 4
    mensagem = caixa[0]
    assert mensagem.assunto == "MordeNews: 4 prazos de inscrição terminando"
    linhas = [linha for linha in mensagem.texto.splitlines() if linha.startswith("•")]
    assert linhas == [
        "• TERMINA HOJE (19/11/2026) — Concurso Hoje",
        "• TERMINA AMANHÃ (20/11/2026) — Vaga Boa",
        "• TERMINA EM 2 DIAS (21/11/2026) — Vaga Salva",
        "• TERMINA EM 3 DIAS (22/11/2026) — Concurso Daqui 3 Dias",
    ]
    assert "TERMINA HOJE" in mensagem.html
    assert supabase.tabelas["execucoes"][-1]["coletor"] == "alertas-prazo"


def test_no_maximo_um_alerta_por_dia(
    supabase: SupabaseFalso, caixa: list[correio.Mensagem]
) -> None:
    _semear(supabase, [{"titulo": "Concurso Hoje", "prazo": "2026-11-19"}])
    alertas.enviar_alertas(agora=AGORA)
    supabase.tabelas["execucoes"][-1]["iniciado_em"] = AGORA.isoformat()

    segunda = alertas.enviar_alertas(agora=datetime(2026, 11, 19, 18, 4, tzinfo=UTC))

    assert segunda.mensagem is None and len(caixa) == 1


def test_sem_prazos_nao_envia(supabase: SupabaseFalso, caixa: list[correio.Mensagem]) -> None:
    _semear(supabase, [{"titulo": "Concurso Longe", "prazo": "2026-12-30"}])
    resultado = alertas.enviar_alertas(agora=AGORA)
    assert resultado.mensagem is None and caixa == []
    assert supabase.tabelas["execucoes"][-1]["ok"] is True


def test_simular_mostra_sem_enviar_nem_registrar(
    supabase: SupabaseFalso, caixa: list[correio.Mensagem]
) -> None:
    _semear(supabase, [{"titulo": "Concurso Hoje", "prazo": "2026-11-19"}])
    resultado = alertas.enviar_alertas(simular=True, agora=AGORA)
    assert resultado.mensagem is not None and caixa == []
    assert supabase.tabelas["execucoes"] == []


def test_texto_externo_e_escapado_no_alerta() -> None:
    from radar.modelos import ItemResumo

    item = ItemResumo(
        id=1, modulo="concursos", fonte="f", titulo="<script>x</script> & cia",
        url="https://e.com/1", nota=5, prazo=HOJE,
    )  # fmt: skip
    html = correio.montar_alerta([item], HOJE).html
    assert "<script>x" not in html and "&lt;script&gt;x&lt;/script&gt; &amp; cia" in html


def test_concurso_com_inscricao_encerrada_nao_entra_no_resumo(
    supabase: SupabaseFalso, caixa: list[correio.Mensagem]
) -> None:
    _semear(
        supabase,
        [
            {"titulo": "Concurso Retificado Antigo", "prazo": "2026-11-06"},
            {"titulo": "Concurso Aberto", "prazo": "2026-11-19"},  # termina hoje: ainda entra
        ],
    )
    resultado = resumo.enviar_resumo(agora=AGORA)
    assert "Concurso Aberto" in caixa[0].texto
    assert "Concurso Retificado Antigo" not in caixa[0].texto
    assert resultado.enviados == 1
