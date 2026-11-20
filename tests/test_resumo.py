from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from radar import banco, config
from radar.entrega import correio, resumo
from radar.modelos import Item, ItemResumo
from tests.conftest import SupabaseFalso

AGORA = datetime(2026, 11, 19, 10, 7, tzinfo=UTC)
CFG = config.Configuracao(
    supabase_url="https://falso.supabase.co",
    supabase_service_role_key="sb_secret_teste",
    gemini_api_key=None,
    gemini_model="x",
    nota_minima_resumo=6,
    email_remetente="robo@exemplo.com",
    email_senha_app="senha",
    email_destino="eu@exemplo.com",
    resumo_maximo=2,
)


def _semear(supabase: SupabaseFalso, notas: list[int | None], **por_item: Any) -> None:
    banco.salvar_itens(
        Item(modulo="noticias", fonte="t", titulo=f"Notícia {n}", url=f"https://e.com/{n}")
        for n in range(1, len(notas) + 1)
    )
    for linha, nota in zip(supabase.tabelas["itens"], notas, strict=True):
        linha.update(
            {
                "nota": nota,
                "resumo": f"Resumo {linha['id']}",
                "tags": ["ia"],
                "status": "processado",
                "coletado_em": "2026-11-19T09:20:00+00:00",
            }
        )
        linha.update(por_item.get(str(linha["id"]), {}))


@pytest.fixture
def enviados(monkeypatch: pytest.MonkeyPatch) -> list[correio.Mensagem]:
    caixa: list[correio.Mensagem] = []

    def enviar_falso(mensagem: correio.Mensagem, **_: Any) -> None:
        caixa.append(mensagem)

    monkeypatch.setattr(config, "carregar", lambda: CFG)
    monkeypatch.setattr(correio, "enviar", enviar_falso)
    return caixa


def _ids_enviados(supabase: SupabaseFalso) -> list[int]:
    return sorted(linha["id"] for linha in supabase.tabelas["itens"] if linha.get("enviado_em"))


def test_para_resumo_filtra_nota_status_envio_e_janela(supabase: SupabaseFalso) -> None:
    _semear(
        supabase,
        [9, 5, 7, 8, 10],
        **{
            "3": {"status": "descartado"},
            "4": {"enviado_em": "2026-11-18T10:07:00+00:00"},
            "5": {"coletado_em": "2026-11-17T09:00:00+00:00"},  # fora da janela de 36h
        },
    )
    itens = banco.para_resumo(datetime(2026, 11, 17, 22, 7, tzinfo=UTC), nota_minima=6)
    assert [i.id for i in itens] == [1]


def test_selecionar_pega_os_de_maior_nota() -> None:
    def item(id_: int, nota: int) -> ItemResumo:
        return ItemResumo(id=id_, modulo="noticias", fonte="t", titulo="x", url="u", nota=nota)

    escolhidos, fora = resumo.selecionar([item(1, 6), item(2, 9), item(3, 7)], maximo=2)
    assert [a.principal.id for a in escolhidos] == [2, 3]
    assert [a.principal.id for a in fora] == [1]


def test_repetidos_viram_um_assunto_e_todos_sao_marcados(
    supabase: SupabaseFalso, enviados: list[correio.Mensagem]
) -> None:
    _semear(
        supabase,
        [10, 9, 7],
        **{
            "1": {"titulo": "Java4Shell no OpenJDK", "resumo": "Falha CVE-2026-114938."},
            "2": {"titulo": "Oracle corrige Java", "resumo": "Inclui CVE-2026-114938."},
        },
    )
    resultado = resumo.enviar_resumo(agora=AGORA)
    assert (resultado.assuntos, resultado.enviados, resultado.fora) == (2, 3, 0)
    assert "Também em: t (https://e.com/2)" in enviados[0].texto
    assert _ids_enviados(supabase) == [1, 2, 3]


def test_envia_e_marca_so_os_escolhidos(
    supabase: SupabaseFalso, enviados: list[correio.Mensagem]
) -> None:
    _semear(supabase, [6, 9, 7])

    resultado = resumo.enviar_resumo(agora=AGORA)

    assert (resultado.enviados, resultado.fora) == (2, 1)
    assert len(enviados) == 1
    assert "[9] Notícia 2" in enviados[0].texto and "Outros 1 itens" in enviados[0].texto
    assert _ids_enviados(supabase) == [2, 3]
    execucao = supabase.tabelas["execucoes"][-1]
    assert (execucao["coletor"], execucao["ok"], execucao["itens_novos"]) == (
        "resumo-diario",
        True,
        2,
    )


def test_segundo_envio_nao_repete_itens(
    supabase: SupabaseFalso, enviados: list[correio.Mensagem]
) -> None:
    _semear(supabase, [6, 9, 7])
    resumo.enviar_resumo(agora=AGORA)
    resumo.enviar_resumo(agora=AGORA)
    assert "Notícia 2" not in enviados[1].texto
    assert "[6] Notícia 1" in enviados[1].texto
    assert _ids_enviados(supabase) == [1, 2, 3]


def test_vagas_aparecem_com_nota_baixa_e_limite_proprio(
    supabase: SupabaseFalso, enviados: list[correio.Mensagem]
) -> None:
    vaga = {"modulo": "estagios", "campos": {"empresa": "Acme", "cidade": "Palmas - TO"}}
    # notícias 9 e 7 enchem o RESUMO_MAXIMO (2); as vagas de nota 2 e 1 entram mesmo assim
    _semear(supabase, [9, 7, 2, 1, 3], **{"3": vaga, "4": vaga, "5": {"status": "descartado"}})

    resultado = resumo.enviar_resumo(agora=AGORA)

    texto = enviados[0].texto
    assert "[2] Notícia 3" in texto and "[1] Notícia 4" in texto
    assert "Acme · Palmas - TO" in texto
    assert "Notícia 5" not in texto  # descartado nunca aparece
    assert "Vagas de estágio aparecem com qualquer nota" in texto
    assert resultado.fora == 0
    assert _ids_enviados(supabase) == [1, 2, 3, 4]


def test_vagas_respeitam_limite_e_nota_propria(
    supabase: SupabaseFalso, enviados: list[correio.Mensagem], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        config, "carregar", lambda: replace(CFG, nota_minima_estagios=2, estagios_maximo=1)
    )
    vaga = {"modulo": "estagios"}
    _semear(supabase, [4, 3, 1], **{"1": vaga, "2": vaga, "3": vaga})

    resultado = resumo.enviar_resumo(agora=AGORA)

    assert "[4] Notícia 1" in enviados[0].texto and "Notícia 2" not in enviados[0].texto
    assert "a partir da nota 2" in enviados[0].texto
    assert (resultado.enviados, resultado.fora) == (1, 1)  # a de nota 1 nem é candidata


def test_sem_itens_nao_envia_email(
    supabase: SupabaseFalso, enviados: list[correio.Mensagem]
) -> None:
    _semear(supabase, [3, 5])
    resultado = resumo.enviar_resumo(agora=AGORA)
    assert resultado.enviados == 0 and enviados == []
    assert supabase.tabelas["execucoes"][-1]["ok"] is True


def test_falha_no_envio_nao_marca_como_enviado(
    supabase: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    _semear(supabase, [9])

    def quebrado(*_: Any, **__: Any) -> None:
        raise correio.ErroEnvio("login SMTP recusado")

    monkeypatch.setattr(config, "carregar", lambda: CFG)
    monkeypatch.setattr(correio, "enviar", quebrado)
    with pytest.raises(correio.ErroEnvio):
        resumo.enviar_resumo(agora=AGORA)
    assert _ids_enviados(supabase) == []
    execucao = supabase.tabelas["execucoes"][-1]
    assert execucao["ok"] is False and "recusado" in execucao["erro"]


def test_simular_nao_envia_nem_marca_e_dispensa_credenciais(
    supabase: SupabaseFalso, enviados: list[correio.Mensagem], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "carregar", lambda: replace(CFG, email_senha_app=None))
    _semear(supabase, [9])
    resultado = resumo.enviar_resumo(simular=True, agora=AGORA)
    assert resultado.mensagem is not None and resultado.enviados == 1
    assert enviados == [] and _ids_enviados(supabase) == []


def test_sem_credenciais_falha_antes_de_consultar(
    supabase: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "carregar", lambda: replace(CFG, email_destino=None))
    with pytest.raises(config.ErroConfiguracao, match="EMAIL_DESTINO"):
        resumo.enviar_resumo(agora=AGORA)
    assert supabase.requisicoes == []
