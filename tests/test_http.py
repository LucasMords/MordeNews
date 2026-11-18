import httpx
import pytest

from radar.coletores.http import BloqueadoPorRobots
from tests.conftest import SiteFalso, cliente_http

FEED = "https://site.com/feed"
ROBOTS = "https://site.com/robots.txt"


def test_envia_user_agent() -> None:
    site = SiteFalso({FEED: httpx.Response(200, text="ok")})
    cliente_http(site).get(FEED)
    assert site.pedidos[-1].headers["User-Agent"] == "RadarPessoal/0.1 (+teste)"


def test_robots_que_bloqueia_impede_a_coleta() -> None:
    site = SiteFalso(
        {
            ROBOTS: httpx.Response(200, text="User-agent: *\nDisallow: /"),
            FEED: httpx.Response(200, text="ok"),
        }
    )
    with pytest.raises(BloqueadoPorRobots):
        cliente_http(site).get(FEED)
    assert FEED not in site.urls()


def test_robots_que_bloqueia_so_o_radar() -> None:
    regras = "User-agent: RadarPessoal\nDisallow: /\n\nUser-agent: *\nAllow: /"
    site = SiteFalso({ROBOTS: httpx.Response(200, text=regras)})
    assert not cliente_http(site).permitido(FEED)


def test_robots_que_permite() -> None:
    site = SiteFalso(
        {
            ROBOTS: httpx.Response(200, text="User-agent: *\nDisallow: /privado/"),
            FEED: httpx.Response(200, text="ok"),
        }
    )
    assert cliente_http(site).get(FEED).text == "ok"


def test_robots_inexistente_libera() -> None:
    site = SiteFalso({FEED: httpx.Response(200, text="ok")})  # robots.txt → 404
    assert cliente_http(site).permitido(FEED)


@pytest.mark.parametrize("status", [401, 403, 503])
def test_robots_proibido_ou_fora_do_ar_bloqueia(status: int) -> None:
    site = SiteFalso({ROBOTS: httpx.Response(status)})
    assert not cliente_http(site).permitido(FEED)


def test_robots_com_erro_de_rede_bloqueia() -> None:
    site = SiteFalso({ROBOTS: httpx.ConnectError("sem rede")})
    assert not cliente_http(site).permitido(FEED)


def test_robots_lido_uma_vez_por_dominio() -> None:
    site = SiteFalso({FEED: httpx.Response(200), "https://site.com/outro": httpx.Response(200)})
    cliente = cliente_http(site)
    cliente.get(FEED)
    cliente.get("https://site.com/outro")
    assert site.urls().count(ROBOTS) == 1


def test_pausa_entre_requisicoes_ao_mesmo_dominio() -> None:
    relogio = [100.0]
    esperas: list[float] = []

    def dormir(segundos: float) -> None:
        esperas.append(segundos)
        relogio[0] += segundos

    site = SiteFalso({FEED: httpx.Response(200), "https://outro.com/feed": httpx.Response(200)})
    cliente = cliente_http(site, pausa=1.5, dormir=dormir, relogio=lambda: relogio[0])

    cliente.get(FEED)  # robots.txt + feed do mesmo domínio → 1 pausa
    cliente.get("https://outro.com/feed")  # domínio novo: robots sem pausa, feed com pausa
    assert esperas == [1.5, 1.5]
