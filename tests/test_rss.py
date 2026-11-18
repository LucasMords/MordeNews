from datetime import UTC, datetime

import httpx
import pytest

from radar.coletores.base import limpar_html
from radar.coletores.rss import ColetorRSS, ErroFeed
from radar.modelos import gerar_id_unico
from tests.conftest import AGORA, SiteFalso, cliente_http, fonte, ler_fixture

URL_FEED = "https://blog.exemplo.com/feed"


def _coletor(conteudo: bytes, **extra_fonte: object) -> tuple[ColetorRSS, SiteFalso]:
    site = SiteFalso({URL_FEED: httpx.Response(200, content=conteudo)})
    coletor = ColetorRSS(fonte(**extra_fonte), cliente_http(site), agora=lambda: AGORA)
    return coletor, site


def test_limpar_html() -> None:
    html = "<p>Olá <b>mundo</b></p><script>x()</script><style>p{}</style>\n\n<p>fim</p>"
    assert limpar_html(html) == "Olá mundo fim"
    assert limpar_html("") == ""
    assert limpar_html("texto puro") == "texto puro"


def test_rss_interpreta_campos() -> None:
    coletor, _ = _coletor(b"")
    itens = coletor.interpretar(ler_fixture("rss_exemplo.xml"))
    por_titulo = {i.titulo: i for i in itens}

    python = por_titulo["Nova versão do Python & o que muda"]
    assert python.modulo == "noticias"
    assert python.fonte == "exemplo"
    assert python.publicado_em == datetime(2026, 11, 18, 10, 0, tzinfo=UTC)
    # content:encoded tem prioridade sobre description; script some
    assert python.texto == "Texto completo do artigo. Segundo parágrafo."
    # utm_* não interfere na deduplicação
    assert python.id_unico == gerar_id_unico("https://blog.exemplo.com/python-novo")

    ransomware = por_titulo["Ataque de ransomware atinge empresa"]
    assert ransomware.texto == "Só a descrição , sem content."
    assert ransomware.publicado_em == datetime(2026, 11, 17, 11, 30, tzinfo=UTC)  # -03:00 → UTC


def test_rss_ignora_entrada_sem_link() -> None:
    coletor, _ = _coletor(b"")
    titulos = [i.titulo for i in coletor.interpretar(ler_fixture("rss_exemplo.xml"))]
    assert "Item sem link deve ser ignorado" not in titulos
    assert len(titulos) == 4


def test_buscar_aplica_janela_e_ordena_do_mais_novo() -> None:
    coletor, site = _coletor(ler_fixture("rss_exemplo.xml"))
    titulos = [i.titulo for i in coletor.buscar()]
    assert titulos == [
        "Nova versão do Python & o que muda",
        "Ataque de ransomware atinge empresa",
        "Item sem data é mantido",
    ]
    assert URL_FEED in site.urls()


def test_buscar_janela_configuravel() -> None:
    coletor, _ = _coletor(ler_fixture("rss_exemplo.xml"), janela_horas=24 * 30)
    assert "Notícia antiga, fora da janela de 72h" in [i.titulo for i in coletor.buscar()]


def test_buscar_respeita_limite() -> None:
    coletor, _ = _coletor(ler_fixture("rss_exemplo.xml"), limite=1)
    assert [i.titulo for i in coletor.buscar()] == ["Nova versão do Python & o que muda"]


def test_atom() -> None:
    coletor, _ = _coletor(ler_fixture("atom_exemplo.xml"))
    itens = coletor.buscar()
    assert [i.titulo for i in itens] == [
        "LLMs locais ficaram mais rápidos",
        "Só com updated e summary",
    ]
    assert itens[0].url == "https://atom.exemplo.com/2026/nov/18/llms/"
    assert itens[0].texto == "Conteúdo com código e detalhes."
    assert itens[0].publicado_em == datetime(2026, 11, 18, 11, 0, tzinfo=UTC)  # published > updated
    assert itens[1].publicado_em == datetime(2026, 11, 16, 20, 0, tzinfo=UTC)
    assert itens[1].texto == "Um resumo simples."


def test_pagina_html_no_lugar_do_feed_e_erro() -> None:
    coletor, _ = _coletor(ler_fixture("nao_e_feed.html"))
    with pytest.raises(ErroFeed):
        coletor.buscar()


@pytest.mark.parametrize("conteudo", [b"isto nao e xml", b'{"json": 1}', b""])
def test_conteudo_que_nao_e_feed_e_erro(conteudo: bytes) -> None:
    coletor, _ = _coletor(conteudo)
    with pytest.raises(ErroFeed):
        coletor.buscar()


def test_feed_truncado_aproveita_o_que_der() -> None:
    # O feedparser recupera entradas parciais; a que não tem link é descartada sem erro.
    coletor, _ = _coletor(b"<rss><channel><item><title>sem fechar")
    assert coletor.buscar() == []


def test_feed_valido_e_vazio_nao_e_erro() -> None:
    vazio = b'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title></channel></rss>'
    coletor, _ = _coletor(vazio)
    assert coletor.buscar() == []


def test_http_500_no_feed_vira_excecao() -> None:
    site = SiteFalso({URL_FEED: httpx.Response(500)})
    coletor = ColetorRSS(fonte(), cliente_http(site), agora=lambda: AGORA)
    with pytest.raises(httpx.HTTPStatusError):
        coletor.buscar()
