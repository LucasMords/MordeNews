from typing import Any

import httpx
import pytest

from radar import cli, config
from radar.coletores.http import ClienteHttp
from radar.modelos import Fonte
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
        telegram_bot_token=None,
        telegram_chat_id=None,
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
