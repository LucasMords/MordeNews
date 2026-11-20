import json
from datetime import UTC, datetime

import httpx
import pytest

from radar import config
from radar.coletores.github import ColetorGitHub, ErroGitHub
from radar.coletores.registro import montar_coletores
from tests.conftest import AGORA, SiteFalso, cliente_http, fonte, ler_fixture

URL_REPO = "https://api.github.com/repos/exemplo/vagas"
URL_ISSUES = f"{URL_REPO}/issues?state=open&sort=created&direction=desc&per_page=50"


def _coletor(site: SiteFalso) -> ColetorGitHub:
    vagas = fonte(modulo="estagios", nome="gh-exemplo", tipo="github", url=URL_REPO)
    return ColetorGitHub(vagas, cliente_http(site), agora=lambda: AGORA)


def _site() -> SiteFalso:
    return SiteFalso({URL_ISSUES: httpx.Response(200, content=ler_fixture("github_issues.json"))})


@pytest.fixture(autouse=True)
def _sem_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "carregar", lambda: config.ler_ambiente())
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


def test_interpreta_issues_e_ignora_pull_requests_e_sem_link() -> None:
    coletor = _coletor(SiteFalso())
    itens = coletor.interpretar(json.loads(ler_fixture("github_issues.json")))
    assert [i.titulo for i in itens] == [
        "[Remoto] Estágio em Desenvolvimento Back-end - Empresa Exemplo",
        "[Palmas] Desenvolvedor Sênior Java",
        "Vaga antiga, fora da janela",
    ]
    vaga = itens[0]
    assert vaga.modulo == "estagios"
    assert vaga.fonte == "gh-exemplo"
    assert vaga.url == "https://github.com/exemplo/vagas/issues/12"
    assert vaga.publicado_em == datetime(2026, 11, 18, 9, 30, tzinfo=UTC)
    # labels vêm antes do corpo e o HTML some
    assert vaga.texto.startswith("Labels: Remoto, Estágio, Python")
    assert "<br>" not in vaga.texto
    assert "https://empresa-exemplo.com/vagas/12" in vaga.texto
    # corpo nulo não quebra
    assert itens[1].texto == "Labels: Sênior, Presencial"


def test_buscar_aplica_janela_de_72h() -> None:
    site = _site()
    titulos = [i.titulo for i in _coletor(site).buscar()]
    assert "Vaga antiga, fora da janela" not in titulos
    assert len(titulos) == 2
    pedido = next(p for p in site.pedidos if p.url.path.endswith("/issues"))
    assert pedido.headers["Accept"] == "application/vnd.github+json"
    assert "Authorization" not in pedido.headers


def test_token_vai_no_cabecalho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_teste")
    site = _site()
    _coletor(site).buscar()
    pedido = next(p for p in site.pedidos if p.url.path.endswith("/issues"))
    assert pedido.headers["Authorization"] == "Bearer ghs_teste"


def test_resposta_que_nao_e_lista_e_erro() -> None:
    with pytest.raises(ErroGitHub):
        _coletor(SiteFalso()).interpretar({"message": "Not Found"})


def test_registro_monta_coletor_github() -> None:
    vagas = fonte(modulo="estagios", nome="gh-x", tipo="github", url=URL_REPO)
    assert isinstance(montar_coletores([vagas], cliente_http(SiteFalso()))[0], ColetorGitHub)
