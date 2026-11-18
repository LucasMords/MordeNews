import httpx
import pytest

from radar.coletores.base import Coletor, executar
from radar.coletores.registro import filtrar_fontes, montar_coletores
from radar.coletores.rss import ColetorRSS
from radar.modelos import Item
from tests.conftest import AGORA, SiteFalso, SupabaseFalso, cliente_http, fonte, ler_fixture

URL_FEED = "https://blog.exemplo.com/feed"


def _coletor_rss(site: SiteFalso, **extra: object) -> ColetorRSS:
    return ColetorRSS(fonte(**extra), cliente_http(site), agora=lambda: AGORA)


class ColetorQuebrado(Coletor):
    def buscar(self) -> list[Item]:
        raise ValueError("site mudou o layout")


def test_executar_grava_e_nao_duplica_na_segunda_vez(supabase: SupabaseFalso) -> None:
    site = SiteFalso({URL_FEED: httpx.Response(200, content=ler_fixture("rss_exemplo.xml"))})
    coletor = _coletor_rss(site)

    primeira = executar(coletor)
    segunda = executar(coletor)

    assert (primeira.ok, primeira.encontrados, primeira.novos) == (True, 3, 3)
    assert (segunda.ok, segunda.encontrados, segunda.novos) == (True, 3, 0)
    assert len(supabase.tabelas["itens"]) == 3
    execucoes = supabase.tabelas["execucoes"]
    assert [(e["coletor"], e["ok"], e["itens_novos"]) for e in execucoes] == [
        ("exemplo", True, 3),
        ("exemplo", True, 0),
    ]


def test_executar_captura_falha_e_registra(supabase: SupabaseFalso) -> None:
    resultado = executar(ColetorQuebrado(fonte(nome="quebrado"), cliente_http(SiteFalso())))
    assert not resultado.ok
    assert resultado.erro == "ValueError: site mudou o layout"
    linha = supabase.tabelas["execucoes"][0]
    assert (linha["coletor"], linha["ok"], linha["erro"]) == (
        "quebrado",
        False,
        "ValueError: site mudou o layout",
    )


def test_executar_nao_propaga_falha_do_banco(supabase: SupabaseFalso) -> None:
    site = SiteFalso({URL_FEED: httpx.Response(200, content=ler_fixture("rss_exemplo.xml"))})
    supabase.falhar_com = 503
    resultado = executar(_coletor_rss(site))  # salvar e registrar falham, mas não explode
    assert not resultado.ok
    assert "ErroBanco" in (resultado.erro or "")


def test_um_coletor_falhando_nao_derruba_os_outros(supabase: SupabaseFalso) -> None:
    site = SiteFalso({URL_FEED: httpx.Response(200, content=ler_fixture("rss_exemplo.xml"))})
    coletores = [
        ColetorQuebrado(fonte(nome="quebrado"), cliente_http(site)),
        _coletor_rss(site),
    ]
    resultados = [executar(c) for c in coletores]
    assert [r.ok for r in resultados] == [False, True]
    assert len(supabase.tabelas["itens"]) == 3


def test_montar_coletores_por_tipo() -> None:
    coletores = montar_coletores([fonte(nome="a"), fonte(nome="b")], cliente_http(SiteFalso()))
    assert [type(c) for c in coletores] == [ColetorRSS, ColetorRSS]
    assert [c.nome for c in coletores] == ["a", "b"]


@pytest.mark.parametrize(
    ("nomes", "modulo", "esperado"),
    [
        ((), None, ["a", "b", "c"]),
        (("b",), None, ["b"]),
        ((), "estagios", ["c"]),
    ],
)
def test_filtrar_fontes(nomes: tuple[str, ...], modulo: str | None, esperado: list[str]) -> None:
    fontes = [fonte(nome="a"), fonte(nome="b"), fonte(nome="c", modulo="estagios")]
    assert [f.nome for f in filtrar_fontes(fontes, nomes=nomes, modulo=modulo)] == esperado
