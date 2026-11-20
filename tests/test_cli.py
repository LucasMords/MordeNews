from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest

from radar import banco, cli, config
from radar.coletores.http import ClienteHttp
from radar.ia import cliente as ia_cliente
from radar.modelos import Fonte, Item, ItemPendente, Modulo, Resultado
from tests.conftest import SiteFalso, SupabaseFalso, cliente_http, fonte, ler_fixture

# ------------------------------------------------------------ teste-banco


def test_teste_banco_ponta_a_ponta(supabase: SupabaseFalso) -> None:
    assert cli.main(["teste-banco"]) == 0
    assert supabase.tabelas["itens"] == []  # item de teste removido ao final
    assert supabase.tabelas["execucoes"][0]["coletor"] == "teste-banco"


def test_teste_banco_manter(supabase: SupabaseFalso) -> None:
    assert cli.main(["teste-banco", "--manter"]) == 0
    assert len(supabase.tabelas["itens"]) == 1
    # rodar de novo remove o item antigo e testa do zero, sem falhar
    assert cli.main(["teste-banco", "--manter"]) == 0
    assert len(supabase.tabelas["itens"]) == 1


def test_teste_banco_falha_de_banco_retorna_1(supabase: SupabaseFalso) -> None:
    supabase.falhar_com = 500
    assert cli.main(["teste-banco"]) == 1


def test_teste_banco_sem_configuracao_retorna_1(monkeypatch: pytest.MonkeyPatch) -> None:
    def sem_supabase() -> config.Configuracao:
        raise config.ErroConfiguracao("Variável de ambiente SUPABASE_URL não definida.")

    monkeypatch.setattr(config, "carregar", sem_supabase)
    assert cli.main(["teste-banco"]) == 1


# ---------------------------------------------------------------- coletar

FEED_OK = "https://ok.com/feed"
FEED_RUIM = "https://ruim.com/feed"


@pytest.fixture
def ambiente_coleta(
    monkeypatch: pytest.MonkeyPatch, supabase: SupabaseFalso
) -> tuple[SiteFalso, SupabaseFalso]:
    """Config falsa, duas fontes (uma quebrada) e sites servidos por fixtures."""
    cfg = config.Configuracao(
        supabase_url="https://falso.supabase.co",
        supabase_service_role_key="sb_secret_teste",
        gemini_api_key=None,
        gemini_model="x",
        nota_minima_resumo=6,
    )
    fontes: list[Fonte] = [
        fonte(nome="ok", url=FEED_OK, janela_horas=24 * 365 * 10),
        fonte(nome="ruim", url=FEED_RUIM),
    ]
    site = SiteFalso(
        {
            FEED_OK: httpx.Response(200, content=ler_fixture("rss_exemplo.xml")),
            FEED_RUIM: httpx.Response(500),
        }
    )

    def http_falso(_user_agent: str, **_: Any) -> ClienteHttp:
        return cliente_http(site)

    monkeypatch.setattr(config, "carregar", lambda: cfg)
    monkeypatch.setattr(config, "carregar_fontes_validas", lambda: fontes)
    monkeypatch.setattr(cli, "ClienteHttp", http_falso)
    return site, supabase


def test_coletar_todos(ambiente_coleta: tuple[SiteFalso, SupabaseFalso]) -> None:
    _, supabase = ambiente_coleta
    assert cli.main(["coletar", "--todos"]) == 0  # uma falha não derruba a coleta
    assert len(supabase.tabelas["itens"]) == 4
    resumo = {e["coletor"]: e["ok"] for e in supabase.tabelas["execucoes"]}
    assert resumo == {"ok": True, "ruim": False}

    assert cli.main(["coletar", "--todos"]) == 0
    assert len(supabase.tabelas["itens"]) == 4  # segunda execução não duplica


def test_coletar_uma_fonte(ambiente_coleta: tuple[SiteFalso, SupabaseFalso]) -> None:
    site, supabase = ambiente_coleta
    assert cli.main(["coletar", "--fonte", "ok"]) == 0
    assert FEED_RUIM not in site.urls()
    assert [e["coletor"] for e in supabase.tabelas["execucoes"]] == ["ok"]


def test_coletar_retorna_1_se_todas_falharem(
    ambiente_coleta: tuple[SiteFalso, SupabaseFalso],
) -> None:
    assert cli.main(["coletar", "--fonte", "ruim"]) == 1


def test_coletar_fonte_inexistente(ambiente_coleta: tuple[SiteFalso, SupabaseFalso]) -> None:
    assert cli.main(["coletar", "--fonte", "nao-existe"]) == 1


def test_coletar_exige_escolha_de_fontes() -> None:
    with pytest.raises(SystemExit):
        cli.main(["coletar"])


# ------------------------------------------------------------ triar / revisar


@pytest.fixture
def ambiente_triagem(monkeypatch: pytest.MonkeyPatch, supabase: SupabaseFalso) -> SupabaseFalso:
    cfg = config.Configuracao(
        supabase_url="https://falso.supabase.co",
        supabase_service_role_key="sb_secret_teste",
        gemini_api_key="chave-falsa",
        gemini_model="x",
        nota_minima_resumo=6,
    )
    monkeypatch.setattr(config, "carregar", lambda: cfg)
    monkeypatch.setattr(config, "carregar_perfil", lambda: "perfil")
    banco.salvar_itens(
        [
            Item(modulo="noticias", fonte="t", titulo="Java 27 lançado", url="https://e.com/1"),
            Item(modulo="noticias", fonte="t", titulo="Cupom de desconto", url="https://e.com/2"),
        ]
    )
    return supabase


def _classificador(itens: Sequence[ItemPendente], _m: Modulo) -> list[Resultado]:
    return [
        Resultado(
            id=i.id,
            nota=9 if "Java" in i.titulo else 1,
            resumo=f"Resumo de {i.titulo}.",
            tags=["java"] if "Java" in i.titulo else ["outros"],
            descartar="Cupom" in i.titulo,
        )
        for i in itens
    ]


def test_triar_e_revisar(
    ambiente_triagem: SupabaseFalso,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(ia_cliente, "classificar_lote", _classificador)
    assert cli.main(["triar"]) == 0
    status = {linha["titulo"]: linha["status"] for linha in ambiente_triagem.tabelas["itens"]}
    assert status == {"Java 27 lançado": "processado", "Cupom de desconto": "descartado"}

    assert cli.main(["revisar", "--quantidade", "5"]) == 0
    saida = capsys.readouterr().out
    assert saida.index("[ 9] Java 27 lançado") < saida.index("[ 1] Cupom de desconto [descartado]")


def test_triar_cota_esgotada_retorna_0(
    ambiente_triagem: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    def sem_cota(_i: Sequence[ItemPendente], _m: Modulo) -> list[Resultado]:
        raise ia_cliente.CotaEsgotada("429")

    monkeypatch.setattr(ia_cliente, "classificar_lote", sem_cota)
    assert cli.main(["triar"]) == 0


def test_triar_modelo_sobrecarregado_retorna_0_e_para_os_outros_modulos(
    ambiente_triagem: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[Modulo] = []

    def sobrecarregado(_i: Sequence[ItemPendente], modulo: Modulo) -> list[Resultado]:
        chamadas.append(modulo)
        raise ia_cliente.ModeloSobrecarregado("503 high demand")

    monkeypatch.setattr(ia_cliente, "classificar_lote", sobrecarregado)
    assert cli.main(["triar"]) == 0
    assert len(chamadas) == 1  # não insiste nos outros módulos
    execucao = ambiente_triagem.tabelas["execucoes"][-1]
    assert execucao["ok"] is True and "modelo indisponível" in execucao["erro"]


def test_triar_erro_da_ia_retorna_1(
    ambiente_triagem: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    def quebrado(_i: Sequence[ItemPendente], _m: Modulo) -> list[Resultado]:
        raise ia_cliente.ErroIA("403 chave inválida")

    monkeypatch.setattr(ia_cliente, "classificar_lote", quebrado)
    assert cli.main(["triar"]) == 1


def test_resumo_simular_mostra_e_salva_previa(
    ambiente_triagem: SupabaseFalso,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(ia_cliente, "classificar_lote", _classificador)
    assert cli.main(["triar"]) == 0
    previa = tmp_path / "previa.html"

    assert cli.main(["resumo", "--simular", "--salvar", str(previa)]) == 0

    saida = capsys.readouterr().out
    assert "Assunto: MordeNews" in saida and "[9] Java 27 lançado" in saida
    assert "Cupom" not in saida  # descartado não entra
    assert "<html" in previa.read_text(encoding="utf-8")
    assert not any(linha.get("enviado_em") for linha in ambiente_triagem.tabelas["itens"])


def test_resumo_sem_configuracao_de_email_retorna_1(ambiente_triagem: SupabaseFalso) -> None:
    assert cli.main(["resumo"]) == 1


def test_triar_sem_chave_do_gemini_retorna_1(
    ambiente_triagem: SupabaseFalso, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = config.carregar()
    monkeypatch.setattr(config, "carregar", lambda: replace(cfg, gemini_api_key=None))
    assert cli.main(["triar"]) == 1
